import io
import os
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
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
from cluster_metadata import build_node_description_section
DARK_BLUE   = colors.HexColor("#1a3a5c")
MID_BLUE    = colors.HexColor("#2c5f8a")
LIGHT_BLUE  = colors.HexColor("#a8c8e8")
LIGHT_GREY  = colors.HexColor("#f4f6f8")
MID_GREY    = colors.HexColor("#7f8c8d")
DARK_GREY   = colors.HexColor("#2c3e50")
WHITE       = colors.white
IISER_RED     = colors.HexColor("#d80100")
IISER_RED_HEX = "#d80100"
COVER_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "iiser_logo.png")
BAR_DEFAULT  = "#2c5f8a"
BAR_TARGET   = IISER_RED_HEX
W, H = A4
CONTENT_W = W - 3.6 * cm   # left + right margin = 1.8cm each
def _header_footer(cluster_name: str, username: str, generated_at: str):
    def on_page(canvas, doc):
        canvas.saveState()
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
        canvas.setFillColor(LIGHT_GREY)
        canvas.rect(0, 0.28 * cm, W, 0.72 * cm, fill=1, stroke=0)
        canvas.setFillColor(MID_GREY)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(1.5 * cm, 0.5 * cm,
                          "IISER Pune HPC Portal — Automated Report Generation System")
        canvas.drawRightString(W - 1.5 * cm, 0.5 * cm,
                               f"Page {doc.page}")
        canvas.setFillColor(DARK_BLUE)
        canvas.rect(0, 0, W, 0.28 * cm, fill=1, stroke=0)
        canvas.restoreState()
    return on_page
def _watermark():
    def on_page_end(canvas, doc):
        canvas.saveState()
        canvas.translate(W / 2, H / 2)
        canvas.rotate(40)
        canvas.setFillGray(0.60)
        canvas.setFillAlpha(0.1)
        canvas.setFont("Helvetica-Bold", 120)
        canvas.drawCentredString(30, 0, "IISER PUNE")
        canvas.setFillAlpha(0.15)
        canvas.restoreState()
    return on_page_end
def _peer_donut_chart(
    peers: list,
    value_key: str,
    title: str,
    path: str,
    target_login: str,
    top_n: int = 10
) -> bool:

    top = sorted(
        [p for p in peers if (p.get(value_key) or 0) > 0],
        key=lambda p: p.get(value_key) or 0,
        reverse=True
    )[:top_n]

    if target_login and not any(p["login"] == target_login for p in top):
        target = next(
            (p for p in peers if p["login"] == target_login),
            None
        )
        if target and (target.get(value_key) or 0) > 0:
            top.append(target)

    if not top:
        return False

    labels = [p["login"] for p in top]
    values = [p.get(value_key) or 0 for p in top]

    clrs = [
        IISER_RED_HEX
        if p["login"] == target_login
        else CHART_COLORS_USER[i % len(CHART_COLORS_USER)]
        for i, p in enumerate(top)
    ]

    import numpy as np

    fig, ax = plt.subplots(
        figsize=(7, 7),
        dpi=300
    )

    wedges, _ = ax.pie(
        values,
        colors=clrs,
        startangle=90,
        radius=0.85,
        wedgeprops={
            "width": 0.60,
            "edgecolor": "white",
            "linewidth": 2
        }
    )

    ax.set_aspect("equal")

    # # Important: keep canvas fixed
    # ax.set_xlim(-1.6, 1.6)
    # ax.set_ylim(-1.6, 1.6)

    total = sum(values)

    for wedge, label, value in zip(wedges, labels, values):
        pct = value / total * 100
        if 0 < pct < 1.5:
            angle = (wedge.theta2 + wedge.theta1) / 2
            x = np.cos(np.deg2rad(angle))
            y = np.sin(np.deg2rad(angle))
            ax.annotate(
                f"{label}\n({pct:.1f}%)",
                xy=(x * 0.85, y * 0.85),
                xytext=(x * 2.70, y * 1.05),
                arrowprops=dict(
                    arrowstyle="-",
                    color="#555555",
                    lw=1
                ),
                fontsize=8,
                color="#333333",
                ha="center"
            )

    legend_labels = [
        f"{label} — {value:,.1f}"
        for label, value in zip(labels, values)
    ]

    ax.legend(
        wedges,
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        fontsize=11,
        labelspacing=1.1,
        handlelength=1.4,
        handleheight=1.4
    )

    ax.set_title(
        title,
        fontsize=11,
        fontweight="bold",
        color="#1a3a5c",
        pad=14
    )

    plt.savefig(
        path,
        dpi=300,
        bbox_inches="tight",
        facecolor="white"
    )

    plt.close()

    return True
