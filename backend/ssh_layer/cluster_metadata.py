"""
cluster_metadata.py

Single source of truth for static hardware specifications per cluster.
This data is intentionally hardcoded — it reflects physical hardware that
rarely changes and is not fetched from Slurm or stored in MySQL.

To update hardware specs: edit CLUSTER_METADATA below. All four PDF
generators will automatically reflect the change on next report generation.

To add a new cluster: add a new key to CLUSTER_METADATA matching the
cluster_id used in config.py (e.g. "fortytwo").
"""

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

# ---------------------------------------------------------------------------
# Color constants — must match the palette used across all PDF generators
# ---------------------------------------------------------------------------
_DARK_BLUE   = colors.HexColor("#1a3a5c")
_MID_BLUE    = colors.HexColor("#2c5f8a")
_WHITE       = colors.white
_DARK_GREY   = colors.HexColor("#2c3e50")
_MID_GREY    = colors.HexColor("#7f8c8d")
_LIGHT_GREY  = colors.HexColor("#f4f6f8")
_DIVIDER     = colors.HexColor("#e6ebf0")   # subtle row divider
_BORDER      = colors.HexColor("#dde3ea")   # outer border, matches particulars table
_GROUP_BG    = colors.HexColor("#e8edf4")   # group header row — muted blue-grey

# ---------------------------------------------------------------------------
# Static hardware data
# ---------------------------------------------------------------------------
CLUSTER_METADATA = {
    "fortytwo": {
        "display_name": "FortyTwo Cluster",
        "nodes": [
            {
                "type":  "Master Node",
                "count": None,
                "specs": [
                    ("CPU",    "2 X Intel Xeon Gold 6342 | 24 cores @ 2.8 GHz | 48 Threads | Dual Socket"),
                    ("Memory", "512 GB"),
                ],
            },
            {
                "type":  "Compute Node",
                "count": 20,
                "specs": [
                    ("CPU",    "2 X Intel Xeon Gold 6338 | 32 cores @ 2.0 GHz | 64 Threads | Dual Socket"),
                    ("Memory", "512 GB"),
                    ("GPU",    "2 X Nvidia A30 24GB RAM"),
                ],
            },
            {
                "type":  "GPU Node",
                "count": 2,
                "specs": [
                    ("CPU",    "2 X AMD EPYC 7742 | 64 cores @ 2.25 GHz | 128 Threads"),
                    ("Memory", "2 TB"),
                    ("GPU",    "8 X NVIDIA A100 80GB RAM"),
                ],
            },
        ],
    },
    # Add future clusters here:
    # "clustername": {
    #     "display_name": "...",
    #     "nodes": [
    #         {"type": "Master Node", "count": None, "specs": [("CPU", "..."), ...]},
    #         ...
    #     ],
    # },
}


def get_cluster_metadata(cluster_id: str) -> dict:
    """Return the metadata dict for a cluster_id, or {} if not found."""
    return CLUSTER_METADATA.get(cluster_id.strip().lower(), {})


def build_node_description_section(cluster_id: str, content_w: float) -> list:
  
    meta = get_cluster_metadata(cluster_id)
    if not meta or not meta.get("nodes"):
        return []

    nodes = meta["nodes"]
    group_header_style = ParagraphStyle(
        'GroupHeader',
        fontSize=10, fontName='Helvetica-Bold',
        textColor=_DARK_BLUE, leading=11,
    )
    spec_key_style = ParagraphStyle(
        'SpecKey',
        fontSize=10, fontName='Helvetica-Bold',
        textColor=_DARK_GREY, leading=11,
    )
    spec_val_style = ParagraphStyle(
        'SpecVal',
        fontSize=10, fontName='Helvetica',
        textColor=_DARK_GREY, leading=11,
    )

    key_w = 4.25 * cm
    val_w = content_w - key_w
    rows         = []
    group_rows   = []
    last_spec_in_group = []

    for node in nodes:
        node_type = node.get("type", "")
        count     = node.get("count")
        specs     = node.get("specs", [])
        if count is not None:
            plural = node_type + "s" if not node_type.endswith("s") else node_type
            label  = f"{plural}  ({count})"
        else:
            label = node_type
        group_rows.append(len(rows))
        rows.append([Paragraph(label, group_header_style), ""])
        for key, value in specs:
            rows.append([
                Paragraph(key,   spec_key_style),
                Paragraph(value, spec_val_style),
            ])

        last_spec_in_group.append(len(rows) - 1)
    table = Table(rows, colWidths=[key_w, val_w])

    style_cmds = [
        ('BOX',           (0, 0),  (-1, -1), 0.6,  _BORDER),
        ('VALIGN',        (0, 0),  (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0),  (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0),  (-1, -1), 10),
    ]
    for r in group_rows:
        style_cmds += [
            ('SPAN',          (0, r),  (-1, r)),
            ('BACKGROUND',    (0, r),  (-1, r),  _GROUP_BG),
            ('TOPPADDING',    (0, r),  (-1, r),  3),
            ('BOTTOMPADDING', (0, r),  (-1, r),  3),
        ]

    for r in group_rows:
        if r > 0:
            style_cmds.append(
                ('LINEABOVE', (0, r), (-1, r), 0.8, _BORDER)
            )
    for r in range(len(rows)):
        if r not in group_rows:
            style_cmds.append(
                ('LINEBELOW', (0, r), (-1, r), 0.25, _DIVIDER)
            )

    table.setStyle(TableStyle(style_cmds))

    return [
        _section_header_bar(content_w),
        table,
        Spacer(1, 0.1 * cm),
    ]


def _section_header_bar(content_w: float) -> Table:
    """Dark blue 'NODE DESCRIPTION' header bar — identical style to REPORT PARTICULARS."""
    t = Table([["NODE DESCRIPTION"]], colWidths=[content_w])
    t.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, -1), _DARK_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, -1), _WHITE),
        ('FONTNAME',    (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, -1), 10),
        ('ALIGN',       (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('ROWPADDING',  (0, 0), (-1, -1), 7),
    ]))
    return t