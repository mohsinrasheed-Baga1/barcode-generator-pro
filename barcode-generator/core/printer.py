"""
Printing module (v2.0.2) - renders a sheet of stickers using a StickerTemplate.
Handles both sheet printers (multi-sticker per A4) and label printers
(single label per page).

Key features:
- PrinterResolution mode for label printer compatibility (Zebra/TSC/Xprinter)
- copies=None parameter to respect user's print dialog choice
- TextDontClip flag to prevent text from being cut off
- _draw_element_at_origin for in-editor rendering
"""
from PyQt5.QtCore import Qt, QRectF, QSizeF, QPointF
from PyQt5.QtGui import (QPainter, QPixmap, QImage, QPageSize, QColor,
                          QPen, QFont, QFontDatabase, QTransform)
from PyQt5.QtPrintSupport import QPrinter

from core.barcode_gen import (make_full_ean13, validate_ean13,
                                generate_ean13_image, draw_sticker,
                                make_fonts)
from core.layouts import StickerLayout, sticker_positions
from core.templates import (StickerTemplate, StickerElement,
                              get_text_for_element, enabled_elements)
from core.units import pt_to_mm


# ---------------------------------------------------------------- helpers
def _element_to_qfont(elem: StickerElement) -> QFont:
    """Build a QFont from an element's font settings."""
    f = QFont(elem.font_family or 'Arial')
    f.setPointSizeF(float(elem.font_size_pt))
    f.setBold(bool(elem.bold))
    f.setItalic(bool(elem.italic))
    return f


def _align_flag(align: str) -> Qt.AlignmentFlag:
    return {
        'left': Qt.AlignLeft | Qt.AlignVCenter,
        'right': Qt.AlignRight | Qt.AlignVCenter,
        'center': Qt.AlignHCenter | Qt.AlignVCenter,
    }.get(align, Qt.AlignHCenter | Qt.AlignVCenter)


