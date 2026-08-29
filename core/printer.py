"""
Printing module - renders a sheet of stickers to a QPrinter (PDF or physical).
"""
from PyQt5.QtCore import Qt, QRectF, QSizeF
from PyQt5.QtGui import QPainter, QPageSize, QPageLayout
from PyQt5.QtPrintSupport import QPrinter

from core.barcode_gen import draw_sticker, make_fonts
from core.layouts import StickerLayout, sticker_positions


# Convert millimeters to pixels at a given DPI.
def mm_to_pixels(mm: float, dpi: float = 300.0) -> float:
    return mm * dpi / 25.4


def print_sticker_sheet(layout: StickerLayout, items: list,
                        font_sizes: dict = None,
                        printer: QPrinter = None,
                        copies: int = 1) -> QPrinter:
    """
    Render `items` (list of dicts) into a sheet using `layout`.
    If `printer` is None, creates a default A4 printer.
    Returns the printer used (caller can call printer.outputFileName() etc.).
    """
    if printer is None:
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QSizeF(layout.paper_w_mm, layout.paper_h_mm),
                                       QPageSize.Millimeter))
        printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)

    printer.setCopyCount(max(1, int(copies)))
    painter = QPainter(printer)
    if not painter.isActive():
        raise RuntimeError("Cannot start painter on printer.")

    fonts = make_fonts(font_sizes or {})
    slots = sticker_positions(layout)
    slots_per_sheet = len(slots)

    # Page resolution in dots (pixels)
    page_rect = printer.pageRect(QPrinter.Millimeter)
    # page_rect is in millimeters — width/height
    page_w_mm = page_rect.width()
    page_h_mm = page_rect.height()

    # We render in device pixels, but compute scale factor from mm to device.
    res = printer.resolution()  # DPI
    scale = res / 25.4  # dots per mm

    for sheet_idx, start in enumerate(range(0, len(items), slots_per_sheet)):
        if sheet_idx > 0:
            printer.newPage()
        sheet_items = items[start:start + slots_per_sheet]
        for (pos_x_mm, pos_y_mm), data in zip(slots, sheet_items):
            # Convert mm to device pixels
            x = pos_x_mm * scale
            y = pos_y_mm * scale
            w = layout.sticker_w_mm * scale
            h = layout.sticker_h_mm * scale
            rect = QRectF(x, y, w, h)
            # Draw with mm-based font sizes; convert to pixels
            scaled_sizes = {
                k: v * scale for k, v in (font_sizes or {}).items()
            } if font_sizes else _auto_font_sizes(layout, scale)
            scaled_fonts = make_fonts(scaled_sizes)
            draw_sticker(painter, rect, data, scaled_fonts)

    painter.end()
    return printer


def _auto_font_sizes(layout: StickerLayout, scale: float) -> dict:
    """Auto-size fonts based on sticker physical size (in device pixels)."""
    # Convert sticker dimensions from mm to pixels
    sticker_h_px = layout.sticker_h_mm * scale
    sticker_w_px = layout.sticker_w_mm * scale
    # Heuristic sizes proportional to sticker height
    company = max(6, int(sticker_h_px * 0.12))
    body = max(5, int(sticker_h_px * 0.09))
    small = max(4, int(sticker_h_px * 0.08))
    barcode = max(5, int(sticker_h_px * 0.09))
    return {
        'company': company,
        'body': body,
        'small': small,
        'barcode_text': barcode,
    }


def render_preview(layout: StickerLayout, items: list,
                   font_sizes: dict = None,
                   dpi: int = 150) -> 'QPixmap':
    """
    Render the sheet/label to a QPixmap (for on-screen preview).
    For small label-printer layouts, automatically scale up to a
    reasonable on-screen size so the label is clearly visible.
    """
    from PyQt5.QtGui import QPixmap, QImage
    # For label mode, render at higher DPI so preview is reasonably sized.
    # Aim for at least 500 px wide for the preview.
    if layout.is_label:
        dpi = max(dpi, int(500 / (layout.paper_w_mm / 25.4)))  # px per inch
        dpi = max(dpi, 300)

    scale = dpi / 25.4
    pix_w = int(layout.paper_w_mm * scale)
    pix_h = int(layout.paper_h_mm * scale)
    pix = QPixmap(pix_w, pix_h)
    pix.fill(Qt.white)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    # Light paper outline
    painter.setPen(Qt.lightGray)
    painter.drawRect(0, 0, pix_w - 1, pix_h - 1)

    fonts = make_fonts(font_sizes or _auto_font_sizes(layout, scale))
    slots = sticker_positions(layout)
    slots_per_sheet = len(slots)
    sheet_items = items[:slots_per_sheet]
    for (pos_x_mm, pos_y_mm), data in zip(slots, sheet_items):
        x = pos_x_mm * scale
        y = pos_y_mm * scale
        w = layout.sticker_w_mm * scale
        h = layout.sticker_h_mm * scale
        rect = QRectF(x, y, w, h)
        draw_sticker(painter, rect, data, fonts)
    painter.end()
    return pix
