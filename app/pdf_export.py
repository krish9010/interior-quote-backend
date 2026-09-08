from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image,
)

# "Studio Drafting" palette — matches the web and mobile apps
INK = colors.HexColor("#22303F")
BRASS = colors.HexColor("#D9A54B")
BRASS_DARK = colors.HexColor("#B8863B")
PAPER = colors.HexColor("#F2EEE6")
PAPER2 = colors.HexColor("#FAF8F3")
MUTED = colors.HexColor("#8C8878")
LINE = colors.HexColor("#DDD6C8")


def _styles():
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle("brand", parent=base["Normal"], fontName="Helvetica-Bold",
                                 fontSize=20, textColor=INK, leading=24),
        "brandSub": ParagraphStyle("brandSub", parent=base["Normal"], fontName="Helvetica",
                                    fontSize=8, textColor=MUTED, leading=11, spaceBefore=2),
        "docTitle": ParagraphStyle("docTitle", parent=base["Normal"], fontName="Helvetica",
                                    fontSize=9, textColor=BRASS_DARK, leading=12,
                                    alignment=TA_RIGHT),
        "docMeta": ParagraphStyle("docMeta", parent=base["Normal"], fontName="Helvetica",
                                   fontSize=8, textColor=MUTED, leading=11, alignment=TA_RIGHT),
        "clientLabel": ParagraphStyle("clientLabel", parent=base["Normal"], fontName="Helvetica-Bold",
                                       fontSize=7, textColor=BRASS_DARK, leading=10),
        "clientValue": ParagraphStyle("clientValue", parent=base["Normal"], fontName="Helvetica",
                                       fontSize=10, textColor=INK, leading=13),
        "roomTitle": ParagraphStyle("roomTitle", parent=base["Normal"], fontName="Helvetica-Bold",
                                     fontSize=12, textColor=INK, leading=16),
        "roomMeta": ParagraphStyle("roomMeta", parent=base["Normal"], fontName="Helvetica",
                                    fontSize=8, textColor=MUTED, leading=11),
        "itemLabel": ParagraphStyle("itemLabel", parent=base["Normal"], fontName="Helvetica-Bold",
                                     fontSize=9, textColor=INK, leading=12),
        "itemDesc": ParagraphStyle("itemDesc", parent=base["Normal"], fontName="Helvetica-Oblique",
                                    fontSize=7, textColor=MUTED, leading=9.5, spaceBefore=1),
        "notes": ParagraphStyle("notes", parent=base["Normal"], fontName="Helvetica",
                                 fontSize=9, textColor=INK, leading=13),
        "notesLabel": ParagraphStyle("notesLabel", parent=base["Normal"], fontName="Helvetica-Bold",
                                      fontSize=7, textColor=BRASS_DARK, leading=10),
        "footer": ParagraphStyle("footer", parent=base["Normal"], fontName="Helvetica",
                                  fontSize=7.5, textColor=MUTED, leading=10),
    }


def _header(story, s, quotation_id: str, logo_bytes: bytes = None):
    logo_cell = ""
    if logo_bytes:
        try:
            import io
            img = Image(io.BytesIO(logo_bytes), width=22 * mm, height=22 * mm, kind="proportional")
            logo_cell = img
        except Exception:
            logo_cell = ""

    header_data = [[
        Paragraph("Interior Quote", s["brand"]),
        logo_cell,
        Paragraph(f"QUOTATION<br/>#{quotation_id[:8].upper()}", s["docTitle"]),
    ], [
        Paragraph("Design &amp; build cost estimate", s["brandSub"]),
        "",
        Paragraph(datetime.now().strftime("%d %b %Y"), s["docMeta"]),
    ]]
    t = Table(header_data, colWidths=[88 * mm, 24 * mm, 60 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 1), "CENTER"),
        ("SPAN", (1, 0), (1, 1)),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.4, color=INK, spaceAfter=14))


def _client_block(story, s, client: dict):
    rows = []
    pairs = [("CLIENT", client.get("name", "")), ("PHONE", client.get("phone")),
             ("EMAIL", client.get("email")), ("ADDRESS", client.get("address"))]
    for label, value in pairs:
        if not value:
            continue
        rows.append([Paragraph(label, s["clientLabel"]), Paragraph(str(value), s["clientValue"])])
    if not rows:
        return
    t = Table(rows, colWidths=[24 * mm, 148 * mm])
    t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))


