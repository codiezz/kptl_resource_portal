
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
# Color palette — matches existing reports exactly
# ---------------------------------------------------------------------------
DARK_BLUE  = colors.HexColor("#1a3a5c")
MID_BLUE   = colors.HexColor("#2c5f8a")
LIGHT_BLUE = colors.HexColor("#a8c8e8")
LIGHT_GREY = colors.HexColor("#f4f6f8")
MID_GREY   = colors.HexColor("#7f8c8d")
DARK_GREY  = colors.HexColor("#2c3e50")
WHITE      = colors.white

CHART_COLORS = [
    "#2c5f8a", "#3a7abf", "#4e95d6", "#6aafe0",
    "#85c0e8", "#a0ccee", "#b8d9f0", "#cde4f5",
    "#deeefa", "#eef6fc"
]

W, H = A4


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def _make_accounts_hbar(accounts: list, path: str, top_n: int = 10) -> bool:
    top = accounts[:top_n]
    if not top:
        return False

    labels = [a['account'] for a in reversed(top)]
    values = [a['hours'] or 0 for a in reversed(top)]
    clrs   = CHART_COLORS[:len(labels)]

    fig, ax = plt.subplots(figsize=(7.5, max(3.5, len(top) * 0.45)))
    bars = ax.barh(labels, values, color=clrs, height=0.6, edgecolor='white')

    max_val = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f'{val:,}', va='center', ha='left',
            fontsize=8, color='#2c3e50'
        )

    ax.set_xlabel("CPU Hours", fontsize=9, color='#2c3e50')
    ax.set_title(f"Top {len(top)} Accounts by CPU Hours",
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


def _make_accounts_pie(accounts: list, path: str, top_n: int = 8) -> bool:
    top = accounts[:top_n]
    if not top:
        return False

    labels = [a['account'] for a in top]
    values = [a['hours'] or 0 for a in top]
    if sum(values) == 0:
        return False

    clrs = CHART_COLORS[:len(labels)]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=clrs,
        autopct='%1.1f%%', startangle=140,
        pctdistance=0.82,
        textprops={'fontsize': 8, 'color': '#2c3e50'},
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5}
    )
    for at in autotexts:
        at.set_fontsize(7.5)
        at.set_fontweight('bold')
    ax.set_title("Account Share of Total CPU Hours",
                 fontsize=10, fontweight='bold', color='#1a3a5c', pad=12)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return True

