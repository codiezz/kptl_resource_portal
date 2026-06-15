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

# GPU uses green palette to distinguish from CPU blue
CHART_COLORS_GPU = ["#1a6b4a", "#5db89a", "#c0392b", "#7f8c8d", "#bdc3c7"]

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

    fig, ax = plt.subplots(figsize=(5.5, 4))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=clrs,
        autopct='%1.1f%%', startangle=140,
        pctdistance=0.82,
        textprops={'fontsize': 9, 'color': '#2c3e50'},
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5}
    )
    for at in autotexts:
        at.set_fontsize(8)
        at.set_fontweight('bold')
    ax.set_title("GPU Utilization Composition", fontsize=11,
                 fontweight='bold', color='#1a3a5c', pad=12)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
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

    fig, ax = plt.subplots(figsize=(6.5, 4))
    bars = ax.bar(labels, values, color=clrs, width=0.5,
                  edgecolor='white', linewidth=1.2)

    for bar, val in zip(bars, values):
        if val > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f'{val:.1f}%', ha='center', va='bottom',
                fontsize=9, fontweight='bold', color='#2c3e50'
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
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()


def _make_gpu_accounts_hbar(accounts: list, path: str, top_n: int = 10) -> bool:
    """Horizontal bar — top accounts by GPU hours."""
    top = [a for a in accounts[:top_n] if (a.get('gpu_hours') or 0) > 0]
    if not top:
        return False

    labels = [a['account'] for a in reversed(top)]
    values = [a['gpu_hours'] for a in reversed(top)]
    clrs   = ["#1a6b4a", "#2e8b57", "#3aad6e", "#5db89a", "#80c9ac",
              "#a0d8be", "#bde5cf", "#d5efdf", "#e8f7ef", "#f4fbf7"][:len(labels)]

    fig, ax = plt.subplots(figsize=(7.5, max(3.5, len(top) * 0.45)))
    bars = ax.barh(labels, values, color=clrs[:len(labels)], height=0.6, edgecolor='white')

    max_val = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f'{val:,.1f}', va='center', ha='left', fontsize=8, color='#2c3e50'
        )

    ax.set_xlabel("GPU Hours", fontsize=9, color='#2c3e50')
    ax.set_title(f"Top {len(top)} Accounts by GPU Hours",
                 fontsize=10, fontweight='bold', color='#1a3a5c')
    ax.set_xlim(0, max_val * 1.18)
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


def _make_gpu_users_hbar(users: list, path: str, top_n: int = 12) -> bool:
    """Horizontal bar — top users by GPU hours."""
    top = [u for u in users[:top_n] if (u.get('gpu_hours') or 0) > 0]
    if not top:
        return False

    labels = [u['login'] for u in reversed(top)]
    values = [u['gpu_hours'] for u in reversed(top)]
    clrs   = ["#2c5f8a", "#3a7abf", "#4e95d6", "#6aafe0", "#85c0e8",
              "#a0ccee", "#b8d9f0", "#cde4f5", "#deeefa", "#eef6fc",
              "#1a6b4a", "#5db89a"][:len(labels)]

    fig, ax = plt.subplots(figsize=(7.5, max(3.5, len(top) * 0.45)))
    bars = ax.barh(labels, values, color=clrs[:len(labels)], height=0.6, edgecolor='white')

    max_val = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f'{val:,.1f}', va='center', ha='left', fontsize=8, color='#2c3e50'
        )

    ax.set_xlabel("GPU Hours", fontsize=9, color='#2c3e50')
    ax.set_title(f"Top {len(top)} Users by GPU Hours",
                 fontsize=10, fontweight='bold', color='#1a3a5c')
    ax.set_xlim(0, max_val * 1.18)
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




def _header_footer(cluster_name: str, generated_at: str):
    def on_page(canvas, doc):
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
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Styles
    s = {
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

    def section_header(title):
        return [
            Paragraph(title, s['section']),
            HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE, spaceAfter=10)
        ]

    # Generate chart images to temp files
    tmp_pie  = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_gpu_pie_')
    tmp_bar  = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_gpu_bar_')
    tmp_acct = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_gpu_acct_')
    tmp_usr  = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_gpu_usr_')
    for f in [tmp_pie, tmp_bar, tmp_acct, tmp_usr]:
        f.close()
    charts_ok    = False
    acct_chart_ok = False
    user_chart_ok = False

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
        if all_users:
            user_chart_ok = _make_gpu_users_hbar(all_users, tmp_usr.name)

        pdf_bytes = _build_pdf(
            cluster_name, start_str, end_str, generated_at,
            s, section_header, gpu_metrics, charts_ok,
            tmp_pie.name, tmp_bar.name,
            acct_list, all_users, acct_chart_ok, user_chart_ok,
            tmp_acct.name, tmp_usr.name
        )

    finally:
        for p in [tmp_pie.name, tmp_bar.name, tmp_acct.name, tmp_usr.name]:
            try:
                os.unlink(p)
            except OSError:
                pass

    return pdf_bytes