def _room_section(story, s, room: dict):
    dims_text = (
        f"{room['length_ft']}' &times; {room['width_ft']}'  &middot;  {room['area_sqft']} sq.ft"
        if room.get("area_sqft", 0) > 0 else ""
    )
    title_row = Table(
        [[Paragraph(room["name"], s["roomTitle"]), Paragraph(dims_text, s["roomMeta"])]],
        colWidths=[110 * mm, 62 * mm],
    )
    title_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(title_row)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.6, color=BRASS, spaceAfter=6))

    table_data = [["ITEM", "QTY", "UNIT", "RATE", "AMOUNT"]]
    for item in room["items"]:
        if item.get("description"):
            item_cell = Paragraph(
                f"{item['label']}<br/><font size=7 color='#8C8878'>{item['description']}</font>",
                s["itemLabel"],
            )
        else:
            item_cell = Paragraph(item["label"], s["itemLabel"])
        table_data.append([
            item_cell, f"{item['quantity']:.2f}", item["unit"],
            f"Rs {item['rate']:.2f}", f"Rs {item['amount']:.2f}",
        ])

    t = Table(table_data, colWidths=[62 * mm, 20 * mm, 20 * mm, 30 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("TEXTCOLOR", (0, 0), (-1, 0), BRASS_DARK),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    total_row = Table(
        [["", "", "", "Module total", f"Rs {room['room_total']:.2f}"]],
        colWidths=[62 * mm, 20 * mm, 20 * mm, 30 * mm, 30 * mm],
    )
    total_row.setStyle(TableStyle([
        ("FONTNAME", (3, 0), (4, 0), "Helvetica-Bold"),
        ("FONTSIZE", (3, 0), (4, 0), 9.5),
        ("TEXTCOLOR", (3, 0), (4, 0), INK),
        ("ALIGN", (3, 0), (4, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("LINEABOVE", (3, 0), (4, 0), 0.8, INK),
    ]))
    story.append(total_row)
    story.append(Spacer(1, 14))


def _totals_block(story, quotation: dict):
    rows = [
        ["Subtotal", f"Rs {quotation['subtotal']:.2f}"],
        [f"Discount ({quotation['discount_percent']:.1f}%)", f"-Rs {quotation['discount_amount']:.2f}"],
        [f"Tax ({quotation['tax_percent']:.1f}%)", f"Rs {quotation['tax_amount']:.2f}"],
        ["GRAND TOTAL", f"Rs {quotation['grand_total']:.2f}"],
    ]
    t = Table(rows, colWidths=[130 * mm, 42 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("TEXTCOLOR", (0, 0), (-1, 2), colors.HexColor("#C7CEDA")),
        ("TEXTCOLOR", (0, 3), (-1, 3), colors.white),
        ("FONTNAME", (0, 0), (-1, 2), "Helvetica"),
        ("FONTNAME", (0, 3), (0, 3), "Helvetica-Bold"),
        ("FONTNAME", (1, 3), (1, 3), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 3), (1, 3), BRASS),
        ("FONTSIZE", (0, 0), (-1, 2), 9.5),
        ("FONTSIZE", (0, 3), (-1, 3), 13),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEABOVE", (0, 3), (-1, 3), 0.6, colors.HexColor("#3E4F61")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(t)


def build_quotation_pdf(quotation: dict, out_path: Path):
    s = _styles()
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    story = []

    logo_bytes = None
    client_email = (quotation.get("client") or {}).get("email")
    if client_email:
        from app import clients as clients_module
        logo_result = clients_module.get_client_logo_bytes(client_email)
        if logo_result:
            logo_bytes = logo_result[0]

    _header(story, s, quotation.get("id", "draft"), logo_bytes=logo_bytes)
    _client_block(story, s, quotation.get("client", {}))

    for room in quotation.get("rooms", []):
        _room_section(story, s, room)

    _totals_block(story, quotation)

    if quotation.get("notes"):
        story.append(Spacer(1, 16))
        story.append(Paragraph("NOTES", s["notesLabel"]))
        story.append(Paragraph(quotation["notes"], s["notes"]))

    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=0.4, color=LINE, spaceAfter=8))
    story.append(Paragraph(
        "This quotation is an estimate based on the modules and measurements provided. "
        "Final pricing may vary after site inspection.", s["footer"]))

    doc.build(story)
    return out_path
