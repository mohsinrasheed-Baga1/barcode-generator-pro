"""
Render a full A4 sheet of 40 sample stickers for visual verification.
"""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, '/home/z/my-project/barcode-generator')

from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

from core.layouts import PRESETS
from core.printer import render_preview

items = []
base_barcodes = [f'50123456789{i:02d}' for i in range(40)]
for i, bc in enumerate(base_barcodes):
    items.append({
        'company_name': 'ABC Traders',
        'product_name': f'Soap Pack {i+1}',
        'product_code': f'SL-{i+1:03d}',
        'barcode': bc[:12],  # 12 digits — checksum auto-added
        'mfg_date': '2025-01-01',
        'exp_date': '2026-01-01',
        'mobile': '+92 300 1234567',
    })

lay = PRESETS['A4-40']
pix = render_preview(lay, items, dpi=180)
out = '/home/z/my-project/barcode-generator/build/sample_full_sheet.png'
pix.save(out)
print(f'Saved full sheet preview: {pix.width()}x{pix.height()} -> {out}')

# Also render A4-24 (larger stickers)
lay2 = PRESETS['A4-24']
items24 = items[:24]
pix2 = render_preview(lay2, items24, dpi=180)
out2 = '/home/z/my-project/barcode-generator/build/sample_A4_24.png'
pix2.save(out2)
print(f'Saved A4-24 preview: {pix2.width()}x{pix2.height()} -> {out2}')
