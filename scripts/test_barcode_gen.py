"""
Quick smoke test: import core modules and render a sample sticker preview.
Runs headless (no window) using QApplication's offscreen platform.
"""
import os
import sys

# Force offscreen rendering so we don't need a display
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, '/home/z/my-project/barcode-generator')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

app = QApplication(sys.argv)

from core.barcode_gen import (make_full_ean13, validate_ean13,
                                generate_ean13_image, draw_sticker,
                                make_fonts, ean13_checksum)
from core.layouts import PRESETS, sticker_positions, total_slots, custom_layout
from core.printer import render_preview
from core.csv_import import write_csv_template, import_csv
from core.database import Database
import tempfile

print("=== Test 1: EAN-13 checksum ===")
result = make_full_ean13("501234567890")
assert len(result) == 13, f"Bad length: {result}"
assert validate_ean13(result), f"Invalid checksum: {result}"
print(f"  501234567890 -> {result} OK")

print("=== Test 2: Barcode image ===")
img, code = generate_ean13_image("501234567890")
print(f"  Image size: {img.width()}x{img.height()}, code: {code}")
assert img.width() > 0 and img.height() > 0

print("=== Test 3: Layouts ===")
for key, lay in PRESETS.items():
    pos = sticker_positions(lay)
    print(f"  {key}: {lay.cols}x{lay.rows} = {len(pos)} stickers, sticker {lay.sticker_w_mm}x{lay.sticker_h_mm}mm")
    assert len(pos) == total_slots(lay)

print("=== Test 4: Custom layout ===")
cl = custom_layout("Custom", 210, 297, 50, 30, 10, 10, 2, 2)
print(f"  Custom: {cl.cols}x{cl.rows} = {total_slots(cl)} stickers")

print("=== Test 5: CSV template + import ===")
tmp = tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w')
tmp.close()
write_csv_template(tmp.name)
rows = import_csv(tmp.name)
print(f"  Template imported {len(rows)} rows")
assert len(rows) == 3
os.unlink(tmp.name)

print("=== Test 6: Database ===")
tmpdb = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
tmpdb.close()
db = Database(tmpdb.name)
id1 = db.save_barcode({
    'company_name': 'Test Co', 'barcode': '501234567890',
    'mfg_date': '2025-01-01', 'exp_date': '2026-01-01',
    'mobile': '+923001234567'
})
rows = db.list_barcodes()
print(f"  Saved id={id1}, list has {len(rows)} rows")
assert len(rows) == 1
db.set_setting('foo', 'bar')
assert db.get_setting('foo') == 'bar'
db.close()
os.unlink(tmpdb.name)

print("=== Test 7: Render preview ===")
items = []
for i in range(3):
    items.append({
        'company_name': f'Test Co #{i+1}',
        'product_name': f'Soap Pack {i+1}',
        'product_code': f'SL-{i+1:03d}',
        'barcode': f'50123456789{i}',
        'mfg_date': '2025-01-01',
        'exp_date': '2026-01-01',
        'mobile': '+923001234567',
    })
lay = PRESETS['A4-40']
pix = render_preview(lay, items, dpi=100)
print(f"  Preview: {pix.width()}x{pix.height()}")
assert pix.width() > 0

# Save preview as PNG for visual check
out_dir = '/home/z/my-project/barcode-generator/build'
os.makedirs(out_dir, exist_ok=True)
pix.save(os.path.join(out_dir, 'sample_preview.png'))
print(f"  Saved preview to {out_dir}/sample_preview.png")

print("\n=== ALL TESTS PASSED ===")
