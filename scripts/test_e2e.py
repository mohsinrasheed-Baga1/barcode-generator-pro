"""
End-to-end test: launches the MainWindow, programmatically fills in fields,
adds stickers, and prints to PDF to verify the full pipeline.
"""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, '/home/z/my-project/barcode-generator')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QDate, QTimer, QSizeF
from PyQt5.QtGui import QPageSize, QPageLayout
from PyQt5.QtPrintSupport import QPrinter

app = QApplication(sys.argv)

from ui.main_window import MainWindow
from core.layouts import PRESETS
from core.printer import print_sticker_sheet

win = MainWindow()

# Fill in fields
win.company_edit.setText("ABC Traders Pakistan")
win.product_edit.setText("Sunlight Soap 200g")
win.code_edit.setText("SL-001")
win.barcode_edit.setText("501234567890")
win.mfg_date.setDate(QDate(2025, 1, 15))
win.exp_date.setDate(QDate(2026, 1, 15))
win.mobile_edit.setText("+92 300 1234567")

# Add 5 stickers
win.qty_spin.setValue(5)
win.on_add_clicked()
assert len(win.current_items) == 5, f"Expected 5 items, got {len(win.current_items)}"
print(f"[OK] Added {len(win.current_items)} stickers")

# Switch to A4-24 layout (bigger stickers)
idx = win.layout_combo.findData('A4-24')
if idx >= 0:
    win.layout_combo.setCurrentIndex(idx)
lay = win._current_layout()
print(f"[OK] Switched to {lay.name}, {lay.cols}x{lay.rows} stickers")

# Test switching to custom
idx = win.layout_combo.findData('A4-12')
if idx >= 0:
    win.layout_combo.setCurrentIndex(idx)
lay = win._current_layout()
print(f"[OK] Switched to {lay.name}, sticker {lay.sticker_w_mm}x{lay.sticker_h_mm}mm")

# Test preview rendering
pix = win.preview_label.pixmap()
print(f"[OK] Preview pixmap: {pix.width()}x{pix.height()}")

# Test history dialog (1 unique entry expected — quantity does NOT multiply db rows)
from ui.history_dialog import HistoryDialog
dlg = HistoryDialog(win.db, win)
print(f"[OK] History has {dlg.model.rowCount()} entries")
assert dlg.model.rowCount() >= 1
dlg.close()

# Test printing to PDF
out_pdf = '/home/z/my-project/barcode-generator/build/test_print.pdf'
os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
printer = QPrinter(QPrinter.HighResolution)
printer.setOutputFormat(QPrinter.PdfFormat)
printer.setOutputFileName(out_pdf)
lay = PRESETS['A4-40']
printer.setPageSize(QPageSize(QSizeF(lay.paper_w_mm, lay.paper_h_mm), QPageSize.Millimeter))
printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)

# Build items to print
items = []
for i in range(8):
    items.append({
        'company_name': 'Test Co',
        'product_name': f'Product {i+1}',
        'product_code': f'PC-{i+1:03d}',
        'barcode': f'50123456789{i:02d}',
        'mfg_date': '2025-01-01',
        'exp_date': '2026-01-01',
        'mobile': '+92 300 1234567',
    })

print_sticker_sheet(lay, items, printer=printer, copies=1)
print(f"[OK] PDF saved: {os.path.getsize(out_pdf)} bytes -> {out_pdf}")

# Test CSV import (with the sample CSV from assets)
sample_csv = '/home/z/my-project/barcode-generator/assets/sample_barcodes.csv'
from core.csv_import import import_csv
rows = import_csv(sample_csv,
                  default_company='Test Co',
                  default_mobile='+92 300 1234567')
print(f"[OK] CSV import: {len(rows)} rows loaded")
assert len(rows) > 0
assert rows[0].get('company_name') == 'ABC Traders'
assert rows[0].get('barcode', '').isdigit()

# Test settings dialog
from ui.settings_dialog import SettingsDialog
sdlg = SettingsDialog(win.db, win)
sdlg.font_company.setValue(11)
sdlg.def_company.setText("Default Co")
sdlg.on_save()  # triggers save
print(f"[OK] Settings saved")

# Reload settings (read directly from db to verify persistence)
import json
fs_raw = win.db.get_setting('font_sizes_json', '')
fs = json.loads(fs_raw) if fs_raw else {}
print(f"[OK] Font sizes saved in DB: {fs}")
assert fs.get('company') == 11, f"Expected 11, got {fs.get('company')}"

# Verify db stored settings
assert win.db.get_setting('default_company') == 'Default Co'
print(f"[OK] DB stored 'Default Co'")

print("\n=== END-TO-END TEST PASSED ===")
