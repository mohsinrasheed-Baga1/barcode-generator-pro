"""
Settings dialog - sticker size customization, font sizes, defaults.
"""
import json

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QPushButton, QMessageBox, QTabWidget, QWidget, QRadioButton
)

from core.layouts import (PRESETS, SHEET_PRESETS, LABEL_PRESETS,
                            custom_layout, StickerLayout)
from core.database import Database


def get_font_sizes_from_settings(db: Database) -> dict:
    raw = db.get_setting('font_sizes_json', '')
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


class SettingsDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Settings / ترتیبات")
        self.resize(560, 540)

        tabs = QTabWidget()
        tabs.addTab(self._build_layout_tab(), "Sheet Layout / شیٹ سائز")
        tabs.addTab(self._build_fonts_tab(), "Fonts / فونٹس")
        tabs.addTab(self._build_defaults_tab(), "Defaults / ڈیفالٹس")
        tabs.addTab(self._build_data_tab(), "Data / ڈیٹا")

        v = QVBoxLayout(self)
        v.addWidget(tabs)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.on_save)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

        self._load_settings()

    # ----- layout tab -----
    def _build_layout_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setLabelAlignment(Qt.AlignRight)

        # Print Mode toggle
        mode_box = QGroupBox("Print Mode / پرنٹ موڈ")
        ml = QVBoxLayout(mode_box)
        self.mode_sheet = QRadioButton(
            "📄 Sheet Printer (A4 paper — multiple stickers per sheet)\n"
            "شیٹ پرنٹر (A4 پیپر — ایک شیٹ پر متعدد اسٹیکر)"
        )
        self.mode_label = QRadioButton(
            "🖨 Label Printer (direct — one label at a time, continuous roll)\n"
            "لیبل پرنٹر (ڈائرکٹ — ایک وقت میں ایک لیبل، کنٹینیوس رول)"
        )
        self.mode_sheet.toggled.connect(self.on_mode_changed)
        self.mode_label.toggled.connect(self.on_mode_changed)
        ml.addWidget(self.mode_sheet)
        ml.addWidget(self.mode_label)
        ml.addWidget(QLabel(
            "Label printer examples: Zebra, TSC, Xprinter, Godex, Rongta, etc.\n"
            "لیبل پرنٹر مثالیں: Zebra, TSC, Xprinter, Godex, Rongta وغیرہ"
        ))
        f.addRow(mode_box)

        self.paper_w = QDoubleSpinBox()
        self.paper_w.setRange(10, 350)
        self.paper_w.setSingleStep(0.5)
        self.paper_w.setValue(210)
        f.addRow("Paper width (mm):", self.paper_w)

        self.paper_h = QDoubleSpinBox()
        self.paper_h.setRange(10, 350)
        self.paper_h.setSingleStep(0.5)
        self.paper_h.setValue(297)
        f.addRow("Paper height (mm):", self.paper_h)

        self.sticker_w = QDoubleSpinBox()
        self.sticker_w.setRange(5, 200)
        self.sticker_w.setSingleStep(0.1)
        self.sticker_w.setValue(38)
        f.addRow("Sticker width (mm):", self.sticker_w)

        self.sticker_h = QDoubleSpinBox()
        self.sticker_h.setRange(3, 150)
        self.sticker_h.setSingleStep(0.1)
        self.sticker_h.setValue(21.2)
        f.addRow("Sticker height (mm):", self.sticker_h)

        self.margin_x = QDoubleSpinBox()
        self.margin_x.setRange(0, 50)
        self.margin_x.setSingleStep(0.5)
        self.margin_x.setValue(7.0)
        f.addRow("Left margin (mm):", self.margin_x)

        self.margin_y = QDoubleSpinBox()
        self.margin_y.setRange(0, 50)
        self.margin_y.setSingleStep(0.5)
        self.margin_y.setValue(13.0)
        f.addRow("Top margin (mm):", self.margin_y)

        self.gap_x = QDoubleSpinBox()
        self.gap_x.setRange(0, 30)
        self.gap_x.setSingleStep(0.5)
        self.gap_x.setValue(2.5)
        f.addRow("Horizontal gap (mm):", self.gap_x)

        self.gap_y = QDoubleSpinBox()
        self.gap_y.setRange(0, 30)
        self.gap_y.setSingleStep(0.5)
        self.gap_y.setValue(0.0)
        f.addRow("Vertical gap (mm):", self.gap_y)

        # Preset buttons - grouped by mode
        preset_box = QGroupBox("Quick presets / تیار سائز")
        pl = QVBoxLayout(preset_box)
        self.preset_combo = QComboBox()
        pl.addWidget(self.preset_combo)
        self._rebuild_preset_combo()
        apply_btn = QPushButton("Load preset into fields / سائز لوڈ کریں")
        apply_btn.clicked.connect(self.on_apply_preset)
        pl.addWidget(apply_btn)
        f.addRow(preset_box)

        return w

    def on_mode_changed(self):
        # When the user toggles sheet/label mode in settings, rebuild the
        # preset dropdown to show only relevant presets.
        self._rebuild_preset_combo()
        # If a preset is selected, auto-apply it so fields update
        if self.preset_combo.count() > 0:
            self.preset_combo.setCurrentIndex(0)
            self.on_apply_preset()

    def _rebuild_preset_combo(self):
        self.preset_combo.clear()
        if self.mode_label.isChecked():
            for key, lay in LABEL_PRESETS.items():
                self.preset_combo.addItem(lay.name, key)
        else:
            for key, lay in SHEET_PRESETS.items():
                self.preset_combo.addItem(lay.name, key)

    def on_apply_preset(self):
        key = self.preset_combo.currentData()
        lay = PRESETS.get(key)
        if not lay:
            return
        self.paper_w.setValue(lay.paper_w_mm)
        self.paper_h.setValue(lay.paper_h_mm)
        self.sticker_w.setValue(lay.sticker_w_mm)
        self.sticker_h.setValue(lay.sticker_h_mm)
        self.margin_x.setValue(lay.margin_x_mm)
        self.margin_y.setValue(lay.margin_y_mm)
        self.gap_x.setValue(lay.gap_x_mm)
        self.gap_y.setValue(lay.gap_y_mm)

    # ----- fonts tab -----
    def _build_fonts_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setLabelAlignment(Qt.AlignRight)

        self.font_company = QSpinBox()
        self.font_company.setRange(4, 72)
        self.font_company.setValue(9)
        f.addRow("Company name (px @ 96dpi):", self.font_company)

        self.font_body = QSpinBox()
        self.font_body.setRange(4, 72)
        self.font_body.setValue(7)
        f.addRow("Body text (px):", self.font_body)

        self.font_small = QSpinBox()
        self.font_small.setRange(4, 72)
        self.font_small.setValue(6)
        f.addRow("Small text (px):", self.font_small)

        self.font_barcode = QSpinBox()
        self.font_barcode.setRange(4, 72)
        self.font_barcode.setValue(7)
        f.addRow("Barcode digits (px):", self.font_barcode)

        info = QLabel(
            "Note: Font sizes are in pixels for the on-screen preview at 96 DPI. "
            "When printing at high DPI, fonts scale automatically. "
            "Tip: keep barcode digits legible — at least 6px."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; font-size: 11px;")
        f.addRow(info)
        return w

    # ----- defaults tab -----
    def _build_defaults_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setLabelAlignment(Qt.AlignRight)

        self.def_company = QLineEdit()
        f.addRow("Default company name:", self.def_company)

        self.def_mobile = QLineEdit()
        f.addRow("Default mobile number:", self.def_mobile)

        return w

    # ----- data tab -----
    def _build_data_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(
            "Data management — clear history of saved barcodes.\n"
            "Warning: this cannot be undone."
        ))
        clear_btn = QPushButton("🗑 Clear all barcode history")
        clear_btn.clicked.connect(self.on_clear_history)
        v.addWidget(clear_btn)
        v.addStretch(1)
        return w

    def on_clear_history(self):
        ok = QMessageBox.question(
            self, "Confirm",
            "Delete ALL saved barcode history? This cannot be undone."
        )
        if ok == QMessageBox.Yes:
            self.db.clear_history()
            QMessageBox.information(self, "Done", "History cleared.")

    # ----- load/save -----
    def _load_settings(self):
        fs = get_font_sizes_from_settings(self.db)
        self.font_company.setValue(int(fs.get('company', 9)))
        self.font_body.setValue(int(fs.get('body', 7)))
        self.font_small.setValue(int(fs.get('small', 6)))
        self.font_barcode.setValue(int(fs.get('barcode_text', 7)))

        self.def_company.setText(self.db.get_setting('default_company', ''))
        self.def_mobile.setText(self.db.get_setting('default_mobile', ''))

        # load custom layout if set, else load preset
        cj = self.db.get_setting('custom_layout_json', '')
        if cj:
            try:
                d = json.loads(cj)
                self.paper_w.setValue(d.get('paper_w', 210))
                self.paper_h.setValue(d.get('paper_h', 297))
                self.sticker_w.setValue(d.get('sticker_w', 38))
                self.sticker_h.setValue(d.get('sticker_h', 21.2))
                self.margin_x.setValue(d.get('margin_x', 7))
                self.margin_y.setValue(d.get('margin_y', 13))
                self.gap_x.setValue(d.get('gap_x', 2.5))
                self.gap_y.setValue(d.get('gap_y', 0))
                if d.get('is_label', False):
                    self.mode_label.setChecked(True)
                else:
                    self.mode_sheet.setChecked(True)
            except Exception:
                self.mode_sheet.setChecked(True)
        else:
            self.mode_sheet.setChecked(True)

    def on_save(self):
        # fonts
        font_sizes = {
            'company': self.font_company.value(),
            'body': self.font_body.value(),
            'small': self.font_small.value(),
            'barcode_text': self.font_barcode.value(),
        }
        self.db.set_setting('font_sizes_json', json.dumps(font_sizes))

        # defaults
        self.db.set_setting('default_company', self.def_company.text())
        self.db.set_setting('default_mobile', self.def_mobile.text())

        # custom layout — keep is_label flag
        is_label = self.mode_label.isChecked()
        custom = {
            'name': 'Custom (Label)' if is_label else 'Custom (Sheet)',
            'paper_w': self.paper_w.value(),
            'paper_h': self.paper_h.value(),
            'sticker_w': self.sticker_w.value(),
            'sticker_h': self.sticker_h.value(),
            'margin_x': self.margin_x.value(),
            'margin_y': self.margin_y.value(),
            'gap_x': self.gap_x.value(),
            'gap_y': self.gap_y.value(),
            'is_label': is_label,
        }
        self.db.set_setting('custom_layout_json', json.dumps(custom))
        self.accept()
