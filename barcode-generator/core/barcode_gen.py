"""
Barcode generation module — supports multiple barcode types:
  - EAN-13 (default, retail)
  - Code 128 (alphanumeric, flexible)
  - Code 39 (alphanumeric, older)
  - UPC-A (US retail, 12 digits)
  - ISBN-13 (books)
"""
import io
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QByteArray
import barcode
from barcode.writer import ImageWriter


# Supported barcode types
BARCODE_TYPES = {
    'ean13': {
        'label': 'EAN-13 (Retail)',
        'class': barcode.get_barcode_class('ean13'),
        'min_digits': 12,
        'max_digits': 13,
        'description': 'Standard retail barcode (13 digits)',
    },
    'code128': {
        'label': 'Code 128 (Alphanumeric)',
        'class': barcode.get_barcode_class('code128'),
        'min_digits': 1,
        'max_digits': 0,  # no limit
        'description': 'Flexible barcode — letters + numbers',
    },
    'code39': {
        'label': 'Code 39 (Alphanumeric)',
        'class': barcode.get_barcode_class('code39'),
        'min_digits': 1,
        'max_digits': 0,
        'description': 'Older alphanumeric barcode',
    },
    'upca': {
        'label': 'UPC-A (US Retail)',
        'class': barcode.get_barcode_class('upca'),
        'min_digits': 11,
        'max_digits': 12,
        'description': 'US retail barcode (12 digits)',
    },
    'isbn13': {
        'label': 'ISBN-13 (Books)',
        'class': barcode.get_barcode_class('isbn13'),
        'min_digits': 12,
        'max_digits': 13,
        'description': 'Book barcode (13 digits)',
    },
}


def get_barcode_types_list():
    """Return list of (key, label) for UI dropdowns."""
    return [(key, info['label']) for key, info in BARCODE_TYPES.items()]


def ean13_checksum(first12: str) -> int:
    if len(first12) != 12 or not first12.isdigit():
        raise ValueError("EAN-13 needs exactly 12 digits")
    digits = [int(d) for d in first12]
    odd_sum = sum(digits[0::2])
    even_sum = sum(digits[1::2])
    total = odd_sum + even_sum * 3
    return (10 - (total % 10)) % 10


def validate_ean13(code: str) -> bool:
    if not (len(code) == 13 and code.isdigit()):
        return False
    expected = ean13_checksum(code[:12])
    return int(code[12]) == expected


def make_full_ean13(code: str) -> str:
    code = code.strip()
    if len(code) == 13 and code.isdigit():
        if validate_ean13(code):
            return code
        return code[:12] + str(ean13_checksum(code[:12]))
    if len(code) == 12 and code.isdigit():
        return code + str(ean13_checksum(code))
    digits = ''.join(ch for ch in code if ch.isdigit())
    if len(digits) >= 12:
        digits = digits[:12]
    else:
        digits = digits.zfill(12)
    return digits + str(ean13_checksum(digits))


def generate_barcode_image(code: str, barcode_type: str = 'ean13',
                             module_width: float = 0.33,
                             module_height: float = 20.0) -> tuple:
    """Generate a barcode image for any supported type.
    Returns (QImage, full_code_string).
    """
    if barcode_type not in BARCODE_TYPES:
        barcode_type = 'ean13'
    info = BARCODE_TYPES[barcode_type]
    bc_class = info['class']

    # Process the code based on barcode type
    raw = code.strip()
    if barcode_type == 'ean13':
        full_code = make_full_ean13(raw)
    elif barcode_type == 'upca':
        # UPC-A: 11 or 12 digits
        digits = ''.join(ch for ch in raw if ch.isdigit())
        if len(digits) >= 11:
            digits = digits[:11]
        else:
            digits = digits.zfill(11)
        full_code = digits
    elif barcode_type == 'isbn13':
        full_code = make_full_ean13(raw)
    else:
        # Code 128, Code 39 — use as-is
        full_code = raw

    try:
        bc = bc_class(full_code, writer=ImageWriter())
        pil_img = bc.render({
            'module_width': module_width,
            'module_height': module_height,
            'font_size': 0,
            'text_distance': 0,
            'quiet_zone': 0,
            'background': 'white',
            'foreground': 'black',
            'write_text': False,
        })
        buf = io.BytesIO()
        pil_img.save(buf, format='PNG')
        ba = QByteArray(buf.getvalue())
        img = QImage()
        img.loadFromData(ba, 'PNG')
        return img, full_code
    except Exception as e:
        raise ValueError(f"Could not generate {barcode_type} barcode: {e}")


# Keep backward compatibility
def generate_ean13_image(code: str, module_width: float = 0.33,
                          module_height: float = 20.0) -> tuple:
    return generate_barcode_image(code, 'ean13', module_width, module_height)
