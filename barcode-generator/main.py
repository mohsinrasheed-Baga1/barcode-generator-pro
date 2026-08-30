"""
Barcode Generator Pro — entry point.
"""
import sys
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from ui.main_window import MainWindow, APP_TITLE


def resource_path(rel: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BarcodeGeneratorPro")
    app.setOrganizationName("BarcodeGenerator")
    app.setWindowIcon(QIcon(resource_path("assets/icon.ico")))

    # Apply a clean, professional Qt stylesheet
    app.setStyleSheet("""
        QMainWindow, QDialog { background: #f5f5f7; }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #c8c8c8;
            border-radius: 6px;
            margin-top: 12px;
            padding: 10px 6px 6px 6px;
            background: #ffffff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 6px;
            background: #ffffff;
        }
        QPushButton {
            padding: 6px 12px;
            border: 1px solid #b0b0b0;
            border-radius: 4px;
            background: #f8f8f8;
            color: #222;
        }
        QPushButton:hover {
            background: #e8f0ff;
            border-color: #1a4d8f;
        }
        QPushButton:pressed { background: #d0e0ff; }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
            padding: 4px 6px;
            border: 1px solid #b0b0b0;
            border-radius: 3px;
            background: #ffffff;
        }
        QTableView {
            gridline-color: #d0d0d0;
            background: #ffffff;
            selection-background-color: #1a4d8f;
            selection-color: #ffffff;
        }
        QHeaderView::section {
            background: #e8e8e8;
            padding: 4px;
            border: 0;
            border-right: 1px solid #c8c8c8;
            font-weight: bold;
        }
        QLabel { color: #222; }
        QTabWidget::pane { border: 1px solid #c8c8c8; background: #ffffff; }
        QTabBar::tab { padding: 6px 14px; }
    """)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
