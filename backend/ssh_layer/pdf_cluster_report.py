"""
pdf_cluster_report.py

Generates an enhanced, information-rich cluster utilization PDF report.

Sections:
  1. Cover Page
  2. Executive Summary (CPU + GPU combined table)
  3. CPU Detailed Analysis (table + pie + bar)
  4. GPU Detailed Analysis (table + pie + bar) OR unavailable notice
  5. Resource Consumption by Account (table + horizontal bar)
  6. Top Users (table + horizontal bar)
  7. Observations

Usage:
    from pdf_cluster_report import generate_enhanced_cluster_report

    pdf_bytes = generate_enhanced_cluster_report({
        "cluster":  "fortytwo",
        "period":   {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "cpu":      {...},   # from parse_tres_utilization, or {}
        "gpu":      {...},   # from parse_tres_utilization, or {}
        "accounts": {...},   # from parse_account_utilization, or {}
    })
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
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak
)

# ---------------------------------------------------------------------------
# Color palette — academic blue/grey (matches existing pdf_generator.py)
# ---------------------------------------------------------------------------
DARK_BLUE   = colors.HexColor("#1a3a5c")
MID_BLUE    = colors.HexColor("#2c5f8a")
LIGHT_BLUE  = colors.HexColor("#a8c8e8")
ACCENT_RED  = colors.HexColor("#c0392b")
LIGHT_GREY  = colors.HexColor("#f4f6f8")
MID_GREY    = colors.HexColor("#7f8c8d")
DARK_GREY   = colors.HexColor("#2c3e50")
WHITE       = colors.white

CHART_COLORS_CPU  = ["#2c5f8a", "#a8c8e8", "#c0392b", "#7f8c8d", "#bdc3c7"]
CHART_COLORS_GPU  = ["#1a6b4a", "#5db89a", "#c0392b", "#7f8c8d", "#bdc3c7"]
CHART_COLORS_ACCT = [
    "#2c5f8a", "#3a7abf", "#4e95d6", "#6aafe0",
    "#85c0e8", "#a0ccee", "#b8d9f0", "#cde4f5",
    "#deeefa", "#eef6fc"
]

W, H = A4


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _make_tres_pie(metrics: dict, title: str, path: str, color_set: list):
    """Pie chart for TRES utilization (allocated/idle/down/planned)."""
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
    clrs   = color_set[:len(labels)]

    fig, ax = plt.subplots(figsize=(5, 3.6))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=clrs,
        autopct='%1.1f%%', startangle=140,
        pctdistance=0.82,
        textprops={'fontsize': 8.5, 'color': '#2c3e50'},
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5}
    )
    for at in autotexts:
        at.set_fontsize(7.5)
        at.set_fontweight('bold')

    ax.set_title(title, fontsize=10, fontweight='bold', color='#1a3a5c', pad=10)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()


def _make_tres_bar(metrics: dict, title: str, path: str, color_set: list):
    """Vertical bar chart for TRES utilization metrics."""
    labels = ["Allocated", "Idle", "Down", "Planned", "Planned\nDown"]
    values = [
        metrics.get("allocated", 0),
        metrics.get("idle", 0),
        metrics.get("down", 0),
        metrics.get("planned", 0),
        metrics.get("planned_down", 0),
    ]
    clrs = color_set[:len(labels)]

    fig, ax = plt.subplots(figsize=(6, 3.6))
    bars = ax.bar(labels, values, color=clrs, width=0.5, edgecolor='white', linewidth=1.2)

    for bar, val in zip(bars, values):
        if val > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f'{val:.1f}%', ha='center', va='bottom',
                fontsize=8.5, fontweight='bold', color='#2c3e50'
            )

    ax.set_ylabel("Percentage (%)", fontsize=9, color='#2c3e50')
    ax.set_title(title, fontsize=10, fontweight='bold', color='#1a3a5c')
    ax.set_ylim(0, max(values) * 1.25 if max(values) > 0 else 100)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')
    ax.tick_params(colors='#555555', labelsize=8.5)
    ax.yaxis.grid(True, linestyle='--', alpha=0.4, color='#aaaaaa')
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()


def _make_hbar_accounts(accounts: list, path: str, top_n: int = 10):
    """Horizontal bar chart — top accounts by CPU hours."""
    top = accounts[:top_n]
    if not top:
        return False

    labels = [a['account'] for a in reversed(top)]
    values = [a['hours'] or 0 for a in reversed(top)]
    clrs   = CHART_COLORS_ACCT[:len(labels)]

    fig, ax = plt.subplots(figsize=(7.5, max(3.5, len(top) * 0.42)))
    bars = ax.barh(labels, values, color=clrs, height=0.6, edgecolor='white')

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max(values) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f'{val:,}', va='center', ha='left',
            fontsize=8, color='#2c3e50'
        )

    ax.set_xlabel("CPU Hours", fontsize=9, color='#2c3e50')
    ax.set_title(f"Top {len(top)} Accounts by CPU Hours", fontsize=10,
                 fontweight='bold', color='#1a3a5c')
    ax.set_xlim(0, max(values) * 1.18 if max(values) > 0 else 1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')
    ax.tick_params(colors='#555555', labelsize=8.5)
    ax.xaxis.grid(True, linestyle='--', alpha=0.4, color='#aaaaaa')
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return True


def _make_hbar_users(users: list, path: str, top_n: int = 12):
    """Horizontal bar chart — top users by CPU hours."""
    top = users[:top_n]
    if not top:
        return False

    labels = [u['login'] for u in reversed(top)]
    values = [u['hours'] or 0 for u in reversed(top)]
    clrs   = CHART_COLORS_ACCT[:len(labels)]

    fig, ax = plt.subplots(figsize=(7.5, max(3.5, len(top) * 0.42)))
    bars = ax.barh(labels, values, color=clrs, height=0.6, edgecolor='white')

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max(values) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f'{val:,}', va='center', ha='left',
            fontsize=8, color='#2c3e50'
        )

    ax.set_xlabel("CPU Hours", fontsize=9, color='#2c3e50')
    ax.set_title(f"Top {len(top)} Users by CPU Hours", fontsize=10,
                 fontweight='bold', color='#1a3a5c')
    ax.set_xlim(0, max(values) * 1.18 if max(values) > 0 else 1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')
    ax.tick_params(colors='#555555', labelsize=8.5)
    ax.xaxis.grid(True, linestyle='--', alpha=0.4, color='#aaaaaa')
    ax.set_axisbelow(True)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return True


# ---------------------------------------------------------------------------
# Page header/footer
# ---------------------------------------------------------------------------

def _header_footer(cluster_name: str, generated_at: str):
    def on_page(canvas, doc):
        canvas.saveState()

        # Header bar
        canvas.setFillColor(DARK_BLUE)
        canvas.rect(0, H - 1.2 * cm, W, 1.2 * cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(1.5 * cm, H - 0.85 * cm, "IISER Pune — HPC Portal")
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(W - 1.5 * cm, H - 0.85 * cm,
                               f"Cluster: {cluster_name.upper()}")

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


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _styles():
    """Return reusable paragraph styles."""
    return {
        'title': ParagraphStyle(
            'Title', fontSize=22, fontName='Helvetica-Bold',
            textColor=DARK_BLUE, alignment=TA_CENTER, spaceAfter=6
        ),
        'subtitle': ParagraphStyle(
            'Subtitle', fontSize=13, fontName='Helvetica',
            textColor=MID_BLUE, alignment=TA_CENTER, spaceAfter=4
        ),
        'section': ParagraphStyle(
            'Section', fontSize=13, fontName='Helvetica-Bold',
            textColor=DARK_BLUE, spaceBefore=14, spaceAfter=8
        ),
        'meta': ParagraphStyle(
            'Meta', fontSize=10, fontName='Helvetica',
            textColor=MID_GREY, alignment=TA_CENTER, spaceAfter=3
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
    }


def _section_header(title: str, s) -> list:
    """Return [Paragraph header, HRFlowable] flowables."""
    return [
        Paragraph(title, s['section']),
        HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE, spaceAfter=10)
    ]


def _metrics_table(metrics: dict, label: str) -> Table:
    """Build a metrics table for one TRES type."""
    rows = [
        ["Metric", "Value", "Description"],
        ["Allocated",    f"{metrics.get('allocated', 0):.2f}%",    "Resources actively in use"],
        ["Idle",         f"{metrics.get('idle', 0):.2f}%",         "Resources available but unused"],
        ["Down",         f"{metrics.get('down', 0):.2f}%",         "Resources unavailable / maintenance"],
        ["Planned",      f"{metrics.get('planned', 0):.2f}%",      "Reserved for planned use"],
        ["Planned Down", f"{metrics.get('planned_down', 0):.2f}%", "Planned for downtime"],
        ["Reported",     f"{metrics.get('reported', 0):.2f}%",     "Total accounted utilization"],
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
    return t


# ---------------------------------------------------------------------------
# Observation generator
# ---------------------------------------------------------------------------

def _generate_observations(cpu: dict, gpu: dict, accounts: dict) -> list:
    """
    Generate simple factual observations from parsed data.
    Returns list of strings. Max 6 observations.
    """
    obs = []
    cm = cpu.get('metrics', {})
    gm = gpu.get('metrics', {})

    if cm:
        if cm.get('allocated', 0) > 80:
            obs.append(f"CPU resources are heavily utilized ({cm['allocated']:.1f}% allocated). Consider capacity expansion.")
        elif cm.get('allocated', 0) < 30:
            obs.append(f"CPU utilization is low ({cm['allocated']:.1f}% allocated). Significant idle capacity available.")
        if cm.get('idle', 0) > 50:
            obs.append(f"CPU idle time is high ({cm['idle']:.1f}%). Scheduling optimization may improve throughput.")
        if cm.get('down', 0) > 10:
            obs.append(f"Notable CPU downtime recorded ({cm['down']:.1f}%). Infrastructure review recommended.")

    if gm:
        if gm.get('allocated', 0) > 80:
            obs.append(f"GPU resources are heavily utilized ({gm['allocated']:.1f}% allocated). High demand period.")
        elif gm.get('idle', 0) > 50:
            obs.append(f"GPU utilization is relatively low ({gm['idle']:.1f}% idle). GPU capacity underutilized.")
    elif gpu == {}:
        obs.append("GPU utilization data was unavailable for this reporting period.")

    accts = accounts.get('accounts', [])
    if accts and accounts.get('cluster_total'):
        total_hours = accounts['cluster_total'].get('hours', 0)
        top_acct    = accts[0]
        if total_hours and top_acct.get('hours'):
            top_pct = (top_acct['hours'] / total_hours) * 100
            if top_pct > 40:
                obs.append(
                    f"Account '{top_acct['account']}' accounts for {top_pct:.1f}% of total "
                    f"cluster usage — dominant consumer this period."
                )

    return obs[:6]  # cap at 6


# ---------------------------------------------------------------------------
# Main PDF builder
# ---------------------------------------------------------------------------

def generate_enhanced_cluster_report(data: dict) -> bytes:
    """
    Generate enhanced cluster utilization PDF.

    Args:
        data = {
            "cluster":  "fortytwo",
            "period":   {"start": "...", "end": "..."},
            "cpu":      dict from parse_tres_utilization, or {}
            "gpu":      dict from parse_tres_utilization, or {}
            "accounts": dict from parse_account_utilization, or {}
        }

    Returns:
        PDF as bytes.
    """
    from slurm_report_parser import get_all_users_sorted

    cluster_name = data.get('cluster', 'Unknown')
    period       = data.get('period', {})
    cpu          = data.get('cpu', {})
    gpu          = data.get('gpu', {})
    accounts     = data.get('accounts', {})

    start_str    = (period.get('start') or '')[:10] or 'N/A'
    end_str      = (period.get('end')   or '')[:10] or 'N/A'
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    cpu_metrics  = cpu.get('metrics', {})
    gpu_metrics  = gpu.get('metrics', {})
    acct_list    = accounts.get('accounts', [])
    all_users    = get_all_users_sorted(accounts, top_n=12)

    s = _styles()

    # Generate chart images to temp files
    tmp = {}
    try:
        for key in ['cpu_pie', 'cpu_bar', 'gpu_pie', 'gpu_bar', 'acct_bar', 'users_bar']:
            f = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix=f'hpc_{key}_')
            f.close()
            tmp[key] = f.name

        if cpu_metrics:
            _make_tres_pie(cpu_metrics, "CPU Utilization Composition", tmp['cpu_pie'], CHART_COLORS_CPU)
            _make_tres_bar(cpu_metrics, "CPU Metrics Breakdown", tmp['cpu_bar'], CHART_COLORS_CPU)

        gpu_charts_ok = False
        if gpu_metrics:
            _make_tres_pie(gpu_metrics, "GPU Utilization Composition", tmp['gpu_pie'], CHART_COLORS_GPU)
            _make_tres_bar(gpu_metrics, "GPU Metrics Breakdown", tmp['gpu_bar'], CHART_COLORS_GPU)
            gpu_charts_ok = True

        acct_chart_ok = _make_hbar_accounts(acct_list, tmp['acct_bar']) if acct_list else False
        user_chart_ok = _make_hbar_users(all_users, tmp['users_bar']) if all_users else False

        pdf_bytes = _build_pdf(
            cluster_name, start_str, end_str, generated_at, s,
            cpu_metrics, gpu_metrics, gpu_charts_ok,
            acct_list, all_users,
            acct_chart_ok, user_chart_ok,
            tmp, accounts,
            cpu, gpu
        )

    finally:
        for path in tmp.values():
            try:
                os.unlink(path)
            except OSError:
                pass

    return pdf_bytes


def _build_pdf(
    cluster_name, start_str, end_str, generated_at, s,
    cpu_metrics, gpu_metrics, gpu_charts_ok,
    acct_list, all_users,
    acct_chart_ok, user_chart_ok,
    tmp, accounts,
    cpu, gpu
) -> bytes:

    buf  = io.BytesIO()
    doc  = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=2.2 * cm, bottomMargin=1.8 * cm,
    )
    frame    = Frame(
        doc.leftMargin, doc.bottomMargin,
        W - doc.leftMargin - doc.rightMargin,
        H - doc.topMargin - doc.bottomMargin,
        id='normal'
    )
    template = PageTemplate(
        id='main', frames=[frame],
        onPage=_header_footer(cluster_name, generated_at)
    )
    doc.addPageTemplates([template])
    story = []

    content_w = W - doc.leftMargin - doc.rightMargin  # usable width

    # ----------------------------------------------------------------
    # PAGE 1 — COVER
    # ----------------------------------------------------------------
    story.append(Spacer(1, 3 * cm))

    logo_table = Table(
        [[Paragraph("IISER PUNE", ParagraphStyle(
            'Logo', fontSize=17, fontName='Helvetica-Bold',
            textColor=WHITE, alignment=TA_CENTER
        ))]],
        colWidths=[6 * cm], rowHeights=[1.8 * cm]
    )
    logo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK_BLUE),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(Table([[logo_table]], colWidths=[content_w]))
    story.append(Spacer(1, 1 * cm))

    story.append(Paragraph("High Performance Computing Portal", s['title']))
    story.append(Paragraph("Comprehensive Cluster Utilization Report", s['subtitle']))
    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width="70%", thickness=1.5, color=LIGHT_BLUE, spaceAfter=20))

    cover_rows = [
        ["Cluster",       cluster_name.upper()],
        ["Report Period", f"{start_str}  →  {end_str}"],
        ["Generated",     generated_at],
        ["Report Type",   "CPU · GPU · Account · User Analysis"],
    ]
    ct = Table(cover_rows, colWidths=[5 * cm, 9 * cm])
    ct.setStyle(TableStyle([
        ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',   (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE',   (0, 0), (-1, -1), 11),
        ('TEXTCOLOR',  (0, 0), (0, -1), DARK_BLUE),
        ('TEXTCOLOR',  (1, 0), (1, -1), DARK_GREY),
        ('ROWPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW',  (0, 0), (-1, -2), 0.5, LIGHT_GREY),
    ]))
    story.append(Table([[ct]], colWidths=[content_w]))
    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 2 — EXECUTIVE SUMMARY
    # ----------------------------------------------------------------
    story += _section_header("Executive Summary", s)

    # Combined CPU vs GPU table
    exec_rows = [
        ["Metric", "CPU", "GPU"],
        ["Allocated %",
         f"{cpu_metrics.get('allocated', 0):.2f}%" if cpu_metrics else "—",
         f"{gpu_metrics.get('allocated', 0):.2f}%" if gpu_metrics else "Unavailable"],
        ["Idle %",
         f"{cpu_metrics.get('idle', 0):.2f}%" if cpu_metrics else "—",
         f"{gpu_metrics.get('idle', 0):.2f}%" if gpu_metrics else "—"],
        ["Down %",
         f"{cpu_metrics.get('down', 0):.2f}%" if cpu_metrics else "—",
         f"{gpu_metrics.get('down', 0):.2f}%" if gpu_metrics else "—"],
        ["Planned %",
         f"{cpu_metrics.get('planned', 0):.2f}%" if cpu_metrics else "—",
         f"{gpu_metrics.get('planned', 0):.2f}%" if gpu_metrics else "—"],
        ["Reported %",
         f"{cpu_metrics.get('reported', 0):.2f}%" if cpu_metrics else "—",
         f"{gpu_metrics.get('reported', 0):.2f}%" if gpu_metrics else "—"],
    ]
    col_w3 = [6 * cm, 5 * cm, 5 * cm]
    et = Table(exec_rows, colWidths=col_w3)
    et.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0),  DARK_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
        ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0),  10),
        ('ALIGN',       (0, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND',  (0, 1), (-1, 1),  LIGHT_GREY),
        ('BACKGROUND',  (0, 3), (-1, 3),  LIGHT_GREY),
        ('BACKGROUND',  (0, 5), (-1, 5),  LIGHT_GREY),
        ('FONTNAME',    (0, 1), (0, -1),  'Helvetica-Bold'),
        ('FONTNAME',    (1, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',    (0, 1), (-1, -1), 10),
        ('ROWPADDING',  (0, 0), (-1, -1), 7),
        ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
        ('LINEBELOW',   (0, 0), (-1, 0),  1.5, DARK_BLUE),
    ]))
    story.append(et)
    story.append(Spacer(1, 0.5 * cm))

    # Quick account stats if available
    if accounts.get('cluster_total') and acct_list:
        total_h = accounts['cluster_total'].get('hours', 0)
        n_accts = len(acct_list)
        all_users_count = sum(len(a.get('users', [])) for a in acct_list)
        story.append(Spacer(1, 0.4 * cm))
        quick_rows = [
            ["Total CPU Hours", f"{total_h:,}" if total_h else "—",
             "Active Accounts", str(n_accts),
             "Active Users", str(all_users_count)]
        ]
        qt = Table(quick_rows, colWidths=[4 * cm, 3 * cm, 4 * cm, 2 * cm, 3 * cm, 2 * cm])
        qt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREY),
            ('FONTNAME',   (0, 0), (0, -1),  'Helvetica-Bold'),
            ('FONTNAME',   (2, 0), (2, -1),  'Helvetica-Bold'),
            ('FONTNAME',   (4, 0), (4, -1),  'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 10),
            ('TEXTCOLOR',  (0, 0), (0, -1),  DARK_BLUE),
            ('TEXTCOLOR',  (2, 0), (2, -1),  DARK_BLUE),
            ('TEXTCOLOR',  (4, 0), (4, -1),  DARK_BLUE),
            ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
            ('ROWPADDING', (0, 0), (-1, -1), 10),
            ('BOX',        (0, 0), (-1, -1), 1, colors.HexColor("#dde3ea")),
            ('INNERGRID',  (0, 0), (-1, -1), 0.5, colors.HexColor("#dde3ea")),
        ]))
        story.append(qt)

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 3 — CPU ANALYSIS
    # ----------------------------------------------------------------
    story += _section_header("CPU Utilization Analysis", s)

    if cpu_metrics:
        story.append(_metrics_table(cpu_metrics, "CPU"))
        story.append(Spacer(1, 0.6 * cm))

        if os.path.exists(tmp['cpu_pie']) and os.path.getsize(tmp['cpu_pie']) > 0:
            pie_img = Image(tmp['cpu_pie'], width=8.5 * cm, height=6.2 * cm)
            bar_img = Image(tmp['cpu_bar'], width=9 * cm, height=6.2 * cm)
            chart_t = Table([[pie_img, bar_img]], colWidths=[9 * cm, 9.5 * cm])
            chart_t.setStyle(TableStyle([
                ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(chart_t)
    else:
        story.append(Paragraph("CPU utilization data was unavailable for this period.", s['unavailable']))

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 4 — GPU ANALYSIS
    # ----------------------------------------------------------------
    story += _section_header("GPU Utilization Analysis", s)

    if gpu_metrics and gpu_charts_ok:
        story.append(_metrics_table(gpu_metrics, "GPU (gres/gpu)"))
        story.append(Spacer(1, 0.6 * cm))

        if os.path.exists(tmp['gpu_pie']) and os.path.getsize(tmp['gpu_pie']) > 0:
            pie_img = Image(tmp['gpu_pie'], width=8.5 * cm, height=6.2 * cm)
            bar_img = Image(tmp['gpu_bar'], width=9 * cm, height=6.2 * cm)
            chart_t = Table([[pie_img, bar_img]], colWidths=[9 * cm, 9.5 * cm])
            chart_t.setStyle(TableStyle([
                ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(chart_t)
    else:
        story.append(Spacer(1, 1 * cm))
        notice = Table(
            [[Paragraph("GPU utilization data was unavailable for this reporting period.\n\n"
                        "This may indicate GPU TRES tracking is not configured on the cluster,\n"
                        "or that no GPU jobs were scheduled during this period.",
                        s['unavailable'])]],
            colWidths=[content_w]
        )
        notice.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREY),
            ('BOX',        (0, 0), (-1, -1), 1, colors.HexColor("#dde3ea")),
            ('ROWPADDING', (0, 0), (-1, -1), 20),
        ]))
        story.append(notice)

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 5 — ACCOUNT UTILIZATION
    # ----------------------------------------------------------------
    story += _section_header("Resource Consumption by Account", s)

    if acct_list:
        # Table — top 10 accounts
        top_accts = acct_list[:10]
        acct_rows = [["Account", "CPU Hours", "Usage %", "Active Users"]]
        for a in top_accts:
            acct_rows.append([
                a['account'],
                f"{a['hours']:,}" if a['hours'] else "—",
                f"{a['percentage']:.2f}%" if a['percentage'] else "—",
                str(len(a.get('users', []))),
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
        story.append(Spacer(1, 0.6 * cm))

        if acct_chart_ok and os.path.exists(tmp['acct_bar']) and os.path.getsize(tmp['acct_bar']) > 0:
            bar_h = min(7 * cm, max(4 * cm, len(top_accts) * 0.6 * cm))
            story.append(Image(tmp['acct_bar'], width=content_w, height=bar_h))
    else:
        story.append(Paragraph("Account utilization data was unavailable.", s['unavailable']))

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 6 — TOP USERS
    # ----------------------------------------------------------------
    story += _section_header("Top Users by Resource Consumption", s)

    if all_users:
        user_rows = [["User (Login)", "Proper Name", "Account", "CPU Hours", "Usage %"]]
        for u in all_users:
            user_rows.append([
                u['login'],
                u.get('proper_name', '') or '—',
                u.get('account', ''),
                f"{u['hours']:,}" if u['hours'] else "—",
                f"{u['percentage']:.2f}%" if u['percentage'] else "—",
            ])

        ut = Table(user_rows, colWidths=[3.5 * cm, 4 * cm, 3.5 * cm, 3.5 * cm, 3 * cm])
        ut.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0),  DARK_BLUE),
            ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
            ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, 0),  10),
            ('ALIGN',       (3, 0), (-1, -1), 'CENTER'),
            ('ALIGN',       (0, 0), (2, -1),  'LEFT'),
            *[('BACKGROUND', (0, i), (-1, i), LIGHT_GREY)
              for i in range(1, len(user_rows), 2)],
            ('FONTSIZE',    (0, 1), (-1, -1), 9),
            ('TEXTCOLOR',   (0, 1), (-1, -1), DARK_GREY),
            ('ROWPADDING',  (0, 0), (-1, -1), 6),
            ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
            ('LINEBELOW',   (0, 0), (-1, 0),  1.5, DARK_BLUE),
        ]))
        story.append(ut)
        story.append(Spacer(1, 0.6 * cm))

        if user_chart_ok and os.path.exists(tmp['users_bar']) and os.path.getsize(tmp['users_bar']) > 0:
            bar_h = min(7 * cm, max(4 * cm, len(all_users) * 0.55 * cm))
            story.append(Image(tmp['users_bar'], width=content_w, height=bar_h))
    else:
        story.append(Paragraph("User utilization data was unavailable.", s['unavailable']))

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 7 — OBSERVATIONS
    # ----------------------------------------------------------------
    story += _section_header("Summary Observations", s)
    story.append(Paragraph(
        f"The following observations are automatically generated based on "
        f"cluster data for the period {start_str} to {end_str}.",
        s['body']
    ))
    story.append(Spacer(1, 0.4 * cm))

    obs = _generate_observations(cpu, gpu, accounts)
    if obs:
        for i, o in enumerate(obs, 1):
            story.append(Paragraph(f"<b>{i}.</b>  {o}", s['obs_item']))
    else:
        story.append(Paragraph("No automated observations available for this period.", s['unavailable']))

    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')

    sample_data = {
        "cluster": "fortytwo",
        "period": {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "cpu": {
            "tres_name": "cpu",
            "period": {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
            "metrics": {
                "allocated": 29.22, "down": 2.75, "planned_down": 0.0,
                "idle": 52.86, "planned": 15.18, "reported": 100.0
            }
        },
        "gpu": {
            "tres_name": "gres/gpu",
            "metrics": {
                "allocated": 49.74, "down": 2.44, "planned_down": 0.0,
                "idle": 47.82, "planned": 0.0, "reported": 100.65
            }
        },
        "accounts": {
            "cluster": "fortytwo",
            "cluster_total": {"hours": 16515432, "percentage": 100.0},
            "accounts": [
                {
                    "account": "dsai_lab",
                    "hours": 4388444, "percentage": 26.56,
                    "users": [
                        {"login": "alice", "proper_name": "Alice Smith",   "hours": 200000, "percentage": 1.21},
                        {"login": "bob",   "proper_name": "Bob Jones",     "hours": 150000, "percentage": 0.91},
                    ]
                },
                {
                    "account": "physics",
                    "hours": 3100000, "percentage": 18.77,
                    "users": [
                        {"login": "charlie", "proper_name": "C. Brown",    "hours": 500000, "percentage": 3.03},
                    ]
                },
                {
                    "account": "chem_dept",
                    "hours": 2000000, "percentage": 12.11,
                    "users": [
                        {"login": "diana", "proper_name": "Diana Prince",  "hours": 300000, "percentage": 1.82},
                        {"login": "eve",   "proper_name": "Eve Wilson",    "hours": 100000, "percentage": 0.61},
                    ]
                },
            ]
        }
    }

    pdf = generate_enhanced_cluster_report(sample_data)
    out = "/tmp/test_enhanced_report.pdf"
    with open(out, 'wb') as f:
        f.write(pdf)
    print(f"PDF generated: {len(pdf):,} bytes → {out}")
    print("7 pages: Cover | Executive Summary | CPU | GPU | Accounts | Users | Observations")