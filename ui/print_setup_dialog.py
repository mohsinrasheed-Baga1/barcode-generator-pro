"""
Custom Print Setup Dialog — replaces QPrintDialog which is unreliable
in PyInstaller-bundled apps on Windows.

This dialog:
- Lists all installed printers via QPrinterInfo.availablePrinters()
- Lets the user pick a printer (default = system default)
- Lets the user set copies count
- Shows the layout info (size, mode)
- Shows the selected printer's actual page size with match indicator
- Has a "Properties" button to open the printer's native properties
- Has a "Test Print" button to print 1 sample label
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

    def __init__(self, layout, default_copies: int = 1, parent=None,
                 test_print_callback=None):
        super().__init__(parent)
        self.layout_obj = layout
        self.test_print_callback = test_print_callback
        self.setWindowTitle("Print Setup / پرنٹ سیٹ اپ")
        self.resize(540, 540)

        # Find available printers
        self.printers = QPrinterInfo.availablePrinters()
        self.default_printer = QPrinterInfo.defaultPrinter()

        self._build_ui(default_copies)
        # Initial printer page size display
        self._update_printer_info()

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
        # Update printer info display when selection changes
        self.printer_combo.currentIndexChanged.connect(self._update_printer_info)
        pl.addRow("Printer:", self.printer_combo)

        # Properties button — opens the native printer properties dialog
        self.props_btn = QPushButton("⚙ Printer Properties / پرنٹر خصوصیات")
        self.props_btn.clicked.connect(self.on_properties_clicked)
        if not self.printers:
            self.props_btn.setEnabled(False)
        pl.addRow("", self.props_btn)

        v.addWidget(printer_box)

        # ---- Printer info display ----
        self.printer_info_label = QLabel("Loading printer info...")
        self.printer_info_label.setStyleSheet("""
            background: #f5f5f5;
            border: 1px solid #ddd;
            padding: 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 11px;
        """)
        self.printer_info_label.setWordWrap(True)
        self.printer_info_label.setTextFormat(Qt.RichText)
        v.addWidget(self.printer_info_label)

        # ---- Copies ----
        copies_box = QGroupBox("Copies / کاپیاں")
        cl = QFormLayout(copies_box)
        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 999)
        self.copies_spin.setValue(default_copies)
        cl.addRow("Number of copies:", self.copies_spin)
        v.addWidget(copies_box)

        # ---- Test Print button ----
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("🧪 Test Print — Print 1 Label / ٹیسٹ پرنٹ")
        self.test_btn.setStyleSheet("background: #f0f0f0; padding: 8px;")
        self.test_btn.clicked.connect(self.on_test_print_clicked)
        if not self.printers or self.test_print_callback is None:
            self.test_btn.setEnabled(False)
        test_row.addWidget(self.test_btn)
        test_row.addStretch(1)
        v.addLayout(test_row)

        # ---- Help text ----
        help_text = QLabel(
            "<b>اہم ہدایات / Important tips:</b><br>"
            "★ اگر آپ کا لیبل 1.5×1 انچ ہے تو 'LBL-1.5x1in' preset استعمال کریں<br>"
            "★ '⚙ Printer Properties' میں جا کر label size وہی set کریں جو software میں selected ہے<br>"
            "★ اگر '✗ NO' دکھائی دے تو printer کا page size layout سے مختلف ہے — properties میں درست کریں<br>"
            "• اگر print نہ نکلے تو 'Save as PDF' استعمال کریں"
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

    def _update_printer_info(self):
        """Show the selected printer's actual page size, with match indicator."""
        info = self.printer_combo.currentData()
        if info is None or info.isNull():
            self.printer_info_label.setText(
                "<b style='color:#c62828'>⚠ کوئی پرنٹر منتخب نہیں</b>"
            )
            return
        try:
            # Create a temporary QPrinter to read its page layout
            printer = QPrinter(info, QPrinter.PrinterResolution)
            pl = printer.pageLayout()
            ps = pl.pageSize()
            sz_mm = ps.size(QPageSize.Millimeter)
            actual_w = sz_mm.width()
            actual_h = sz_mm.height()
            lay = self.layout_obj
            # Check if matches
            match = (abs(actual_w - lay.paper_w_mm) < 1.0
                     and abs(actual_h - lay.paper_h_mm) < 1.0)
            match_html = (
                "<b style='color:#2e7d32'>✓ MATCHES layout — perfect!</b>"
                if match else
                f"<b style='color:#c62828'>✗ مختلف — printer پر size درست کریں!</b><br>"
                f"  Required: {lay.paper_w_mm} × {lay.paper_h_mm} mm"
            )
            dpi = printer.resolution()
            self.printer_info_label.setText(
                f"<b>{info.printerName()}</b><br>"
                f"Page size (mm): <b>{actual_w:.2f} × {actual_h:.2f}</b> "
                f"({actual_w / 25.4:.2f} × {actual_h / 25.4:.2f} in)<br>"
                f"Resolution: {dpi} DPI<br>"
                f"Layout paper: {lay.paper_w_mm} × {lay.paper_h_mm} mm<br>"
                f"{match_html}"
            )
        except Exception as e:
            self.printer_info_label.setText(
                f"<b style='color:#c62828'>Error reading printer info:</b><br>{e}"
            )

    def on_properties_clicked(self):
        """Open the native printer properties dialog for the selected printer."""
        info = self.printer_combo.currentData()
        if info is None or info.isNull():
            QMessageBox.warning(self, "No printer",
                                "Please select a printer first.")
            return
        try:
            printer = QPrinter(info, QPrinter.PrinterResolution)
            lay = self.layout_obj
            printer.setPageSize(QPageSize(
                QSizeF(lay.paper_w_mm, lay.paper_h_mm),
                QPageSize.Millimeter
            ))
            printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
            printer.setFullPage(True)
            dlg = QPageSetupDialog(printer, self)
            dlg.exec_()
            # After dialog, refresh printer info
            self._update_printer_info()
        except Exception as e:
            QMessageBox.warning(self, "Properties",
                f"Could not open printer properties:\n{e}\n\n"
                f"You can still print — just click Print.")

    def on_test_print_clicked(self):
        """Print a single test label to verify the setup."""
        if self.test_print_callback is None:
            QMessageBox.information(self, "Test Print",
                "Test print not available from this context.")
            return
        try:
            info = self.printer_combo.currentData()
            if info is None or info.isNull():
                QMessageBox.warning(self, "No printer",
                                    "Please select a printer first.")
                return
            msg = QMessageBox.question(
                self,
                "Test Print Confirmation",
                f"Print 1 test label to:\n  {info.printerName()}\n\n"
                f"This will print just 1 label as a test.\n"
                f"Make sure your printer is ON and has labels loaded."
            )
            if msg != QMessageBox.Yes:
                return
            # Call the test print callback
            self.test_print_callback(info)
        except Exception as e:
            QMessageBox.critical(self, "Test Print Failed",
                f"Test print error:\n{e}")

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
        printer.setFullPage(True)  # CRITICAL for label printers
        printer.setCopyCount(self.copies_spin.value())
        return printer
