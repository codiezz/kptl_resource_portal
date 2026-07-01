"""
pdf_gpu_report.py

Generates a GPU-focused utilization PDF report.

Sections:
  1. Cover Page
  2. Executive GPU Summary
  3. GPU Utilization Analysis (table + pie + bar)
  4. GPU Observations

Reuses color palette and header/footer patterns from pdf_cluster_report.py.
Graceful degradation: if GPU data unavailable, PDF still generates with notice.

Usage:
    from pdf_gpu_report import generate_gpu_report
    pdf_bytes = generate_gpu_report({
        "cluster":  "fortytwo",
        "period":   {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "gpu":      {...},  # from parse_tres_utilization, or {}
    })
"""

import io
import os
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak
)
from cluster_metadata import build_node_description_section

# ---------------------------------------------------------------------------
# Color palette — matches pdf_cluster_report.py exactly
# ---------------------------------------------------------------------------
DARK_BLUE  = colors.HexColor("#1a3a5c")
MID_BLUE   = colors.HexColor("#2c5f8a")
LIGHT_BLUE = colors.HexColor("#a8c8e8")
LIGHT_GREY = colors.HexColor("#f4f6f8")
MID_GREY   = colors.HexColor("#7f8c8d")
DARK_GREY  = colors.HexColor("#2c3e50")
WHITE      = colors.white

# IISER Pune logo red — sampled directly from official logo asset (#d80100)
IISER_RED  = colors.HexColor("#d80100")
IISER_RED_HEX = "#d80100"  # plain hex string for matplotlib (ReportLab uses IISER_RED above)
COVER_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "iiser_logo.png")  # relative path to logo image for cover page
# Navy-dominant, non-monochromatic palette for GPU charts.
# Red reserved as a sparing accent (used only for the "Down" / attention metric).
CHART_COLORS_GPU = [
    "#1B3A61",
    "#336699",
    "#5E90BF",
    "#E10600",
    "#8AA1A8",
    "#264653",
    "#457B9D",
    "#6D9DC5",
    "#B56576",
    "#2A9D8F",
    "#577590",
    "#4D648D",
]

W, H = A4


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def _make_gpu_pie(metrics: dict, path: str):
    data = {
        "Allocated": metrics.get("allocated", 0),
        "Idle":      metrics.get("idle", 0),
        "Down":      metrics.get("down", 0),
        "Planned":   metrics.get("planned", 0),
    }
    if metrics.get("planned_down", 0) > 0:
        data["Planned\nDown"] = metrics["planned_down"]

    labels = list(data.keys())
    sizes  = list(data.values())
    clrs   = CHART_COLORS_GPU[:len(labels)]

    total = sum(sizes) or 1

    fig, ax = plt.subplots(figsize=(7,7), dpi=300)

    wedges, _ = ax.pie(
    sizes,
    colors=clrs,
    startangle=90,
    radius=0.85,
    wedgeprops={
        'width': 0.60,
        'edgecolor': 'white',
        'linewidth': 2
    }
)
    ax.set_aspect('equal')

    import numpy as np

    for wedge, label, value in zip(wedges, labels, sizes):

        pct = value / total * 100

        if 0 < pct < 5:

            angle = (wedge.theta2 + wedge.theta1) / 2

            x = np.cos(np.deg2rad(angle))
            y = np.sin(np.deg2rad(angle))

            ax.annotate(
                f"{label} ({pct:.1f}%)",
                xy=(x * 0.85, y * 0.85),
                xytext=(x * 1.05, y * 1.05),
                arrowprops=dict(
                    arrowstyle='-',
                    color='#555555',
                    lw=1
                ),
                fontsize=8,
                color='#333333'
            )

    # Donut style with an external legend only — no text or percentage
    # labels are drawn on the wedges themselves, so collisions between
    # adjacent small slices are structurally impossible regardless of
    # how thin any individual slice is.
    legend_labels = [
    f"{label} — {value:,.1f} hrs"
    for label, value in zip(labels, sizes)
]
    ax.legend(
        wedges, legend_labels,
        loc='center left', bbox_to_anchor=(1.0, 0.5),
        frameon=False, fontsize=9.5, labelspacing=1.1,
        handlelength=1.4, handleheight=1.4
    )

    ax.set_title("GPU Utilization Composition", fontsize=11,
                 fontweight='bold', color='#1a3a5c', pad=14)
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

def _make_gpu_bar(metrics: dict, path: str):
    labels = ["Allocated", "Idle", "Down", "Planned", "Planned\nDown"]
    values = [
        metrics.get("allocated", 0),
        metrics.get("idle", 0),
        metrics.get("down", 0),
        metrics.get("planned", 0),
        metrics.get("planned_down", 0),
    ]
    clrs = CHART_COLORS_GPU[:len(labels)]

    fig, ax = plt.subplots(figsize=(7,7), dpi=300)
    bars = ax.bar(labels, values, color=clrs, width=0.4,
                  edgecolor='white', linewidth=1.2)

    for bar, val in zip(bars, values):
        if val > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f'{val:.1f}%', ha='center', va='bottom',
                fontsize=10, fontweight='bold', color='#2c3e50'
            )

    ax.set_ylabel("Percentage (%)", fontsize=9, color='#2c3e50')
    ax.set_title("GPU Metrics Breakdown", fontsize=11,
                 fontweight='bold', color='#1a3a5c')
    ax.set_ylim(0, max(values) * 1.25 if max(values) > 0 else 100)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')
    ax.tick_params(colors='#555555', labelsize=9)
    ax.yaxis.grid(True, linestyle='--', alpha=0.4, color='#aaaaaa')
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()


