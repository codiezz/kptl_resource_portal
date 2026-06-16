"""
pdf_user_report.py

Generates a premium 4-page user-specific HPC utilization report.

Expects the enriched payload produced by get_user_report() in app.py:
{
    "username", "account", "cluster", "start", "end", "generated_at",
    "user_cpu_hours", "user_cpu_pct", "user_gpu_hours", "user_gpu_pct",
    "acct_cpu_total", "acct_gpu_total", "acct_cpu_avg", "acct_cpu_median", "acct_gpu_avg",
    "n_peers", "cpu_vs_avg", "cpu_vs_median", "gpu_vs_avg",
    "cpu_rank", "gpu_rank", "cpu_top_pct", "gpu_top_pct",
    "resource_profile", "observations",
    "cpu_peers": [{"login", "hours", "is_target"}, ...],
    "gpu_peers": [{"login", "gpu_hours", "is_target"}, ...]
}
"""

import io
import os
import tempfile
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak
)

# ── Colour palette ────────────────────────────────────────────────────────────
DARK_BLUE   = colors.HexColor("#1a3a5c")
MID_BLUE    = colors.HexColor("#2c5f8a")
LIGHT_BLUE  = colors.HexColor("#a8c8e8")
ACCENT      = colors.HexColor("#e67e22")       # orange — highlight colour
ACCENT2     = colors.HexColor("#27ae60")       # green  — positive metric
LIGHT_GREY  = colors.HexColor("#f4f6f8")
MID_GREY    = colors.HexColor("#7f8c8d")
DARK_GREY   = colors.HexColor("#2c3e50")
WHITE       = colors.white
RED_SOFT    = colors.HexColor("#e74c3c")

BAR_DEFAULT  = "#4e95d6"
BAR_TARGET   = "#e67e22"   # arnab highlighted in orange

W, H = A4
CONTENT_W = W - 3.6 * cm   # left + right margin = 1.8cm each


# ── Header / footer drawn on every page ───────────────────────────────────────

def _header_footer(cluster_name: str, username: str, generated_at: str):
    def on_page(canvas, doc):
        canvas.saveState()

        # Header bar
        canvas.setFillColor(DARK_BLUE)
        canvas.rect(0, H - 1.2 * cm, W, 1.2 * cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(1.5 * cm, H - 0.85 * cm, "IISER Pune — HPC Portal")
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(
            W - 1.5 * cm, H - 0.85 * cm,
            f"Cluster: {cluster_name.upper()}  |  User: {username}"
        )

        # Footer bar
        canvas.setFillColor(LIGHT_GREY)
        canvas.rect(0, 0, W, 1.0 * cm, fill=1, stroke=0)
        canvas.setFillColor(MID_GREY)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(1.5 * cm, 0.35 * cm,
                          "Generated automatically by IISER Pune HPC Portal")
        canvas.drawRightString(W - 1.5 * cm, 0.35 * cm,
                               f"Page {doc.page}   |   {generated_at}")

        canvas.restoreState()
    return on_page


# ── Chart helpers ─────────────────────────────────────────────────────────────

def _peer_bar_chart(peers: list, value_key: str, xlabel: str,
                    title: str, path: str, top_n: int = 20) -> bool:
    """
    Horizontal bar chart of top_n peers.
    Target user bar rendered in BAR_TARGET colour, others in BAR_DEFAULT.
    """
    # Show top_n by value, but always include the target user
    target = next((p for p in peers if p.get("is_target")), None)
    top = [p for p in peers if not p.get("is_target")][:top_n]
    if target and target not in top:
        top.append(target)
    # Re-sort
    top = sorted(top, key=lambda p: p.get(value_key) or 0)

    if not top:
        return False

    labels = [p["login"] for p in top]
    values = [p.get(value_key) or 0 for p in top]
    clrs   = [BAR_TARGET if p.get("is_target") else BAR_DEFAULT for p in top]

    fig, ax = plt.subplots(figsize=(7.5, max(3.5, len(top) * 0.42)))
    bars = ax.barh(labels, values, color=clrs, height=0.6, edgecolor="white")

    max_val = max(values) if values else 1
    for bar, val, peer in zip(bars, values, top):
        label_str = f"{val:,.0f}"
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            label_str, va="center", ha="left",
            fontsize=7.5,
            color=BAR_TARGET if peer.get("is_target") else "#2c3e50",
            fontweight="bold" if peer.get("is_target") else "normal"
        )

    ax.set_xlabel(xlabel, fontsize=9, color="#2c3e50")
    ax.set_title(title, fontsize=10, fontweight="bold", color="#1a3a5c")
    ax.set_xlim(0, max_val * 1.20)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.tick_params(colors="#555555", labelsize=8)
    ax.xaxis.grid(True, linestyle="--", alpha=0.4, color="#aaaaaa")
    ax.set_axisbelow(True)

    legend_patches = [
        mpatches.Patch(color=BAR_TARGET, label="Selected user"),
        mpatches.Patch(color=BAR_DEFAULT, label="Peers"),
    ]
    ax.legend(handles=legend_patches, fontsize=8, loc="lower right")

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return True