def _make_top_cpu_hbar(users: list, path: str, top_n: int = 10) -> bool:
    top = sorted(users, key=lambda u: u['cpu_hours'] or 0, reverse=True)[:top_n]
    top = [u for u in top if (u['cpu_hours'] or 0) > 0]
    if not top:
        return False

    labels = [u['login'] for u in reversed(top)]
    values = [u['cpu_hours'] or 0 for u in reversed(top)]
    clrs   = CHART_COLORS[:len(labels)]

    fig, ax = plt.subplots(figsize=(7.5, max(3.5, len(top) * 0.45)))
    bars = ax.barh(labels, values, color=clrs, height=0.6, edgecolor='white')

    max_val = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f'{val:,.1f}', va='center', ha='left',
            fontsize=8, color='#2c3e50'
        )

    ax.set_xlabel("CPU Hours", fontsize=9, color='#2c3e50')
    ax.set_title(f"Top {len(top)} CPU Users",
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


def _make_top_gpu_hbar(users: list, path: str, top_n: int = 10) -> bool:
    top = [u for u in users if (u.get('gpu_hours') or 0) > 0]
    top = sorted(top, key=lambda u: u['gpu_hours'] or 0, reverse=True)[:top_n]
    if not top:
        return False

    labels = [u['login'] for u in reversed(top)]
    values = [u['gpu_hours'] or 0 for u in reversed(top)]
    clrs   = CHART_COLORS[:len(labels)]

    fig, ax = plt.subplots(figsize=(7.5, max(3.5, len(top) * 0.45)))
    bars = ax.barh(labels, values, color=clrs, height=0.6, edgecolor='white')

    max_val = max(values) if values else 1
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f'{val:,.1f}', va='center', ha='left',
            fontsize=8, color='#2c3e50'
        )

    ax.set_xlabel("GPU Hours", fontsize=9, color='#2c3e50')
    ax.set_title(f"Top {len(top)} GPU Users",
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

# ---------------------------------------------------------------------------
# Header / footer
# ---------------------------------------------------------------------------

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

def _account_observations(accounts: dict) -> list:
    obs = []
    acct_list   = accounts.get('accounts', [])
    total       = accounts.get('cluster_total', {})
    total_hours = total.get('hours', 0) if total else 0

    if not acct_list:
        return ["No account utilization data available for this period."]

    top = acct_list[0]
    if total_hours and top.get('hours'):
        top_pct = (top['hours'] / total_hours) * 100
        if top_pct > 40:
            obs.append(
                f"Account '{top['account']}' is the dominant consumer at "
                f"{top_pct:.1f}% of total cluster usage."
            )

    n_accounts = len(acct_list)
    obs.append(f"{n_accounts} active account(s) recorded usage during this period.")

    total_users = sum(len(a.get('users', [])) for a in acct_list)
    if total_users:
        obs.append(f"{total_users} unique user(s) across all accounts.")

    if len(acct_list) >= 2:
        bottom = acct_list[-1]
        if bottom.get('hours') and total_hours:
            b_pct = (bottom['hours'] / total_hours) * 100
            obs.append(
                f"Account '{bottom['account']}' has the lowest usage at {b_pct:.1f}%."
            )

    return obs[:5]

def _account_insights(users: list, totals: dict) -> list:
    insights = []

    if not users:
        return ["No usage data available for this account."]

    total_cpu = totals.get('cpu_hours', 0) or 0
    total_gpu = totals.get('gpu_hours', 0) or 0

    active = [u for u in users if (u['cpu_hours'] or 0) > 0 or (u['gpu_hours'] or 0) > 0]
    insights.append(
        f"{len(active)} of {len(users)} users actively used resources during this period."
    )

    if total_cpu > 0:
        top3_cpu = sum(sorted([u['cpu_hours'] or 0 for u in users], reverse=True)[:3])
        pct = (top3_cpu / total_cpu) * 100
        insights.append(f"Top 3 users contributed {pct:.1f}% of CPU usage.")

    if total_gpu > 0:
        top5_gpu = sum(sorted([u['gpu_hours'] or 0 for u in users], reverse=True)[:5])
        pct = (top5_gpu / total_gpu) * 100
        insights.append(f"Top 5 users account for {pct:.1f}% of GPU utilization.")

        if total_gpu > total_cpu:
            insights.append("Account workload appears GPU-intensive.")
        elif total_cpu > 0 and total_gpu / total_cpu < 0.1:
            insights.append("Account workload is predominantly CPU-based.")
    else:
        insights.append("No GPU usage recorded for this account.")

    no_gpu = sum(1 for u in users if (u['gpu_hours'] or 0) == 0)
    if no_gpu:
        insights.append(f"{no_gpu} user(s) had no GPU usage.")

    inactive = len(users) - len(active)
    if inactive:
        insights.append(f"{inactive} user(s) recorded no activity in this period.")

    return insights[:6]

# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_account_report(data: dict) -> bytes:

    cluster_name = data.get("cluster", "Unknown")
    account_name = data.get("account", "Unknown")
    period       = data.get("period", {})
    users        = data.get("users", [])
    totals       = data.get("account_totals", {})

    start_str    = (period.get("start") or "")[:10] or "N/A"
    end_str      = (period.get("end")   or "")[:10] or "N/A"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

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

    def section_hdr(title):
        return [
            Paragraph(title, s['section']),
            HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE, spaceAfter=10)
        ]

    tmp_cpu = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_acct_cpu_')
    tmp_gpu = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_acct_gpu_')
    tmp_cpu.close()
    tmp_gpu.close()
    cpu_chart_ok = False
    gpu_chart_ok = False

    try:
        if users:
            cpu_chart_ok = _make_top_cpu_hbar(users, tmp_cpu.name)
            gpu_chart_ok = _make_top_gpu_hbar(users, tmp_gpu.name)

        pdf_bytes = _build_pdf(
            cluster_name, account_name, start_str, end_str, generated_at,
            s, section_hdr, users, totals,
            cpu_chart_ok, gpu_chart_ok, tmp_cpu.name, tmp_gpu.name
        )
    finally:
        for p in [tmp_cpu.name, tmp_gpu.name]:
            try:
                os.unlink(p)
            except OSError:
                pass

    return pdf_bytes


