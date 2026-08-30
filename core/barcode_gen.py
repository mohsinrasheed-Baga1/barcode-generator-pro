"""
Barcode Generator - EAN-13 module
Generates EAN-13 barcodes and renders them as QImage for display/printing.
"""
import io
from datetime import datetime

import barcode
from barcode.ean import EAN13
from barcode.writer import SVGWriter, ImageWriter

from PyQt5.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QPen, QBrush
from PyQt5.QtCore import Qt, QSize, QRectF, QByteArray


def ean13_checksum(first12: str) -> int:
    """Compute the EAN-13 checksum digit from first 12 digits."""
    if len(first12) != 12 or not first12.isdigit():
        raise ValueError("EAN-13 needs exactly 12 digits (13th is auto)")
    digits = [int(d) for d in first12]
    odd_sum = sum(digits[0::2])     # positions 1,3,5,7,9,11 (0-indexed even)
    even_sum = sum(digits[1::2])   # positions 2,4,6,8,10,12 (0-indexed odd)
    total = odd_sum + even_sum * 3
    return (10 - (total % 10)) % 10


def validate_ean13(code: str) -> bool:
    """Validate a complete 13-digit EAN-13 code."""
    if not (len(code) == 13 and code.isdigit()):
        return False
    expected = ean13_checksum(code[:12])
    return int(code[12]) == expected


def make_full_ean13(code: str) -> str:
    """Take 12 (or 13) digits and return a full valid 13-digit EAN-13 code."""
    code = code.strip()
    if len(code) == 13 and code.isdigit():
        if validate_ean13(code):
            return code
        # fix checksum
        return code[:12] + str(ean13_checksum(code[:12]))
    if len(code) == 12 and code.isdigit():
        return code + str(ean13_checksum(code))
    # Fallback: pad/truncate and recompute
    if not code.isdigit():
        # strip non-digits and reuse
        digits = ''.join(ch for ch in code if ch.isdigit())
    else:
        digits = code
    if len(digits) >= 12:
        digits = digits[:12]
    else:
        # pad with zeros on left
        digits = digits.zfill(12)
    return digits + str(ean13_checksum(digits))


def generate_ean13_image(code: str, module_width: float = 0.33, module_height: float = 20.0) -> QImage:
    """Generate an EAN-13 barcode as a high-resolution QImage (black bars on transparent)."""
    full_code = make_full_ean13(code)
    ean = EAN13(full_code, writer=ImageWriter())
    # Build PIL image
    pil_img = ean.render({
        'module_width': module_width,
        'module_height': module_height,
        'font_size': 0,        # hide text under barcode (we'll render ourselves)
        'text_distance': 0,
        'quiet_zone': 0,
        'background': 'white',
        'foreground': 'black',
        'write_text': False,
    })
    # PIL -> bytes -> QImage
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    ba = QByteArray(buf.getvalue())
    img = QImage()
    img.loadFromData(ba, 'PNG')
    return img, full_code