def _kpi_donut(value_pct: float, label: str, path: str,
               colour: str = "#2c5f8a") -> bool:
    """Small donut chart showing user's share as a percentage."""
    if value_pct is None:
        return False
    fig, ax = plt.subplots(figsize=(2.2, 2.2))
    rest = max(0, 100 - value_pct)
    ax.pie(
        [value_pct, rest],
        colors=[colour, "#eef2f7"],
        startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        counterclock=False,
    )
    ax.text(0, 0, f"{value_pct:.1f}%", ha="center", va="center",
            fontsize=13, fontweight="bold", color=colour)
    ax.set_title(label, fontsize=8, color="#2c3e50", pad=4)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return True


# ── Style factory ─────────────────────────────────────────────────────────────

def _styles():
    return {
        "title": ParagraphStyle(
            "Title", fontSize=24, fontName="Helvetica-Bold",
            textColor=DARK_BLUE, alignment=TA_CENTER, spaceAfter=6
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", fontSize=13, fontName="Helvetica",
            textColor=MID_BLUE, alignment=TA_CENTER, spaceAfter=4
        ),
        "section": ParagraphStyle(
            "Section", fontSize=13, fontName="Helvetica-Bold",
            textColor=DARK_BLUE, spaceBefore=14, spaceAfter=8
        ),
        "body": ParagraphStyle(
            "Body", fontSize=10, fontName="Helvetica",
            textColor=DARK_GREY, spaceAfter=4
        ),
        "body_small": ParagraphStyle(
            "BodySmall", fontSize=8.5, fontName="Helvetica",
            textColor=MID_GREY, spaceAfter=3
        ),
        "obs": ParagraphStyle(
            "Obs", fontSize=10, fontName="Helvetica",
            textColor=DARK_GREY, spaceAfter=7, leftIndent=14
        ),
        "kpi_label": ParagraphStyle(
            "KpiLabel", fontSize=8, fontName="Helvetica",
            textColor=MID_GREY, alignment=TA_CENTER
        ),
        "kpi_value": ParagraphStyle(
            "KpiValue", fontSize=18, fontName="Helvetica-Bold",
            textColor=DARK_BLUE, alignment=TA_CENTER
        ),
        "unavail": ParagraphStyle(
            "Unavail", fontSize=11, fontName="Helvetica",
            textColor=MID_GREY, alignment=TA_CENTER, spaceBefore=20
        ),
    }


def _section_hdr(title: str, s: dict) -> list:
    return [
        Paragraph(title, s["section"]),
        HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE, spaceAfter=10),
    ]


# ── KPI card helper ───────────────────────────────────────────────────────────

