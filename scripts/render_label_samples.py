"""
Render a sample label-printer preview (50x30mm label) for documentation.
"""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, '/home/z/my-project/barcode-generator')

from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

from core.layouts import LABEL_PRESETS
from core.printer import render_preview

items = [{
    'company_name': 'ABC Traders',
    'product_name': 'Sunlight Soap',
    'product_code': 'SL-001',
    'barcode': '501234567890',
    'mfg_date': '2025-01-01',
    'exp_date': '2026-01-01',
    'mobile': '+92 300 1234567',
}]

# Render a few label sizes
for key in ['LBL-50x30', 'LBL-60x40', 'LBL-100x50']:
    lay = LABEL_PRESETS[key]
    pix = render_preview(lay, items, dpi=120)
    # Convert key to filename
    fname = key.replace('x', '_').lower() + '_preview.png'
    out = f'/home/z/my-project/barcode-generator/assets/sample_{fname}'
    pix.save(out)
    print(f"  {key}: {pix.width()}x{pix.height()} -> {out}")

# Also render a "queue" preview: 3 different labels stacked
print("\nMulti-label preview:")
items3 = []
for i, bc in enumerate(['501234567890', '501234567891', '501234567892']):
    items3.append({
        'company_name': 'ABC Traders',
        'product_name': f'Product {i+1}',
        'product_code': f'P-{i+1:03d}',
        'barcode': bc,
        'mfg_date': '2025-01-01',
        'exp_date': '2026-01-01',
        'mobile': '+92 300 1234567',
    })
lay = LABEL_PRESETS['LBL-50x30']
pix = render_preview(lay, items3[:1], dpi=120)  # Only 1 fits per "page" in label mode
pix.save('/home/z/my-project/barcode-generator/assets/sample_lbl_50x30_single.png')
print(f"  Single label: {pix.width()}x{pix.height()}")