def draw_sticker(painter: QPainter, rect: QRectF, data: dict, fonts: dict):
    """
    Draw a single sticker inside the given QRectF.
    data keys:
        company_name, product_name (optional), product_code, barcode,
        mfg_date, exp_date, mobile
    fonts dict: { 'company': QFont, 'body': QFont, 'small': QFont, 'barcode_text': QFont }
    """
    painter.save()
    # Background
    painter.setBrush(QBrush(QColor('#FFFFFF')))
    painter.setPen(Qt.NoPen)
    painter.drawRect(rect)

    # Border (thin, professional)
    pen = QPen(QColor('#000000'))
    pen.setWidthF(0.4)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))

    pad = 2.0
    inner = rect.adjusted(pad, pad, -pad, -pad)
    x = inner.x()
    y = inner.y()
    w = inner.width()

    # Company name (top, bold, centered)
    company = (data.get('company_name') or '').strip()
    if company:
        painter.setFont(fonts['company'])
        painter.drawText(QRectF(x, y, w, fonts['company'].pixelSize() + 2),
                         Qt.AlignCenter, company)
        y += fonts['company'].pixelSize() + 2

    # Product name (optional, below company)
    pname = (data.get('product_name') or '').strip()
    if pname:
        painter.setFont(fonts['body'])
        painter.drawText(QRectF(x, y, w, fonts['body'].pixelSize() + 1),
                         Qt.AlignCenter, pname)
        y += fonts['body'].pixelSize() + 1

    # Barcode image (center)
    barcode_value = (data.get('barcode') or '').strip()
    if barcode_value:
        try:
            # Size relative to sticker
            bar_h = min(28, (rect.height() - y + inner.y()) * 0.45)
            bar_w = w * 0.95
            img, full_code = generate_ean13_image(
                barcode_value,
                module_width=0.165,
                module_height=bar_h * 0.7
            )
            # Scale to fit
            scaled = img.scaled(int(bar_w), int(bar_h),
                                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            bar_x = x + (w - scaled.width()) / 2
            painter.drawImage(int(bar_x), int(y), scaled)
            y += scaled.height() + 1

            # Barcode text (digits) under the bars
            painter.setFont(fonts['barcode_text'])
            painter.drawText(QRectF(x, y, w, fonts['barcode_text'].pixelSize() + 1),
                             Qt.AlignCenter, full_code)
            y += fonts['barcode_text'].pixelSize() + 2
        except Exception as e:
            painter.setFont(fonts['body'])
            painter.drawText(QRectF(x, y, w, 14), Qt.AlignCenter, f"Barcode error: {e}")
            y += 16

    # Product code (optional)
    pcode = (data.get('product_code') or '').strip()
    if pcode:
        painter.setFont(fonts['body'])
        painter.drawText(QRectF(x, y, w, fonts['body'].pixelSize() + 1),
                         Qt.AlignCenter, f"Code: {pcode}")
        y += fonts['body'].pixelSize() + 1

    # Dates line: Mfg: ... Exp: ...
    mfg = (data.get('mfg_date') or '').strip()
    exp = (data.get('exp_date') or '').strip()
    if mfg or exp:
        painter.setFont(fonts['small'])
        dates_txt = ""
        if mfg and exp:
            dates_txt = f"Mfg: {mfg}    Exp: {exp}"
        elif mfg:
            dates_txt = f"Mfg: {mfg}"
        else:
            dates_txt = f"Exp: {exp}"
        painter.drawText(QRectF(x, y, w, fonts['small'].pixelSize() + 1),
                         Qt.AlignCenter, dates_txt)
        y += fonts['small'].pixelSize() + 1

    # Mobile number (bottom)
    mobile = (data.get('mobile') or '').strip()
    if mobile:
        painter.setFont(fonts['small'])
        painter.drawText(QRectF(x, y, w, fonts['small'].pixelSize() + 1),
                         Qt.AlignCenter, f"Contact: {mobile}")
        y += fonts['small'].pixelSize() + 1

    painter.restore()


def _make_font(size: int, bold: bool = False) -> QFont:
    f = QFont('Arial')
    f.setPixelSize(int(size))
    if bold:
        f.setBold(True)
    return f


def default_fonts() -> dict:
    """Default font sizes (in pixels, tuned for ~40-per-A4 sticker)."""
    return {
        'company': _make_font(9, bold=True),
        'body':    _make_font(7),
        'small':   _make_font(6),
        'barcode_text': _make_font(7),
    }


def make_fonts(sizes: dict) -> dict:
    """Make fonts from sizes dict {company, body, small, barcode_text}."""
    return {
        'company': _make_font(sizes.get('company', 9), bold=True),
        'body':    _make_font(sizes.get('body', 7)),
        'small':   _make_font(sizes.get('small', 6)),
        'barcode_text': _make_font(sizes.get('barcode_text', 7)),
    }