def _make_gpu_accounts_hbar(accounts: list, path: str, top_n: int = 10) -> bool:
    """Horizontal bar — top accounts by GPU hours."""
    top = [a for a in accounts[:top_n] if (a.get('gpu_hours') or 0) > 0]
    if not top:
        return False

    labels = [a['account'] for a in reversed(top)]
    values = [a['gpu_hours'] for a in reversed(top)]
    # Top 3 by GPU hours are highlighted red ("heavy usage"); rest navy.
    # `top` is already sorted by gpu_hours descending before reversal for display.
    heavy_cutoff = min(3, len(top))
    clrs = []

    for idx, acct in enumerate(reversed(top)):
        rank = len(top) - idx

        if rank == 1:
            clrs.append(IISER_RED_HEX)      # highest consumer
        elif rank == 2:
            clrs.append("#b53a3a")          # muted red
        else:
            clrs.append("#1a3a5c")          # institutional navy

    fig, ax = plt.subplots(figsize=(7.5, max(3.5, len(top) * 0.45)))
    bars = ax.barh(labels, values, color=clrs[:len(labels)], height=0.35, edgecolor='#ffffff',
linewidth=0.7)

    max_val = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f'{val:,.1f} hrs', va='center', ha='left', fontsize=9, color='#2c3e50'
        )

    ax.set_xlabel("GPU Hours", fontsize=10, fontweight='bold', color='#2c3e50')
    ax.set_xlim(0, max_val * 1.18)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')
    ax.tick_params(colors='#555555', labelsize=10)
    ax.xaxis.grid(
    True,
    linestyle=':',
    linewidth=0.8,
    alpha=0.35,
    color='#9aa5b1'
)
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    return True

def _make_gpu_accounts_donut(accounts: list, path: str, top_n: int = 10) -> bool:

    top = [a for a in accounts[:top_n] if (a.get('gpu_hours') or 0) > 0]

    if not top:
        return False

    labels = [a['account'] for a in top]
    values = [a['gpu_hours'] for a in top]

    colors = CHART_COLORS_GPU[:len(labels)]

    fig, ax = plt.subplots(figsize=(7, 7), dpi=300)

    wedges, _ = ax.pie(
    values,
    colors=colors,
    startangle=90,
    radius=0.85,
    wedgeprops={
        'width': 0.60,
        'edgecolor': 'white',
        'linewidth': 2
    }
)
    import numpy as np

    total = sum(values)

    for wedge, label, value in zip(wedges, labels, values):

        pct = value / total * 100

        if pct < 5 and value > 0:

            angle = (wedge.theta1 + wedge.theta2) / 2

            x = np.cos(np.deg2rad(angle))
            y = np.sin(np.deg2rad(angle))

            ax.annotate(
                f"{label}\n({pct:.2f}%)",
                xy=(x * 0.85, y * 0.85),
                xytext=(x * 1.05, y * 1.05),
                arrowprops=dict(
                    arrowstyle='-',
                    lw=1,
                    color='#555555'
                ),
                fontsize=8,
                color='#333333'
            )

    ax.set_aspect('equal')
    legend_labels = [
    f"{label} — {value:,.1f} hrs"
    for label, value in zip(labels, values)
]

    ax.legend(
    wedges,
    legend_labels,
    loc='center left',
    bbox_to_anchor=(1.02, 0.5),
    frameon=False,
    fontsize=11
)

    ax.set_title(
        "GPU Hours Distribution by Account",
        fontsize=11,
        fontweight='bold',
        color='#1a3a5c'
    )

    plt.savefig(
        path,
        dpi=300,
        bbox_inches='tight',
        facecolor='white'
    )

    plt.close()

    return True


def _make_gpu_users_hbar(users: list, path: str, top_n: int = 12) -> bool:
    """Horizontal bar — top users by GPU hours."""
    top = [u for u in users[:top_n] if (u.get('gpu_hours') or 0) > 0]
    if not top:
        return False


    labels = [u['login'] for u in reversed(top)]
    values = [u['gpu_hours'] for u in reversed(top)]
    # Top 3 by GPU hours are highlighted red ("heavy usage"); rest navy.
    heavy_cutoff = min(3, len(top))
    heavy_logins = {u['login'] for u in top[:heavy_cutoff]}
    blue_palette = [
    "#1B3A61",
    "#29527A",
    "#376A93",
    "#4B82AA",
    "#6199C0",
    "#78AFD4",
    "#90C4E6",
    "#A9D5F0",
    "#C1E2F7"
]

    clrs = []

    for idx, u in enumerate(reversed(top)):

        if u['login'] in heavy_logins:
            clrs.append(IISER_RED_HEX)

        else:
            clrs.append(
                blue_palette[idx % len(blue_palette)]
            )

    fig, ax = plt.subplots(figsize=(7.5, max(3.5, len(top) * 0.45)))
    bars = ax.barh(labels, values, color=clrs[:len(labels)], height=0.6, edgecolor='white')

    max_val = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f'{val:,.1f}', va='center', ha='left', fontsize=9, color='#2c3e50'
        )

    ax.set_xlabel("GPU Hours", fontsize=10, color='#2c3e50')
    ax.set_title(f"Top {len(top)} Users by GPU Hours",
                 fontsize=11, fontweight='bold', color='#1a3a5c')
    ax.set_xlim(0, max_val * 1.18)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')
    ax.tick_params(colors='#555555', labelsize=10)
    ax.xaxis.grid(True, linestyle='--', alpha=0.4, color='#aaaaaa')
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    return True

