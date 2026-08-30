"""
Settings dialog - sticker size customization, font sizes, defaults, units.
"""
import json

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QPushButton, QMessageBox, QTabWidget, QWidget, QRadioButton,
    QButtonGroup
)

from core.layouts import (PRESETS, SHEET_PRESETS, LABEL_PRESETS,
                            custom_layout, StickerLayout)
from core.database import Database
from core.units import MM, IN, get_unit


def get_font_sizes_from_settings(db: Database) -> dict:
    raw = db.get_setting('font_sizes_json', '')
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def get_unit_from_settings(db: Database):
    code = db.get_setting('unit_code', 'mm')
    return code


class SettingsDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Settings / ترتیبات")
        self.resize(560, 600)

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

        # Units selector (mm or inches)
        unit_box = QGroupBox("Measurement Units / پیمائش کی اکائی")
        ul = QHBoxLayout(unit_box)
        self.unit_mm = QRadioButton("Millimeters (mm) / ملی میٹر")
        self.unit_in = QRadioButton("Inches (in) / انچ")
        self.unit_grp = QButtonGroup(self)
        self.unit_grp.addButton(self.unit_mm)
        self.unit_grp.addButton(self.unit_in)
        self.unit_mm.toggled.connect(self.on_unit_changed)
        ul.addWidget(self.unit_mm)
        ul.addWidget(self.unit_in)
        ul.addStretch(1)
        f.addRow(unit_box)

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
        f.addRow("Paper width:", self.paper_w)

        self.paper_h = QDoubleSpinBox()
        self.paper_h.setRange(10, 350)
        self.paper_h.setSingleStep(0.5)
        self.paper_h.setValue(297)
        f.addRow("Paper height:", self.paper_h)

        self.sticker_w = QDoubleSpinBox()
        self.sticker_w.setRange(5, 200)
        self.sticker_w.setSingleStep(0.1)
        self.sticker_w.setValue(38)
        f.addRow("Sticker width:", self.sticker_w)

        self.sticker_h = QDoubleSpinBox()
        self.sticker_h.setRange(3, 150)
        self.sticker_h.setSingleStep(0.1)
        self.sticker_h.setValue(21.2)
        f.addRow("Sticker height:", self.sticker_h)

        self.margin_x = QDoubleSpinBox()
        self.margin_x.setRange(0, 50)
        self.margin_x.setSingleStep(0.5)
        self.margin_x.setValue(7.0)
        f.addRow("Left margin:", self.margin_x)

        self.margin_y = QDoubleSpinBox()
        self.margin_y.setRange(0, 50)
        self.margin_y.setSingleStep(0.5)
        self.margin_y.setValue(13.0)
        f.addRow("Top margin:", self.margin_y)

        self.gap_x = QDoubleSpinBox()
        self.gap_x.setRange(0, 30)
        self.gap_x.setSingleStep(0.5)
        self.gap_x.setValue(2.5)
        f.addRow("Horizontal gap:", self.gap_x)

        self.gap_y = QDoubleSpinBox()
        self.gap_y.setRange(0, 30)
        self.gap_y.setSingleStep(0.5)
        self.gap_y.setValue(0.0)
        f.addRow("Vertical gap:", self.gap_y)

        preset_box = QGroupBox("Quick presets / تیار سائز")
        pl = QVBoxLayout(preset_box)
        self.preset_combo = QComboBox()
        pl.addWidget(self.preset_combo)
        self._rebuild_preset_combo()
        apply_btn = QPushButton("Load preset into fields / سائز لوڈ کریں")
        apply_btn.clicked.connect(self.on_apply_preset)
        pl.addWidget(apply_btn)
        f.addRow(preset_box)

        self.size_info = QLabel("")
        self.size_info.setStyleSheet("color: #1a4d8f; font-size: 11px;")
        f.addRow("Current size:", self.size_info)

        for spin in [self.paper_w, self.paper_h, self.sticker_w, self.sticker_h,
                     self.margin_x, self.margin_y, self.gap_x, self.gap_y]:
            spin.valueChanged.connect(lambda _: self._update_size_info())

        return w

    def on_unit_changed(self):
        """Switch unit displayed in the spin boxes."""
        old_unit = self._current_unit()
        if self.unit_mm.isChecked():
            new_unit = MM
        else:
            new_unit = IN
        for spin in [self.paper_w, self.paper_h, self.sticker_w, self.sticker_h,
                     self.margin_x, self.margin_y, self.gap_x, self.gap_y]:
            cur_val = spin.value()
            mm_val = old_unit.to_mm(cur_val)
            new_val = new_unit.from_mm(mm_val)
            spin.blockSignals(True)
            spin.setValue(new_val)
            spin.setSuffix(f" {new_unit.symbol}")
            if new_unit.code == 'mm':
                spin.setDecimals(2)
                spin.setSingleStep(0.5)
            else:
                spin.setDecimals(3)
                spin.setSingleStep(0.05)
            spin.blockSignals(False)
        self._update_size_info()

    def _current_unit(self):
        return MM if self.unit_mm.isChecked() else IN

    def _update_size_info(self):
        u = self._current_unit()
        sw_mm = u.to_mm(self.sticker_w.value())
        sh_mm = u.to_mm(self.sticker_h.value())
        if u.code == 'mm':
            self.size_info.setText(
                f"{sw_mm:.2f} × {sh_mm:.2f} mm  =  "
                f"{IN.from_mm(sw_mm):.3f} × {IN.from_mm(sh_mm):.3f} in"
            )
        else:
            self.size_info.setText(
                f"{IN.from_mm(sw_mm):.3f} × {IN.from_mm(sh_mm):.3f} in  =  "
                f"{sw_mm:.2f} × {sh_mm:.2f} mm"
            )

    def on_mode_changed(self):
        self._rebuild_preset_combo()
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
        u = self._current_unit()
        self.paper_w.blockSignals(True)
        self.paper_h.blockSignals(True)
        self.sticker_w.blockSignals(True)
        self.sticker_h.blockSignals(True)
        self.margin_x.blockSignals(True)
        self.margin_y.blockSignals(True)
        self.gap_x.blockSignals(True)
        self.gap_y.blockSignals(True)
        self.paper_w.setValue(u.from_mm(lay.paper_w_mm))
        self.paper_h.setValue(u.from_mm(lay.paper_h_mm))
        self.sticker_w.setValue(u.from_mm(lay.sticker_w_mm))
        self.sticker_h.setValue(u.from_mm(lay.sticker_h_mm))
        self.margin_x.setValue(u.from_mm(lay.margin_x_mm))
        self.margin_y.setValue(u.from_mm(lay.margin_y_mm))
        self.gap_x.setValue(u.from_mm(lay.gap_x_mm))
        self.gap_y.setValue(u.from_mm(lay.gap_y_mm))
        self.paper_w.blockSignals(False)
        self.paper_h.blockSignals(False)
        self.sticker_w.blockSignals(False)
        self.sticker_h.blockSignals(False)
        self.margin_x.blockSignals(False)
        self.margin_y.blockSignals(False)
        self.gap_x.blockSignals(False)
        self.gap_y.blockSignals(False)
        self._update_size_info()

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
            "Note: These settings are legacy defaults. For full control, "
            "use 'Edit Sticker Layout' button in the main window — "
            "it lets you set font family, size, bold, italic per element."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #b85c00; font-size: 11px;")
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

        ucode = self.db.get_setting('unit_code', 'mm')
        if ucode == 'in':
            self.unit_in.setChecked(True)
        else:
            self.unit_mm.setChecked(True)
        u = self._current_unit()
        for spin in [self.paper_w, self.paper_h, self.sticker_w, self.sticker_h,
                     self.margin_x, self.margin_y, self.gap_x, self.gap_y]:
            spin.setSuffix(f" {u.symbol}")
            if u.code == 'mm':
                spin.setDecimals(2)
                spin.setSingleStep(0.5)
            else:
                spin.setDecimals(3)
                spin.setSingleStep(0.05)

        cj = self.db.get_setting('custom_layout_json', '')
        if cj:
            try:
                d = json.loads(cj)
                self.paper_w.setValue(u.from_mm(d.get('paper_w', 210)))
                self.paper_h.setValue(u.from_mm(d.get('paper_h', 297)))
                self.sticker_w.setValue(u.from_mm(d.get('sticker_w', 38)))
                self.sticker_h.setValue(u.from_mm(d.get('sticker_h', 21.2)))
                self.margin_x.setValue(u.from_mm(d.get('margin_x', 7)))
                self.margin_y.setValue(u.from_mm(d.get('margin_y', 13)))
                self.gap_x.setValue(u.from_mm(d.get('gap_x', 2.5)))
                self.gap_y.setValue(u.from_mm(d.get('gap_y', 0)))
                if d.get('is_label', False):
                    self.mode_label.setChecked(True)
                else:
                    self.mode_sheet.setChecked(True)
            except Exception:
                self.mode_sheet.setChecked(True)
        else:
            self.mode_sheet.setChecked(True)
        self._update_size_info()

    def on_save(self):
        font_sizes = {
            'company': self.font_company.value(),
            'body': self.font_body.value(),
            'small': self.font_small.value(),
            'barcode_text': self.font_barcode.value(),
        }
        self.db.set_setting('font_sizes_json', json.dumps(font_sizes))

        self.db.set_setting('default_company', self.def_company.text())
        self.db.set_setting('default_mobile', self.def_mobile.text())

        u = self._current_unit()
        self.db.set_setting('unit_code', u.code)

        is_label = self.mode_label.isChecked()
        custom = {
            'name': 'Custom (Label)' if is_label else 'Custom (Sheet)',
            'paper_w': u.to_mm(self.paper_w.value()),
            'paper_h': u.to_mm(self.paper_h.value()),
            'sticker_w': u.to_mm(self.sticker_w.value()),
            'sticker_h': u.to_mm(self.sticker_h.value()),
            'margin_x': u.to_mm(self.margin_x.value()),
            'margin_y': u.to_mm(self.margin_y.value()),
            'gap_x': u.to_mm(self.gap_x.value()),
            'gap_y': u.to_mm(self.gap_y.value()),
            'is_label': is_label,
        }
        self.db.set_setting('custom_layout_json', json.dumps(custom))
        self.accept()
