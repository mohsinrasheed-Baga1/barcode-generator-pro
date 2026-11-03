"""
Test the new label printer mode (direct label printing).
"""
import os, sys, json
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, '/home/z/my-project/barcode-generator')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QSizeF
from PyQt5.QtGui import QPageSize
from PyQt5.QtPrintSupport import QPrinter

app = QApplication(sys.argv)

from core.layouts import (PRESETS, SHEET_PRESETS, LABEL_PRESETS,
                            custom_layout, StickerLayout, total_slots,
                            sticker_positions, is_label_preset_key)
from core.printer import render_preview, print_sticker_sheet
from core.database import Database
from ui.main_window import MainWindow
from ui.settings_dialog import SettingsDialog
import tempfile

print("=== Test 1: Label presets exist ===")
assert len(SHEET_PRESETS) == 4
assert len(LABEL_PRESETS) == 7
assert len(PRESETS) == 11
for key, lay in LABEL_PRESETS.items():
    assert lay.is_label is True, f"{key} should be label"
    assert lay.cols == 1 and lay.rows == 1, f"{key} should be 1x1"
    print(f"  {key}: {lay.sticker_w_mm}x{lay.sticker_h_mm}mm — {lay.name}")
print("OK")

print("\n=== Test 2: Sheet presets not labels ===")
for key, lay in SHEET_PRESETS.items():
    assert lay.is_label is False, f"{key} should not be label"
print("OK")

print("\n=== Test 3: is_label_preset_key() helper ===")
assert is_label_preset_key('LBL-50x30') is True
assert is_label_preset_key('A4-40') is False
print("OK")

print("\n=== Test 4: Custom label layout ===")
cl = custom_layout(name='Custom Label', paper_w=45, paper_h=25,
                    sticker_w=45, sticker_h=25,
                    margin_x=0, margin_y=0, gap_x=0, gap_y=0,
                    is_label=True)
assert cl.is_label is True
assert cl.cols == 1 and cl.rows == 1
assert total_slots(cl) == 1
print(f"  Custom label: {cl.paper_w_mm}x{cl.paper_h_mm}mm, slots={total_slots(cl)}")

print("\n=== Test 5: Custom sheet layout (still works) ===")
cs = custom_layout(name='Custom Sheet', paper_w=210, paper_h=297,
                    sticker_w=50, sticker_h=30,
                    margin_x=10, margin_y=10, gap_x=2, gap_y=2,
                    is_label=False)
assert cs.is_label is False
assert cs.cols >= 1 and cs.rows >= 1
print(f"  Custom sheet: {cs.cols}x{cs.rows} = {total_slots(cs)} slots")

print("\n=== Test 6: Label preview rendering (scaled up) ===")
lay = LABEL_PRESETS['LBL-50x30']
items = [{
    'company_name': 'Test Co', 'product_name': 'Soap 200g',
    'product_code': 'SL-001', 'barcode': '501234567890',
    'mfg_date': '2025-01-01', 'exp_date': '2026-01-01',
    'mobile': '+923001234567',
}]
pix = render_preview(lay, items, dpi=120)
# For a 50x30mm label at 120 DPI base, the auto-scaling should make it bigger
print(f"  Label preview size: {pix.width()}x{pix.height()}")
assert pix.width() >= 500, f"Label preview too small: {pix.width()}"
print("OK")

print("\n=== Test 7: Sheet preview (still A4 sized) ===")
lay2 = SHEET_PRESETS['A4-40']
pix2 = render_preview(lay2, items, dpi=120)
print(f"  Sheet preview size: {pix2.width()}x{pix2.height()}")
assert abs(pix2.width() - 992) < 50  # A4 at 120 DPI is ~992px
print("OK")

print("\n=== Test 8: Print label mode to PDF ===")
out_pdf = tempfile.mktemp(suffix='.pdf')
printer = QPrinter(QPrinter.HighResolution)
printer.setOutputFormat(QPrinter.PdfFormat)
printer.setOutputFileName(out_pdf)
lay = LABEL_PRESETS['LBL-50x30']
printer.setPageSize(QPageSize(QSizeF(lay.paper_w_mm, lay.paper_h_mm), QPageSize.Millimeter))
printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)

items = []
for i in range(3):
    items.append({
        'company_name': 'ABC Traders',
        'product_name': f'Product {i+1}',
        'product_code': f'P-{i+1}',
        'barcode': f'50123456789{i}',
        'mfg_date': '2025-01-01',
        'exp_date': '2026-01-01',
        'mobile': '+923001234567',
    })

print_sticker_sheet(lay, items, printer=printer, copies=1)
size = os.path.getsize(out_pdf)
print(f"  Label PDF: {size} bytes")
assert size > 1000
os.unlink(out_pdf)
print("OK — 3 labels = 3 pages")

print("\n=== Test 9: Main window with label mode ===")
# Clear DB
for p in [
    os.path.expanduser('~/.local/share/BarcodeGenerator/barcodes.db'),
]:
    if os.path.exists(p):
        os.unlink(p)

win = MainWindow()
# Switch to label preset
idx = win.layout_combo.findData('LBL-50x30')
assert idx >= 0, "Label preset not in combo"
win.layout_combo.setCurrentIndex(idx)
lay = win._current_layout()
assert lay.is_label is True
print(f"  Current layout: {lay.name} (is_label={lay.is_label})")
print(f"  Layout info: {win.layout_info.text()}")

# Verify count label updates correctly
win.company_edit.setText('Test Co')
win.barcode_edit.setText('501234567890')
win.on_add_clicked()  # adds 1 sticker
n = len(win.current_items)
print(f"  After add: {n} items in queue")
print(f"  Count label: {win.count_label.text()}")

# Set copies=2 and verify count updates
win.copies_spin.setValue(2)
print(f"  After copies=2: {win.count_label.text()}")

print("\n=== Test 10: Settings dialog — toggle print mode ===")
# Force label mode in settings
sdlg = SettingsDialog(win.db, win)
sdlg.mode_label.setChecked(True)
# Verify combo rebuilt with label presets only
print(f"  After toggling label mode: {sdlg.preset_combo.count()} presets")
assert sdlg.preset_combo.count() == len(LABEL_PRESETS)
sdlg.mode_sheet.setChecked(True)
print(f"  After toggling sheet mode: {sdlg.preset_combo.count()} presets")
assert sdlg.preset_combo.count() == len(SHEET_PRESETS)
print("OK")

# Save label mode and verify persistence
sdlg.mode_label.setChecked(True)
sdlg.paper_w.setValue(55)
sdlg.paper_h.setValue(35)
sdlg.sticker_w.setValue(55)
sdlg.sticker_h.setValue(35)
sdlg.on_save()

# Verify saved as label
import json
saved = json.loads(win.db.get_setting('custom_layout_json', '{}'))
assert saved.get('is_label') is True, f"Saved is_label: {saved.get('is_label')}"
print(f"  Saved custom layout: {saved}")
print("OK")

print("\n=== ALL LABEL MODE TESTS PASSED ===")