def _make_gpu_users_donut(users: list, path: str, top_n: int = 12) -> bool:

    top = [u for u in users[:top_n] if (u.get('gpu_hours') or 0) > 0]

    if not top:
        return False

    labels = [u['login'] for u in top]
    values = [u['gpu_hours'] for u in top]

    fig, ax = plt.subplots(figsize=(7, 7), dpi=300)

    wedges, _ = ax.pie(
        values,
        startangle=90,
        radius=0.85,
        colors=CHART_COLORS_GPU[:len(labels)],
        wedgeprops={
            'width': 0.60,
            'edgecolor': 'white',
            'linewidth': 2
        }
    )

    total = sum(values)

    import numpy as np

    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.3, 1.3)

    small = [(w, l, v) for w, l, v in zip(wedges, labels, values) if 0 < v / total * 100 < 1]

    for s_idx, (wedge, label, value) in enumerate(small):

        pct = value / total * 100
        angle = (wedge.theta1 + wedge.theta2) / 2

        x = np.cos(np.deg2rad(angle))
        y = np.sin(np.deg2rad(angle))

        ytext = (1.12 if y >= 0 else -1.12) + s_idx * 0.12

        ax.annotate(
            f"{label}\n({pct:.1f}%)",
            xy=(x * 0.80, y * 0.80),
            xytext=(x * 1.05, ytext),
            arrowprops=dict(arrowstyle='-', lw=1, color='#555555'),
            fontsize=8,
            ha='center'
        )
    legend_labels = [
        f"{label} — {value:,.1f} hrs"
        for label, value in zip(labels, values)
    ]

    ax.legend(
        wedges,
        legend_labels,
        loc='center left',
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        fontsize=11
    )

    ax.set_aspect('equal')

    ax.set_title(
        "GPU Hours Distribution by User",
        fontsize=11,
        fontweight='bold'
    )

    plt.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    return True