CHART_COLORS_USER = [
    "#1B3A61",  # navy
    "#5E90BF",  # blue
    "#8AA1A8",  # slate
    "#264653",  # dark teal
    "#6D9DC5",  # steel blue
    "#A3B18A",  # muted green
    "#B56576",  # muted rose
    "#7D8597",  # blue grey
    "#6C757D",  # grey
    "#457B9D",  # medium blue
]

def _peer_bar_chart(peers: list, value_key: str, xlabel: str,
                    title: str, path: str, top_n: int = 20) -> bool:
    target = next((p for p in peers if p.get("is_target")), None)
    top = [p for p in peers if not p.get("is_target")][:top_n]
    if target and target not in top:
        top.append(target)
    top = sorted(top, key=lambda p: p.get(value_key) or 0)
    if not top:
        return False
    labels = [p["login"] for p in top]
    values = [p.get(value_key) or 0 for p in top]
    clrs   = [BAR_TARGET if p.get("is_target") else BAR_DEFAULT for p in top]

    fig, ax = plt.subplots(figsize=(5.5, max(5.5, len(top) * 0.38)))
    bars = ax.barh(labels, values, color=clrs, height=0.6, edgecolor="white")

    max_val = max(values) if values else 1
    for bar, val, peer in zip(bars, values, top):
        label_str = f"{val:,.0f}"
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            label_str, va="center", ha="left",
            fontsize=8.5,
            color=BAR_TARGET if peer.get("is_target") else "#2c3e50",
            fontweight="bold" if peer.get("is_target") else "normal"
        )
    ax.set_xlabel(xlabel, fontsize=10, color="#2c3e50")
    ax.set_title(title, fontsize=11, fontweight="bold", color="#1a3a5c")
    ax.tick_params(colors="#555555", labelsize=9)
    ax.set_xlim(0, max_val * 1.20)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.xaxis.grid(True, linestyle="--", alpha=0.4, color="#aaaaaa")
    ax.set_axisbelow(True)
    legend_patches = [
        mpatches.Patch(color=BAR_TARGET, label="Selected user"),
        mpatches.Patch(color=BAR_DEFAULT, label="Peers"),
    ]
    ax.legend(handles=legend_patches, fontsize=8, loc="lower right")
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    return True
def _kpi_donut(value_pct: float, label: str, path: str,
               colour: str = "#2c5f8a") -> bool:
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
def _styles():
    return {
        "title": ParagraphStyle(
            "Title", fontSize=22, leading=30, fontName="Helvetica-Bold",
            textColor=DARK_BLUE, alignment=TA_CENTER, spaceAfter=10
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", fontSize=13, leading=18, fontName="Helvetica",
            textColor=MID_BLUE, alignment=TA_CENTER, spaceBefore=2, spaceAfter=8
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
            "KpiLabel", fontSize=8, fontName="Helvetica-Bold",
            textColor=MID_GREY, alignment=TA_CENTER, leading=10,
            spaceAfter=2
        ),
        "kpi_value": ParagraphStyle(
            "KpiValue", fontSize=17, fontName="Helvetica-Bold",
            textColor=DARK_BLUE, alignment=TA_CENTER, leading=21,
            spaceBefore=3, spaceAfter=3
        ),
        "kpi_sub": ParagraphStyle(
            "KpiSub", fontSize=7.5, fontName="Helvetica",
            textColor=MID_GREY, alignment=TA_CENTER, leading=9.5,
            spaceBefore=2
        ),
        "unavail": ParagraphStyle(
            "Unavail", fontSize=11, fontName="Helvetica",
            textColor=MID_GREY, alignment=TA_CENTER, spaceBefore=20
        ),
        "figure_caption": ParagraphStyle(
            "FigureCaption", fontSize=8.5, fontName="Helvetica-Oblique",
            textColor=DARK_GREY, alignment=TA_CENTER, spaceAfter=6
        ),
        "section_desc": ParagraphStyle(
            "SectionDesc", fontSize=10, leading=14, fontName="Helvetica",
            textColor=DARK_GREY, spaceAfter=10
        ),
    }
