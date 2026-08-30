"""
Main window for the Barcode Generator (v2.0.4).
"""
import os
import json
import traceback
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QSize, QSizeF, QRectF, QRect, QDate, QTimer
from PyQt5.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QPen,
    QIcon, QStandardItemModel, QStandardItem, QPalette, QPageSize
)
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QComboBox, QSpinBox,
    QDateEdit, QCheckBox, QTableView, QHeaderView, QTabWidget, QSplitter,
    QMessageBox, QFileDialog, QDialog, QGroupBox,
    QScrollArea, QFrame, QSizePolicy, QApplication, QStatusBar,
    QInputDialog, QDialogButtonBox, QListWidget, QListWidgetItem
)
from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog, QPrintDialog, QPrinterInfo

from core.barcode_gen import make_full_ean13, validate_ean13
from core.database import Database
from core.csv_import import import_csv, write_csv_template
from core.layouts import (PRESETS, SHEET_PRESETS, LABEL_PRESETS,
                            custom_layout, StickerLayout, sticker_positions,
                            total_slots, is_label_preset_key)
from core.templates import (StickerTemplate, StickerElement,
                              default_template, template_to_json,
                              template_from_json)
from core.units import MM, IN, get_unit, format_value
from core.printer import (print_sticker_sheet, render_preview,
                            export_to_pdf, render_single_sticker_preview,
                            diagnose_printer)
from ui.settings_dialog import (SettingsDialog, get_font_sizes_from_settings,
                                   get_unit_from_settings)
from ui.history_dialog import HistoryDialog
from ui.sticker_editor import StickerEditorDialog
from ui.print_setup_dialog import PrintSetupDialog