def _header_footer(cluster_name: str, generated_at: str):
    def on_page(canvas, doc):
        # # Watermark
        # canvas.saveState()

        # canvas.translate(W / 2, H / 2)
        # canvas.rotate(40)

        # canvas.setFillGray(0.95)

        # canvas.setFont(
        #     "Helvetica-Bold",
        #     110
        # )

        # canvas.drawCentredString(
        #     30,
        #     0,
        #     "IISER PUNE"
        # )

        # canvas.restoreState()
        canvas.saveState()

        canvas.setFillColor(DARK_BLUE)
        canvas.rect(0, H - 1.2 * cm, W, 1.2 * cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(1.5 * cm, H - 0.85 * cm, "IISER Pune — HPC Portal")
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(W - 1.5 * cm, H - 0.85 * cm,
                               f"Cluster: {cluster_name.upper()}")

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

        canvas.setFont(
            "Helvetica-Bold",
            120
        )

        canvas.drawCentredString(
            30,
            0,
            "IISER PUNE"
        )
        canvas.setFillAlpha(0.15)

        canvas.restoreState()

    return on_page_end


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------

def _gpu_observations(metrics: dict) -> list:
    obs = []
    alloc = metrics.get("allocated", 0)
    idle  = metrics.get("idle", 0)
    down  = metrics.get("down", 0)

    if alloc > 80:
        obs.append(f"GPU resources are heavily utilized ({alloc:.1f}% allocated). High demand — consider capacity planning.")
    elif alloc < 30:
        obs.append(f"GPU utilization is low ({alloc:.1f}% allocated). Significant GPU capacity is available.")

    if idle > 50:
        obs.append(f"GPU idle time is high ({idle:.1f}%). Consider workload scheduling improvements.")

    if down > 10:
        obs.append(f"Notable GPU downtime recorded ({down:.1f}%). Hardware maintenance review recommended.")

    if not obs:
        obs.append(f"GPU allocated at {alloc:.1f}%. No anomalies detected in this reporting period.")

    return obs[:4]


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_gpu_report(data: dict) -> bytes:
    """
    Generate GPU utilization PDF report.

    Args:
        data = {
            "cluster":      "fortytwo",
            "period":       {"start": "...", "end": "..."},
            "gpu":          dict from parse_tres_utilization, or {}
            "gpu_accounts": dict from merge_gpu_account_data, or {}  [optional]
        }

    Returns:
        PDF as bytes.
    """
    cluster_name  = data.get("cluster", "Unknown")
    period        = data.get("period", {})
    gpu           = data.get("gpu", {})
    gpu_metrics   = gpu.get("metrics", {})
    gpu_accounts  = data.get("gpu_accounts", {})

    start_str    = (period.get("start") or "")[:10] or "N/A"
    end_str      = (period.get("end")   or "")[:10] or "N/A"
    generated_at = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M IST")

    # Styles
    s = {
        'title': ParagraphStyle(
    'Title',
    fontSize=22,
    leading=30,
    fontName='Helvetica-Bold',
    textColor=DARK_BLUE,
    alignment=TA_CENTER,
    spaceAfter=10
),
        'subtitle': ParagraphStyle(
    'Subtitle',
    fontSize=13,
    leading=18,
    fontName='Helvetica',
    textColor=MID_BLUE,
    alignment=TA_CENTER,
    spaceBefore=2,
    spaceAfter=8
),
        'section': ParagraphStyle(
            'Section', fontSize=13, fontName='Helvetica-Bold',
            textColor=DARK_BLUE, spaceBefore=14, spaceAfter=8
        ),
        'body': ParagraphStyle(
            'Body', fontSize=10, fontName='Helvetica',
            textColor=DARK_GREY, spaceAfter=4
        ),
        'unavailable': ParagraphStyle(
            'Unavail', fontSize=11, fontName='Helvetica',
            textColor=MID_GREY, alignment=TA_CENTER, spaceBefore=20
        ),
        'obs_item': ParagraphStyle(
            'ObsItem', fontSize=10, fontName='Helvetica',
            textColor=DARK_GREY, spaceAfter=6, leftIndent=12
        ),
        'figure_caption': ParagraphStyle(
            'FigureCaption',
            fontSize=8.5,
            fontName='Helvetica-Oblique',
            textColor=DARK_GREY,
            alignment=TA_CENTER,
            spaceAfter=6
        ),
        'section_desc': ParagraphStyle(
        'SectionDesc',
        fontSize=10,
        leading=14,
        fontName='Helvetica',
        textColor=DARK_GREY,
        spaceAfter=10
    )
    }

    def section_header(title):
        return [
            Paragraph(title, s['section']),
            HRFlowable(width="100%", thickness=1.2, color=IISER_RED,
                       hAlign='LEFT', spaceAfter=10)
        ]

    # Generate chart images to temp files
    tmp_pie  = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_gpu_pie_')
    tmp_bar  = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_gpu_bar_')
    tmp_acct = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_gpu_acct_')
    tmp_usr  = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_gpu_usr_')
    tmp_usr_donut = tempfile.NamedTemporaryFile(
    suffix='.png',
    delete=False,
    prefix='hpc_gpu_usr_donut_'
)
    tmp_acct_donut = tempfile.NamedTemporaryFile(
    suffix='.png',
    delete=False,
    prefix='hpc_gpu_acct_donut_'
)
    for f in [tmp_pie, tmp_bar, tmp_acct, tmp_usr, tmp_acct_donut, tmp_usr_donut]:
        f.close()
    charts_ok    = False
    acct_chart_ok = False
    user_chart_ok = False
    acct_donut_ok = False

    try:
        if gpu_metrics:
            _make_gpu_pie(gpu_metrics, tmp_pie.name)
            _make_gpu_bar(gpu_metrics, tmp_bar.name)
            charts_ok = True

        acct_list  = gpu_accounts.get('accounts', [])
        all_users  = []
        for acct in acct_list:
            for u in acct.get('users', []):
                all_users.append({**u, 'account': acct['account']})
        all_users.sort(key=lambda u: u.get('gpu_hours') or 0, reverse=True)

        if acct_list:
            acct_chart_ok = _make_gpu_accounts_hbar(acct_list, tmp_acct.name)
            acct_donut_ok = _make_gpu_accounts_donut(acct_list, tmp_acct_donut.name)
            print("ACCOUNT DONUT CREATED:", acct_donut_ok)
            print("ACCOUNT DONUT FILE:", tmp_acct_donut.name)
        if all_users:
            user_chart_ok = _make_gpu_users_hbar(all_users, tmp_usr.name)
            user_donut_ok = False

            if all_users:
                user_donut_ok = _make_gpu_users_donut(
                all_users,
                tmp_usr_donut.name
            )

        pdf_bytes = _build_pdf(
            cluster_name, start_str, end_str, generated_at,
            s, section_header, gpu_metrics, charts_ok,
            tmp_pie.name, tmp_bar.name,
            acct_list, all_users, acct_chart_ok,
            acct_donut_ok,
            user_chart_ok,
            tmp_acct.name,
            tmp_acct_donut.name,
            tmp_usr.name,
            user_donut_ok,
            tmp_usr_donut.name
        )

    finally:
        for p in [tmp_pie.name, tmp_bar.name, tmp_acct.name, tmp_usr.name, tmp_acct_donut.name, tmp_usr_donut.name]:
            try:
                os.unlink(p)
            except OSError:
                pass

    return pdf_bytes


def _build_pdf(
    cluster_name, start_str, end_str, generated_at,
    s, section_header, gpu_metrics, charts_ok,
    pie_path, bar_path,
    acct_list, all_users,
    acct_chart_ok, acct_donut_ok,
    user_chart_ok,
    acct_path, acct_donut_path, usr_path, user_donut_ok, usr_donut_path
) -> bytes:

    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=2.2 * cm, bottomMargin=1.8 * cm,
    )
    content_w = W - doc.leftMargin - doc.rightMargin
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        content_w,
        H - doc.topMargin - doc.bottomMargin,
        id='normal'
    )
    template = PageTemplate(
        id='main', frames=[frame],
        onPage=_header_footer(cluster_name, generated_at),
        onPageEnd=_watermark()
    )
    doc.addPageTemplates([template])
    story = []

    # ----------------------------------------------------------------
    # PAGE 1 — COVER
    # ----------------------------------------------------------------
    story.append(Spacer(1, 0.15 * cm))

    institute_style = ParagraphStyle(
        'InstituteName', fontSize=16, fontName='Helvetica-Bold',
        textColor=DARK_BLUE, leading=19
    )
    institute_full_style = ParagraphStyle(
        'InstituteFull', fontSize=10.5, fontName='Helvetica',
        textColor=DARK_GREY, leading=13, spaceBefore=2
    )
    institute_sub_style = ParagraphStyle(
        'InstituteSub', fontSize=8, fontName='Helvetica',
        textColor=MID_GREY, leading=10, spaceBefore=2
    )

    if os.path.exists(COVER_LOGO_PATH) and os.path.getsize(COVER_LOGO_PATH) > 0:
        logo_img = Image(COVER_LOGO_PATH, width=2.6 * cm, height=2.6 * cm)
    else:
        logo_img = Paragraph("IISER<br/>PUNE", ParagraphStyle(
            'LogoFallback', fontSize=10, fontName='Helvetica-Bold',
            textColor=DARK_BLUE, alignment=TA_CENTER
        ))

    institute_text = [
        Paragraph("IISER PUNE", institute_style),
        Paragraph("Indian Institute of Science Education and Research Pune", institute_full_style),
        Paragraph("Autonomous Institution under Ministry of Education, Govt. of India", institute_sub_style),
    ]

    header_row = Table(
        [[logo_img, institute_text]],
        colWidths=[3.2 * cm, content_w - 3.2 * cm],
        rowHeights=[2.8 * cm]
    )
    header_row.setStyle(TableStyle([
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',      (0, 0), (0, 0),   'LEFT'),
        #('BACKGROUND', (1, 0), (1, 0),   IISER_RED),
        ('LEFTPADDING',  (0, 0), (0, 0), 4),
        ('RIGHTPADDING', (0, 0), (0, 0), 4),
        ('LEFTPADDING',  (2, 0), (2, 0), 10),
    ]))
    story.append(header_row)
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1.3, color=IISER_RED, spaceAfter=18))

    eyebrow_style = ParagraphStyle(
        'Eyebrow', fontSize=9, fontName='Helvetica-Bold',
        textColor=IISER_RED, alignment=TA_CENTER, spaceAfter=6,
        leading=11
    )
    story.append(Paragraph("HPC PORTAL — AUTOMATED ANALYTICS REPORT", eyebrow_style))
    story.append(Spacer(1, 0.05 * cm))
    story.append(Paragraph("High Performance Computing Portal", s['title']))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph("GPU Utilization Report", s['subtitle']))
    story.append(Spacer(1, 0.25 * cm))

    asterisk_style = ParagraphStyle(
        'Asterisks', fontSize=11, fontName='Helvetica',
        textColor=MID_GREY, alignment=TA_CENTER, spaceAfter=8
    )
    story.append(Paragraph("*&nbsp;&nbsp;&nbsp;*&nbsp;&nbsp;&nbsp;*", asterisk_style))
    story.extend(
    build_node_description_section(cluster_name, content_w)
)

    particulars_header = Table(
        [["REPORT PARTICULARS"]], colWidths=[content_w]
    )
    particulars_header.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, -1), DARK_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, -1), WHITE),
        ('FONTNAME',    (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, -1), 10),
        ('ALIGN',       (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('ROWPADDING',  (0, 0), (-1, -1), 7),
    ]))
    story.append(particulars_header)

    cover_rows = [
        ["Cluster Name", cluster_name.upper()],
        ["Report Type",    "GPU (gres/gpu) Utilization Analysis"],
        ["Report Period",  f"{start_str}  to  {end_str}"],
        ["Generated On",   f"{generated_at}"],
        ["Generated By",   "IISER Pune HPC Portal (Automated System)"],
        ["Classification", "Internal — Restricted Circulation"],
    ]
    ct = Table(cover_rows, colWidths=[4.2 * cm, content_w - 4.2 * cm])
    ct.setStyle(TableStyle([
        ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',   (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE',   (0, 0), (-1, -1), 10),
        ('TEXTCOLOR',  (0, 0), (0, -1), DARK_BLUE),
        ('TEXTCOLOR',  (1, 0), (1, -1), DARK_GREY),
        ('ROWPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',(0, 0), (-1, -1), 10),
        ('BOX',        (0, 0), (-1, -1), 0.6, colors.HexColor("#dde3ea")),
        ('LINEBELOW',  (0, 0), (-1, -2), 0.25, colors.HexColor("#e6ebf0")),
    ]))
    story.append(ct)
    story.append(Spacer(1, 0.7 * cm))

    disclaimer_style = ParagraphStyle(
        'Disclaimer', fontSize=8, fontName='Helvetica',
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
        ('BOX',        (0, 0), (-1, -1), 0.8, DARK_BLUE),
        ('LINEBELOW', (0, 0), (-1, -2), 0.25, colors.HexColor("#e6ebf0")),
        ('FONTNAME',   (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 8),
        ('TEXTCOLOR',  (0, 0), (-1, -1), DARK_BLUE),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('ROWPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(Table([[badge]], colWidths=[content_w], style=[('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 2 — EXECUTIVE GPU SUMMARY + ANALYSIS
    # ----------------------------------------------------------------
    story += section_header("Executive GPU Summary")
    description_text = """
This section presents an executive overview of GPU resource utilization
across the reporting period. The metrics summarize the distribution of
GPU resources between active allocations, idle capacity, maintenance
downtime, and planned reservations. These values provide a high-level
assessment of accelerator usage efficiency within the cluster.
"""

    desc_box = Table(
        [[Paragraph(description_text, s['section_desc'])]],
        colWidths=[content_w]
    )

    desc_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f5f7fa")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#d6dde6")),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))

    story.append(desc_box)
    story.append(Spacer(1, 0.4 * cm))

    if gpu_metrics:
        # Summary metrics table
        rows = [
            ["Metric", "Value", "Description"],
            ["Allocated",    f"{gpu_metrics.get('allocated', 0):.2f}%",    "GPU resources actively in use"],
            ["Idle",         f"{gpu_metrics.get('idle', 0):.2f}%",         "GPU resources available but unused"],
            ["Down",         f"{gpu_metrics.get('down', 0):.2f}%",         "GPU resources unavailable / maintenance"],
            ["Planned",      f"{gpu_metrics.get('planned', 0):.2f}%",      "GPU resources reserved for planned use"],
            ["Planned Down", f"{gpu_metrics.get('planned_down', 0):.2f}%", "GPU resources planned for downtime"],
            ["Reported",     f"{gpu_metrics.get('reported', 0):.2f}%",     "Total accounted GPU utilization"],
        ]
        t = Table(rows, colWidths=[4.5 * cm, 3 * cm, 9 * cm])
        t.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0),  DARK_BLUE),
            ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
            ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, 0),  10),
            ('ALIGN',       (0, 0), (-1, 0),  'CENTER'),
            ('BACKGROUND',  (0, 1), (-1, 1),  LIGHT_GREY),
            ('BACKGROUND',  (0, 3), (-1, 3),  LIGHT_GREY),
            ('BACKGROUND',  (0, 5), (-1, 5),  LIGHT_GREY),
            ('FONTNAME',    (0, 1), (0, -1),  'Helvetica-Bold'),
            ('FONTNAME',    (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',    (0, 1), (-1, -1), 9.5),
            ('TEXTCOLOR',   (0, 1), (-1, -1), DARK_GREY),
            ('ALIGN',       (1, 0), (1, -1),  'CENTER'),
            ('ROWPADDING',  (0, 0), (-1, -1), 7),
            ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
            ('LINEBELOW',   (0, 0), (-1, 0),  1.5, DARK_BLUE),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.4 * cm))

        # Charts
        story += section_header("Visual Analysis")
        description_text = """
The following visualizations illustrate the proportional distribution
of GPU resources and provide a graphical interpretation of overall
utilization trends. Donut charts emphasize percentage composition,
while bar charts highlight the relative contribution of each category.
Together, these figures provide a concise overview of accelerator
availability, usage, and operational status.
"""

        desc_box = Table(
            [[Paragraph(description_text, s['section_desc'])]],
            colWidths=[content_w]
        )

        desc_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f5f7fa")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#d6dde6")),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))

        story.append(desc_box)
        story.append(Spacer(1, 0.4 * cm))

        if charts_ok and os.path.exists(pie_path) and os.path.getsize(pie_path) > 0:

            pie_img = Image(
                pie_path,
                width=14 * cm,
                height=11 * cm
                )

            pie_box = Table([[pie_img]])
            pie_box.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor("#cfd6df")),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))

            story.append(pie_box)

            story.append(Spacer(1, 0.08 * cm))

            story.append(Paragraph(
            "FIG. 2A — GPU UTILIZATION DISTRIBUTION",
            s['figure_caption']
            ))

            story.append(Spacer(1, 0.35 * cm))

            bar_img = Image(
                bar_path,
                width=15 * cm,
                height=11 * cm
                )

            bar_box = Table([[bar_img]])
            bar_box.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor("#cfd6df")),
                ('LEFTPADDING', (0,0), (-1,-1), 4),
                ('RIGHTPADDING', (0,0), (-1,-1), 4),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))

            story.append(bar_box)

            story.append(Spacer(1, 0.08 * cm))

            story.append(Paragraph(
            "FIG. 2B — GPU UTILIZATION BREAKDOWN",
            s['figure_caption']
        ))

    else:
        # GPU unavailable notice
        story.append(Spacer(1, 1 * cm))
        notice = Table(
            [[Paragraph(
                "GPU utilization data was unavailable for this reporting period.\n\n"
                "Possible reasons:\n"
                "• GPU TRES tracking not configured on this cluster\n"
                "• No GPU jobs scheduled during this period\n"
                "• sreport gres/gpu command returned no data",
                s['unavailable']
            )]],
            colWidths=[content_w]
        )
        notice.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREY),
            ('BOX',        (0, 0), (-1, -1), 1, colors.HexColor("#dde3ea")),
            ('ROWPADDING', (0, 0), (-1, -1), 24),
        ]))
        story.append(notice)

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 3 — OBSERVATIONS
    # ----------------------------------------------------------------
    # story += section_header("GPU Observations")
    # story.append(Paragraph(
    #     f"Automatically generated observations for {cluster_name.upper()} "
    #     f"GPU utilization, period {start_str} to {end_str}.",
    #     s['body']
    # ))
    # story.append(Spacer(1, 0.4 * cm))

    # if gpu_metrics:
    #     obs = _gpu_observations(gpu_metrics)
    #     for i, o in enumerate(obs, 1):
    #         story.append(Paragraph(f"<b>{i}.</b>  {o}", s['obs_item']))
    # else:
    #     story.append(Paragraph(
    #         "No GPU observations available — data was unavailable for this period.",
    #         s['unavailable']
    #     ))

    # ----------------------------------------------------------------
    # NEW PAGE — GPU RESOURCE CONSUMPTION BY ACCOUNT
    # ----------------------------------------------------------------
    # story.append(PageBreak())
    story += section_header("GPU Resource Consumption by Account")
    description_text = """
GPU consumption is aggregated by project account to identify the primary
consumers of accelerator resources during the reporting period. These
statistics provide insight into how GPU capacity is distributed among
research groups, projects, and organizational units utilizing the cluster.
"""

    desc_box = Table(
        [[Paragraph(description_text, s['section_desc'])]],
        colWidths=[content_w]
    )

    desc_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f5f7fa")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#d6dde6")),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))

    story.append(desc_box)
    story.append(Spacer(1, 0.4 * cm))

    active_accounts = [a for a in acct_list if (a.get('gpu_hours') or 0) > 0]

    if active_accounts:
            top_accts = active_accounts[:10]
            acct_rows = [["Account", "GPU Hours", "Usage %", "Active Users"]]
            for a in top_accts:
                active_users = len([u for u in a.get('users', [])
                                    if (u.get('gpu_hours') or 0) > 0])
                acct_rows.append([
                    a['account'],
                    f"{a['gpu_hours']:,.1f}",
                    f"{a['gpu_pct']:.2f}%" if a.get('gpu_pct') is not None else "—",
                    str(active_users),
                ])

            at = Table(acct_rows, colWidths=[6 * cm, 4 * cm, 3.5 * cm, 3.5 * cm])
            at.setStyle(TableStyle([
                ('BACKGROUND',  (0, 0), (-1, 0),  DARK_BLUE),
                ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
                ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
                ('FONTSIZE',    (0, 0), (-1, 0),  10),
                ('ALIGN',       (1, 0), (-1, -1), 'CENTER'),
                ('ALIGN',       (0, 0), (0, -1),  'LEFT'),
                *[('BACKGROUND', (0, i), (-1, i), LIGHT_GREY)
                for i in range(1, len(acct_rows), 2)],
                ('FONTSIZE',    (0, 1), (-1, -1), 9.5),
                ('TEXTCOLOR',   (0, 1), (-1, -1), DARK_GREY),
                ('ROWPADDING',  (0, 0), (-1, -1), 7),
                ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
                ('LINEBELOW',   (0, 0), (-1, 0),  1.5, DARK_BLUE),
            ]))
            story.append(at)
            story.append(Spacer(1, 0.4 * cm))

            story += section_header("Visual Analysis")
            description_text = """
The following charts compare GPU-hour consumption across active accounts.
The donut chart illustrates each account's proportional contribution to
overall GPU utilization, while the horizontal bar chart highlights total
GPU-hour consumption. Together, these visualizations help identify the
most resource-intensive projects within the cluster.
"""

            desc_box = Table(
                [[Paragraph(description_text, s['section_desc'])]],
                colWidths=[content_w]
            )

            desc_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f5f7fa")),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#d6dde6")),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ]))

            story.append(desc_box)
            story.append(Spacer(1, 0.4 * cm))

            content_w = W - 1.8 * cm - 1.8 * cm
            if acct_donut_ok and os.path.exists(acct_donut_path) and os.path.getsize(acct_donut_path) > 0:

                donut_img = Image(
                    acct_donut_path,
                    width=15 * cm,
                    height=11 * cm
                    )

                donut_box = Table([[donut_img]])
                donut_box.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor("#cfd6df")),
                ('LEFTPADDING', (0,0), (-1,-1), 4),
                ('RIGHTPADDING', (0,0), (-1,-1), 4),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))

                story.append(donut_box)

                story.append(
                    Paragraph(
                        "FIG. 3A — GPU HOURS DISTRIBUTION BY ACCOUNT",
                            s['figure_caption']
                     )
                )

                story.append(Spacer(1, 0.08 * cm))
                story.append(PageBreak())
            else:
                story.append(Paragraph(
                    "No GPU account consumption data available for this period.",
                    s['unavailable']
            ))
            if acct_chart_ok and os.path.exists(acct_path) and os.path.getsize(acct_path) > 0:

                bar_h = min(11 * cm, max(8 * cm, len(top_accts) * 0.8 * cm))

                bar_img = Image(
                acct_path,
                width=content_w,
                height=bar_h
                )

                bar_box = Table([[bar_img]])
                bar_box.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor("#cfd6df")),
                ('LEFTPADDING', (0,0), (-1,-1), 4),
                ('RIGHTPADDING', (0,0), (-1,-1), 4),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ]))

                story.append(bar_box)

                story.append(
                    Paragraph(
                    "FIG. 3B — TOP GPU CONSUMING ACCOUNTS",
                    s['figure_caption']
                    )
                )

    # ----------------------------------------------------------------
    # NEW PAGE — TOP GPU USERS
    # ----------------------------------------------------------------
    story.append(PageBreak())
    story += section_header("Top GPU Users by Resource Consumption")
    description_text = """
This section identifies individual users with the highest GPU resource
consumption during the selected reporting period. The presented statistics
support workload attribution, capacity planning, and identification of
major computational workloads executed on the cluster infrastructure.
"""

    desc_box = Table(
        [[Paragraph(description_text, s['section_desc'])]],
        colWidths=[content_w]
    )

    desc_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f5f7fa")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#d6dde6")),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))

    story.append(desc_box)
    story.append(Spacer(1, 0.4 * cm))

    # Filter: users with >0 gpu_hours, unless too few
    active_users = [u for u in all_users if (u.get('gpu_hours') or 0) > 0]
    display_users = active_users if len(active_users) >= 3 else all_users
    display_users = display_users[:15]

    if display_users:
        user_rows = [["User (Login)", "Account", "GPU Hours", "Usage %"]]
        for u in display_users:
            user_rows.append([
                u.get('login', ''),
                u.get('account', ''),
                f"{u['gpu_hours']:,.1f}",
                f"{u['gpu_pct']:.2f}%" if u.get('gpu_pct') is not None else "—",
            ])

        ut = Table(user_rows, colWidths=[4.5 * cm, 4.5 * cm, 4 * cm, 4 * cm])
        ut.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0),  DARK_BLUE),
            ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
            ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, 0),  10),
            ('ALIGN',       (2, 0), (-1, -1), 'CENTER'),
            ('ALIGN',       (0, 0), (1, -1),  'LEFT'),
            *[('BACKGROUND', (0, i), (-1, i), LIGHT_GREY)
              for i in range(1, len(user_rows), 2)],
            ('FONTSIZE',    (0, 1), (-1, -1), 9.5),
            ('TEXTCOLOR',   (0, 1), (-1, -1), DARK_GREY),
            ('ROWPADDING',  (0, 0), (-1, -1), 7),
            ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
            ('LINEBELOW',   (0, 0), (-1, 0),  1.5, DARK_BLUE),
        ]))
        story.append(ut)
        story.append(Spacer(1, 0.4 * cm))
        story += section_header("Visual Analysis")
        description_text = """
The user-level visualizations provide a comparative analysis of GPU
resource consumption across active researchers. The donut chart
illustrates the proportional share of total GPU utilization, while
the horizontal bar chart presents absolute GPU-hour consumption for
each user. These charts help identify dominant workloads and overall
usage distribution patterns.
"""

        desc_box = Table(
            [[Paragraph(description_text, s['section_desc'])]],
            colWidths=[content_w]
        )

        desc_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f5f7fa")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#d6dde6")),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))

        story.append(desc_box)
        story.append(Spacer(1, 0.4 * cm))

        if user_donut_ok and os.path.exists(usr_donut_path):

                donut_img = Image(
                    usr_donut_path,
                    width=15 * cm,
                    height=11 * cm
                )

                donut_box = Table([[donut_img]])
                donut_box.setStyle(TableStyle([
                    ('BOX',(0,0),(-1,-1),0.6,colors.HexColor("#cfd6df"))
                ]))

                story.append(donut_box)

                story.append(
                    Paragraph(
                        "FIG. 5A — GPU HOURS DISTRIBUTION BY USER",
                        s['figure_caption']
                    )
                )

        bar_img = Image(
            usr_path,
            width=content_w,
            height=11 * cm
)   
        
    if user_chart_ok and os.path.exists(usr_path) and os.path.getsize(usr_path) > 0:

        content_w = W - 1.8 * cm - 1.8 * cm

        bar_img = Image(
            usr_path,
            width=content_w,
            height=11 * cm
    )

        bar_box = Table([[bar_img]])
        bar_box.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.6, colors.HexColor("#cfd6df")),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
         ]))

        story.append(bar_box)

        story.append(
            Paragraph(
                "FIG. 5B — TOP GPU CONSUMING USERS",
                s['figure_caption']
            )
        )

        story.append(Spacer(1, 0.08 * cm))
    else:
        story.append(Paragraph(
            "No GPU user consumption data available for this period.",
            s['unavailable']
        ))

    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from slurm_report_parser import merge_gpu_account_data

    # Sample merged GPU account data
    gpu_accounts = merge_gpu_account_data(
        {
            'cluster': 'fortytwo',
            'period': {'start': '2025-10-01T00:00:00', 'end': '2025-12-31T23:59:59'},
            'accounts': [
                {'account': 'iiser', 'gpu_minutes': 3328062,
                 'users': [
                     {'login': 'arnab',  'gpu_minutes': 213443},
                     {'login': 'ashish', 'gpu_minutes':  51019},
                     {'login': 'madhu',  'gpu_minutes': 563280},
                 ]},
                {'account': 'root',  'gpu_minutes': 3739174, 'users': []},
            ]
        },
        {
            'accounts': [
                {'account': 'root',  'gpu_pct': 49.74, 'users': []},
                {'account': 'iiser', 'gpu_pct': 44.27, 'users': [
                    {'login': 'arnab',  'gpu_pct':  2.84},
                    {'login': 'ashish', 'gpu_pct':  0.68},
                    {'login': 'madhu',  'gpu_pct':  7.49},
                ]},
            ]
        }
    )

    # Test 1: full report with all data
    pdf = generate_gpu_report({
        "cluster": "fortytwo",
        "period": {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "gpu": {
            "tres_name": "gres/gpu",
            "metrics": {
                "allocated": 49.74, "down": 2.44, "planned_down": 0.0,
                "idle": 47.82, "planned": 0.0, "reported": 100.65
            }
        },
        "gpu_accounts": gpu_accounts,
    })
    with open("/tmp/test_gpu_report_full.pdf", "wb") as f:
        f.write(pdf)
    print(f"[PASS] Full GPU report: {len(pdf):,} bytes → /tmp/test_gpu_report_full.pdf")

    # Test 2: no gpu_accounts — existing pages still render, new pages show notice
    pdf2 = generate_gpu_report({
        "cluster": "fortytwo",
        "period": {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "gpu": {
            "tres_name": "gres/gpu",
            "metrics": {
                "allocated": 49.74, "down": 2.44, "planned_down": 0.0,
                "idle": 47.82, "planned": 0.0, "reported": 100.65
            }
        },
        "gpu_accounts": {},
    })
    with open("/tmp/test_gpu_report_no_accounts.pdf", "wb") as f:
        f.write(pdf2)
    print(f"[PASS] GPU report (no accounts): {len(pdf2):,} bytes — no crash")

    # Test 3: full graceful degradation — no gpu data at all
    pdf3 = generate_gpu_report({
        "cluster": "fortytwo",
        "period": {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "gpu": {},
        "gpu_accounts": {},
    })
    with open("/tmp/test_gpu_report_empty.pdf", "wb") as f:
        f.write(pdf3)
    print(f"[PASS] GPU report (fully empty): {len(pdf3):,} bytes — no crash")