def _kpi_table(items: list, col_w: float, s: dict) -> Table:
    """
    items = [("label", "value", "sub"), ...]
    Renders as a single-row KPI strip.
    """
    cells = []
    for label, value, sub in items:
        cell = [
            Paragraph(label, s["kpi_label"]),
            Paragraph(str(value), s["kpi_value"]),
            Paragraph(sub, s["kpi_label"]),
        ]
        cells.append(cell)

    t = Table([cells], colWidths=[col_w] * len(items))
    t.setStyle(TableStyle([
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
        ("BOX",        (0, 0), (-1, -1), 0.5, LIGHT_BLUE),
        ("INNERGRID",  (0, 0), (-1, -1), 0.3, LIGHT_BLUE),
        ("ROWPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


# ── Profile badge colour ──────────────────────────────────────────────────────

_PROFILE_COLOUR = {
    "GPU-Heavy":    "#8e44ad",
    "CPU-Heavy":    "#2c5f8a",
    "Power User":   "#c0392b",
    "Balanced":     "#27ae60",
    "Light User":   "#7f8c8d",
}

_PROFILE_DESC = {
    "GPU-Heavy":  "This user's workload is dominated by GPU computation.",
    "CPU-Heavy":  "This user's workload is dominated by CPU computation.",
    "Power User": "This user is a heavy consumer of both CPU and GPU resources.",
    "Balanced":   "This user has a balanced mix of CPU and GPU workloads.",
    "Light User": "This user has light overall resource consumption.",
}


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_user_report(data: dict) -> bytes:
    """
    Accepts the enriched payload from get_user_report() and returns PDF bytes.
    """
    # ── Unpack payload ────────────────────────────────────────────────────
    username      = data.get("username", "unknown")
    account       = data.get("account",  "N/A")
    cluster       = data.get("cluster",  "N/A")
    start         = data.get("start",    "N/A")
    end           = data.get("end",      "N/A")
    generated_at  = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))

    user_cpu_h    = data.get("user_cpu_hours",  0)
    user_cpu_pct  = data.get("user_cpu_pct",    0.0)
    user_gpu_h    = data.get("user_gpu_hours",  0.0)
    user_gpu_pct  = data.get("user_gpu_pct",    None)

    acct_cpu_tot  = data.get("acct_cpu_total",  0)
    acct_gpu_tot  = data.get("acct_gpu_total",  0.0)
    acct_cpu_avg  = data.get("acct_cpu_avg",    0.0)
    acct_cpu_med  = data.get("acct_cpu_median", 0.0)
    acct_gpu_avg  = data.get("acct_gpu_avg",    0.0)
    n_peers       = data.get("n_peers",         0)

    cpu_vs_avg    = data.get("cpu_vs_avg",    0.0)
    cpu_vs_med    = data.get("cpu_vs_median", 0.0)
    gpu_vs_avg    = data.get("gpu_vs_avg",    0.0)

    cpu_rank      = data.get("cpu_rank",    "N/A")
    gpu_rank      = data.get("gpu_rank",    "N/A")
    cpu_top_pct   = data.get("cpu_top_pct", 0)
    gpu_top_pct   = data.get("gpu_top_pct", 0)

    profile       = data.get("resource_profile", "Unknown")
    observations  = data.get("observations", [])
    cpu_peers     = data.get("cpu_peers", [])
    gpu_peers     = data.get("gpu_peers", [])

    s = _styles()

    # ── Temp files for charts ─────────────────────────────────────────────
    tmp = {}
    for key in ["cpu_bar", "gpu_bar", "cpu_donut", "gpu_donut"]:
        f = tempfile.NamedTemporaryFile(
            suffix=".png", delete=False, prefix=f"hpc_usr_{key}_"
        )
        f.close()
        tmp[key] = f.name

    charts = {}
    try:
        charts["cpu_bar"] = _peer_bar_chart(
            cpu_peers, "hours", "CPU Hours",
            f"CPU Consumption — {account.upper()} Account",
            tmp["cpu_bar"], top_n=20
        )
        charts["gpu_bar"] = _peer_bar_chart(
            gpu_peers, "gpu_hours", "GPU Hours",
            f"GPU Consumption — {account.upper()} Account",
            tmp["gpu_bar"], top_n=20
        )
        charts["cpu_donut"] = _kpi_donut(
            user_cpu_pct, "CPU Share of Account",
            tmp["cpu_donut"], colour="#2c5f8a"
        )
        charts["gpu_donut"] = _kpi_donut(
            user_gpu_pct, "GPU Share of Cluster",
            tmp["gpu_donut"], colour="#8e44ad"
        )

        pdf_bytes = _build_pdf(
            username, account, cluster, start, end, generated_at,
            user_cpu_h, user_cpu_pct, user_gpu_h, user_gpu_pct,
            acct_cpu_tot, acct_gpu_tot, acct_cpu_avg, acct_cpu_med, acct_gpu_avg,
            n_peers, cpu_vs_avg, cpu_vs_med, gpu_vs_avg,
            cpu_rank, gpu_rank, cpu_top_pct, gpu_top_pct,
            profile, observations, cpu_peers, gpu_peers,
            s, charts, tmp
        )
    finally:
        for path in tmp.values():
            try:
                os.unlink(path)
            except OSError:
                pass

    return pdf_bytes


# ── PDF builder ───────────────────────────────────────────────────────────────

def _build_pdf(
    username, account, cluster, start, end, generated_at,
    user_cpu_h, user_cpu_pct, user_gpu_h, user_gpu_pct,
    acct_cpu_tot, acct_gpu_tot, acct_cpu_avg, acct_cpu_med, acct_gpu_avg,
    n_peers, cpu_vs_avg, cpu_vs_med, gpu_vs_avg,
    cpu_rank, gpu_rank, cpu_top_pct, gpu_top_pct,
    profile, observations, cpu_peers, gpu_peers,
    s, charts, tmp
) -> bytes:

    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=2.2 * cm, bottomMargin=1.8 * cm,
    )
    cw = CONTENT_W
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        cw, H - doc.topMargin - doc.bottomMargin,
        id="normal"
    )
    doc.addPageTemplates([PageTemplate(
        id="main", frames=[frame],
        onPage=_header_footer(cluster, username, generated_at)
    )])

    story = []

    # ════════════════════════════════════════════════════════════════════
    # PAGE 1 — User Cover
    # ════════════════════════════════════════════════════════════════════

    story.append(Spacer(1, 2.0 * cm))

    # Logo block
    logo_cell = Table(
        [[Paragraph("IISER PUNE", ParagraphStyle(
            "Logo", fontSize=17, fontName="Helvetica-Bold",
            textColor=WHITE, alignment=TA_CENTER
        ))]],
        colWidths=[6 * cm], rowHeights=[1.8 * cm]
    )
    logo_cell.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK_BLUE),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Table([[logo_cell]], colWidths=[cw]))
    story.append(Spacer(1, 0.8 * cm))

    story.append(Paragraph("High Performance Computing Portal", s["title"]))
    story.append(Paragraph("Individual User Utilization Report", s["subtitle"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="70%", thickness=1.5, color=LIGHT_BLUE, spaceAfter=16))

    # Identity table
    id_rows = [
        ["User (Login)",   username],
        ["Account",        account],
        ["Cluster",        cluster.upper()],
        ["Report Period",  f"{start}  →  {end}"],
        ["Generated",      generated_at],
    ]
    id_t = Table(id_rows, colWidths=[4.5 * cm, 9.5 * cm])
    id_t.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, -1), 11),
        ("TEXTCOLOR",  (0, 0), (0, -1), DARK_BLUE),
        ("TEXTCOLOR",  (1, 0), (1, -1), DARK_GREY),
        ("ROWPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW",  (0, 0), (-1, -2), 0.5, colors.HexColor("#f0f0f0")),
    ]))
    story.append(Table([[id_t]], colWidths=[cw]))
    story.append(Spacer(1, 0.8 * cm))

    # Resource profile badge
    profile_colour = colors.HexColor(_PROFILE_COLOUR.get(profile, "#2c5f8a"))
    badge = Table(
        [[Paragraph(f"Resource Profile: {profile}", ParagraphStyle(
            "Badge", fontSize=12, fontName="Helvetica-Bold",
            textColor=WHITE, alignment=TA_CENTER
        ))]],
        colWidths=[8 * cm], rowHeights=[1.0 * cm]
    )
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), profile_colour),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(Table([[badge]], colWidths=[cw]))
    story.append(Spacer(1, 0.8 * cm))

    # Quick KPI strip — 4 cards
    gpu_pct_str = f"{user_gpu_pct:.2f}%" if user_gpu_pct is not None else "N/A"
    kpi_items = [
        ("CPU Hours",       f"{user_cpu_h:,}",          f"{user_cpu_pct:.2f}% of account"),
        ("GPU Hours",       f"{user_gpu_h:,.1f}",       f"{gpu_pct_str} of cluster"),
        ("CPU Rank",        f"#{cpu_rank}/{n_peers}",    f"Top {100 - cpu_top_pct + 1}%"),
        ("GPU Rank",        f"#{gpu_rank}/{n_peers}",    f"Top {100 - gpu_top_pct + 1}%"),
    ]
    story.append(_kpi_table(kpi_items, cw / 4, s))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════
    # PAGE 2 — Deep Utilization Summary
    # ════════════════════════════════════════════════════════════════════

    story += _section_hdr("Executive User Summary", s)

    # Main metrics table
    def _fmt(v, decimals=1):
        if v is None:
            return "N/A"
        if isinstance(v, float):
            return f"{v:,.{decimals}f}"
        return f"{v:,}"

    def _ratio_str(r):
        if not r:
            return "N/A"
        direction = "above" if r > 1 else "below"
        return f"{r}x {direction} average"

    metric_rows = [
        ["Metric", "Value", "Context"],
        # CPU
        ["CPU Hours",
         f"{user_cpu_h:,}",
         f"Cluster total: {acct_cpu_tot:,}  |  Account avg: {_fmt(acct_cpu_avg, 0)}"],
        ["CPU Share of Account",
         f"{user_cpu_pct:.2f}%",
         f"Account total: {acct_cpu_tot:,} hrs"],
        ["CPU vs Account Avg",
         f"{cpu_vs_avg}x",
         _ratio_str(cpu_vs_avg)],
        ["CPU vs Account Median",
         f"{cpu_vs_med}x",
         f"Median peer usage: {_fmt(acct_cpu_med, 0)} hrs"],
        ["CPU Rank in Account",
         f"#{cpu_rank} of {n_peers}",
         f"Top {100 - cpu_top_pct + 1}% of {account} users"],
        # GPU
        ["GPU Hours",
         f"{user_gpu_h:,.1f}",
         f"Account GPU total: {acct_gpu_tot:,.1f} hrs"],
        ["GPU Share of Cluster",
         gpu_pct_str,
         f"Account GPU avg: {_fmt(acct_gpu_avg, 1)} hrs/user"],
        ["GPU vs Account Avg",
         f"{gpu_vs_avg}x",
         _ratio_str(gpu_vs_avg)],
        ["GPU Rank in Account",
         f"#{gpu_rank} of {n_peers}",
         f"Top {100 - gpu_top_pct + 1}% of {account} users"],
        # Profile
        ["Resource Profile",
         profile,
         _PROFILE_DESC.get(profile, "")],
    ]

    col_w = [4.5 * cm, 3.5 * cm, cw - 8.0 * cm]
    mt = Table(metric_rows, colWidths=col_w)
    mt.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",  (0, 0), (-1, 0),  DARK_BLUE),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  10),
        # Data rows
        ("FONTNAME",    (0, 1), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 1), (-1, -1), 9),
        ("TEXTCOLOR",   (0, 1), (0, -1),  DARK_BLUE),
        ("TEXTCOLOR",   (1, 1), (1, -1),  DARK_GREY),
        ("TEXTCOLOR",   (2, 1), (2, -1),  MID_GREY),
        ("ALIGN",       (1, 0), (1, -1),  "CENTER"),
        ("ALIGN",       (0, 0), (0, -1),  "LEFT"),
        # Alternating rows
        *[("BACKGROUND", (0, i), (-1, i), LIGHT_GREY)
          for i in range(2, len(metric_rows), 2)],
        ("ROWPADDING",  (0, 0), (-1, -1), 6),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#dde3ea")),
        ("LINEBELOW",   (0, 0), (-1, 0),  1.5, DARK_BLUE),
        # Section dividers — after CPU block row 5, before GPU
        ("LINEBELOW",   (0, 5), (-1, 5),  1.0, LIGHT_BLUE),
        ("LINEBELOW",   (0, 9), (-1, 9),  1.0, LIGHT_BLUE),
    ]))
    story.append(mt)

    # Donut charts row
    story.append(Spacer(1, 0.6 * cm))
    donut_cells = []
    if charts.get("cpu_donut") and os.path.exists(tmp["cpu_donut"]) and os.path.getsize(tmp["cpu_donut"]) > 0:
        donut_cells.append(Image(tmp["cpu_donut"], width=4.5 * cm, height=4.5 * cm))
    if charts.get("gpu_donut") and os.path.exists(tmp["gpu_donut"]) and os.path.getsize(tmp["gpu_donut"]) > 0:
        donut_cells.append(Image(tmp["gpu_donut"], width=4.5 * cm, height=4.5 * cm))

    if donut_cells:
        pad = [Spacer(1, 1)] * (2 - len(donut_cells))
        donut_t = Table([donut_cells + pad], colWidths=[cw / 2] * 2)
        donut_t.setStyle(TableStyle([
            ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(donut_t)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════
    # PAGE 3 — Peer Comparison
    # ════════════════════════════════════════════════════════════════════

    story += _section_hdr(f"Peer Comparison — {account.upper()} Account", s)
    story.append(Paragraph(
        f"Comparing <b>{username}</b> against all {n_peers} users in account "
        f"<b>{account}</b>. Selected user is highlighted in "
        f"<font color='#e67e22'><b>orange</b></font>.",
        s["body"]
    ))
    story.append(Spacer(1, 0.5 * cm))

    # CPU bar chart
    if charts.get("cpu_bar") and os.path.exists(tmp["cpu_bar"]) and os.path.getsize(tmp["cpu_bar"]) > 0:
        story += _section_hdr("CPU Consumption — Account Ranking", s)
        story.append(Image(tmp["cpu_bar"], width=cw, height=min(cw * 0.65, 14 * cm)))
        story.append(Spacer(1, 0.4 * cm))
    else:
        story.append(Paragraph("CPU peer chart unavailable.", s["unavail"]))

    # GPU bar chart
    if charts.get("gpu_bar") and os.path.exists(tmp["gpu_bar"]) and os.path.getsize(tmp["gpu_bar"]) > 0:
        story += _section_hdr("GPU Consumption — Account Ranking", s)
        story.append(Image(tmp["gpu_bar"], width=cw, height=min(cw * 0.65, 14 * cm)))
    else:
        story.append(Paragraph("GPU peer chart unavailable.", s["unavail"]))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════
    # PAGE 4 — Resource Profile & Observations
    # ════════════════════════════════════════════════════════════════════

    story += _section_hdr("Resource Profile & Observations", s)
    story.append(Paragraph(
        f"Automatically generated observations for user <b>{username}</b>, "
        f"account <b>{account}</b>, cluster <b>{cluster.upper()}</b>, "
        f"period {start} to {end}.",
        s["body"]
    ))
    story.append(Spacer(1, 0.4 * cm))

    # Profile description box
    prof_colour = colors.HexColor(_PROFILE_COLOUR.get(profile, "#2c5f8a"))
    prof_desc   = _PROFILE_DESC.get(profile, "")
    prof_box = Table(
        [[
            Paragraph(f"<b>{profile}</b>", ParagraphStyle(
                "ProfTitle", fontSize=13, fontName="Helvetica-Bold",
                textColor=WHITE
            )),
            Paragraph(prof_desc, ParagraphStyle(
                "ProfDesc", fontSize=10, fontName="Helvetica",
                textColor=WHITE
            ))
        ]],
        colWidths=[4 * cm, cw - 4 * cm]
    )
    prof_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), prof_colour),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWPADDING", (0, 0), (-1, -1), 12),
        ("BOX",        (0, 0), (-1, -1), 0, prof_colour),
    ]))
    story.append(prof_box)
    story.append(Spacer(1, 0.6 * cm))

    # Observations list
    story += _section_hdr("Observations", s)
    if observations:
        for i, obs in enumerate(observations, 1):
            story.append(Paragraph(f"<b>{i}.</b>  {obs}", s["obs"]))
    else:
        story.append(Paragraph("No observations generated.", s["unavail"]))

    story.append(Spacer(1, 0.8 * cm))

    # Summary statistics box
    story += _section_hdr("Summary Statistics", s)
    stats_rows = [
        ["Statistic", "Value"],
        ["Total CPU Hours (user)",       f"{user_cpu_h:,}"],
        ["Total GPU Hours (user)",       f"{user_gpu_h:,.1f}"],
        ["CPU Share of Account",         f"{user_cpu_pct:.2f}%"],
        ["GPU Share of Cluster",         gpu_pct_str],
        ["CPU Rank in Account",          f"#{cpu_rank} of {n_peers}"],
        ["GPU Rank in Account",          f"#{gpu_rank} of {n_peers}"],
        ["CPU vs Account Average",       f"{cpu_vs_avg}x"],
        ["CPU vs Account Median",        f"{cpu_vs_med}x"],
        ["GPU vs Account Average",       f"{gpu_vs_avg}x"],
        ["Account CPU Average",          f"{acct_cpu_avg:,.0f} hrs/user"],
        ["Account CPU Median",           f"{acct_cpu_med:,.0f} hrs/user"],
        ["Account GPU Average",          f"{acct_gpu_avg:,.1f} hrs/user"],
        ["Total Users in Account",       str(n_peers)],
    ]
    st = Table(stats_rows, colWidths=[9 * cm, cw - 9 * cm])
    st.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  DARK_BLUE),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  10),
        ("FONTNAME",    (0, 1), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 1), (-1, -1), 9),
        ("TEXTCOLOR",   (0, 1), (0, -1),  DARK_BLUE),
        ("TEXTCOLOR",   (1, 1), (1, -1),  DARK_GREY),
        ("ALIGN",       (1, 0), (1, -1),  "RIGHT"),
        *[("BACKGROUND", (0, i), (-1, i), LIGHT_GREY)
          for i in range(2, len(stats_rows), 2)],
        ("ROWPADDING",  (0, 0), (-1, -1), 5),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#dde3ea")),
        ("LINEBELOW",   (0, 0), (-1, 0),  1.5, DARK_BLUE),
    ]))
    story.append(st)

    doc.build(story)
    return buf.getvalue()


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_payload = {
        "username":        "arnab",
        "account":         "iiser",
        "cluster":         "fortytwo",
        "start":           "2025-10-01",
        "end":             "2025-12-31",
        "generated_at":    "2026-06-16 10:03",
        "user_cpu_hours":  81270,
        "user_cpu_pct":    0.48,
        "user_gpu_hours":  3557.38,
        "user_gpu_pct":    2.84,
        "acct_cpu_total":  1476846,
        "acct_gpu_total":  55467.61,
        "acct_cpu_avg":    44752.9,
        "acct_cpu_median": 2425,
        "acct_gpu_avg":    1680.8,
        "n_peers":         33,
        "cpu_vs_avg":      1.82,
        "cpu_vs_median":   33.51,
        "gpu_vs_avg":      2.12,
        "cpu_rank":        3,
        "gpu_rank":        5,
        "cpu_top_pct":     94,
        "gpu_top_pct":     88,
        "resource_profile": "CPU-Heavy",
        "observations": [
            "arnab contributed 0.48% of account CPU utilization.",
            "Ranked #3 highest CPU consumer in iiser (top 7%).",
            "Ranked #5 highest GPU consumer in iiser.",
            "CPU usage exceeds account median by 33.51x.",
            "GPU usage exceeds account average by 2.12x.",
            "Workload is CPU-heavy with minimal GPU usage.",
            "Compute activity indicates sustained, intensive HPC usage.",
        ],
        "cpu_peers": [
            {"login": "sonali",   "hours": 580441, "is_target": False},
            {"login": "madhu",    "hours": 476355, "is_target": False},
            {"login": "arnab",    "hours": 78604,  "is_target": True},
            {"login": "leelavati","hours": 76987,  "is_target": False},
            {"login": "vishnu",   "hours": 61213,  "is_target": False},
            {"login": "ashish",   "hours": 35426,  "is_target": False},
            {"login": "parth",    "hours": 28443,  "is_target": False},
            {"login": "bikirna",  "hours": 26880,  "is_target": False},
            {"login": "nachiket", "hours": 26804,  "is_target": False},
            {"login": "sreejith", "hours": 13023,  "is_target": False},
        ],
        "gpu_peers": [
            {"login": "sonali",  "gpu_hours": 13948.82, "is_target": False},
            {"login": "madhu",   "gpu_hours": 11759.45, "is_target": False},
            {"login": "sreejith","gpu_hours": 8489.53,  "is_target": False},
            {"login": "vishnu",  "gpu_hours": 4076.02,  "is_target": False},
            {"login": "arnab",   "gpu_hours": 3557.38,  "is_target": True},
            {"login": "ashishta+","gpu_hours": 2946.43, "is_target": False},
            {"login": "bikirna", "gpu_hours": 2751.55,  "is_target": False},
            {"login": "nishidh", "gpu_hours": 1749.68,  "is_target": False},
        ],
    }

    pdf = generate_user_report(test_payload)
    out = "/tmp/test_user_report_new.pdf"
    with open(out, "wb") as f:
        f.write(pdf)
    print(f"[PASS] {len(pdf):,} bytes → {out}")