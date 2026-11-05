"""
Sticker template system - each element on the sticker is independently
configurable: position (x,y), size (w,h), rotation, font family, font size,
bold, alignment, and visibility (on/off).

Element ids (fixed):
    company_name    — Company name (top)
    product_name    — Product name (optional, below company)
    product_code    — Product code
    barcode         — The EAN-13 barcode image
    barcode_digits  — The 13-digit text under the barcode
    dates           — Mfg/Exp dates line
    mobile          — Mobile number line
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import json


@dataclass
class StickerElement:
    id: str
    label: str
    enabled: bool = True
    x_mm: float = 0.0
    y_mm: float = 0.0
    w_mm: float = 38.0
    h_mm: float = 5.0
    rotation: float = 0.0
    font_family: str = 'Arial'
    font_size_pt: float = 7.0
    bold: bool = False
    italic: bool = False
    align: str = 'center'
    color: str = '#000000'
    # For logo elements only
    image_data: str = ''
    image_format: str = 'PNG'
    image_fit: str = 'contain'
    # Barcode type for barcode elements
    barcode_type: str = 'ean13'


@dataclass
class StickerTemplate:
    name: str = 'Default'
    sticker_w_mm: float = 38.0
    sticker_h_mm: float = 21.2
    elements: List[StickerElement] = field(default_factory=list)
    background_color: str = '#FFFFFF'
    border_color: str = '#000000'
    border_width_mm: float = 0.2


def default_template(sticker_w_mm: float, sticker_h_mm: float,
                     include_barcode: bool = True,
                     include_product_name: bool = True,
                     include_product_code: bool = True,
                     include_dates: bool = True,
                     include_mobile: bool = True,
                     include_company: bool = True,
                     include_logo: bool = False,
                     include_price: bool = False,
                     barcode_type: str = 'ean13') -> StickerTemplate:
    """Auto-build a sensible default template for a given sticker size."""
    base_h = sticker_h_mm
    # Scale font sizes based on sticker size — with LARGER minimums
    # for readability on small labels (24mm tall)
    company_pt = max(7.0, min(16.0, base_h * 0.22))   # min 7pt
    body_pt    = max(6.0, min(13.0, base_h * 0.18))   # min 6pt
    small_pt   = max(5.0, min(11.0, base_h * 0.15))   # min 5pt
    barcode_pt = max(6.0, min(12.0, base_h * 0.16))   # min 6pt

    # Element heights as fraction of sticker height — compact layout
    # that fits within the sticker boundary even for small stickers (25mm)
    barcode_h = base_h * 0.35       # barcode bars
    barcode_digit_h = base_h * 0.08  # digits below barcode
    company_h = base_h * 0.15
    product_h = base_h * 0.10
    code_h = base_h * 0.10
    dates_h = base_h * 0.08
    mobile_h = base_h * 0.08
    price_h = base_h * 0.12  # price element

    elements: List[StickerElement] = []
    y = 0.5

    # Logo at top-left corner (small, 8x8mm by default)
    if include_logo:
        logo_size = min(8.0, base_h * 0.4, sticker_w_mm * 0.25)
        elements.append(StickerElement(
            id='logo',
            label='Logo / لوگو',
            enabled=True,
            x_mm=0.5, y_mm=0.5,
            w_mm=logo_size, h_mm=logo_size,
            image_data='',  # empty — user will load an image
            image_format='PNG',
            image_fit='contain',
        ))

    if include_company:
        elements.append(StickerElement(
            id='company_name',
            label='Company Name / کمپنی نام',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=company_h,
            font_family='Arial',
            font_size_pt=company_pt,
            bold=True,
            align='center',
        ))
        y += company_h

    if include_product_name:
        elements.append(StickerElement(
            id='product_name',
            label='Product Name / پروڈکٹ نام',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=product_h,
            font_family='Arial',
            font_size_pt=body_pt,
            bold=False,
            align='center',
        ))
        y += product_h

    if include_barcode:
        elements.append(StickerElement(
            id='barcode',
            label='Barcode / بارکوڈ',
            enabled=True,
            x_mm=1.0, y_mm=y,
            w_mm=sticker_w_mm - 2.0,
            h_mm=barcode_h,
            barcode_type=barcode_type,
        ))
        y += barcode_h

        elements.append(StickerElement(
            id='barcode_digits',
            label='Barcode Digits / بارکوڈ ہندسے',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=barcode_digit_h,
            font_family='Arial',
            font_size_pt=barcode_pt,
            bold=False,
            align='center',
        ))
        y += barcode_digit_h

    if include_product_code:
        elements.append(StickerElement(
            id='product_code',
            label='Product Code / پروڈکٹ کوڈ',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=code_h,
            font_family='Arial',
            font_size_pt=body_pt,
            bold=False,
            align='center',
        ))
        y += code_h

    if include_dates:
        elements.append(StickerElement(
            id='dates',
            label='Mfg / Exp Dates / تاریخیں',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=dates_h,
            font_family='Arial',
            font_size_pt=small_pt,
            bold=False,
            align='center',
        ))
        y += dates_h

    if include_mobile:
        elements.append(StickerElement(
            id='mobile',
            label='Mobile / موبائل',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=mobile_h,
            font_family='Arial',
            font_size_pt=small_pt,
            bold=False,
            align='center',
        ))
        y += mobile_h

    if include_price:
        # Price — bold, prominent, large
        price_pt = max(7.0, min(16.0, base_h * 0.20))
        elements.append(StickerElement(
            id='price',
            label='Price / قیمت',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=price_h,
            font_family='Arial',
            font_size_pt=price_pt,
            bold=True,
            align='center',
            color='#c62828',  # red color for price
        ))
        y += price_h

    return StickerTemplate(
        name='Default',
        sticker_w_mm=sticker_w_mm,
        sticker_h_mm=sticker_h_mm,
        elements=elements,
    )


def template_to_json(t: StickerTemplate) -> str:
    d = {
        'name': t.name,
        'sticker_w_mm': t.sticker_w_mm,
        'sticker_h_mm': t.sticker_h_mm,
        'background_color': t.background_color,
        'border_color': t.border_color,
        'border_width_mm': t.border_width_mm,
        'elements': [asdict(e) for e in t.elements],
    }
    return json.dumps(d, indent=2)


def template_from_json(s: str) -> StickerTemplate:
    d = json.loads(s)
    elements = [StickerElement(**e) for e in d.get('elements', [])]
    return StickerTemplate(
        name=d.get('name', 'Default'),
        sticker_w_mm=d.get('sticker_w_mm', 38.0),
        sticker_h_mm=d.get('sticker_h_mm', 21.2),
        elements=elements,
        background_color=d.get('background_color', '#FFFFFF'),
        border_color=d.get('border_color', '#000000'),
        border_width_mm=d.get('border_width_mm', 0.2),
    )


def get_text_for_element(element_id: str, data: dict) -> str:
    if element_id == 'company_name':
        return data.get('company_name', '')
    if element_id == 'product_name':
        return data.get('product_name', '')
    if element_id == 'product_code':
        c = data.get('product_code', '')
        return f"Code: {c}" if c else ''
    if element_id == 'barcode':
        return ''
    if element_id == 'barcode_digits':
        return data.get('barcode', '')
    if element_id == 'dates':
        mfg = data.get('mfg_date', '')
        exp = data.get('exp_date', '')
        if mfg and exp:
            return f"Mfg: {mfg}    Exp: {exp}"
        if mfg:
            return f"Mfg: {mfg}"
        if exp:
            return f"Exp: {exp}"
        return ''
    if element_id == 'mobile':
        m = data.get('mobile', '')
        return f"Contact: {m}" if m else ''
    if element_id == 'price':
        p = data.get('price', '')
        if not p:
            return ''
        # Format: if it's a number, prefix with Rs.
        try:
            float(p)
            return f"Rs. {p}"
        except ValueError:
            return p
    return ''


def enabled_elements(template: StickerTemplate) -> List[StickerElement]:
    return [e for e in template.elements if e.enabled]
