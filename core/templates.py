"""
Sticker template system - each element on the sticker is independently
configurable: position (x,y), size (w,h), rotation, font family, font size,
bold, alignment, and visibility (on/off).

A template defines the LAYOUT. The actual data (company name, barcode
digits, etc.) is supplied at print time and merged with the template.

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
    id: str                 # 'company_name', 'barcode', etc.
    label: str              # human-readable name (for the editor UI)
    enabled: bool = True
    # All dimensions in millimeters relative to sticker top-left corner
    x_mm: float = 0.0
    y_mm: float = 0.0
    w_mm: float = 38.0
    h_mm: float = 5.0
    rotation: float = 0.0   # degrees, clockwise
    # Font settings
    font_family: str = 'Arial'
    font_size_pt: float = 7.0  # points (1 pt = 1/72 inch)
    bold: bool = False
    italic: bool = False
    align: str = 'center'   # 'left', 'center', 'right'
    color: str = '#000000'  # hex


@dataclass
class StickerTemplate:
    """A complete sticker layout — list of elements + sticker size."""
    name: str = 'Default'
    sticker_w_mm: float = 38.0
    sticker_h_mm: float = 21.2
    elements: List[StickerElement] = field(default_factory=list)
    background_color: str = '#FFFFFF'
    border_color: str = '#000000'
    border_width_mm: float = 0.2  # 0 = no border


# ---------------------------------------------------- default templates
def default_template(sticker_w_mm: float, sticker_h_mm: float,
                     include_barcode: bool = True,
                     include_product_name: bool = True,
                     include_product_code: bool = True,
                     include_dates: bool = True,
                     include_mobile: bool = True,
                     include_company: bool = True) -> StickerTemplate:
    """
    Auto-build a sensible default template for a given sticker size.
    Elements are stacked vertically top-to-bottom.
    """
    # Scale font sizes based on sticker size
    base_h = sticker_h_mm
    company_pt = max(4.0, min(14.0, base_h * 0.18))   # ~18% of sticker height
    body_pt    = max(3.0, min(11.0, base_h * 0.14))
    small_pt   = max(3.0, min(10.0, base_h * 0.12))
    barcode_pt = max(3.0, min(11.0, base_h * 0.13))

    # Barcode takes ~35% of sticker height
    barcode_h = base_h * 0.35
    barcode_digit_h = base_h * 0.08

    elements: List[StickerElement] = []
    y = 0.5  # start with tiny margin

    # Company name at top
    if include_company:
        elements.append(StickerElement(
            id='company_name',
            label='Company Name / کمپنی نام',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=base_h * 0.18,
            font_family='Arial',
            font_size_pt=company_pt,
            bold=True,
            align='center',
        ))
        y += base_h * 0.18

    # Product name (optional)
    if include_product_name:
        elements.append(StickerElement(
            id='product_name',
            label='Product Name / پروڈکٹ نام',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=base_h * 0.13,
            font_family='Arial',
            font_size_pt=body_pt,
            bold=False,
            align='center',
        ))
        y += base_h * 0.13

    # Barcode (center)
    if include_barcode:
        elements.append(StickerElement(
            id='barcode',
            label='Barcode / بارکوڈ',
            enabled=True,
            x_mm=1.0, y_mm=y,
            w_mm=sticker_w_mm - 2.0,
            h_mm=barcode_h,
        ))
        y += barcode_h

        # Barcode digits below the bars
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

    # Product code
    if include_product_code:
        elements.append(StickerElement(
            id='product_code',
            label='Product Code / پروڈکٹ کوڈ',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=base_h * 0.13,
            font_family='Arial',
            font_size_pt=body_pt,
            bold=False,
            align='center',
        ))
        y += base_h * 0.13

    # Dates
    if include_dates:
        elements.append(StickerElement(
            id='dates',
            label='Mfg / Exp Dates / تاریخیں',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=base_h * 0.12,
            font_family='Arial',
            font_size_pt=small_pt,
            bold=False,
            align='center',
        ))
        y += base_h * 0.12

    # Mobile
    if include_mobile:
        elements.append(StickerElement(
            id='mobile',
            label='Mobile / موبائل',
            enabled=True,
            x_mm=0.5, y_mm=y,
            w_mm=sticker_w_mm - 1.0,
            h_mm=base_h * 0.12,
            font_family='Arial',
            font_size_pt=small_pt,
            bold=False,
            align='center',
        ))
        y += base_h * 0.12

    return StickerTemplate(
        name='Default',
        sticker_w_mm=sticker_w_mm,
        sticker_h_mm=sticker_h_mm,
        elements=elements,
    )


# ---------------------------------------------------- serialization
def template_to_json(t: StickerTemplate) -> str:
    """Serialize a template to JSON string."""
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
    """Deserialize a template from JSON string."""
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


# ---------------------------------------------------- data merge
def get_text_for_element(element_id: str, data: dict) -> str:
    """Get the text to render for a given element id from data dict."""
    if element_id == 'company_name':
        return data.get('company_name', '')
    if element_id == 'product_name':
        return data.get('product_name', '')
    if element_id == 'product_code':
        c = data.get('product_code', '')
        return f"Code: {c}" if c else ''
    if element_id == 'barcode':
        return ''  # barcode is an image, not text
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
    return ''


def enabled_elements(template: StickerTemplate) -> List[StickerElement]:
    """Return only enabled elements (in order)."""
    return [e for e in template.elements if e.enabled]