APP_TITLE = "Barcode Generator Pro — EAN-13"
APP_VERSION = "2.0.4"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1240, 820)

        self.db = Database()

        self.current_items = []

        self.default_company = self.db.get_setting('default_company', '')
        self.default_mobile = self.db.get_setting('default_mobile', '')

        self.layout_key = self.db.get_setting('layout_key', 'A4-40')
        self.custom_layout = None

        self.unit = get_unit(get_unit_from_settings(self.db))

        # Template — load from DB or generate default
        template_json = self.db.get_setting('sticker_template_json', '')
        if template_json:
            try:
                self.template = template_from_json(template_json)
            except Exception:
                self.template = default_template(38, 21.2)
        else:
            self.template = default_template(38, 21.2)

        self._build_ui()
        self._refresh_preview()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ---- left: input form ----
        left = QWidget()
        left.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        left.setMaximumWidth(460)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        title = QLabel(f"<h2>{APP_TITLE}</h2><i>Version {APP_VERSION}</i>")
        title.setStyleSheet("color: #1a4d8f;")
        left_layout.addWidget(title)

        form_box = QGroupBox("Sticker Information / اسٹیکر کی معلومات")
        form = QFormLayout(form_box)
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.company_edit = QLineEdit()
        self.company_edit.setPlaceholderText("e.g. ABC Traders / مثال: اے بی سی ٹریڈرز")
        self.company_edit.setText(self.default_company)
        form.addRow("Company Name / کمپنی نام:", self.company_edit)

        self.product_edit = QLineEdit()
        form.addRow("Product Name / پروڈکٹ نام:", self.product_edit)

        self.code_edit = QLineEdit()
        form.addRow("Product Code / پروڈکٹ کوڈ:", self.code_edit)

        self.barcode_edit = QLineEdit()
        self.barcode_edit.setPlaceholderText("12 digits — 13th auto / 12 ہندسے")
        self.barcode_edit.setMaxLength(13)
        self.barcode_enabled_chk = QCheckBox("Include Barcode / بارکوڈ شامل کریں")
        self.barcode_enabled_chk.setChecked(True)
        self.barcode_enabled_chk.toggled.connect(self.on_barcode_enabled_toggled)
        form.addRow("Barcode (EAN-13) / بارکوڈ:", self.barcode_edit)
        form.addRow("", self.barcode_enabled_chk)

        dates_row = QHBoxLayout()
        self.mfg_date = QDateEdit()
        self.mfg_date.setDisplayFormat("yyyy-MM-dd")
        self.mfg_date.setCalendarPopup(True)
        self.mfg_date.setDate(QDate.currentDate())
        dates_row.addWidget(QLabel("Mfg:"))
        dates_row.addWidget(self.mfg_date)

        self.exp_date = QDateEdit()
        self.exp_date.setDisplayFormat("yyyy-MM-dd")
        self.exp_date.setCalendarPopup(True)
        self.exp_date.setDate(QDate.currentDate().addMonths(12))
        dates_row.addWidget(QLabel("Exp:"))
        dates_row.addWidget(self.exp_date)
        dates_row.addStretch(1)
        dates_wrap = QWidget()
        dates_wrap.setLayout(dates_row)
        form.addRow("Dates / تاریخیں:", dates_wrap)

        self.mobile_edit = QLineEdit()
        self.mobile_edit.setText(self.default_mobile)
        form.addRow("Mobile / موبائل:", self.mobile_edit)

        left_layout.addWidget(form_box)

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Quantity / تعداد:"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1000)
        self.qty_spin.setValue(1)
        qty_row.addWidget(self.qty_spin)
        qty_row.addStretch(1)
        left_layout.addLayout(qty_row)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("➕ Add to Sheet\nشیٹ میں شامل کریں")
        self.add_btn.setStyleSheet("background: #1a4d8f; color: white; padding: 8px; font-weight: bold;")
        self.add_btn.clicked.connect(self.on_add_clicked)
        btn_row.addWidget(self.add_btn)

        self.clear_btn = QPushButton("🗑 Clear Sheet\nشیٹ خالی کریں")
        self.clear_btn.clicked.connect(self.on_clear_clicked)
        btn_row.addWidget(self.clear_btn)
        left_layout.addLayout(btn_row)

        bulk_box = QGroupBox("Bulk Import / بلک امپورٹ (CSV)")
        bulk_layout = QVBoxLayout(bulk_box)
        bulk_btns = QHBoxLayout()
        self.import_btn = QPushButton("📂 Import CSV")
        self.import_btn.clicked.connect(self.on_import_csv)
        bulk_btns.addWidget(self.import_btn)
        self.template_btn = QPushButton("📝 Save Template")
        self.template_btn.clicked.connect(self.on_save_template)
        bulk_btns.addWidget(self.template_btn)
        bulk_layout.addLayout(bulk_btns)
        self.bulk_status = QLabel("No file loaded.")
        self.bulk_status.setStyleSheet("color: #555; font-size: 11px;")
        bulk_layout.addWidget(self.bulk_status)
        left_layout.addWidget(bulk_box)

        layout_box = QGroupBox("Sheet Layout / شیٹ سائز")
        layout_form = QFormLayout(layout_box)
        self.layout_combo = QComboBox()
        for key, lay in SHEET_PRESETS.items():
            self.layout_combo.addItem(lay.name, key)
        for key, lay in LABEL_PRESETS.items():
            self.layout_combo.addItem(lay.name, key)
        self.layout_combo.addItem("Custom (set in Settings)...", "__custom__")
        idx = self.layout_combo.findData(self.layout_key)
        if idx >= 0:
            self.layout_combo.setCurrentIndex(idx)
        self.layout_combo.currentIndexChanged.connect(self.on_layout_changed)
        layout_form.addRow("Layout:", self.layout_combo)

        self.layout_info = QLabel("")
        self.layout_info.setStyleSheet("color: #1a4d8f; font-size: 11px; font-weight: bold;")
        layout_form.addRow("", self.layout_info)

        self.edit_layout_btn = QPushButton("✏ Edit Sticker Layout\nاسٹیکر لی آؤٹ ایڈیٹ کریں")
        self.edit_layout_btn.setStyleSheet("background: #f0f0f0; padding: 6px;")
        self.edit_layout_btn.clicked.connect(self.on_edit_layout_clicked)
        layout_form.addRow("", self.edit_layout_btn)

        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 999)
        self.copies_spin.setValue(1)
        self.copies_spin.valueChanged.connect(lambda _: self._refresh_preview())
        layout_form.addRow("Print copies:", self.copies_spin)

        left_layout.addWidget(layout_box)

        # Print buttons — three options
        print_row = QHBoxLayout()
        self.print_btn = QPushButton("🖨 Print\nپرنٹ")
        self.print_btn.setStyleSheet("background: #1a4d8f; color: white; padding: 10px; font-weight: bold;")
        self.print_btn.clicked.connect(self.on_print_clicked)
        print_row.addWidget(self.print_btn)

        self.quick_print_btn = QPushButton("⚡ Quick Print\nفوری پرنٹ")
        self.quick_print_btn.setStyleSheet("background: #2e7d32; color: white; padding: 10px;")
        self.quick_print_btn.clicked.connect(self.on_quick_print_clicked)
        print_row.addWidget(self.quick_print_btn)

        self.pdf_btn = QPushButton("📄 Save as PDF\nPDF محفوظ کریں")
        self.pdf_btn.setStyleSheet("background: #b85c00; color: white; padding: 10px;")
        self.pdf_btn.clicked.connect(self.on_save_pdf_clicked)
        print_row.addWidget(self.pdf_btn)
        left_layout.addLayout(print_row)

        # Preview button (separate row, smaller)
        prev_row = QHBoxLayout()
        self.preview_btn = QPushButton("👁 Preview / پریویو")
        self.preview_btn.clicked.connect(self.on_preview_clicked)
        prev_row.addWidget(self.preview_btn)
        prev_row.addStretch(1)
        left_layout.addLayout(prev_row)

        sec_row = QHBoxLayout()
        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.clicked.connect(self.on_settings_clicked)
        sec_row.addWidget(self.settings_btn)
        self.history_btn = QPushButton("📜 History")
        self.history_btn.clicked.connect(self.on_history_clicked)
        sec_row.addWidget(self.history_btn)
        left_layout.addLayout(sec_row)

        left_layout.addStretch(1)

        # ---- right: preview ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_label = QLabel("Sheet Preview / شیٹ پریویو")
        preview_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        right_layout.addWidget(preview_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setBackgroundRole(QPalette.Mid)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(540, 760)
        self.preview_label.setStyleSheet("background: #999;")
        scroll.setWidget(self.preview_label)
        right_layout.addWidget(scroll, 1)

        self.count_label = QLabel("0 stickers in sheet")
        self.count_label.setStyleSheet("padding: 4px; color: #333;")
        right_layout.addWidget(self.count_label)

        self.items_model = QStandardItemModel(0, 4)
        self.items_model.setHorizontalHeaderLabels(["#", "Barcode", "Product", "Qty"])
        self.items_table = QTableView()
        self.items_table.setModel(self.items_model)
        self.items_table.setMaximumHeight(160)
        self.items_table.setSelectionBehavior(QTableView.SelectRows)
        self.items_table.setEditTriggers(QTableView.NoEditTriggers)
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.items_table)

        del_row = QHBoxLayout()
        self.del_sel_btn = QPushButton("✖ Remove Selected Row")
        self.del_sel_btn.clicked.connect(self.on_remove_selected)
        del_row.addWidget(self.del_sel_btn)
        self.del_all_btn = QPushButton("✖ Clear All")
        self.del_all_btn.clicked.connect(self.on_clear_clicked)
        del_row.addWidget(self.del_all_btn)
        right_layout.addLayout(del_row)

        root.addWidget(left, 0)
        root.addWidget(right, 1)

        self._build_statusbar()
        self._update_layout_info()

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_unit_label = QLabel()
        self.status_template_label = QLabel()
        sb.addWidget(self.status_unit_label)
        sb.addPermanentWidget(self.status_template_label)
        self._update_statusbar()

    def _update_statusbar(self):
        self.status_unit_label.setText(
            f"Unit: {self.unit.label} ({self.unit.symbol})  |  "
            f"Layout: {self._current_layout().name}"
        )
        n_elements = len(self.template.elements)
        n_enabled = sum(1 for e in self.template.elements if e.enabled)
        self.status_template_label.setText(
            f"Template: {n_enabled}/{n_elements} elements enabled"
        )

    # ----------------------------------------------------- barcode toggle
    def on_barcode_enabled_toggled(self, checked: bool):
        for e in self.template.elements:
            if e.id in ('barcode', 'barcode_digits'):
                e.enabled = bool(checked)
        self.barcode_edit.setEnabled(checked)
        self._refresh_preview()
        self._update_statusbar()

    # ----------------------------------------------------- event handlers
    def on_add_clicked(self):
        if self.barcode_enabled_chk.isChecked():
            bc_raw = self.barcode_edit.text().strip()
            if not bc_raw:
                QMessageBox.warning(self, "Missing",
                                    "Please enter a barcode value or uncheck 'Include Barcode'.\n"
                                    "براہ کرم بارکوڈ درج کریں یا 'Include Barcode' کا check ہٹائیں۔")
                return
            try:
                full = make_full_ean13(bc_raw)
            except Exception as e:
                QMessageBox.warning(self, "Invalid barcode",
                                    f"Could not generate EAN-13: {e}")
                return
        else:
            full = ''

        data = {
            'company_name': self.company_edit.text().strip(),
            'product_name': self.product_edit.text().strip(),
            'product_code': self.code_edit.text().strip(),
            'barcode': full,
            'mfg_date': self.mfg_date.date().toString("yyyy-MM-dd"),
            'exp_date': self.exp_date.date().toString("yyyy-MM-dd"),
            'mobile': self.mobile_edit.text().strip(),
        }
        try:
            self.db.save_barcode(data)
        except Exception:
            pass

        qty = self.qty_spin.value()
        for _ in range(qty):
            self.current_items.append(data)
        self._refresh_preview()

    def on_clear_clicked(self):
        self.current_items.clear()
        self._refresh_preview()

    def on_remove_selected(self):
        sm = self.items_table.selectionModel()
        if sm is None:
            return
        rows = sorted([i.row() for i in sm.selectedRows()], reverse=True)
        for r in rows:
            if 0 <= r < len(self.current_items):
                del self.current_items[r]
        self._refresh_preview()

    def on_import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV file", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            rows = import_csv(path,
                             default_company=self.company_edit.text().strip(),
                             default_mobile=self.mobile_edit.text().strip())
        except Exception as e:
            QMessageBox.critical(self, "Import failed",
                                 f"Could not import CSV:\n{e}")
            return
        if not rows:
            QMessageBox.information(self, "Import", "No data rows found in CSV.")
            return
        self.current_items.extend(rows)
        for r in rows:
            try:
                self.db.save_barcode(r)
            except Exception:
                pass
        self.bulk_status.setText(f"Loaded {len(rows)} rows from:\n{os.path.basename(path)}")
        self._refresh_preview()

    def on_save_template(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV template", "barcode_template.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            write_csv_template(path)
            QMessageBox.information(self, "Template saved",
                                   f"Sample template saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def on_layout_changed(self, idx: int):
        key = self.layout_combo.currentData()
        if key == "__custom__":
            prev_key = self.layout_key
            self.on_settings_clicked()
            if self.custom_layout is not None:
                self.layout_key = '__custom__'
            else:
                revert_idx = self.layout_combo.findData(prev_key)
                if revert_idx < 0:
                    revert_idx = 0
                self.layout_combo.blockSignals(True)
                self.layout_combo.setCurrentIndex(revert_idx)
                self.layout_combo.blockSignals(False)
                self.layout_key = self.layout_combo.currentData()
            self._update_layout_info()
            self._refresh_preview()
            return
        self.layout_key = key
        self.db.set_setting('layout_key', key)
        lay = self._current_layout()
        if lay is not None:
            self.template.sticker_w_mm = lay.sticker_w_mm
            self.template.sticker_h_mm = lay.sticker_h_mm
            self.db.set_setting('sticker_template_json', template_to_json(self.template))
        self._update_layout_info()
        self._refresh_preview()

    def _current_layout(self) -> StickerLayout:
        if self.layout_key == '__custom__' and self.custom_layout is not None:
            return self.custom_layout
        return PRESETS.get(self.layout_key, PRESETS['A4-40'])

    def _update_layout_info(self):
        lay = self._current_layout()
        if lay.is_label:
            self.layout_info.setText(
                f"🖨 LABEL PRINTER MODE\n"
                f"Label: {lay.sticker_w_mm} × {lay.sticker_h_mm} mm"
            )
        else:
            self.layout_info.setText(
                f"📄 SHEET PRINTER MODE\n"
                f"{lay.cols}×{lay.rows} = {total_slots(lay)} stickers/sheet\n"
                f"Sticker: {lay.sticker_w_mm} × {lay.sticker_h_mm} mm"
            )
        self._update_statusbar()

    def _refresh_preview(self):
        if not hasattr(self, 'preview_label'):
            return
        lay = self._current_layout()
        try:
            pix = render_preview(lay, self.current_items, self.template, dpi=120)
            self.preview_label.setPixmap(pix)
        except Exception as e:
            self.preview_label.setText(f"Preview error:\n{e}")

        n = len(self.current_items)
        per_sheet = total_slots(lay)
        if lay.is_label:
            if n > 0:
                total_prints = n * self.copies_spin.value()
                self.count_label.setText(
                    f"{n} label(s) × {self.copies_spin.value()} copy = {total_prints} labels will print"
                )
            else:
                self.count_label.setText("0 labels in queue")
        else:
            sheets = (n + per_sheet - 1) // per_sheet if n > 0 else 0
            self.count_label.setText(
                f"{n} stickers — {sheets} sheet(s) will print"
            )

        self.items_model.removeRows(0, self.items_model.rowCount())
        i = 0
        while i < len(self.current_items):
            d = self.current_items[i]
            qty = 1
            j = i + 1
            while (j < len(self.current_items)
                   and self.current_items[j].get('barcode') == d.get('barcode')
                   and self.current_items[j].get('product_code') == d.get('product_code')
                   and self.current_items[j].get('company_name') == d.get('company_name')
                   and self.current_items[j].get('product_name') == d.get('product_name')):
                qty += 1
                j += 1
            idx = self.items_model.rowCount() + 1
            self.items_model.appendRow([
                QStandardItem(str(idx)),
                QStandardItem(d.get('barcode', '') or '(no barcode)'),
                QStandardItem(d.get('product_name') or d.get('product_code') or ''),
                QStandardItem(str(qty)),
            ])
            i = j

    # ----------------------------------------------- print (CUSTOM DIALOG — FIX)
    def on_print_clicked(self):
        """Print button — shows custom PrintSetupDialog (no QPrintDialog).
        This is more reliable in PyInstaller-bundled apps."""
        if not self.current_items:
            QMessageBox.warning(self, "Empty",
                                "Please add at least one sticker first.")
            return
        lay = self._current_layout()

        # Show our custom print setup dialog
        try:
            dlg = PrintSetupDialog(
                lay,
                default_copies=self.copies_spin.value(),
                parent=self,
                test_print_callback=self._do_test_print
            )
            if dlg.exec_() != QDialog.Accepted:
                self.statusBar().showMessage("Print cancelled by user.", 3000)
                return
            printer = dlg.make_printer()
            copies = dlg.selected_copies()
            self.copies_spin.setValue(copies)
        except Exception as e:
            tb = traceback.format_exc()
            QMessageBox.critical(self, "Print setup failed",
                f"Could not open the print setup dialog:\n\n{e}\n\n"
                f"Technical details:\n{tb}\n\n"
                f"Try 'Save as PDF' as a backup option.")
            return

        # Now print using the user's selected printer
        try:
            n_items = len(self.current_items)
            print_sticker_sheet(lay, self.current_items, self.template,
                                 printer=printer, copies=None)  # use printer's copies
            # Success message with diagnostic info
            self.statusBar().showMessage(
                f"✓ Print sent to: {printer.printerName()}  |  "
                f"Copies: {printer.copyCount()}  |  "
                f"Items: {n_items}",
                8000
            )
            QMessageBox.information(
                self, "Print Submitted / پرنٹ بھیج دیا گیا",
                f"✓ Print job submitted to:\n  {printer.printerName()}\n\n"
                f"Copies: {printer.copyCount()}\n"
                f"Items: {n_items}\n\n"
                f"📋 Diagnostic info:\n{diagnose_printer(printer, lay)}\n\n"
                f"If the print doesn't come out within a minute:\n"
                f"  • Check printer is turned ON and has paper/labels\n"
                f"  • Check Windows Print Queue (Control Panel > Devices & Printers)\n"
                f"  • Make sure label size in printer Properties matches software\n\n"
                f"Backup option: Use 'Save as PDF' button to save a PDF,\n"
                f"then open in Adobe Acrobat / Edge and print from there.\n"
                f"(In PDF viewer: set Page Size to 'Actual Size' — no scaling)"
            )
        except Exception as e:
            tb = traceback.format_exc()
            QMessageBox.critical(self, "Print failed / پرنٹ ناکام",
                f"Could not print to {printer.printerName()}:\n\n{e}\n\n"
                f"📋 Diagnostic info:\n{diagnose_printer(printer, lay)}\n\n"
                f"Technical details:\n{tb}\n\n"
                f"Possible causes:\n"
                f"  • Printer is offline or has paper jam\n"
                f"  • Wrong label/paper size in printer Properties — "
                f"required: {lay.paper_w_mm} × {lay.paper_h_mm} mm\n"
                f"  • Printer driver issue\n\n"
                f"Try 'Save as PDF' as a backup — it always works.")

    def _do_test_print(self, printer_info):
        """Print a single test label using the given printer info.
        Uses the first item in queue, or builds a test sample if queue is empty."""
        lay = self._current_layout()
        try:
            if self.current_items:
                test_items = [self.current_items[0]]
            else:
                test_items = [{
                    'company_name': 'TEST PRINT',
                    'product_name': 'Sample Product',
                    'product_code': 'TEST-001',
                    'barcode': '501234567890',
                    'mfg_date': self.mfg_date.date().toString("yyyy-MM-dd"),
                    'exp_date': self.exp_date.date().toString("yyyy-MM-dd"),
                    'mobile': self.mobile_edit.text() or '+92 300 1234567',
                }]
            printer = QPrinter(printer_info, QPrinter.PrinterResolution)
            printer.setPageSize(QPageSize(QSizeF(lay.paper_w_mm, lay.paper_h_mm),
                                           QPageSize.Millimeter))
            printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
            printer.setFullPage(True)
            printer.setCopyCount(1)
            print_sticker_sheet(lay, test_items, self.template,
                                 printer=printer, copies=None)
            QMessageBox.information(
                self, "Test Print Sent / ٹیسٹ پرنٹ بھیج دیا گیا",
                f"✓ Test print sent to:\n  {printer.printerName()}\n\n"
                f"1 test label should now print.\n\n"
                f"📋 Diagnostic info:\n{diagnose_printer(printer, lay)}\n\n"
                f"If the test label comes out correctly:\n"
                f"  → Click '🖨 Print' to print all your labels.\n\n"
                f"If the test print didn't come out correctly:\n"
                f"  1. Use '⚙ Printer Properties' to set label size to "
                f"{lay.paper_w_mm} × {lay.paper_h_mm} mm\n"
                f"  2. Select a different preset that matches your label roll\n"
                f"  3. Use 'Save as PDF' as a backup"
            )
        except Exception as e:
            tb = traceback.format_exc()
            QMessageBox.critical(self, "Test Print Failed / ٹیسٹ پرنٹ ناکام",
                f"Could not test print:\n\n{e}\n\n"
                f"Technical details:\n{tb}")

    def on_quick_print_clicked(self):
        """Quick Print — uses the system default printer, no dialog.
        Best for when you just want to send to your default printer."""
        if not self.current_items:
            QMessageBox.warning(self, "Empty",
                                "Please add at least one sticker first.")
            return
        lay = self._current_layout()

        # Get default printer
        try:
            default_info = QPrinterInfo.defaultPrinter()
            if default_info is None or default_info.isNull():
                QMessageBox.warning(self, "No default printer",
                    "No default printer is set on this system.\n\n"
                    "Please:\n"
                    "  1. Open Windows Settings > Printers & scanners\n"
                    "  2. Set a printer as 'Set as default'\n"
                    "  3. Or use the regular 'Print' button to pick a printer")
                return
            printer_name = default_info.printerName()
        except Exception as e:
            QMessageBox.warning(self, "Error",
                f"Could not get default printer:\n{e}")
            return

        # Ask for confirmation + copies
        copies, ok = QInputDialog.getInt(
            self,
            "Quick Print / فوری پرنٹ",
            f"Send to default printer: {printer_name}\n"
            f"ڈیفالٹ پرنٹر پر بھیجیں\n\n"
            f"Copies / کاپیاں:",
            self.copies_spin.value(), 1, 999, 1
        )
        if not ok:
            return
        self.copies_spin.setValue(copies)

        # Print directly
        try:
            printer = QPrinter(default_info, QPrinter.PrinterResolution)
            printer.setPageSize(QPageSize(QSizeF(lay.paper_w_mm, lay.paper_h_mm),
                                           QPageSize.Millimeter))
            printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
            printer.setCopyCount(copies)

            n_items = len(self.current_items)
            print_sticker_sheet(lay, self.current_items, self.template,
                                 printer=printer, copies=None)
            self.statusBar().showMessage(
                f"✓ Quick Print sent to: {printer_name}  |  "
                f"Copies: {copies}  |  Items: {n_items}",
                8000
            )
            QMessageBox.information(
                self, "Quick Print Sent",
                f"✓ Print job sent to default printer:\n  {printer_name}\n\n"
                f"Copies: {copies}\n"
                f"Items: {n_items}\n\n"
                f"If print doesn't come out, use the regular 'Print' button\n"
                f"to choose a different printer."
            )
        except Exception as e:
            tb = traceback.format_exc()
            QMessageBox.critical(self, "Quick Print failed",
                f"Could not quick print to {printer_name}:\n\n{e}\n\n"
                f"Technical details:\n{tb}\n\n"
                f"Try the regular 'Print' button or 'Save as PDF'.")

    def on_preview_clicked(self):
        """Preview using QPrintPreviewDialog."""
        if not self.current_items:
            QMessageBox.warning(self, "Empty",
                                "Please add at least one sticker first.")
            return
        lay = self._current_layout()
        try:
            printer = QPrinter(QPrinter.PrinterResolution)
            printer.setPageSize(QPageSize(QSizeF(lay.paper_w_mm, lay.paper_h_mm),
                                           QPageSize.Millimeter))
            printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
            printer.setCopyCount(self.copies_spin.value())
            if not printer.isValid():
                QMessageBox.warning(self, "No printer",
                    "No valid printer found.\n"
                    "Use 'Save as PDF' instead, or install a printer driver.")
                return
            dlg = QPrintPreviewDialog(printer, self)
            dlg.paintRequested.connect(lambda p: self._print_to(p))
            dlg.exec_()
        except Exception as e:
            tb = traceback.format_exc()
            QMessageBox.critical(self, "Preview failed",
                f"Could not open the print preview:\n{e}\n\n"
                f"Technical details:\n{tb}\n\n"
                f"Try 'Save as PDF' instead — it always works.")

    def _print_to(self, printer: QPrinter):
        lay = self._current_layout()
        try:
            print_sticker_sheet(lay, self.current_items, self.template,
                                 printer=printer, copies=None)
        except Exception as e:
            print(f"Print error: {e}")

    def on_save_pdf_clicked(self):
        """Save as PDF — always works, no printer needed."""
        if not self.current_items:
            QMessageBox.warning(self, "Empty",
                                "Please add at least one sticker first.")
            return
        lay = self._current_layout()
        default_name = f"barcodes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save as PDF", default_name, "PDF Files (*.pdf)"
        )
        if not path:
            return
        try:
            export_to_pdf(lay, self.current_items, self.template, path)
            QMessageBox.information(self, "PDF Saved / PDF محفوظ ہو گیا",
                f"✓ PDF saved to:\n{path}\n\n"
                f"To print this PDF:\n"
                f"  1. Open it in Adobe Acrobat, Microsoft Edge, or any PDF viewer\n"
                f"  2. Press Ctrl+P (or File > Print)\n"
                f"  3. CRITICAL: In Page Size & Handling, select 'Actual size'\n"
                f"     (NOT 'Fit' or 'Shrink to fit')\n"
                f"  4. Set Page Orientation to 'Auto'\n"
                f"  5. Set Margins to 'None' or 'Minimum'\n"
                f"  6. Select your label printer (if label mode)\n"
                f"     or A4 printer (if sheet mode)\n"
                f"  7. Click Print\n\n"
                f"If the print is wrong size, the PDF viewer is auto-scaling it.\n"
                f"Look for 'Page Sizing' or 'Scale' settings and set to 100%.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save PDF:\n{e}")

    # ----------------------------------------------- sticker editor
    def on_edit_layout_clicked(self):
        if self.current_items:
            sample_data = self.current_items[0]
        else:
            sample_data = {
                'company_name': self.company_edit.text() or 'Company Name',
                'product_name': self.product_edit.text() or 'Product Name',
                'product_code': self.code_edit.text() or 'CODE-001',
                'barcode': self.barcode_edit.text() or '501234567890',
                'mfg_date': self.mfg_date.date().toString("yyyy-MM-dd"),
                'exp_date': self.exp_date.date().toString("yyyy-MM-dd"),
                'mobile': self.mobile_edit.text() or '+92 300 1234567',
            }
        lay = self._current_layout()
        self.template.sticker_w_mm = lay.sticker_w_mm
        self.template.sticker_h_mm = lay.sticker_h_mm
        dlg = StickerEditorDialog(self.template, sample_data,
                                    lay.sticker_w_mm, lay.sticker_h_mm,
                                    unit_code=self.unit.code,
                                    parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.template = dlg.template
            self.db.set_setting('sticker_template_json',
                                template_to_json(self.template))
            self._refresh_preview()
            self._update_statusbar()

    # ----------------------------------------------- settings + history
    def on_settings_clicked(self):
        dlg = SettingsDialog(self.db, self)
        if dlg.exec_() == QDialog.Accepted:
            self.unit = get_unit(get_unit_from_settings(self.db))
            custom_key = self.db.get_setting('custom_layout_json', '')
            if custom_key:
                try:
                    d = json.loads(custom_key)
                    self.custom_layout = custom_layout(**d)
                    self.layout_key = '__custom__'
                    idx = self.layout_combo.findData('__custom__')
                    if idx >= 0:
                        self.layout_combo.setCurrentIndex(idx)
                except Exception:
                    pass
            self._update_layout_info()
            self._refresh_preview()
            self._update_statusbar()

    def on_history_clicked(self):
        dlg = HistoryDialog(self.db, self)
        if dlg.exec_() == QDialog.Accepted and dlg.selected_entry:
            e = dlg.selected_entry
            self.company_edit.setText(e.get('company_name') or '')
            self.product_edit.setText(e.get('product_name') or '')
            self.code_edit.setText(e.get('product_code') or '')
            self.barcode_edit.setText(e.get('barcode') or '')
            self.mobile_edit.setText(e.get('mobile') or '')
            if e.get('mfg_date'):
                d = QDate.fromString(e['mfg_date'], "yyyy-MM-dd")
                if d.isValid():
                    self.mfg_date.setDate(d)
            if e.get('exp_date'):
                d = QDate.fromString(e['exp_date'], "yyyy-MM-dd")
                if d.isValid():
                    self.exp_date.setDate(d)

    def closeEvent(self, event):
        try:
            self.db.set_setting('default_company', self.company_edit.text().strip())
            self.db.set_setting('default_mobile', self.mobile_edit.text().strip())
            self.db.set_setting('layout_key', self.layout_key)
            self.db.set_setting('sticker_template_json',
                                template_to_json(self.template))
        except Exception:
            pass
        self.db.close()
        super().closeEvent(event)
