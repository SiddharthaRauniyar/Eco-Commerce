"""Small, printable PDF invoices generated from immutable order snapshots."""

from io import BytesIO

from django.db import transaction
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from apps.orders.models import Order


def ensure_invoice_number(order: Order) -> Order:
    """Assign a stable invoice number on first download without a sequence table."""

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if not order.invoice_number:
            order.invoice_number = f"INV-{order.placed_at:%Y%m%d}-{order.pk:06d}"
            order.save(update_fields=("invoice_number", "updated_at"))
    return order


def _text(value) -> str:
    return str(value or "").encode("latin-1", "replace").decode("latin-1")


def _truncate(value, width: float, font: str = "Helvetica", size: int = 9) -> str:
    value = _text(value)
    while value and stringWidth(value + "...", font, size) > width:
        value = value[:-1]
    return value if value == _text(value) else value + "..."


def _money(order: Order, amount) -> str:
    return f"{order.currency} {amount:,.2f}"


def _address(snapshot: dict) -> list[str]:
    return [
        _text(snapshot.get("recipient_name")),
        _text(snapshot.get("line1")),
        _text(snapshot.get("line2")),
        _text(" ".join(filter(None, (snapshot.get("city"), snapshot.get("region"), snapshot.get("postal_code"))))),
        _text(snapshot.get("country_code")),
    ]


def render_invoice(order: Order) -> bytes:
    """Render a compact invoice from persisted order lines and address snapshots."""

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=0)
    width, height = A4
    left, right = 20 * mm, width - 20 * mm
    brand, ink, muted, rule = HexColor("#4f49c8"), HexColor("#20233a"), HexColor("#687087"), HexColor("#dfe3f4")
    page_number = 1

    def header() -> float:
        pdf.setFillColor(brand)
        pdf.rect(0, height - 35 * mm, width, 35 * mm, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#ffffff"))
        pdf.setFont("Helvetica-Bold", 19)
        pdf.drawString(left, height - 18 * mm, "SECURE COMMERCE")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(left, height - 24 * mm, "Order invoice")
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawRightString(right, height - 18 * mm, _text(order.invoice_number))
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(right, height - 24 * mm, f"Issued {order.placed_at:%d %b %Y}")
        return height - 48 * mm

    def footer() -> None:
        pdf.setStrokeColor(rule)
        pdf.line(left, 16 * mm, right, 16 * mm)
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(left, 10 * mm, f"Order {order.order_number}")
        pdf.drawRightString(right, 10 * mm, f"Page {page_number}")

    def new_page() -> float:
        nonlocal page_number
        footer()
        pdf.showPage()
        page_number += 1
        return header()

    y = header()
    pdf.setFillColor(ink)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(left, y, "Bill to")
    pdf.drawString(left + 90 * mm, y, "Ship to")
    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 9)
    for index, (billing, shipping) in enumerate(zip(_address(order.billing_address_snapshot), _address(order.shipping_address_snapshot))):
        y -= 5 * mm
        pdf.drawString(left, y, billing)
        pdf.drawString(left + 90 * mm, y, shipping)
    y -= 12 * mm

    columns = (left, left + 67 * mm, left + 94 * mm, left + 108 * mm, left + 143 * mm)
    pdf.setFillColor(HexColor("#eef0ff"))
    pdf.rect(left, y - 7 * mm, right - left, 8 * mm, fill=1, stroke=0)
    pdf.setFillColor(ink)
    pdf.setFont("Helvetica-Bold", 8)
    for label, x in zip(("Item", "SKU", "Qty", "Unit price", "Total"), columns):
        pdf.drawString(x + 2 * mm, y - 4.5 * mm, label)
    y -= 12 * mm

    for item in order.items.all():
        if y < 48 * mm:
            y = new_page()
        pdf.setStrokeColor(rule)
        pdf.line(left, y - 2 * mm, right, y - 2 * mm)
        pdf.setFillColor(ink)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(columns[0] + 2 * mm, y - 7 * mm, _truncate(item.product_name, 63 * mm))
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(columns[1] + 2 * mm, y - 7 * mm, _truncate(item.sku, 23 * mm, size=8))
        pdf.setFillColor(ink)
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(columns[3] - 2 * mm, y - 7 * mm, str(item.quantity))
        pdf.drawRightString(columns[4] - 2 * mm, y - 7 * mm, _money(order, item.unit_price))
        pdf.drawRightString(right - 2 * mm, y - 7 * mm, _money(order, item.line_total))
        y -= 12 * mm

    if y < 62 * mm:
        y = new_page()
    totals_left = left + 112 * mm
    for label, value in (
        ("Subtotal", order.subtotal),
        ("Discount", -order.discount_total),
        ("Tax", order.tax_total),
        ("Shipping", order.shipping_total),
    ):
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(totals_left, y, label)
        pdf.drawRightString(right, y, _money(order, value))
        y -= 6 * mm
    pdf.setStrokeColor(rule)
    pdf.line(totals_left, y + 2 * mm, right, y + 2 * mm)
    pdf.setFillColor(ink)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(totals_left, y - 4 * mm, "Total")
    pdf.drawRightString(right, y - 4 * mm, _money(order, order.grand_total))
    footer()
    pdf.save()
    return buffer.getvalue()
