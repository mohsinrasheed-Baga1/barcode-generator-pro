"""
Import audit test — ensures all Qt classes used in the codebase are actually
imported in the files that use them. Catches bugs like the v2.0.3
'QSizeF is not defined' issue before they reach users.
"""
import os
import re
import sys
import ast

PROJECT_DIR = '/home/z/my-project/barcode-generator'

# Qt classes we want to track
QT_CLASSES = ['QSizeF', 'QSize', 'QRectF', 'QRect', 'QPageSize', 'QPrinter',
              'QPrinterInfo', 'QPageSetupDialog', 'QPrintDialog',
              'QPrintPreviewDialog', 'QPainter', 'QPixmap', 'QImage',
              'QColor', 'QFont', 'QPen', 'QBrush', 'QPalette',
              'QStandardItem', 'QStandardItemModel', 'QIcon',
              'QTransform', 'QFontDatabase', 'QColorDialog',
              'QGraphicsScene', 'QGraphicsView', 'QGraphicsRectItem',
              'QGraphicsItem', 'QGraphicsTextItem', 'QButtonGroup']

errors = []

def get_imported_names(filepath: str) -> set:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    local = alias.asname if alias.asname else alias.name
                    names.add(local)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname if alias.asname else alias.name.split('.')[0]
                    names.add(local)
        return names
    except Exception:
        return set()

def find_class_usages(filepath: str, classes: list) -> dict:
    used = {c: [] for c in classes}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith('from ') or stripped.startswith('import ') or stripped.startswith('#'):
                continue
            for c in classes:
                pattern = r'\b' + re.escape(c) + r'\b'
                if re.search(pattern, line):
                    used[c].append(i)
        return used
    except Exception:
        return used

def check_file(filepath: str):
    imported = get_imported_names(filepath)
    used = find_class_usages(filepath, QT_CLASSES)
    for cls, lines in used.items():
        if lines and cls not in imported:
            errors.append(f"{filepath}:{lines[0]}: uses '{cls}' but NOT imported")

for root, dirs, files in os.walk(PROJECT_DIR):
    if '/build' in root or '/dist' in root or '/.git' in root or '__pycache__' in root:
        continue
    for f in files:
        if f.endswith('.py'):
            check_file(os.path.join(root, f))

print("=== Testing main_window imports ===")
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, PROJECT_DIR)
try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    from ui.main_window import MainWindow
    from ui.print_setup_dialog import PrintSetupDialog
    from ui.sticker_editor import StickerEditorDialog
    from ui.settings_dialog import SettingsDialog
    print("✓ All UI modules imported successfully")
    win = MainWindow()
    print(f"✓ MainWindow instantiated: {win.windowTitle()}")
except Exception as e:
    errors.append(f"Failed to import or instantiate: {e}")
    import traceback
    traceback.print_exc()

print()
if errors:
    print(f"❌ FOUND {len(errors)} import issues:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("✓ All Qt classes used in the codebase are properly imported")
