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
            "cluster":  "fortytwo",
            "period":   {"start": "...", "end": "..."},
            "gpu":      dict from parse_tres_utilization, or {}
        }

    Returns:
        PDF as bytes.
    """
    cluster_name = data.get("cluster", "Unknown")
    period       = data.get("period", {})
    gpu          = data.get("gpu", {})
    gpu_metrics  = gpu.get("metrics", {})

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

    # Generate charts if data available
    tmp_pie = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_gpu_pie_')
    tmp_bar = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='hpc_gpu_bar_')
    tmp_pie.close()
    tmp_bar.close()
    charts_ok = False

    try:
        if gpu_metrics:
            _make_gpu_pie(gpu_metrics, tmp_pie.name)
            _make_gpu_bar(gpu_metrics, tmp_bar.name)
            charts_ok = True

        pdf_bytes = _build_pdf(
            cluster_name, start_str, end_str, generated_at,
            s, section_header, gpu_metrics, charts_ok,
            tmp_pie.name, tmp_bar.name
        )

    finally:
        for p in [tmp_pie.name, tmp_bar.name]:
            try:
                os.unlink(p)
            except OSError:
                pass

    return pdf_bytes


def _build_pdf(
    cluster_name, start_str, end_str, generated_at,
    s, section_header, gpu_metrics, charts_ok,
    pie_path, bar_path
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

    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    # Test with GPU data
    pdf = generate_gpu_report({
        "cluster": "fortytwo",
        "period": {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "gpu": {
            "tres_name": "gres/gpu",
            "metrics": {
                "allocated": 49.74, "down": 2.44, "planned_down": 0.0,
                "idle": 47.82, "planned": 0.0, "reported": 100.65
            }
        }
    })
    with open("/tmp/test_gpu_report.pdf", "wb") as f:
        f.write(pdf)
    print(f"[PASS] GPU report: {len(pdf):,} bytes → /tmp/test_gpu_report.pdf")

    # Test graceful degradation — no GPU data
    pdf2 = generate_gpu_report({
        "cluster": "fortytwo",
        "period": {"start": "2025-10-01T00:00:00", "end": "2025-12-31T23:59:59"},
        "gpu": {}
    })
    with open("/tmp/test_gpu_report_unavailable.pdf", "wb") as f:
        f.write(pdf2)
    print(f"[PASS] GPU unavailable report: {len(pdf2):,} bytes — no crash")