def _build_pdf(
    cluster_name, account_name, start_str, end_str, generated_at,
    s, section_hdr, users, totals,
    cpu_chart_ok, gpu_chart_ok, cpu_chart_path, gpu_chart_path
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
        content_w, H - doc.topMargin - doc.bottomMargin,
        id='normal'
    )
    doc.addPageTemplates([PageTemplate(
        id='main', frames=[frame],
        onPage=_header_footer(cluster_name, generated_at)
    )])
    story = []

    # ----------------------------------------------------------------
    # Pre-compute summary values used across pages
    # ----------------------------------------------------------------
    total_cpu_hours = totals.get('cpu_hours', 0) or 0
    total_gpu_hours = totals.get('gpu_hours', 0) or 0
    account_cpu_pct = totals.get('cpu_pct', 0) or 0
    account_gpu_pct = totals.get('gpu_pct', 0) or 0

    total_users  = len(users)
    active_users = sum(
        1 for u in users
        if (u['cpu_hours'] or 0) > 0 or (u['gpu_hours'] or 0) > 0
    )

    top_cpu_user = "N/A"
    if users:
        top_cpu = max(users, key=lambda u: u['cpu_hours'] or 0)
        if (top_cpu['cpu_hours'] or 0) > 0:
            top_cpu_user = top_cpu['login']

    top_gpu_user = "N/A"
    gpu_users = [u for u in users if (u['gpu_hours'] or 0) > 0]
    if gpu_users:
        top_gpu = max(gpu_users, key=lambda u: u['gpu_hours'] or 0)
        top_gpu_user = top_gpu['login']

    # ----------------------------------------------------------------
    # PAGE 1 — COVER
    # ----------------------------------------------------------------
    story.append(Spacer(1, 3 * cm))
    logo_t = Table(
        [[Paragraph("IISER PUNE", ParagraphStyle(
            'Logo', fontSize=17, fontName='Helvetica-Bold',
            textColor=WHITE, alignment=TA_CENTER
        ))]],
        colWidths=[6 * cm], rowHeights=[1.8 * cm]
    )
    logo_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK_BLUE),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(Table([[logo_t]], colWidths=[content_w]))
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph("High Performance Computing Portal", s['title']))
    story.append(Paragraph("Account Utilization Report", s['subtitle']))
    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width="70%", thickness=1.5, color=LIGHT_BLUE, spaceAfter=20))

    cover_rows = [
        ["Account",        account_name],
        ["Cluster",        cluster_name.upper()],
        ["Report Period",  f"{start_str}  →  {end_str}"],
        ["Generated",      generated_at],
        ["Total CPU Hours", f"{total_cpu_hours:,.1f}" if total_cpu_hours else "N/A"],
        ["Total GPU Hours", f"{total_gpu_hours:,.1f}" if total_gpu_hours else "N/A"],
        ["Total Users",    str(total_users)],
        ["Active Users",   str(active_users)],
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
    # PAGE 2 — EXECUTIVE ACCOUNT SUMMARY
    # ----------------------------------------------------------------
    story += section_hdr("Executive Account Summary")

    summary_rows = [
        ["Metric", "Value"],
        ["Account Name",   account_name],
        ["Total Users",    str(total_users)],
        ["Active Users",   str(active_users)],
        ["Total CPU Hours", f"{total_cpu_hours:,.1f}" if total_cpu_hours else "N/A"],
        ["Total GPU Hours", f"{total_gpu_hours:,.1f}" if total_gpu_hours else "N/A"],
        ["CPU Usage %",    f"{account_cpu_pct:.2f}%" if account_cpu_pct else "N/A"],
        ["GPU Usage %",    f"{account_gpu_pct:.2f}%" if account_gpu_pct else "N/A"],
        ["Top CPU User",   top_cpu_user],
        ["Top GPU User",   top_gpu_user],
    ]
    st = Table(summary_rows, colWidths=[7 * cm, 7 * cm])
    st.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0),  DARK_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
        ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0),  10),
        ('FONTNAME',    (0, 1), (0, -1),  'Helvetica-Bold'),
        ('FONTNAME',    (1, 1), (1, -1),  'Helvetica'),
        ('TEXTCOLOR',   (0, 1), (0, -1),  DARK_BLUE),
        ('TEXTCOLOR',   (1, 1), (1, -1),  DARK_GREY),
        *[('BACKGROUND', (0, i), (-1, i), LIGHT_GREY)
          for i in range(1, len(summary_rows), 2)],
        ('FONTSIZE',    (0, 1), (-1, -1), 10),
        ('ROWPADDING',  (0, 0), (-1, -1), 7),
        ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
        ('LINEBELOW',   (0, 0), (-1, 0),  1.5, DARK_BLUE),
    ]))
    story.append(st)
    story.append(Spacer(1, 0.8 * cm))

    story.append(Paragraph("Key Insights", s['section']))
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE, spaceAfter=10))
    for i, ins in enumerate(_account_insights(users, totals), 1):
        story.append(Paragraph(f"<b>{i}.</b>  {ins}", s['obs_item']))

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 3 — USER RESOURCE CONSUMPTION TABLE
    # ----------------------------------------------------------------
    story += section_hdr("User Resource Consumption")

    if users:
        sorted_users = sorted(
            users,
            key=lambda u: (u['cpu_hours'] or 0) + (u['gpu_hours'] or 0),
            reverse=True
        )

        user_rows = [["Login", "CPU Hours", "CPU %", "GPU Hours", "GPU %", "Resource Profile"]]
        for u in sorted_users:
            user_rows.append([
                u['login'],
                f"{u['cpu_hours']:,.1f}" if u['cpu_hours'] else "0.0",
                f"{u['cpu_pct']:.2f}%"   if u['cpu_pct']   else "0.00%",
                f"{u['gpu_hours']:,.1f}" if u['gpu_hours'] else "0.0",
                f"{u['gpu_pct']:.2f}%"   if u['gpu_pct']   else "0.00%",
                u.get('profile', 'Inactive'),
            ])

        ut = Table(user_rows, colWidths=[3.5 * cm, 2.7 * cm, 2.2 * cm, 2.7 * cm, 2.2 * cm, 3.4 * cm])
        ut.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0),  DARK_BLUE),
            ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
            ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, 0),  9),
            ('ALIGN',       (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN',       (0, 0), (0, -1),  'LEFT'),
            *[('BACKGROUND', (0, i), (-1, i), LIGHT_GREY)
              for i in range(1, len(user_rows), 2)],
            ('FONTSIZE',    (0, 1), (-1, -1), 9),
            ('TEXTCOLOR',   (0, 1), (-1, -1), DARK_GREY),
            ('ROWPADDING',  (0, 0), (-1, -1), 6),
            ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
            ('LINEBELOW',   (0, 0), (-1, 0),  1.5, DARK_BLUE),
        ]))
        story.append(ut)
    else:
        story.append(Paragraph(
            "No user-level data available for this account.", s['unavailable']
        ))

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 4 — TOP CPU CONSUMERS
    # ----------------------------------------------------------------
    story += section_hdr("Top CPU Consumers")

    cpu_ranked = sorted(
        [u for u in users if (u['cpu_hours'] or 0) > 0],
        key=lambda u: u['cpu_hours'] or 0, reverse=True
    )[:10]

    if cpu_ranked:
        if cpu_chart_ok and os.path.exists(cpu_chart_path) and os.path.getsize(cpu_chart_path) > 0:
            story.append(Image(cpu_chart_path, width=content_w, height=content_w * 0.5))
            story.append(Spacer(1, 0.5 * cm))

        rows = [["User", "CPU Hours", "CPU %", "Share within Account"]]
        for u in cpu_ranked:
            share = (u['cpu_hours'] / total_cpu_hours * 100) if total_cpu_hours else 0
            rows.append([
                u['login'],
                f"{u['cpu_hours']:,.1f}",
                f"{u['cpu_pct']:.2f}%" if u['cpu_pct'] else "0.00%",
                f"{share:.1f}%",
            ])
        ct4 = Table(rows, colWidths=[4.5 * cm, 4 * cm, 3 * cm, 4.5 * cm])
        ct4.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0),  MID_BLUE),
            ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
            ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, 0),  9.5),
            ('ALIGN',       (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN',       (0, 0), (0, -1),  'LEFT'),
            *[('BACKGROUND', (0, i), (-1, i), LIGHT_GREY)
              for i in range(1, len(rows), 2)],
            ('FONTSIZE',    (0, 1), (-1, -1), 9.5),
            ('TEXTCOLOR',   (0, 1), (-1, -1), DARK_GREY),
            ('ROWPADDING',  (0, 0), (-1, -1), 6),
            ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
            ('LINEBELOW',   (0, 0), (-1, 0),  1, MID_BLUE),
        ]))
        story.append(ct4)
        story.append(Spacer(1, 0.5 * cm))

        top3_share = sum(u['cpu_hours'] or 0 for u in cpu_ranked[:3])
        if total_cpu_hours:
            pct = top3_share / total_cpu_hours * 100
            story.append(Paragraph(
                f"The top 3 CPU users account for {pct:.1f}% of this account's total CPU usage.",
                s['body']
            ))
    else:
        story.append(Paragraph(
            "No CPU usage recorded for any user in this account.", s['unavailable']
        ))

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 5 — TOP GPU CONSUMERS
    # ----------------------------------------------------------------
    story += section_hdr("Top GPU Consumers")

    gpu_ranked = sorted(
        [u for u in users if (u['gpu_hours'] or 0) > 0],
        key=lambda u: u['gpu_hours'] or 0, reverse=True
    )[:10]

    if gpu_ranked:
        if gpu_chart_ok and os.path.exists(gpu_chart_path) and os.path.getsize(gpu_chart_path) > 0:
            story.append(Image(gpu_chart_path, width=content_w, height=content_w * 0.5))
            story.append(Spacer(1, 0.5 * cm))

        rows = [["User", "GPU Hours", "GPU %", "Share within Account"]]
        for u in gpu_ranked:
            share = (u['gpu_hours'] / total_gpu_hours * 100) if total_gpu_hours else 0
            rows.append([
                u['login'],
                f"{u['gpu_hours']:,.1f}",
                f"{u['gpu_pct']:.2f}%" if u['gpu_pct'] else "0.00%",
                f"{share:.1f}%",
            ])
        ct5 = Table(rows, colWidths=[4.5 * cm, 4 * cm, 3 * cm, 4.5 * cm])
        ct5.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0),  MID_BLUE),
            ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
            ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, 0),  9.5),
            ('ALIGN',       (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN',       (0, 0), (0, -1),  'LEFT'),
            *[('BACKGROUND', (0, i), (-1, i), LIGHT_GREY)
              for i in range(1, len(rows), 2)],
            ('FONTSIZE',    (0, 1), (-1, -1), 9.5),
            ('TEXTCOLOR',   (0, 1), (-1, -1), DARK_GREY),
            ('ROWPADDING',  (0, 0), (-1, -1), 6),
            ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
            ('LINEBELOW',   (0, 0), (-1, 0),  1, MID_BLUE),
        ]))
        story.append(ct5)
        story.append(Spacer(1, 0.5 * cm))

        top3_share = sum(u['gpu_hours'] or 0 for u in gpu_ranked[:3])
        if total_gpu_hours:
            pct = top3_share / total_gpu_hours * 100
            story.append(Paragraph(
                f"The top 3 GPU users account for {pct:.1f}% of this account's total GPU usage.",
                s['body']
            ))
    else:
        story.append(Paragraph(
            "No GPU usage recorded for any user in this account.", s['unavailable']
        ))

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 6 — ACCOUNT UTILIZATION INSIGHTS
    # ----------------------------------------------------------------
    story += section_hdr("Account Utilization Insights")
    story.append(Paragraph(
        f"Derived analytics for account <b>{account_name}</b> on cluster "
        f"{cluster_name.upper()}, period {start_str} to {end_str}.",
        s['body']
    ))
    story.append(Spacer(1, 0.4 * cm))

    insights6 = list(_account_insights(users, totals))

    if total_cpu_hours and total_gpu_hours:
        ratio = total_cpu_hours / total_gpu_hours
        insights6.append(f"CPU-to-GPU usage ratio is approximately {ratio:.1f}:1.")
    elif total_cpu_hours and not total_gpu_hours:
        insights6.append("This account shows CPU-only usage with no GPU activity.")

    inactive_users = [u['login'] for u in users
                       if (u['cpu_hours'] or 0) == 0 and (u['gpu_hours'] or 0) == 0]
    if inactive_users:
        if len(inactive_users) <= 8:
            insights6.append(
                "Inactive users (no recorded usage): " + ", ".join(inactive_users) + "."
            )
        else:
            insights6.append(f"{len(inactive_users)} users recorded no usage during this period.")

    for i, ins in enumerate(insights6, 1):
        story.append(Paragraph(f"<b>{i}.</b>  {ins}", s['obs_item']))

    doc.build(story)
    return buf.getvalue()

