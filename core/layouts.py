"""
Sticker sheet / label layouts.
All dimensions in millimeters (mm).

Two print modes are supported:
  1. SHEET printer   — A4 paper with multiple stickers per sheet
  2. LABEL printer   — Direct label printer (Zebra/TSC/Godex/etc.),
                       one label at a time (continuous roll)

For label printers, the "paper" is the label itself:
    paper_w_mm == sticker_w_mm
    paper_h_mm == sticker_h_mm
    cols = rows = 1
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class StickerLayout:
    name: str
    paper_w_mm: float        # paper width
    paper_h_mm: float        # paper height
    margin_x_mm: float       # left/right margin
    margin_y_mm: float       # top/bottom margin
    gap_x_mm: float           # horizontal gap between stickers
    gap_y_mm: float           # vertical gap between stickers
    sticker_w_mm: float       # sticker width
    sticker_h_mm: float       # sticker height
    cols: int
    rows: int
    is_label: bool = False    # True => direct label printer mode


# ---------------------------------------------------------------- A4 SHEET PRESETS
SHEET_PRESETS = {
    'A4-40': StickerLayout(
        name='[Sheet] A4 — 40 labels (38 x 21.2 mm)',
        paper_w_mm=210, paper_h_mm=297,
        margin_x_mm=7.0, margin_y_mm=13.0,
        gap_x_mm=2.5, gap_y_mm=0.0,
        sticker_w_mm=38.0, sticker_h_mm=21.2,
        cols=4, rows=10,
    ),
    'A4-24': StickerLayout(
        name='[Sheet] A4 — 24 labels (63.5 x 33.9 mm)',
        paper_w_mm=210, paper_h_mm=297,
        margin_x_mm=7.0, margin_y_mm=13.0,
        gap_x_mm=3.0, gap_y_mm=0.0,
        sticker_w_mm=63.5, sticker_h_mm=33.9,
        cols=3, rows=8,
    ),
    'A4-80': StickerLayout(
        name='[Sheet] A4 — 80 labels (38 x 12.7 mm)',
        paper_w_mm=210, paper_h_mm=297,
        margin_x_mm=7.0, margin_y_mm=15.0,
        gap_x_mm=2.0, gap_y_mm=0.0,
        sticker_w_mm=38.0, sticker_h_mm=12.7,
        cols=4, rows=20,
    ),
    'A4-12': StickerLayout(
        name='[Sheet] A4 — 12 labels (63.5 x 72 mm)',
        paper_w_mm=210, paper_h_mm=297,
        margin_x_mm=8.0, margin_y_mm=12.0,
        gap_x_mm=4.0, gap_y_mm=0.0,
        sticker_w_mm=63.5, sticker_h_mm=72.0,
        cols=3, rows=4,
    ),
}


# ---------------------------------------------------------------- LABEL PRINTER PRESETS
# Direct label printers (Zebra GC420, TSC TDP-225, Godex RT, Xprinter, etc.)
# Each preset = one label, paper size = label size, 1 sticker per "page".
LABEL_PRESETS = {
    'LBL-50x30': StickerLayout(
        name='[Label] 50 x 30 mm  (price tag)',
        paper_w_mm=50, paper_h_mm=30,
        margin_x_mm=0.5, margin_y_mm=0.5,
        gap_x_mm=0, gap_y_mm=0,
        sticker_w_mm=49, sticker_h_mm=29,
        cols=1, rows=1, is_label=True,
    ),
    'LBL-40x30': StickerLayout(
        name='[Label] 40 x 30 mm  (small barcode)',
        paper_w_mm=40, paper_h_mm=30,
        margin_x_mm=0.5, margin_y_mm=0.5,
        gap_x_mm=0, gap_y_mm=0,
        sticker_w_mm=39, sticker_h_mm=29,
        cols=1, rows=1, is_label=True,
    ),
    'LBL-40x25': StickerLayout(
        name='[Label] 40 x 25 mm  (mini barcode)',
        paper_w_mm=40, paper_h_mm=25,
        margin_x_mm=0.5, margin_y_mm=0.5,
        gap_x_mm=0, gap_y_mm=0,
        sticker_w_mm=39, sticker_h_mm=24,
        cols=1, rows=1, is_label=True,
    ),
    'LBL-60x40': StickerLayout(
        name='[Label] 60 x 40 mm  (product label)',
        paper_w_mm=60, paper_h_mm=40,
        margin_x_mm=0.8, margin_y_mm=0.8,
        gap_x_mm=0, gap_y_mm=0,
        sticker_w_mm=58.4, sticker_h_mm=38.4,
        cols=1, rows=1, is_label=True,
    ),
    'LBL-70x40': StickerLayout(
        name='[Label] 70 x 40 mm  (large product)',
        paper_w_mm=70, paper_h_mm=40,
        margin_x_mm=0.8, margin_y_mm=0.8,
        gap_x_mm=0, gap_y_mm=0,
        sticker_w_mm=68.4, sticker_h_mm=38.4,
        cols=1, rows=1, is_label=True,
    ),
    'LBL-100x50': StickerLayout(
        name='[Label] 100 x 50 mm  (logistics)',
        paper_w_mm=100, paper_h_mm=50,
        margin_x_mm=1.0, margin_y_mm=1.0,
        gap_x_mm=0, gap_y_mm=0,
        sticker_w_mm=98, sticker_h_mm=48,
        cols=1, rows=1, is_label=True,
    ),
    'LBL-80x60': StickerLayout(
        name='[Label] 80 x 60 mm  (warehouse tag)',
        paper_w_mm=80, paper_h_mm=60,
        margin_x_mm=1.0, margin_y_mm=1.0,
        gap_x_mm=0, gap_y_mm=0,
        sticker_w_mm=78, sticker_h_mm=58,
        cols=1, rows=1, is_label=True,
    ),
}


# Combined presets dict (sheet presets first, then label presets)
PRESETS = {**SHEET_PRESETS, **LABEL_PRESETS}


def is_label_preset_key(key: str) -> bool:
    """True if the key refers to a label-printer preset."""
    return key in LABEL_PRESETS


def custom_layout(name: str, paper_w: float, paper_h: float,
                  sticker_w: float, sticker_h: float,
                  margin_x: float, margin_y: float,
                  gap_x: float, gap_y: float,
                  is_label: bool = False) -> StickerLayout:
    """Build a custom layout, auto-calculating cols/rows."""
    if is_label:
        # For label printers: paper == sticker, 1 per page
        return StickerLayout(
            name=name,
            paper_w_mm=paper_w, paper_h_mm=paper_h,
            margin_x_mm=margin_x, margin_y_mm=margin_y,
            gap_x_mm=0, gap_y_mm=0,
            sticker_w_mm=sticker_w, sticker_h_mm=sticker_h,
            cols=1, rows=1,
            is_label=True,
        )
    avail_w = paper_w - 2 * margin_x
    avail_h = paper_h - 2 * margin_y
    cols = max(1, int((avail_w + gap_x) // (sticker_w + gap_x)))
    rows = max(1, int((avail_h + gap_y) // (sticker_h + gap_y)))
    return StickerLayout(
        name=name,
        paper_w_mm=paper_w, paper_h_mm=paper_h,
        margin_x_mm=margin_x, margin_y_mm=margin_y,
        gap_x_mm=gap_x, gap_y_mm=gap_y,
        sticker_w_mm=sticker_w, sticker_h_mm=sticker_h,
        cols=cols, rows=rows,
        is_label=False,
    )


def sticker_positions(layout: StickerLayout) -> List[tuple]:
    """Return list of (x_mm, y_mm) top-left positions for each sticker slot."""
    out = []
    for r in range(layout.rows):
        for c in range(layout.cols):
            x = layout.margin_x_mm + c * (layout.sticker_w_mm + layout.gap_x_mm)
            y = layout.margin_y_mm + r * (layout.sticker_h_mm + layout.gap_y_mm)
            out.append((x, y))
    return out


def total_slots(layout: StickerLayout) -> int:
    return layout.cols * layout.rows
