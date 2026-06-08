"""
pdf_generator.py

Generates a professional academic-style PDF report for cluster utilization.
Uses reportlab for PDF, matplotlib for charts.
Temp chart images are created and cleaned up automatically.

Usage:
    from pdf_generator import generate_utilization_report
    pdf_bytes = generate_utilization_report(parsed_data)
    # return pdf_bytes as Flask response
"""

import io
import os
import tempfile
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak
)

# ---------------------------------------------------------------------------
# Colour palette — academic blue/grey
# ---------------------------------------------------------------------------
DARK_BLUE   = colors.HexColor("#1a3a5c")
MID_BLUE    = colors.HexColor("#2c5f8a")
LIGHT_BLUE  = colors.HexColor("#a8c8e8")
ACCENT_RED  = colors.HexColor("#c0392b")
LIGHT_GREY  = colors.HexColor("#f4f6f8")
MID_GREY    = colors.HexColor("#7f8c8d")
DARK_GREY   = colors.HexColor("#2c3e50")
WHITE       = colors.white
BLACK       = colors.black

CHART_COLORS = ["#2c5f8a", "#a8c8e8", "#c0392b", "#7f8c8d", "#bdc3c7"]


# ---------------------------------------------------------------------------
# Chart generators
# ---------------------------------------------------------------------------

def _make_pie_chart(metrics: dict, path: str):
    pie_data = {
        "Allocated": metrics["allocated"],
        "Idle":      metrics["idle"],
        "Down":      metrics["down"],
        "Planned":   metrics["planned"],
    }
    if metrics.get("planned_down", 0) > 0:
        pie_data["Planned Down"] = metrics["planned_down"]

    labels = list(pie_data.keys())
    sizes  = list(pie_data.values())
    clrs   = CHART_COLORS[:len(labels)]

    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=clrs,
        autopct='%1.1f%%', startangle=140,
        textprops={'fontsize': 9, 'color': '#2c3e50'},
        pctdistance=0.82,
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5}
    )
    for at in autotexts:
        at.set_fontsize(8)
        at.set_fontweight('bold')
    ax.set_title("Utilization Composition", fontsize=11,
                 fontweight='bold', color='#1a3a5c', pad=12)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()


def _make_bar_chart(metrics: dict, path: str):
    bar_labels = ["Allocated", "Idle", "Down", "Planned", "Planned\nDown"]
    bar_values = [
        metrics["allocated"], metrics["idle"], metrics["down"],
        metrics["planned"],   metrics.get("planned_down", 0)
    ]
    clrs = CHART_COLORS[:len(bar_labels)]

    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    bars = ax.bar(bar_labels, bar_values, color=clrs,
                  width=0.5, edgecolor='white', linewidth=1.2)

    for bar, val in zip(bars, bar_values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.6,
            f'{val:.1f}%',
            ha='center', va='bottom', fontsize=9,
            fontweight='bold', color='#2c3e50'
        )

    ax.set_ylabel("Percentage (%)", fontsize=9, color='#2c3e50')
    ax.set_title("Metrics Breakdown", fontsize=11,
                 fontweight='bold', color='#1a3a5c')
    ax.set_ylim(0, max(bar_values) * 1.25)
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
# Header / footer callbacks
# ---------------------------------------------------------------------------

