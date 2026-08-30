"""
Custom Print Setup Dialog — replaces QPrintDialog which is unreliable
in PyInstaller-bundled apps on Windows.

This dialog:
- Lists all installed printers via QPrinterInfo.availablePrinters()
- Lets the user pick a printer (default = system default)
- Lets the user set copies count
- Shows the layout info (size, mode)
- Has a "Properties" button to open the printer's native properties
- On confirm, returns the chosen QPrinter
"""
from PyQt5.QtCore import Qt, QSizeF
from PyQt5.QtGui import QPageSize, QIcon
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QWidget, QLabel, QComboBox, QSpinBox, QPushButton, QGroupBox,
    QMessageBox, QFrame, QSizePolicy
)
from PyQt5.QtPrintSupport import QPrinter, QPrinterInfo, QPageSetupDialog


class PrintSetupDialog(QDialog):
    """Custom print setup dialog. Returns (printer, copies) on accept."""

    def __init__(self, layout, default_copies: int = 1, parent=None):
        super().__init__(parent)
        self.layout_obj = layout
        self.setWindowTitle("Print Setup / پرنٹ سیٹ اپ")
        self.resize(480, 420)

        # Find available printers
        self.printers = QPrinterInfo.availablePrinters()
        self.default_printer = QPrinterInfo.defaultPrinter()

        self._build_ui(default_copies)

    def _build_ui(self, default_copies: int):
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        # ---- Info banner ----
        lay = self.layout_obj
        mode_label = "🖨 Label Printer Mode" if lay.is_label else "📄 Sheet Printer Mode"
        info = QLabel(
            f"<b>{mode_label}</b><br>"
            f"Layout: {lay.name}<br>"
            f"Page size: {lay.paper_w_mm} × {lay.paper_h_mm} mm<br>"
            f"Sticker size: {lay.sticker_w_mm} × {lay.sticker_h_mm} mm"
        )
        info.setStyleSheet("""
            background: #eef4fb;
            border: 1px solid #b8d4eb;
            padding: 10px;
            color: #1a4d8f;
            border-radius: 4px;
        """)
        info.setTextFormat(Qt.RichText)
        v.addWidget(info)

        # ---- Printer selection ----
        printer_box = QGroupBox("Select Printer / پرنٹر منتخب کریں")
        pl = QFormLayout(printer_box)
        pl.setLabelAlignment(Qt.AlignRight)

        self.printer_combo = QComboBox()
        if not self.printers:
            self.printer_combo.addItem("No printers found", None)
            self.printer_combo.setEnabled(False)
        else:
            default_idx = 0
            for i, p in enumerate(self.printers):
                name = p.printerName()
                if p.isNull():
                    continue
                is_default = (self.default_printer is not None
                              and not self.default_printer.isNull()
                              and p.printerName() == self.default_printer.printerName())
                label = f"{name}  (Default)" if is_default else name
                self.printer_combo.addItem(label, p)
                if is_default:
                    default_idx = self.printer_combo.count() - 1
            self.printer_combo.setCurrentIndex(default_idx)
        pl.addRow("Printer:", self.printer_combo)

        # Properties button — opens the native printer properties dialog
        self.props_btn = QPushButton("⚙ Printer Properties / پرنٹر خصوصیات")
        self.props_btn.clicked.connect(self.on_properties_clicked)
        if not self.printers:
            self.props_btn.setEnabled(False)
        pl.addRow("", self.props_btn)

        v.addWidget(printer_box)

        # ---- Copies ----
        copies_box = QGroupBox("Copies / کاپیاں")
        cl = QFormLayout(copies_box)
        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 999)
        self.copies_spin.setValue(default_copies)
        cl.addRow("Number of copies:", self.copies_spin)
        v.addWidget(copies_box)

        # ---- Help text ----
        help_text = QLabel(
            "<b>Troubleshooting tips / مددگار تجاویز:</b><br>"
            "• If print doesn't come out, check printer is ON and has paper/labels<br>"
            "• Make sure label size in printer Properties matches software<br>"
            "• For label printers (Zebra/TSC/etc.), select printer here, "
            "set label size in Properties<br>"
            "• If still fails, use 'Save as PDF' button instead"
        )
        help_text.setStyleSheet("""
            background: #fff8e1;
            border: 1px solid #ffd54f;
            padding: 8px;
            color: #5d4037;
            border-radius: 4px;
            font-size: 11px;
        """)
        help_text.setTextFormat(Qt.RichText)
        help_text.setWordWrap(True)
        v.addWidget(help_text)

        v.addStretch(1)

        # ---- Buttons ----
        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btn_box.button(QDialogButtonBox.Ok).setText("🖨 Print / پرنٹ")
        btn_box.button(QDialogButtonBox.Cancel).setText("Cancel / منسوخ")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        v.addWidget(btn_box)

    def on_properties_clicked(self):
        """Open the native printer properties dialog for the selected printer."""
        info = self.printer_combo.currentData()
        if info is None or info.isNull():
            QMessageBox.warning(self, "No printer",
                                "Please select a printer first.")
            return
        try:
            printer = QPrinter(info, QPrinter.PrinterResolution)
            # Set page size to our layout's size
            lay = self.layout_obj
            printer.setPageSize(QPageSize(
                QSizeF(lay.paper_w_mm, lay.paper_h_mm),
                QPageSize.Millimeter
            ))
            printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
            dlg = QPageSetupDialog(printer, self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Properties",
                f"Could not open printer properties:\n{e}\n\n"
                f"You can still print — just click Print.")

    def selected_printer_info(self) -> QPrinterInfo:
        info = self.printer_combo.currentData()
        if info is None or info.isNull():
            return None
        return info

    def selected_copies(self) -> int:
        return self.copies_spin.value()

    def make_printer(self) -> QPrinter:
        """Build a QPrinter from the user's selections."""
        info = self.selected_printer_info()
        if info is None:
            raise RuntimeError("No printer selected")
        # Use PrinterResolution mode for best label-printer compatibility
        printer = QPrinter(info, QPrinter.PrinterResolution)
        lay = self.layout_obj
        printer.setPageSize(QPageSize(
            QSizeF(lay.paper_w_mm, lay.paper_h_mm),
            QPageSize.Millimeter
        ))
        printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
        printer.setCopyCount(self.copies_spin.value())
        return printer