def _build_pdf(
    cluster_name, start_str, end_str, generated_at,
    s, section_header, gpu_metrics, charts_ok,
    pie_path, bar_path,
    acct_list, all_users, acct_chart_ok, user_chart_ok,
    acct_path, usr_path
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
        onPage=_header_footer(cluster_name, generated_at)
    )
    doc.addPageTemplates([template])
    story = []

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
    story.append(Paragraph("GPU Utilization Report", s['subtitle']))
    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width="70%", thickness=1.5, color=LIGHT_BLUE, spaceAfter=20))

    cover_rows = [
        ["Cluster",       cluster_name.upper()],
        ["Report Period", f"{start_str}  →  {end_str}"],
        ["Generated",     generated_at],
        ["Report Type",   "GPU (gres/gpu) Utilization Analysis"],
    ]
    ct = Table(cover_rows, colWidths=[5 * cm, 9 * cm])
    ct.setStyle(TableStyle([
        ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',   (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE',   (0, 0), (-1, -1), 11),
        ('TEXTCOLOR',  (0, 0), (0, -1), DARK_BLUE),
        ('TEXTCOLOR',  (1, 0), (1, -1), DARK_GREY),
        ('ROWPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW',  (0, 0), (-1, -2), 0.5, colors.HexColor("#f0f0f0")),
    ]))
    story.append(Table([[ct]], colWidths=[content_w]))
    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 2 — EXECUTIVE GPU SUMMARY + ANALYSIS
    # ----------------------------------------------------------------
    story += section_header("Executive GPU Summary")

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
        story.append(Spacer(1, 0.8 * cm))

        # Charts
        story += section_header("Visual Analysis")

        if charts_ok and os.path.exists(pie_path) and os.path.getsize(pie_path) > 0:
            pie_img = Image(pie_path, width=8.5 * cm, height=6.2 * cm)
            bar_img = Image(bar_path, width=9 * cm, height=6.2 * cm)
            chart_t = Table([[pie_img, bar_img]], colWidths=[9 * cm, 9.5 * cm])
            chart_t.setStyle(TableStyle([
                ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(chart_t)

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
    story += section_header("GPU Observations")
    story.append(Paragraph(
        f"Automatically generated observations for {cluster_name.upper()} "
        f"GPU utilization, period {start_str} to {end_str}.",
        s['body']
    ))
    story.append(Spacer(1, 0.4 * cm))

    if gpu_metrics:
        obs = _gpu_observations(gpu_metrics)
        for i, o in enumerate(obs, 1):
            story.append(Paragraph(f"<b>{i}.</b>  {o}", s['obs_item']))
    else:
        story.append(Paragraph(
            "No GPU observations available — data was unavailable for this period.",
            s['unavailable']
        ))

    # ----------------------------------------------------------------
    # NEW PAGE — GPU RESOURCE CONSUMPTION BY ACCOUNT
    # ----------------------------------------------------------------
    story.append(PageBreak())
    story += section_header("GPU Resource Consumption by Account")

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
        story.append(Spacer(1, 0.7 * cm))

        if acct_chart_ok and os.path.exists(acct_path) and os.path.getsize(acct_path) > 0:
            bar_h = min(7 * cm, max(4 * cm, len(top_accts) * 0.6 * cm))
            content_w = W - 1.8 * cm - 1.8 * cm
            story.append(Image(acct_path, width=content_w, height=bar_h))
    else:
        story.append(Paragraph(
            "No GPU account consumption data available for this period.",
            s['unavailable']
        ))

    # ----------------------------------------------------------------
    # NEW PAGE — TOP GPU USERS
    # ----------------------------------------------------------------
    story.append(PageBreak())
    story += section_header("Top GPU Users by Resource Consumption")

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
        story.append(Spacer(1, 0.7 * cm))

        if user_chart_ok and os.path.exists(usr_path) and os.path.getsize(usr_path) > 0:
            bar_h = min(7 * cm, max(4 * cm, len(display_users) * 0.55 * cm))
            content_w = W - 1.8 * cm - 1.8 * cm
            story.append(Image(usr_path, width=content_w, height=bar_h))
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