def _make_header_footer(cluster_name: str, generated_at: str):
    def on_page(canvas, doc):
        canvas.saveState()
        w, h = A4

        # Header bar
        canvas.setFillColor(DARK_BLUE)
        canvas.rect(0, h - 1.2*cm, w, 1.2*cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(1.5*cm, h - 0.85*cm, "IISER Pune — HPC Portal")
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(w - 1.5*cm, h - 0.85*cm,
                               f"Cluster: {cluster_name.upper()}")

        # Footer bar
        canvas.setFillColor(LIGHT_GREY)
        canvas.rect(0, 0, w, 1.0*cm, fill=1, stroke=0)
        canvas.setFillColor(MID_GREY)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(1.5*cm, 0.35*cm,
                          "Generated automatically by IISER Pune HPC Portal")
        canvas.drawRightString(w - 1.5*cm, 0.35*cm,
                               f"Page {doc.page}   |   {generated_at}")

        canvas.restoreState()

    return on_page


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_utilization_report(data: dict) -> bytes:
    """
    Generate a PDF report from parsed cluster utilization data.

    Args:
        data: dict from parse_cluster_utilization(), e.g.:
            {
                "cluster": "fortytwo",
                "period": {"start": "2025-10-01T00:00:00", "end": "..."},
                "metrics": {"allocated": 29.22, "idle": 52.86, ...}
            }

    Returns:
        PDF as bytes — caller sends as Flask file response.
    """
    cluster_name = data.get("cluster", "Unknown")
    period       = data.get("period", {})
    metrics      = data.get("metrics", {})

    start_raw = period.get("start", "")
    end_raw   = period.get("end", "")
    start_str = start_raw[:10] if start_raw else "N/A"
    end_str   = end_raw[:10]   if end_raw   else "N/A"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Generate chart images to temp files
    tmp_pie = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp_bar = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp_pie.close()
    tmp_bar.close()

    try:
        _make_pie_chart(metrics, tmp_pie.name)
        _make_bar_chart(metrics, tmp_bar.name)
        pdf_bytes = _build_pdf(
            cluster_name, start_str, end_str, generated_at,
            metrics, tmp_pie.name, tmp_bar.name
        )
    finally:
        for p in [tmp_pie.name, tmp_bar.name]:
            try:
                os.unlink(p)
            except OSError:
                pass

    return pdf_bytes


def _build_pdf(cluster_name, start_str, end_str, generated_at,
               metrics, pie_path, bar_path) -> bytes:
    buf = io.BytesIO()
    w, h = A4

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CoverTitle',
        fontSize=24, fontName='Helvetica-Bold',
        textColor=DARK_BLUE, alignment=TA_CENTER,
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        fontSize=14, fontName='Helvetica',
        textColor=MID_BLUE, alignment=TA_CENTER,
        spaceAfter=4
    )
    section_header = ParagraphStyle(
        'SectionHeader',
        fontSize=13, fontName='Helvetica-Bold',
        textColor=DARK_BLUE, spaceBefore=14, spaceAfter=8
    )
    body_style = ParagraphStyle(
        'Body',
        fontSize=10, fontName='Helvetica',
        textColor=DARK_GREY, spaceAfter=4
    )
    meta_style = ParagraphStyle(
        'Meta',
        fontSize=10, fontName='Helvetica',
        textColor=MID_GREY, alignment=TA_CENTER,
        spaceAfter=3
    )

    # Doc with header/footer
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=2.2*cm,  bottomMargin=1.8*cm,
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        w - doc.leftMargin - doc.rightMargin,
        h - doc.topMargin - doc.bottomMargin,
        id='normal'
    )
    template = PageTemplate(
        id='main', frames=[frame],
        onPage=_make_header_footer(cluster_name, generated_at)
    )
    doc.addPageTemplates([template])

    story = []

    # ----------------------------------------------------------------
    # PAGE 1 — COVER
    # ----------------------------------------------------------------
    story.append(Spacer(1, 3.5*cm))

    # Logo placeholder box
    logo_table = Table(
        [[Paragraph("IISER PUNE", ParagraphStyle(
            'Logo', fontSize=18, fontName='Helvetica-Bold',
            textColor=WHITE, alignment=TA_CENTER
        ))]],
        colWidths=[6*cm], rowHeights=[2*cm]
    )
    logo_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), DARK_BLUE),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ROWPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(Table([[logo_table]], colWidths=[w - 3.6*cm]))
    story.append(Spacer(1, 1.2*cm))

    story.append(Paragraph("High Performance Computing Portal", title_style))
    story.append(Paragraph("Cluster Utilization Report", subtitle_style))
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="70%", thickness=1.5,
                            color=LIGHT_BLUE, spaceAfter=20))

    # Cover meta table
    meta_rows = [
        ["Cluster",     cluster_name.upper()],
        ["Report Period", f"{start_str}  →  {end_str}"],
        ["Generated",   generated_at],
    ]
    meta_table = Table(meta_rows, colWidths=[5*cm, 9*cm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME',    (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME',    (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE',    (0,0), (-1,-1), 11),
        ('TEXTCOLOR',   (0,0), (0,-1), DARK_BLUE),
        ('TEXTCOLOR',   (1,0), (1,-1), DARK_GREY),
        ('ALIGN',       (0,0), (-1,-1), 'LEFT'),
        ('ROWPADDING',  (0,0), (-1,-1), 6),
        ('LINEBELOW',   (0,0), (-1,-2), 0.5, LIGHT_GREY),
    ]))
    story.append(Table([[meta_table]], colWidths=[w - 3.6*cm]))

    story.append(PageBreak())

    # ----------------------------------------------------------------
    # PAGE 2 — EXECUTIVE SUMMARY + CHARTS
    # ----------------------------------------------------------------
    story.append(Paragraph("Executive Summary", section_header))
    story.append(HRFlowable(width="100%", thickness=1,
                            color=LIGHT_BLUE, spaceAfter=10))

    # Metrics table
    metric_rows = [
        ["Metric", "Value", "Description"],
        ["Allocated",    f"{metrics.get('allocated', 0):.2f}%",
         "Resources actively in use by jobs"],
        ["Idle",         f"{metrics.get('idle', 0):.2f}%",
         "Resources available but unused"],
        ["Down",         f"{metrics.get('down', 0):.2f}%",
         "Resources unavailable / maintenance"],
        ["Planned",      f"{metrics.get('planned', 0):.2f}%",
         "Resources reserved for planned use"],
        ["Planned Down", f"{metrics.get('planned_down', 0):.2f}%",
         "Resources planned for downtime"],
        ["Reported",     f"{metrics.get('reported', 0):.2f}%",
         "Total accounted utilization"],
    ]

    col_w = [4.5*cm, 3*cm, 9*cm]
    mt = Table(metric_rows, colWidths=col_w)
    mt.setStyle(TableStyle([
        # Header row
        ('BACKGROUND',  (0,0), (-1,0),  DARK_BLUE),
        ('TEXTCOLOR',   (0,0), (-1,0),  WHITE),
        ('FONTNAME',    (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0,0), (-1,0),  10),
        ('ALIGN',       (0,0), (-1,0),  'CENTER'),
        # Data rows alternating
        ('BACKGROUND',  (0,1), (-1,1),  LIGHT_GREY),
        ('BACKGROUND',  (0,3), (-1,3),  LIGHT_GREY),
        ('BACKGROUND',  (0,5), (-1,5),  LIGHT_GREY),
        ('FONTNAME',    (0,1), (0,-1),  'Helvetica-Bold'),
        ('FONTNAME',    (1,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE',    (0,1), (-1,-1), 9.5),
        ('TEXTCOLOR',   (0,1), (-1,-1), DARK_GREY),
        ('ALIGN',       (1,0), (1,-1),  'CENTER'),
        ('ALIGN',       (0,1), (0,-1),  'LEFT'),
        ('ROWPADDING',  (0,0), (-1,-1), 7),
        ('GRID',        (0,0), (-1,-1), 0.4, colors.HexColor("#dde3ea")),
        ('LINEBELOW',   (0,0), (-1,0),  1.5, DARK_BLUE),
    ]))
    story.append(mt)
    story.append(Spacer(1, 0.8*cm))

    # Charts side by side
    story.append(Paragraph("Visual Analysis", section_header))
    story.append(HRFlowable(width="100%", thickness=1,
                            color=LIGHT_BLUE, spaceAfter=10))

    pie_img = Image(pie_path, width=8.5*cm, height=6*cm)
    bar_img = Image(bar_path, width=9.5*cm, height=6*cm)

    chart_table = Table(
        [[pie_img, bar_img]],
        colWidths=[9*cm, 10*cm]
    )
    chart_table.setStyle(TableStyle([
        ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(chart_table)

    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Quick standalone test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    sample = {
        "cluster": "fortytwo",
        "period": {
            "start": "2025-10-01T00:00:00",
            "end":   "2025-12-30T23:59:59"
        },
        "metrics": {
            "allocated":    29.22,
            "down":          2.75,
            "planned_down":  0.0,
            "idle":         52.86,
            "planned":      15.18,
            "reported":    100.0
        }
    }
    pdf = generate_utilization_report(sample)
    out = "/tmp/test_report.pdf"
    with open(out, 'wb') as f:
        f.write(pdf)
    print(f"PDF generated: {len(pdf)} bytes → {out}")