def _draw_element(painter: QPainter, elem: StickerElement, data: dict,
                  scale: float, sticker_origin: QPointF):
    """Draw a single element at its position within the sticker."""
    if not elem.enabled:
        return
    w_px = elem.w_mm * scale
    h_px = elem.h_mm * scale
    x_px = sticker_origin.x() + elem.x_mm * scale
    y_px = sticker_origin.y() + elem.y_mm * scale

    painter.save()
    if elem.rotation:
        cx = x_px + w_px / 2
        cy = y_px + h_px / 2
        painter.translate(cx, cy)
        painter.rotate(elem.rotation)
        painter.translate(-cx, -cy)

    rect = QRectF(x_px, y_px, w_px, h_px)

    if elem.id == 'barcode':
        bc = data.get('barcode', '')
        if not bc:
            painter.restore()
            return
        try:
            module_w = (w_px / 100) * 0.165
            img, full_code = generate_ean13_image(
                bc,
                module_width=module_w,
                module_height=h_px * 0.7,
            )
            scaled = img.scaled(int(w_px), int(h_px),
                                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            tx = x_px + (w_px - scaled.width()) / 2
            ty = y_px + (h_px - scaled.height()) / 2
            painter.drawImage(QPointF(tx, ty), scaled)
        except Exception:
            pass
    else:
        text = get_text_for_element(elem.id, data)
        if not text:
            painter.restore()
            return
        font = _element_to_qfont(elem)
        painter.setFont(font)
        painter.setPen(QColor(elem.color or '#000000'))
        # IMPORTANT: TextDontClip prevents text from being cut off when
        # the element rect is smaller than the text size. The user can
        # still adjust the element size in the editor.
        flags = _align_flag(elem.align) | Qt.TextDontClip
        painter.drawText(rect, flags, text)

    painter.restore()


def _draw_element_at_origin(painter: QPainter, elem: StickerElement,
                             data: dict, scale: float,
                             local_rect: QRectF):
    """Draw an element at the given local rect (used by the sticker editor)."""
    if not elem.enabled:
        return
    painter.save()

    if elem.rotation:
        cx = local_rect.center().x()
        cy = local_rect.center().y()
        painter.translate(cx, cy)
        painter.rotate(elem.rotation)
        painter.translate(-cx, -cy)

    if elem.id == 'barcode':
        bc = data.get('barcode', '')
        if bc:
            try:
                w_px = local_rect.width()
                h_px = local_rect.height()
                module_w = (w_px / 100) * 0.165
                img, full_code = generate_ean13_image(
                    bc,
                    module_width=module_w,
                    module_height=h_px * 0.7,
                )
                scaled = img.scaled(int(w_px), int(h_px),
                                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
                tx = local_rect.left() + (w_px - scaled.width()) / 2
                ty = local_rect.top() + (h_px - scaled.height()) / 2
                painter.drawImage(QPointF(tx, ty), scaled)
            except Exception:
                pass
    else:
        text = get_text_for_element(elem.id, data)
        if text:
            font = _element_to_qfont(elem)
            painter.setFont(font)
            painter.setPen(QColor(elem.color or '#000000'))
            flags = _align_flag(elem.align) | Qt.TextDontClip
            painter.drawText(local_rect, flags, text)

    painter.restore()


def draw_sticker_with_template(painter: QPainter, rect: QRectF,
                                data: dict, template: StickerTemplate,
                                scale: float):
    """Draw a sticker using the template at `rect` (in device pixels)."""
    painter.save()

    bg = QColor(template.background_color or '#FFFFFF')
    painter.fillRect(rect, bg)

    if template.border_width_mm > 0:
        pen = QPen(QColor(template.border_color or '#000000'))
        pen.setWidthF(template.border_width_mm * scale)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

    sticker_w_px = rect.width()
    sticker_h_px = rect.height()
    sx = sticker_w_px / (template.sticker_w_mm * scale)
    sy = sticker_h_px / (template.sticker_h_mm * scale)
    painter.translate(rect.topLeft())
    if abs(sx - 1.0) > 0.01 or abs(sy - 1.0) > 0.01:
        painter.scale(sx, sy)

    for elem in template.elements:
        _draw_element(painter, elem, data, scale, QPointF(0, 0))

    painter.restore()


# ---------------------------------------------------------------- sheet printing
def print_sticker_sheet(layout: StickerLayout, items: list,
                        template: StickerTemplate,
                        printer: QPrinter = None,
                        copies: int = None) -> QPrinter:
    """
    Render `items` onto pages using `layout` + `template`.

    `printer`: If None, a new QPrinter is created with PrinterResolution mode.
    `copies`: If provided, overrides the printer's copy count. If None and
             printer was provided, the printer's existing copy count is used
             (this respects the user's choice in the print dialog).

    CRITICAL: For label printers, we call setFullPage(True) which tells Qt
    to use the FULL physical page (no hard margins). Without this, Qt adds
    its own default margins that consume a significant portion of small
    labels (e.g. 3-5mm on a 25mm tall label = huge offset).
    """
    if printer is None:
        printer = QPrinter(QPrinter.PrinterResolution)
        printer.setPageSize(QPageSize(QSizeF(layout.paper_w_mm, layout.paper_h_mm),
                                       QPageSize.Millimeter))
        printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
        if copies is not None:
            printer.setCopyCount(max(1, int(copies)))
    elif copies is not None:
        printer.setCopyCount(max(1, int(copies)))

    # CRITICAL for label printers: use full physical page (no Qt margins)
    printer.setFullPage(True)

    painter = QPainter(printer)
    if not painter.isActive():
        raise RuntimeError(
            "Cannot start painter on printer. The printer may not be valid "
            "or the print job was cancelled.\n\n"
            f"Printer: {printer.printerName()}\n"
            f"Page size (mm): {printer.pageLayout().pageSize().size(QPageSize.Millimeter).width():.1f} x "
            f"{printer.pageLayout().pageSize().size(QPageSize.Millimeter).height():.1f}\n"
            f"Resolution (DPI): {printer.resolution()}\n"
            f"Layout paper (mm): {layout.paper_w_mm} x {layout.paper_h_mm}\n"
            f"Items to print: {len(items)}"
        )

    slots = sticker_positions(layout)
    slots_per_page = len(slots)
    res = printer.resolution()
    scale = res / 25.4

    page = 0
    for start in range(0, len(items), slots_per_page):
        if page > 0:
            printer.newPage()
        page += 1
        page_items = items[start:start + slots_per_page]
        for (pos_x_mm, pos_y_mm), data in zip(slots, page_items):
            x = pos_x_mm * scale
            y = pos_y_mm * scale
            w = layout.sticker_w_mm * scale
            h = layout.sticker_h_mm * scale
            rect = QRectF(x, y, w, h)
            draw_sticker_with_template(painter, rect, data, template, scale)

    painter.end()
    return printer


def diagnose_printer(printer: QPrinter, layout: StickerLayout) -> str:
    """Return a diagnostic string with printer info — useful for error messages."""
    try:
        pl = printer.pageLayout()
        ps = pl.pageSize()
        sz_mm = ps.size(QPageSize.Millimeter)
        return (
            f"Printer: {printer.printerName()}\n"
            f"Resolution: {printer.resolution()} DPI\n"
            f"Page size (mm): {sz_mm.width():.2f} x {sz_mm.height():.2f}\n"
            f"Layout paper (mm): {layout.paper_w_mm:.2f} x {layout.paper_h_mm:.2f}\n"
            f"Layout sticker (mm): {layout.sticker_w_mm:.2f} x {layout.sticker_h_mm:.2f}\n"
            f"Match: {'✓ YES' if (abs(sz_mm.width() - layout.paper_w_mm) < 0.5 and abs(sz_mm.height() - layout.paper_h_mm) < 0.5) else '✗ NO — sizes differ!'}\n"
            f"Copies: {printer.copyCount()}\n"
            f"Full page mode: {printer.fullPage()}\n"
            f" isValid: {printer.isValid()}"
        )
    except Exception as e:
        return f"Could not get printer info: {e}"


# ---------------------------------------------------------------- preview
def render_preview(layout: StickerLayout, items: list,
                   template: StickerTemplate,
                   dpi: int = 150) -> QPixmap:
    """Render the sheet/label to a QPixmap (for on-screen preview)."""
    if layout.is_label:
        dpi = max(dpi, int(500 / (layout.paper_w_mm / 25.4)))
        dpi = max(dpi, 300)

    scale = dpi / 25.4
    pix_w = int(layout.paper_w_mm * scale)
    pix_h = int(layout.paper_h_mm * scale)
    pix = QPixmap(pix_w, pix_h)
    pix.fill(Qt.white)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.Antialiasing, True)

    painter.setPen(Qt.lightGray)
    painter.drawRect(0, 0, pix_w - 1, pix_h - 1)

    slots = sticker_positions(layout)
    slots_per_page = len(slots)
    page_items = items[:slots_per_page]
    for (pos_x_mm, pos_y_mm), data in zip(slots, page_items):
        x = pos_x_mm * scale
        y = pos_y_mm * scale
        w = layout.sticker_w_mm * scale
        h = layout.sticker_h_mm * scale
        rect = QRectF(x, y, w, h)
        draw_sticker_with_template(painter, rect, data, template, scale)

    painter.end()
    return pix


def render_single_sticker_preview(template: StickerTemplate, data: dict,
                                   dpi: int = 200) -> QPixmap:
    """Render just one sticker (used by the sticker editor)."""
    scale = dpi / 25.4
    pix_w = int(template.sticker_w_mm * scale)
    pix_h = int(template.sticker_h_mm * scale)
    pix = QPixmap(pix_w, pix_h)
    pix.fill(Qt.white)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.Antialiasing, True)

    rect = QRectF(0, 0, pix_w, pix_h)
    draw_sticker_with_template(painter, rect, data, template, scale)
    painter.end()
    return pix


# ---------------------------------------------------------------- PDF export
def export_to_pdf(layout: StickerLayout, items: list,
                  template: StickerTemplate, pdf_path: str) -> str:
    """
    Export the current batch to a PDF file. Always works (no printer needed).
    Uses HighResolution mode so the PDF has crisp barcodes for scanning.

    CRITICAL: setFullPage(True) ensures the PDF page is exactly the label
    size, not the PDF default (Letter/A4). This is essential for label
    printers — the PDF viewer will use the PDF's page size as the print size.
    """
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(pdf_path)
    printer.setPageSize(QPageSize(QSizeF(layout.paper_w_mm, layout.paper_h_mm),
                                   QPageSize.Millimeter))
    printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
    printer.setFullPage(True)  # use full PDF page, no Qt margins
    printer.setResolution(600)
    print_sticker_sheet(layout, items, template, printer=printer, copies=1)
    return pdf_path
