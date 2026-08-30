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
                   dpi: int = 150,
                   show_ruler: bool = True) -> QPixmap:
    """
    Render the sheet/label to a QPixmap (for on-screen preview).

    If show_ruler=True (default), draws:
      - A ruler/scale bar showing actual sticker dimensions
      - A size label "Sticker: 38.1 × 25.4 mm (1.5 × 1.0 in)" at the top
      - Dimension lines on each sticker
    This helps the user verify that the sticker size matches their physical
    label — they can hold their physical label up to the screen.

    For label mode, automatically scales up to keep preview visible.
    """
    if layout.is_label:
        dpi = max(dpi, int(500 / (layout.paper_w_mm / 25.4)))
        dpi = max(dpi, 300)

    scale = dpi / 25.4
    sticker_w_px = layout.sticker_w_mm * scale
    sticker_h_px = layout.sticker_h_mm * scale

    # If show_ruler, add extra space at top for size label and around for ruler
    ruler_margin_px = 60 if show_ruler else 10
    paper_w_px = int(layout.paper_w_mm * scale)
    paper_h_px = int(layout.paper_h_mm * scale)
    pix_w = paper_w_px + 2 * ruler_margin_px
    pix_h = paper_h_px + 2 * ruler_margin_px

    pix = QPixmap(pix_w, pix_h)
    pix.fill(QColor('#f0f0f0'))  # gray background so white paper stands out

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.Antialiasing, True)

    # White paper area
    paper_rect = QRectF(ruler_margin_px, ruler_margin_px,
                        paper_w_px, paper_h_px)
    painter.fillRect(paper_rect, Qt.white)
    painter.setPen(QPen(QColor('#888'), 1))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(paper_rect)

    # Size label at the top
    if show_ruler:
        in_w = layout.sticker_w_mm / 25.4
        in_h = layout.sticker_h_mm / 25.4
        size_text = (f"Sticker size: {layout.sticker_w_mm:.1f} × {layout.sticker_h_mm:.1f} mm"
                     f"  ({in_w:.2f} × {in_h:.2f} in)"
                     f"  |  Layout: {layout.name}")
        # Scale font based on ruler_margin_px
        font = QFont('Arial', 9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor('#1a4d8f'))
        text_rect = QRectF(0, 5, pix_w, ruler_margin_px - 10)
        painter.drawText(text_rect, Qt.AlignCenter, size_text)

        # Ruler ticks along top of paper (cm marks)
        painter.setPen(QPen(QColor('#666'), 1))
        painter.setFont(QFont('Arial', 7))
        # 1 cm = 10 mm = scale * 10 px
        cm_px = 10 * scale
        paper_left = ruler_margin_px
        cm = 0
        x = paper_left
        while x <= paper_left + paper_w_px + 1:
            # Major tick every 1cm, minor tick every 5mm
            if cm % 1 == 0:
                painter.drawLine(QPointF(x, paper_rect.top() - 8),
                                  QPointF(x, paper_rect.top()))
                if cm > 0:
                    painter.drawText(QRectF(x - 10, paper_rect.top() - 22,
                                            20, 12),
                                     Qt.AlignCenter, str(cm))
            else:
                painter.drawLine(QPointF(x, paper_rect.top() - 4),
                                  QPointF(x, paper_rect.top()))
            cm += 0.5
            x += cm_px / 2

        # Ruler ticks along left of paper (cm marks)
        paper_top = ruler_margin_px
        cm = 0
        y = paper_top
        while y <= paper_top + paper_h_px + 1:
            if cm % 1 == 0:
                painter.drawLine(QPointF(paper_rect.left() - 8, y),
                                  QPointF(paper_rect.left(), y))
                if cm > 0:
                    painter.save()
                    painter.translate(paper_rect.left() - 18, y + 5)
                    painter.rotate(-90)
                    painter.drawText(QRectF(0, 0, 20, 12),
                                     Qt.AlignCenter, str(cm))
                    painter.restore()
            else:
                painter.drawLine(QPointF(paper_rect.left() - 4, y),
                                  QPointF(paper_rect.left(), y))
            cm += 0.5
            y += cm_px / 2

        # Dimension lines on the sticker (showing actual W×H)
        # Draw width dimension below sticker (only for label mode)
        if layout.is_label:
            slots = sticker_positions(layout)
            if slots:
                pos_x, pos_y = slots[0]
                sticker_left = ruler_margin_px + pos_x * scale
                sticker_top = ruler_margin_px + pos_y * scale
                sticker_w = layout.sticker_w_mm * scale
                sticker_h = layout.sticker_h_mm * scale
                # Width dimension below
                dim_y = sticker_top + sticker_h + 15
                painter.setPen(QPen(QColor('#1a4d8f'), 1))
                painter.drawLine(QPointF(sticker_left, dim_y),
                                  QPointF(sticker_left + sticker_w, dim_y))
                # Arrowheads (small)
                for x_end in [sticker_left, sticker_left + sticker_w]:
                    painter.drawLine(QPointF(x_end, dim_y - 4),
                                      QPointF(x_end, dim_y + 4))
                # Width text
                w_text = f"{layout.sticker_w_mm:.1f} mm"
                painter.setFont(QFont('Arial', 8))
                painter.setPen(QColor('#1a4d8f'))
                painter.drawText(QRectF(sticker_left, dim_y + 4,
                                         sticker_w, 14),
                                 Qt.AlignCenter, w_text)
                # Height dimension on right
                dim_x = sticker_left + sticker_w + 15
                painter.setPen(QPen(QColor('#1a4d8f'), 1))
                painter.drawLine(QPointF(dim_x, sticker_top),
                                  QPointF(dim_x, sticker_top + sticker_h))
                for y_end in [sticker_top, sticker_top + sticker_h]:
                    painter.drawLine(QPointF(dim_x - 4, y_end),
                                      QPointF(dim_x + 4, y_end))
                h_text = f"{layout.sticker_h_mm:.1f} mm"
                painter.save()
                painter.translate(dim_x + 6, sticker_top + sticker_h / 2 + 5)
                painter.rotate(90)
                painter.drawText(QRectF(-40, -7, 80, 14),
                                 Qt.AlignCenter, h_text)
                painter.restore()

    # Now draw the stickers inside the paper area
    painter.save()
    painter.translate(ruler_margin_px, ruler_margin_px)

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

    painter.restore()
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