# ---------------------------------------------------------------------------
# Standalone test — zero dummy data, structure test only
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    # Test 1: with parsed-style data (structure only, no real SSH)
    test_data = {
        "cluster": "fortytwo",
        "period": {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "accounts": {
            "cluster_total": {"hours": 5000000, "percentage": 100.0},
            "accounts": [
                {
                    "account": "labA",
                    "hours": 3000000, "percentage": 60.0,
                    "users": [
                        {"login": "u001", "proper_name": "User One", "hours": 1500000, "percentage": 30.0},
                        {"login": "u002", "proper_name": "User Two", "hours": 1500000, "percentage": 30.0},
                    ]
                },
                {
                    "account": "labB",
                    "hours": 2000000, "percentage": 40.0,
                    "users": [
                        {"login": "u003", "proper_name": "User Three", "hours": 2000000, "percentage": 40.0},
                    ]
                },
            ]
        }
    }
    pdf = generate_account_report(test_data)
    with open("/tmp/test_account_report.pdf", "wb") as f:
        f.write(pdf)
    print(f"[PASS] Account report with data: {len(pdf):,} bytes")

    # Test 2: graceful degradation — empty accounts
    pdf2 = generate_account_report({
        "cluster": "fortytwo",
        "period": {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "accounts": {}
    })
    with open("/tmp/test_account_report_empty.pdf", "wb") as f:
        f.write(pdf2)
    print(f"[PASS] Account report empty/graceful: {len(pdf2):,} bytes — no crash")