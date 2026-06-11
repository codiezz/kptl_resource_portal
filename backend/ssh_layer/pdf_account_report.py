"""
pdf_account_report.py

Generates an account-specific utilization PDF report.

Sections:
  1. Cover Page
  2. Account Summary Table
  3. Per-Account Utilization (table + horizontal bar chart)
  4. User Breakdown Table
  5. Observations

All data comes from parse_account_utilization() — zero hardcoded values.
Graceful degradation: missing data shows notice, never crashes.

Usage:
    from pdf_account_report import generate_account_report
    pdf_bytes = generate_account_report({
        "cluster":  "fortytwo",
        "period":   {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "accounts": {...},  # from parse_account_utilization(), or {}
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


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_account_report(data: dict) -> bytes:
    """
    Generate account utilization PDF report.

    Args:
        data = {
            "cluster":  "fortytwo",
            "period":   {"start": "...", "end": "..."},
            "accounts": dict from parse_account_utilization(), or {}
        }

    Returns: PDF as bytes.
    """
    cluster_name = data.get("cluster", "Unknown")
    period       = data.get("period", {})
    accounts     = data.get("accounts", {})

    start_str    = (period.get("start") or "")[:10] or "N/A"
    end_str      = (period.get("end")   or "")[:10] or "N/A"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    acct_list    = accounts.get("accounts", [])

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

    tmp_bar = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_acct_bar_')
    tmp_pie = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_acct_pie_')
    tmp_bar.close()
    tmp_pie.close()
    bar_ok = False
    pie_ok = False

    try:
        if acct_list:
            bar_ok = _make_accounts_hbar(acct_list, tmp_bar.name)
            pie_ok = _make_accounts_pie(acct_list, tmp_pie.name)

        pdf_bytes = _build_pdf(
            cluster_name, start_str, end_str, generated_at,
            s, section_hdr, accounts, acct_list,
            bar_ok, pie_ok, tmp_bar.name, tmp_pie.name
        )
    finally:
        for p in [tmp_bar.name, tmp_pie.name]:
            try:
                os.unlink(p)
            except OSError:
                pass

    return pdf_bytes


def _build_pdf(
    cluster_name, start_str, end_str, generated_at,
    s, section_hdr, accounts, acct_list,
    bar_ok, pie_ok, bar_path, pie_path
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

    total        = accounts.get('cluster_total', {})
    total_hours  = total.get('hours', 0) if total else 0
    n_accounts   = len(acct_list)
    total_users  = sum(len(a.get('users', [])) for a in acct_list)

    cover_rows = [
        ["Cluster",        cluster_name.upper()],
        ["Report Period",  f"{start_str}  →  {end_str}"],
        ["Generated",      generated_at],
        ["Total CPU Hours",f"{total_hours:,}" if total_hours else "N/A"],
        ["Active Accounts",str(n_accounts)],
        ["Active Users",   str(total_users)],
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
    # PAGE 2 — ACCOUNT SUMMARY TABLE + CHARTS
    # ----------------------------------------------------------------
    story += section_hdr("Account Utilization Summary")

    if acct_list:
        rows = [["Account", "CPU Hours", "Usage %", "Active Users"]]
        for a in acct_list[:15]:
            rows.append([
                a['account'],
                f"{a['hours']:,}"         if a['hours']      else "—",
                f"{a['percentage']:.2f}%" if a['percentage'] else "—",
                str(len(a.get('users', []))),
            ])
        t = Table(rows, colWidths=[6 * cm, 4 * cm, 3.5 * cm, 3.5 * cm])
        t.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0),  DARK_BLUE),
            ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
            ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, 0),  10),
            ('ALIGN',       (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN',       (0, 0), (0, -1),  'LEFT'),
            *[('BACKGROUND', (0, i), (-1, i), LIGHT_GREY)
              for i in range(1, len(rows), 2)],
            ('FONTSIZE',    (0, 1), (-1, -1), 9.5),
            ('TEXTCOLOR',   (0, 1), (-1, -1), DARK_GREY),
            ('ROWPADDING',  (0, 0), (-1, -1), 7),
            ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
            ('LINEBELOW',   (0, 0), (-1, 0),  1.5, DARK_BLUE),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.7 * cm))

        # Charts side by side
        charts = []
        if bar_ok and os.path.exists(bar_path) and os.path.getsize(bar_path) > 0:
            charts.append(Image(bar_path, width=9 * cm, height=6 * cm))
        if pie_ok and os.path.exists(pie_path) and os.path.getsize(pie_path) > 0:
            charts.append(Image(pie_path, width=8 * cm, height=6 * cm))

        if len(charts) == 2:
            ct2 = Table([charts], colWidths=[9.5 * cm, 8.5 * cm])
            ct2.setStyle(TableStyle([
                ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(ct2)
        elif len(charts) == 1:
            story.append(Table([charts], colWidths=[content_w]))

    else:
        notice = Table(
            [[Paragraph(
                "Account utilization data was unavailable for this reporting period.",
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
    # PAGE 3 — USER BREAKDOWN PER ACCOUNT
    # ----------------------------------------------------------------
    story += section_hdr("User Breakdown by Account")

    if acct_list:
        for acct in acct_list[:10]:
            users = acct.get('users', [])
            if not users:
                continue

            story.append(Paragraph(
                f"Account: <b>{acct['account']}</b>  "
                f"({acct['hours']:,} CPU hrs, {acct['percentage']:.2f}%)"
                if acct.get('hours') else f"Account: <b>{acct['account']}</b>",
                s['body']
            ))

            user_rows = [["Login", "Proper Name", "CPU Hours", "Usage %"]]
            for u in sorted(users, key=lambda x: x.get('hours') or 0, reverse=True):
                user_rows.append([
                    u.get('login', ''),
                    u.get('proper_name', '') or '—',
                    f"{u['hours']:,}"         if u.get('hours')      else "—",
                    f"{u['percentage']:.2f}%" if u.get('percentage') else "—",
                ])

            ut = Table(user_rows, colWidths=[4 * cm, 5 * cm, 4 * cm, 4 * cm])
            ut.setStyle(TableStyle([
                ('BACKGROUND',  (0, 0), (-1, 0),  MID_BLUE),
                ('TEXTCOLOR',   (0, 0), (-1, 0),  WHITE),
                ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
                ('FONTSIZE',    (0, 0), (-1, 0),  9),
                ('ALIGN',       (2, 0), (-1, -1), 'CENTER'),
                ('ALIGN',       (0, 0), (1, -1),  'LEFT'),
                *[('BACKGROUND', (0, i), (-1, i), LIGHT_GREY)
                  for i in range(1, len(user_rows), 2)],
                ('FONTSIZE',    (0, 1), (-1, -1), 9),
                ('TEXTCOLOR',   (0, 1), (-1, -1), DARK_GREY),
                ('ROWPADDING',  (0, 0), (-1, -1), 6),
                ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ea")),
                ('LINEBELOW',   (0, 0), (-1, 0),  1, MID_BLUE),
            ]))
            story.append(ut)
            story.append(Spacer(1, 0.5 * cm))
    else:
        story.append(Paragraph(
            "No user breakdown data available.", s['unavailable']
        ))

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 4 — OBSERVATIONS
    # ----------------------------------------------------------------
    story += section_hdr("Observations")
    story.append(Paragraph(
        f"Automatically generated observations for {cluster_name.upper()} "
        f"account utilization, period {start_str} to {end_str}.",
        s['body']
    ))
    story.append(Spacer(1, 0.4 * cm))

    for i, o in enumerate(_account_observations(accounts), 1):
        story.append(Paragraph(f"<b>{i}.</b>  {o}", s['obs_item']))

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