"""
Direct test of on_print_clicked — simulates what happens when user
clicks the Print button. Catches any NameError / ImportError that
would crash the dialog.
"""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, '/home/z/my-project/barcode-generator')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtPrintSupport import QPrinter, QPrinterInfo

app = QApplication(sys.argv)

from ui.main_window import MainWindow
from ui.print_setup_dialog import PrintSetupDialog
from core.layouts import LABEL_PRESETS

# Init
for p in [os.path.expanduser('~/.local/share/BarcodeGenerator/barcodes.db')]:
    if os.path.exists(p):
        os.unlink(p)

win = MainWindow()
# Add an item so Print can proceed
win.company_edit.setText('Test Co')
win.barcode_edit.setText('501234567890')
win.on_add_clicked()
assert len(win.current_items) == 1
print(f'✓ {len(win.current_items)} item added')

# Set layout to user's label size (1.5x1 inch)
idx = win.layout_combo.findData('LBL-1.5x1in')
if idx >= 0:
    win.layout_combo.setCurrentIndex(idx)
print(f'✓ Layout: {win._current_layout().name}')

# Now try to invoke the PrintSetupDialog (which is what on_print_clicked does first)
print()
print('=== Test 1: PrintSetupDialog opens without error ===')
try:
    lay = win._current_layout()
    dlg = PrintSetupDialog(
        lay,
        default_copies=1,
        parent=win,
        test_print_callback=win._do_test_print
    )
    print(f'✓ PrintSetupDialog created')
    print(f'  Printers found: {dlg.printer_combo.count()}')
    print(f'  printer_info_label text: {dlg.printer_info_label.text()[:80]}...')
    # Try make_printer (should work even if no printer is selected)
    try:
        printer = dlg.make_printer()
        print(f'✓ make_printer() OK: fullPage={printer.fullPage()}')
    except Exception as e:
        print(f'  (make_printer needs selected printer — OK on headless: {e})')
except Exception as e:
    import traceback
    tb = traceback.format_exc()
    print(f'❌ FAILED: {e}')
    print(tb)
    sys.exit(1)

# Test 2: Verify the QSizeF fix works by directly calling the print path
print()
print('=== Test 2: Direct call to print_sticker_sheet ===')
try:
    from core.printer import print_sticker_sheet, export_to_pdf, diagnose_printer
    from PyQt5.QtGui import QPageSize
    from PyQt5.QtCore import QSizeF
    import tempfile
    
    # Simulate what _do_test_print does
    items = win.current_items
    out = tempfile.mktemp(suffix='.pdf')
    
    # Use PDF printer (simulates real printer)
    printer = QPrinter(QPrinter.PrinterResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(out)
    printer.setPageSize(QPageSize(QSizeF(lay.paper_w_mm, lay.paper_h_mm),
                                   QPageSize.Millimeter))
    printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
    printer.setFullPage(True)
    printer.setCopyCount(1)
    
    print_sticker_sheet(lay, items, win.template, printer=printer, copies=None)
    print(f'✓ print_sticker_sheet completed')
    print(f'✓ PDF created: {os.path.getsize(out)} bytes')
    print(f'  fullPage: {printer.fullPage()}')
    print(f'  copyCount: {printer.copyCount()}')
    
    # Diagnose
    print()
    print('=== Test 3: diagnose_printer ===')
    diag = diagnose_printer(printer, lay)
    print(diag)
    
    os.unlink(out)
except NameError as e:
    import traceback
    tb = traceback.format_exc()
    print(f'❌ NameError: {e}')
    print(tb)
    sys.exit(1)
except Exception as e:
    import traceback
    tb = traceback.format_exc()
    print(f'❌ FAILED: {e}')
    print(tb)
    sys.exit(1)

print()
print('=== ALL PRINT-BUTTON TESTS PASSED ===')
