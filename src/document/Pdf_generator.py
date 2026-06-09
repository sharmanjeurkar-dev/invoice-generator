import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_invoice_pdf(invoice_data, output_filename="invoice_output.pdf"):

    pdf = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    elements = []

    inv_number = invoice_data.get("invoice_number") or "AUTO-1042"
    inv_date = invoice_data.get("invoice_date") or date.today()

    header_data = [
        [
            Paragraph("<b>TAX INVOICE</b>", styles["Heading1"]),
            Paragraph(
                f"<b>Invoice #:</b> {inv_number}<br/><b>Date:</b> {inv_date}",
                styles["Normal"],
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=[300, 200])
    header_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    client = invoice_data.get("client", {})
    address = client.get("address", {})

    address_lines = [f"<b>{client.get('name', 'Client Name')}</b>"]
    for key in ["line1", "line2", "line3"]:
        if address.get(key):
            address_lines.append(address.get(key))

    client_info = "<br/>".join(address_lines)

    elements.append(Paragraph("<b>Billed To:</b>", styles["Normal"]))
    elements.append(Paragraph(client_info, styles["Normal"]))
    elements.append(Spacer(1, 30))

    table_data = [["Service Category", "Details", "Qty", "Amount (₹)"]]  # Header Row

    for service in invoice_data.get("services", []):
        table_data.append(
            [
                service.get("category", ""),
                Paragraph(service.get("details", ""), styles["Normal"]),
                str(service.get("qty", 1)),
                f"{service.get('amount', 0):,.2f}",
            ]
        )

    table_data.append(["", "", "Subtotal:", f"{invoice_data.get('subtotal', 0):,.2f}"])
    table_data.append(
        [
            "",
            "",
            f"GST ({(invoice_data.get('gst', 0) * 100):.0f}%):",
            f"{(invoice_data.get('subtotal', 0) * invoice_data.get('gst', 0)):,.2f}",
        ]
    )
    table_data.append(["", "", "TOTAL:", f"{invoice_data.get('total', 0):,.2f}"])

    service_table = Table(table_data, colWidths=[130, 220, 50, 100])
    service_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("GRID", (0, 0), (-1, -4), 1, colors.lightgrey),
                ("LINEABOVE", (2, -3), (-1, -1), 1, colors.black),
                ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )
    elements.append(service_table)

    pdf.build(elements)
    print(f"📄 PDF successfully generated: {os.path.abspath(output_filename)}")
