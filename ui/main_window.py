"""
Main window for the Barcode Generator.
Bilingual labels (English / Urdu) where helpful.
"""
import os
import csv
import json
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QSize, QRectF, QDate
from PyQt5.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QPen,
    QIcon, QStandardItemModel, QStandardItem, QPalette, QPageSize
)
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QComboBox, QSpinBox,
    QDateEdit, QCheckBox, QTableView, QHeaderView, QTabWidget, QSplitter,
    QMessageBox, QFileDialog, QDialog, QDialogButtonBox, QGroupBox,
    QScrollArea, QFrame, QSizePolicy, QApplication
)
from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog, QPrintDialog

from core.barcode_gen import (make_full_ean13, validate_ean13,
                                draw_sticker, make_fonts, generate_ean13_image)
from core.database import Database
from core.csv_import import import_csv, write_csv_template
from core.layouts import PRESETS, custom_layout, StickerLayout, sticker_positions, total_slots
from core.printer import print_sticker_sheet, render_preview
from ui.settings_dialog import SettingsDialog, get_font_sizes_from_settings
from ui.history_dialog import HistoryDialog


APP_TITLE = "Barcode Generator Pro — EAN-13"
APP_VERSION = "1.0.0"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1180, 780)

        self.db = Database()

        # Current batch of items to print (list of dicts)
        self.current_items = []

        # Default company & mobile (saved settings)
        self.default_company = self.db.get_setting('default_company', '')
        self.default_mobile = self.db.get_setting('default_mobile', '')

        # Current layout selection
        self.layout_key = self.db.get_setting('layout_key', 'A4-40')
        self.custom_layout = None  # if set, override PRESETS
        self.font_sizes = get_font_sizes_from_settings(self.db)

        self._build_ui()
        self._restore_settings()
        self._refresh_preview()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ---- left: input form ----
        left = QWidget()
        left.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        left.setMaximumWidth(460)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Title
        title = QLabel("Barcode Generator — EAN-13\nبارکوڈ جنریٹر")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a4d8f;")
        title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(title)

        # Form group
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
        self.product_edit.setPlaceholderText("e.g. Sunlight Soap 200g")
        form.addRow("Product Name / پروڈکٹ نام:", self.product_edit)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("e.g. SL-001")
        form.addRow("Product Code / پروڈکٹ کوڈ:", self.code_edit)

        self.barcode_edit = QLineEdit()
        self.barcode_edit.setPlaceholderText("12 digits — 13th auto / 12 ہندسے")
        self.barcode_edit.setMaxLength(13)
        form.addRow("Barcode (EAN-13) / بارکوڈ:", self.barcode_edit)

        # Dates row
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
        self.mobile_edit.setPlaceholderText("e.g. +92 300 1234567")
        self.mobile_edit.setText(self.default_mobile)
        form.addRow("Mobile / موبائل:", self.mobile_edit)

        left_layout.addWidget(form_box)

        # Quantity + Add
        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Quantity / تعداد:"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1000)
        self.qty_spin.setValue(1)
        qty_row.addWidget(self.qty_spin)
        qty_row.addStretch(1)
        left_layout.addLayout(qty_row)

        # Action buttons
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("➕ Add to Sheet\nشیٹ میں شامل کریں")
        self.add_btn.clicked.connect(self.on_add_clicked)
        btn_row.addWidget(self.add_btn)

        self.clear_btn = QPushButton("🗑 Clear Sheet\nشیٹ خالی کریں")
        self.clear_btn.clicked.connect(self.on_clear_clicked)
        btn_row.addWidget(self.clear_btn)
        left_layout.addLayout(btn_row)

        # Bulk import
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

        # Sheet layout selector
        layout_box = QGroupBox("Sheet Layout / شیٹ سائز")
        layout_form = QFormLayout(layout_box)
        self.layout_combo = QComboBox()
        for key, lay in PRESETS.items():
            self.layout_combo.addItem(lay.name, key)
        # add custom option if exists
        self.layout_combo.addItem("Custom (set in Settings)...", "__custom__")
        # try to set saved
        idx = self.layout_combo.findData(self.layout_key)
        if idx >= 0:
            self.layout_combo.setCurrentIndex(idx)
        self.layout_combo.currentIndexChanged.connect(self.on_layout_changed)
        layout_form.addRow("Layout:", self.layout_combo)

        self.layout_info = QLabel("")
        self.layout_info.setStyleSheet("color: #555; font-size: 11px;")
        layout_form.addRow("", self.layout_info)

        # Print settings
        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 999)
        self.copies_spin.setValue(1)
        self.copies_spin.valueChanged.connect(lambda _: self._refresh_preview())
        layout_form.addRow("Print copies:", self.copies_spin)

        left_layout.addWidget(layout_box)

        # Print buttons
        print_row = QHBoxLayout()
        self.print_btn = QPushButton("🖨 Print\nپرنٹ")
        self.print_btn.setStyleSheet("background: #1a4d8f; color: white; padding: 10px; font-weight: bold;")
        self.print_btn.clicked.connect(self.on_print_clicked)
        print_row.addWidget(self.print_btn)

        self.preview_btn = QPushButton("👁 Preview\nپریویو")
        self.preview_btn.clicked.connect(self.on_preview_clicked)
        print_row.addWidget(self.preview_btn)
        left_layout.addLayout(print_row)

        # Settings / History row
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
        scroll.setBackgroundRole(QPalette.Mid)  # neutral gray bg
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(540, 760)
        self.preview_label.setStyleSheet("background: #999;")
        scroll.setWidget(self.preview_label)
        right_layout.addWidget(scroll, 1)

        # Items count info bar
        self.count_label = QLabel("0 stickers in sheet")
        self.count_label.setStyleSheet("padding: 4px; color: #333;")
        right_layout.addWidget(self.count_label)

        # Items list (mini table)
        self.items_model = QStandardItemModel(0, 4)
        self.items_model.setHorizontalHeaderLabels(
            ["#", "Barcode", "Product", "Qty"]
        )
        self.items_table = QTableView()
        self.items_table.setModel(self.items_model)
        self.items_table.setMaximumHeight(160)
        self.items_table.setSelectionBehavior(QTableView.SelectRows)
        self.items_table.setEditTriggers(QTableView.NoEditTriggers)
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.items_table)

        # Delete selected button
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

        self._update_layout_info()

    # ----------------------------------------------------- event handlers
    def on_add_clicked(self):
        # Validate barcode
        bc_raw = self.barcode_edit.text().strip()
        if not bc_raw:
            QMessageBox.warning(self, "Missing",
                                "Please enter a barcode value.\nبراہ کرم بارکوڈ درج کریں۔")
            return
        try:
            full = make_full_ean13(bc_raw)
        except Exception as e:
            QMessageBox.warning(self, "Invalid barcode",
                                f"Could not generate EAN-13: {e}")
            return

        data = {
            'company_name': self.company_edit.text().strip(),
            'product_name': self.product_edit.text().strip(),
            'product_code': self.code_edit.text().strip(),
            'barcode': full,
            'mfg_date': self.mfg_date.date().toString("yyyy-MM-dd"),
            'exp_date': self.exp_date.date().toString("yyyy-MM-dd"),
            'mobile': self.mobile_edit.text().strip(),
        }
        # Save to history
        try:
            self.db.save_barcode(data)
        except Exception as e:
            # ignore db errors
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
            QMessageBox.information(self, "Import",
                                   "No data rows found in CSV.")
            return
        self.current_items.extend(rows)
        # Save to history
        for r in rows:
            try:
                self.db.save_barcode(r)
            except Exception:
                pass
        self.bulk_status.setText(f"Loaded {len(rows)} rows from:\n{os.path.basename(path)}")
        self._refresh_preview()

    def on_save_template(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV template", "barcode_template.csv",
            "CSV Files (*.csv)"
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
            # Try to use the saved custom layout, if any
            prev_key = self.layout_key
            self.on_settings_clicked()
            # After settings dialog closes, check if we now have a custom layout
            if self.custom_layout is not None:
                self.layout_key = '__custom__'
            else:
                # Revert combo to previous selection
                revert_idx = self.layout_combo.findData(prev_key)
                if revert_idx < 0:
                    revert_idx = 0  # fallback to first preset
                self.layout_combo.blockSignals(True)
                self.layout_combo.setCurrentIndex(revert_idx)
                self.layout_combo.blockSignals(False)
                self.layout_key = self.layout_combo.currentData()
            self._update_layout_info()
            self._refresh_preview()
            return
        self.layout_key = key
        self.db.set_setting('layout_key', key)
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
                f"🖨 LABEL PRINTER MODE — direct label printing\n"
                f"Label: {lay.sticker_w_mm} × {lay.sticker_h_mm} mm\n"
                f"1 label per print, multiple pages = multiple labels"
            )
            self.layout_info.setStyleSheet("color: #b85c00; font-size: 11px; font-weight: bold;")
        else:
            self.layout_info.setText(
                f"📄 SHEET PRINTER MODE — A4 multi-label sheet\n"
                f"{lay.cols} cols × {lay.rows} rows = {total_slots(lay)} stickers/sheet\n"
                f"Sticker: {lay.sticker_w_mm} × {lay.sticker_h_mm} mm"
            )
            self.layout_info.setStyleSheet("color: #1a4d8f; font-size: 11px; font-weight: bold;")

    def _refresh_preview(self):
        if not hasattr(self, 'preview_label'):
            return
        lay = self._current_layout()
        try:
            pix = render_preview(lay, self.current_items,
                                  font_sizes=self.font_sizes,
                                  dpi=120)
            self.preview_label.setPixmap(pix)
        except Exception as e:
            self.preview_label.setText(f"Preview error:\n{e}")

        # Update count label
        n = len(self.current_items)
        per_sheet = total_slots(lay)
        if lay.is_label:
            # Label mode: each item = 1 label = 1 page
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

        # Update items table
        self.items_model.removeRows(0, self.items_model.rowCount())
        idx = 0
        # Group identical consecutive entries for display
        i = 0
        while i < len(self.current_items):
            d = self.current_items[i]
            qty = 1
            # Count consecutive duplicates (by barcode + product_code)
            j = i + 1
            while (j < len(self.current_items)
                   and self.current_items[j].get('barcode') == d.get('barcode')
                   and self.current_items[j].get('product_code') == d.get('product_code')
                   and self.current_items[j].get('company_name') == d.get('company_name')
                   and self.current_items[j].get('product_name') == d.get('product_name')):
                qty += 1
                j += 1
            idx += 1
            self.items_model.appendRow([
                QStandardItem(str(idx)),
                QStandardItem(d.get('barcode', '')),
                QStandardItem(d.get('product_name') or d.get('product_code') or ''),
                QStandardItem(str(qty)),
            ])
            i = j

    def on_preview_clicked(self):
        if not self.current_items:
            QMessageBox.warning(self, "Empty",
                                "Please add at least one sticker first.")
            return
        printer = QPrinter(QPrinter.HighResolution)
        lay = self._current_layout()
        
        printer.setPageSize(QPageSize(QSizeF(lay.paper_w_mm, lay.paper_h_mm),
                                       QPageSize.Millimeter))
        printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
        dlg = QPrintPreviewDialog(printer, self)
        dlg.paintRequested.connect(lambda p: self._print_to(p))
        dlg.exec_()

    def _print_to(self, printer: QPrinter):
        lay = self._current_layout()
        try:
            print_sticker_sheet(lay, self.current_items,
                                 font_sizes=self.font_sizes,
                                 printer=printer,
                                 copies=self.copies_spin.value())
        except Exception as e:
            QMessageBox.critical(self, "Print error", str(e))

    def on_print_clicked(self):
        if not self.current_items:
            QMessageBox.warning(self, "Empty",
                                "Please add at least one sticker first.")
            return
        lay = self._current_layout()
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QSizeF(lay.paper_w_mm, lay.paper_h_mm),
                                       QPageSize.Millimeter))
        printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
        printer.setCopyCount(self.copies_spin.value())

        # Reminder for label printer mode
        if lay.is_label:
            QMessageBox.information(
                self, "Label Printer Mode",
                "🖨 Label Printer Mode is ON.\n\n"
                "Important:\n"
                "  1. In the Print dialog, SELECT your label printer\n"
                "     (e.g. Zebra, TSC, Xprinter, Godex)\n"
                "  2. Make sure the label size in the printer driver\n"
                "     matches the selected label size\n"
                "  3. Do NOT use A4 paper printers — they will\n"
                "     print the label in the corner of an A4 sheet\n\n"
                "Each item in the queue will print as one label."
            )

        dlg = QPrintDialog(printer, self)
        if dlg.exec_() == QDialog.Accepted:
            try:
                print_sticker_sheet(lay, self.current_items,
                                     font_sizes=self.font_sizes,
                                     printer=printer,
                                     copies=1)  # copies handled by printer
            except Exception as e:
                QMessageBox.critical(self, "Print error", str(e))

    def on_settings_clicked(self):
        dlg = SettingsDialog(self.db, self)
        if dlg.exec_() == QDialog.Accepted:
            self.font_sizes = get_font_sizes_from_settings(self.db)
            self.default_company = self.db.get_setting('default_company', '')
            self.default_mobile = self.db.get_setting('default_mobile', '')
            custom_key = self.db.get_setting('custom_layout_json', '')
            if custom_key:
                try:
                    d = json.loads(custom_key)
                    self.custom_layout = custom_layout(**d)
                    # switch combo to custom
                    self.layout_key = '__custom__'
                    idx = self.layout_combo.findData('__custom__')
                    if idx >= 0:
                        self.layout_combo.setCurrentIndex(idx)
                except Exception:
                    pass
            self._update_layout_info()
            self._refresh_preview()

    def on_history_clicked(self):
        dlg = HistoryDialog(self.db, self)
        if dlg.exec_() == QDialog.Accepted and dlg.selected_entry:
            e = dlg.selected_entry
            self.company_edit.setText(e.get('company_name') or '')
            self.product_edit.setText(e.get('product_name') or '')
            self.code_edit.setText(e.get('product_code') or '')
            self.barcode_edit.setText(e.get('barcode') or '')
            self.mobile_edit.setText(e.get('mobile') or '')
            # dates
            if e.get('mfg_date'):
                d = QDate.fromString(e['mfg_date'], "yyyy-MM-dd")
                if d.isValid():
                    self.mfg_date.setDate(d)
            if e.get('exp_date'):
                d = QDate.fromString(e['exp_date'], "yyyy-MM-dd")
                if d.isValid():
                    self.exp_date.setDate(d)

    # ------------------------------------------------------ settings
    def _restore_settings(self):
        # already restored layout_key, default_company, default_mobile in __init__
        pass

    def closeEvent(self, event):
        # save defaults
        self.db.set_setting('default_company', self.company_edit.text().strip())
        self.db.set_setting('default_mobile', self.mobile_edit.text().strip())
        self.db.set_setting('layout_key', self.layout_key)
        # window geometry
        try:
            self.db.set_setting('window_geometry', self.saveGeometry().data().hex())
        except Exception:
            pass
        self.db.close()
        super().closeEvent(event)