def _section_hdr(title: str, s: dict) -> list:
    return [
        Paragraph(title, s["section"]),
        HRFlowable(width="100%", thickness=1.2, color=IISER_RED,
                   hAlign="LEFT", spaceAfter=10),
    ]
def _desc_box(text: str, content_w: float, s: dict) -> Table:
    box = Table(
        [[Paragraph(text, s["section_desc"])]],
        colWidths=[content_w]
    )
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f7fa")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6dde6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return box
def _kpi_table(items: list, col_w: float, s: dict) -> Table:
    cells = []
    for label, value, sub in items:
        cell = [
            Paragraph(label, s["kpi_label"]),
            Paragraph(str(value), s["kpi_value"]),
            Paragraph(sub, s["kpi_sub"]),
        ]
        cells.append(cell)
    t = Table([cells], colWidths=[col_w] * len(items), rowHeights=[2.6 * cm])
    t.setStyle(TableStyle([
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND",   (0, 0), (-1, -1), LIGHT_GREY),
        ("BOX",          (0, 0), (-1, -1), 0.5, LIGHT_BLUE),
        ("INNERGRID",    (0, 0), (-1, -1), 0.3, LIGHT_BLUE),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t
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
def generate_user_report(data: dict) -> bytes:
    username      = data.get("username", "unknown")
    account       = data.get("account",  "N/A")
    cluster       = data.get("cluster",  "N/A")
    start         = data.get("start",    "N/A")
    end           = data.get("end",      "N/A")
    generated_at  = data.get("generated_at", datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M IST"))
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
    tmp = {}
    for key in ["cpu_bar", "gpu_bar", "cpu_peer_donut", "gpu_peer_donut"]:
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
        charts["cpu_peer_donut"] = _peer_donut_chart(
            cpu_peers, "hours", "CPU Hours Distribution by User",
            tmp["cpu_peer_donut"], target_login=username, top_n=10
        )
        charts["gpu_peer_donut"] = _peer_donut_chart(
            gpu_peers, "gpu_hours", "GPU Hours Distribution by User",
            tmp["gpu_peer_donut"], target_login=username, top_n=10
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
        onPage=_header_footer(cluster, username, generated_at),
        onPageEnd=_watermark(),
    )])
    story = []
    # ── Cover page ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.15 * cm))
    institute_style = ParagraphStyle(
        "InstituteName", fontSize=16, fontName="Helvetica-Bold",
        textColor=DARK_BLUE, leading=19
    )
    institute_full_style = ParagraphStyle(
        "InstituteFull", fontSize=10.5, fontName="Helvetica",
        textColor=DARK_GREY, leading=13, spaceBefore=2
    )
    institute_sub_style = ParagraphStyle(
        "InstituteSub", fontSize=8, fontName="Helvetica",
        textColor=MID_GREY, leading=10, spaceBefore=2
    )
    if os.path.exists(COVER_LOGO_PATH) and os.path.getsize(COVER_LOGO_PATH) > 0:
        logo_img = Image(COVER_LOGO_PATH, width=2.6 * cm, height=2.6 * cm)
    else:
        logo_img = Paragraph("IISER<br/>PUNE", ParagraphStyle(
            "LogoFallback", fontSize=10, fontName="Helvetica-Bold",
            textColor=DARK_BLUE, alignment=TA_CENTER
        ))
    institute_text = [
        Paragraph("IISER PUNE", institute_style),
        Paragraph("Indian Institute of Science Education and Research Pune", institute_full_style),
        Paragraph("Autonomous Institution under Ministry of Education, Govt. of India", institute_sub_style),
    ]
    header_row = Table(
        [[logo_img, institute_text]],
        colWidths=[3.2 * cm, cw - 3.2 * cm],
        rowHeights=[2.8 * cm]
    )
    header_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",  (0, 0), (0, 0),   "LEFT"),
        ("LEFTPADDING",  (0, 0), (0, 0), 4),
        ("RIGHTPADDING", (0, 0), (0, 0), 4),
        ("LEFTPADDING",  (1, 0), (1, 0), 10),
    ]))
    story.append(header_row)
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1.3, color=IISER_RED, spaceAfter=18))
    eyebrow_style = ParagraphStyle(
        "Eyebrow", fontSize=9, fontName="Helvetica-Bold",
        textColor=IISER_RED, alignment=TA_CENTER, spaceAfter=6, leading=11
    )
    story.append(Paragraph("HPC PORTAL — AUTOMATED ANALYTICS REPORT", eyebrow_style))
    story.append(Spacer(1, 0.05 * cm))
    story.append(Paragraph("High Performance Computing Portal", s["title"]))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph("Individual User Utilization Report", s["subtitle"]))
    story.append(Spacer(1, 0.25 * cm))
    asterisk_style = ParagraphStyle(
        "Asterisks", fontSize=11, fontName="Helvetica",
        textColor=MID_GREY, alignment=TA_CENTER, spaceAfter=8
    )
    story.append(Paragraph("*&nbsp;&nbsp;&nbsp;*&nbsp;&nbsp;&nbsp;*", asterisk_style))
    story.extend(
    build_node_description_section(cluster, cw)
)
    # Report Particulars header bar
    particulars_header = Table([["REPORT PARTICULARS"]], colWidths=[cw])
    particulars_header.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), DARK_BLUE),
        ("TEXTCOLOR",   (0, 0), (-1, -1), WHITE),
        ("FONTNAME",    (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("ROWPADDING",  (0, 0), (-1, -1), 7),
    ]))
    story.append(particulars_header)
    # Cover page detail rows — unified order matching GPU report
    id_rows = [
        ["User (Login)",   username],
        ["Account",        account],
        ["Cluster",        cluster.upper()],
        ["Report Type",    "Individual User Utilization Analysis"],
        ["Report Period",  f"{start}  to  {end}"],
        ["Generated On",   generated_at],
        ["Generated By",   "IISER Pune HPC Portal (Automated System)"],
        ["Resource Profile", profile],
        ["Classification", "Internal — Restricted Circulation"],
    ]
    id_t = Table(id_rows, colWidths=[4.2 * cm, cw - 4.2 * cm])
    id_t.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",  (0, 0), (0, -1), DARK_BLUE),
        ("TEXTCOLOR",  (1, 0), (1, -1), DARK_GREY),
        ("ROWPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",(0, 0), (-1, -1), 10),
        ("BOX",        (0, 0), (-1, -1), 0.6, colors.HexColor("#dde3ea")),
        ("LINEBELOW",  (0, 0), (-1, -2), 0.25, colors.HexColor("#e6ebf0")),
    ]))
    story.append(id_t)
    story.append(Spacer(1, 0.7 * cm))
    disclaimer_style = ParagraphStyle(
        "Disclaimer", fontSize=8, fontName="Helvetica",
        textColor=MID_GREY, alignment=TA_CENTER, leading=11
    )
    story.append(Paragraph(
        "This report is auto-generated by the IISER Pune HPC Portal.<br/>"
        "For queries: hpc-support@iiserpune.ac.in  |  IISER Pune, Dr. Homi Bhabha Road, Pune — 411 008",
        disclaimer_style
    ))
    story.append(Spacer(1, 0.4 * cm))
    badge = Table([["FOR OFFICIAL USE ONLY"]], colWidths=[5.2 * cm])
    badge.setStyle(TableStyle([
        ("BOX",        (0, 0), (-1, -1), 0.8, DARK_BLUE),
        ("LINEBELOW",  (0, 0), (-1, -2), 0.25, colors.HexColor("#e6ebf0")),
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("TEXTCOLOR",  (0, 0), (-1, -1), DARK_BLUE),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("ROWPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Table([[badge]], colWidths=[cw], style=[("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(PageBreak())
    # ── Executive Summary ───────────────────────────────────────────────────
    story += _section_hdr("Executive User Summary", s)
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
    gpu_pct_str = f"{user_gpu_pct:.2f}%" if user_gpu_pct is not None else "N/A"
    metric_rows = [
        ["Metric", "Value", "Context"],
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
        ["Resource Profile",
         profile,
         _PROFILE_DESC.get(profile, "")],
    ]
    col_w = [4.5 * cm, 3.5 * cm, cw - 8.0 * cm]
    mt = Table(metric_rows, colWidths=col_w)
    mt.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  DARK_BLUE),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  10),
        ("FONTNAME",    (0, 1), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 1), (-1, -1), 9),
        ("TEXTCOLOR",   (0, 1), (0, -1),  DARK_BLUE),
        ("TEXTCOLOR",   (1, 1), (1, -1),  DARK_GREY),
        ("TEXTCOLOR",   (2, 1), (2, -1),  MID_GREY),
        ("ALIGN",       (1, 0), (1, -1),  "CENTER"),
        ("ALIGN",       (0, 0), (0, -1),  "LEFT"),
        *[("BACKGROUND", (0, i), (-1, i), LIGHT_GREY)
          for i in range(2, len(metric_rows), 2)],
        ("ROWPADDING",  (0, 0), (-1, -1), 6),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#dde3ea")),
        ("LINEBELOW",   (0, 0), (-1, 0),  1.5, DARK_BLUE),
        ("LINEBELOW",   (0, 5), (-1, 5),  1.0, LIGHT_BLUE),
        ("LINEBELOW",   (0, 9), (-1, 9),  1.0, LIGHT_BLUE),
    ]))
    story.append(mt)
    story.append(Spacer(1, 0.6 * cm))
    # KPI donuts
    story.append(Spacer(1, 0.5 * cm))
    kpi_items = [
        ("CPU HOURS",  f"{user_cpu_h:,}",        f"{user_cpu_pct:.2f}% of account"),
        ("GPU HOURS",  f"{user_gpu_h:,.1f}",     f"{gpu_pct_str} of cluster"),
        ("CPU RANK",   f"#{cpu_rank}/{n_peers}",  f"Top {100 - cpu_top_pct + 1}%"),
        ("GPU RANK",   f"#{gpu_rank}/{n_peers}",  f"Top {100 - gpu_top_pct + 1}%"),
    ]
    story.append(_kpi_table(kpi_items, cw / 4, s))
    story.append(PageBreak())
    # ── Peer Comparison ─────────────────────────────────────────────────────
    story += _section_hdr(f"Peer Comparison — {account.upper()} Account", s)
    story.append(_desc_box(
        f"This section compares <b>{username}</b> against all {n_peers} users "
        f"in account <b>{account}</b>, ranking resource consumption and "
        f"identifying the selected user's position relative to peers. "
        f"The selected user is highlighted in red across all charts and tables.",
        cw, s
    ))
    story.append(Spacer(1, 0.4 * cm))
    story += _section_hdr("CPU Consumption — Account Ranking", s)
    story.append(_desc_box(
        "The following visualizations compare CPU-hour consumption across "
        "all account peers. The donut chart illustrates each user's "
        "proportional share of CPU hours, while the bar chart presents "
        "absolute CPU-hour consumption ranked by usage.",
        cw, s
    ))
    story.append(Spacer(1, 0.4 * cm))
    # CPU peer table
    if cpu_peers:
        sorted_cpu = sorted(cpu_peers, key=lambda p: p.get("hours") or 0, reverse=True)
        cpu_total = sum(p.get("hours") or 0 for p in sorted_cpu) or 1
        cpu_tbl_rows = [["Rank", "User (Login)", "CPU Hours", "Share of Account"]]
        for rank, p in enumerate(sorted_cpu, 1):
            hrs = p.get("hours") or 0
            cpu_tbl_rows.append([
                str(rank),
                p["login"],
                f"{hrs:,.0f}",
                f"{hrs / cpu_total * 100:.2f}%",
            ])
        is_target = [p.get("is_target", False) for p in sorted_cpu]
        cpu_col_w = [1.5 * cm, 5.5 * cm, 4 * cm, 4.5 * cm]
        cpu_t = Table(cpu_tbl_rows, colWidths=cpu_col_w)
        highlight = [
            ("BACKGROUND", (0, i + 1), (-1, i + 1), colors.HexColor("#fdecea"))
            for i, t in enumerate(is_target) if t
        ]
        cpu_t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  DARK_BLUE),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  WHITE),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0),  10),
            ("ALIGN",       (0, 0), (-1, 0),  "CENTER"),
            *[("BACKGROUND", (0, i), (-1, i), LIGHT_GREY)
            for i in range(1, len(cpu_tbl_rows), 2)],
            *highlight,
            ("FONTNAME",    (0, 1), (0, -1),  "Helvetica-Bold"),
            ("FONTNAME",    (1, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",    (0, 1), (-1, -1), 9.5),
            ("TEXTCOLOR",   (0, 1), (-1, -1), DARK_GREY),
            ("ALIGN",       (0, 1), (0, -1),  "CENTER"),
            ("ALIGN",       (2, 1), (-1, -1), "CENTER"),
            ("ALIGN",       (1, 1), (1, -1),  "LEFT"),
            ("ROWPADDING",  (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
            ("LINEBELOW",   (0, 0), (-1, 0),  1.5, DARK_BLUE),
        ]))
    story.append(cpu_t)
    story.append(Spacer(1, 0.4 * cm))
    if charts.get("cpu_peer_donut") and os.path.exists(tmp["cpu_peer_donut"]) and os.path.getsize(tmp["cpu_peer_donut"]) > 0:
        donut_box = Table([[Image(tmp["cpu_peer_donut"], width=13 * cm, height=10 * cm)]])
        donut_box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfd6df")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(donut_box)
        story.append(Spacer(1, 0.08 * cm))
        story.append(Paragraph("FIG. 3A — CPU HOURS DISTRIBUTION BY USER", s["figure_caption"]))
        story.append(Spacer(1, 0.35 * cm))
    if charts.get("cpu_bar") and os.path.exists(tmp["cpu_bar"]) and os.path.getsize(tmp["cpu_bar"]) > 0:
        bar_box = Table([[Image(tmp["cpu_bar"], width=min(cw * 0.65, 14 * cm), height=min(cw * 0.65, 14 * cm))]])
        bar_box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfd6df")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(bar_box)
        story.append(Spacer(1, 0.08 * cm))
        story.append(Paragraph("FIG. 3B — TOP CPU CONSUMING USERS", s["figure_caption"]))
    else:
        story.append(Paragraph("CPU peer chart unavailable.", s["unavail"]))
    story.append(PageBreak())
    # ── GPU Peer Comparison ─────────────────────────────────────────────────
    story += _section_hdr("GPU Consumption — Account Ranking", s)
    story.append(_desc_box(
        "The following visualizations compare GPU-hour consumption across "
        "all account peers. The donut chart illustrates each user's "
        "proportional share of GPU hours, while the bar chart presents "
        "absolute GPU-hour consumption ranked by usage.",
        cw, s
    ))
    story.append(Spacer(1, 0.4 * cm))
    # GPU peer table
    if gpu_peers:
        sorted_gpu = sorted(gpu_peers, key=lambda p: p.get("gpu_hours") or 0, reverse=True)
        gpu_total = sum(p.get("gpu_hours") or 0 for p in sorted_gpu) or 1
        gpu_tbl_rows = [["Rank", "User (Login)", "GPU Hours", "Share of Account"]]
        for rank, p in enumerate(sorted_gpu, 1):
            hrs = p.get("gpu_hours") or 0
            gpu_tbl_rows.append([
                str(rank),
                p["login"],
                f"{hrs:,.1f}",
                f"{hrs / gpu_total * 100:.2f}%",
            ])
        is_target = [p.get("is_target", False) for p in sorted_gpu]
        gpu_col_w = [1.5 * cm, 5.5 * cm, 4 * cm, 4.5 * cm]
        gpu_t = Table(gpu_tbl_rows, colWidths=gpu_col_w)
        highlight = [
            ("BACKGROUND", (0, i + 1), (-1, i + 1), colors.HexColor("#fdecea"))
            for i, t in enumerate(is_target) if t
        ]
        gpu_t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  DARK_BLUE),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  WHITE),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0),  10),
            ("ALIGN",       (0, 0), (-1, 0),  "CENTER"),
            *[("BACKGROUND", (0, i), (-1, i), LIGHT_GREY)
            for i in range(1, len(gpu_tbl_rows), 2)],
            *highlight,
            ("FONTNAME",    (0, 1), (0, -1),  "Helvetica-Bold"),
            ("FONTNAME",    (1, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",    (0, 1), (-1, -1), 9.5),
            ("TEXTCOLOR",   (0, 1), (-1, -1), DARK_GREY),
            ("ALIGN",       (0, 1), (0, -1),  "CENTER"),
            ("ALIGN",       (2, 1), (-1, -1), "CENTER"),
            ("ALIGN",       (1, 1), (1, -1),  "LEFT"),
            ("ROWPADDING",  (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
            ("LINEBELOW",   (0, 0), (-1, 0),  1.5, DARK_BLUE),
        ]))
    story.append(gpu_t)
    story.append(Spacer(1, 0.4 * cm))
    if charts.get("gpu_peer_donut") and os.path.exists(tmp["gpu_peer_donut"]) and os.path.getsize(tmp["gpu_peer_donut"]) > 0:
        donut_box = Table([[Image(tmp["gpu_peer_donut"], width=13 * cm, height=10 * cm)]])
        donut_box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfd6df")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(donut_box)
        story.append(Spacer(1, 0.08 * cm))
        story.append(Paragraph("FIG. 4A — GPU HOURS DISTRIBUTION BY USER", s["figure_caption"]))
        story.append(Spacer(1, 0.35 * cm))
    if charts.get("gpu_bar") and os.path.exists(tmp["gpu_bar"]) and os.path.getsize(tmp["gpu_bar"]) > 0:
        bar_box = Table([[Image(tmp["gpu_bar"], width=min(cw * 0.65, 14 * cm), height=min(cw * 0.65, 14 * cm))]])
        bar_box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfd6df")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(bar_box)
        story.append(Spacer(1, 0.08 * cm))
        story.append(Paragraph("FIG. 4B — TOP GPU CONSUMING USERS", s["figure_caption"]))
    else:
        story.append(Paragraph("GPU peer chart unavailable.", s["unavail"]))
    story.append(Spacer(1, 0.6 * cm))
    story.append(PageBreak())
    story.append(Spacer(1, 0.6 * cm))
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