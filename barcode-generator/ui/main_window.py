"""
Main window for the Barcode Generator (v2.0.4).
"""
import os
import json
import traceback
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QSize, QSizeF, QRectF, QRect, QDate, QTimer
from PyQt5.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QPen, QFontDatabase,
    QIcon, QStandardItemModel, QStandardItem, QPalette, QPageSize, QTransform
)
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QComboBox, QSpinBox,
    QDoubleSpinBox, QDateEdit, QCheckBox, QTableView, QHeaderView, QTabWidget,
    QSplitter, QMessageBox, QFileDialog, QDialog, QGroupBox,
    QScrollArea, QFrame, QSizePolicy, QApplication, QStatusBar,
    QInputDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QStackedWidget, QColorDialog, QGraphicsView
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
APP_VERSION = "2.5.0"


class ZoomableGraphicsView(QGraphicsView):
    """QGraphicsView with direct mouse wheel zoom (no Ctrl needed)."""
    def __init__(self, scene=None, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self._zoom_factor = 1.0

    def wheelEvent(self, event):
        # Direct wheel zoom — no Ctrl modifier needed
        delta = event.angleDelta().y()
        if delta > 0:
            self.scale(1.15, 1.15)
        else:
            self.scale(1/1.15, 1/1.15)
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        # Make window responsive — start at reasonable size
        self.resize(1280, 800)
        # Minimum size — UI should work on small screens too
        self.setMinimumSize(900, 600)

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
        # Use QSplitter so the user can resize left/right panels
        from PyQt5.QtWidgets import QSplitter
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setContentsMargins(0, 0, 0, 0)

        # ---- left: input form (wrapped in scroll area for small screens) ----
        left_inner = QWidget()
        left_layout = QVBoxLayout(left_inner)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

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

        # Price field + Include Price checkbox
        self.price_edit = QLineEdit()
        self.price_edit.setPlaceholderText("e.g. 150 or Rs. 150")
        form.addRow("Price / قیمت:", self.price_edit)
        self.price_enabled_chk = QCheckBox("Include Price / قیمت شامل کریں")
        self.price_enabled_chk.setChecked(False)
        self.price_enabled_chk.toggled.connect(self.on_price_enabled_toggled)
        form.addRow("", self.price_enabled_chk)

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

        # Logo upload button
        logo_row = QHBoxLayout()
        self.logo_btn = QPushButton("🖼 Add Logo / لوگو شامل کریں")
        self.logo_btn.setStyleSheet(
            "background: #f0f4fa; color: #1a4d8f; padding: 8px; "
            "border: 2px dashed #1a4d8f; font-weight: bold;"
        )
        self.logo_btn.clicked.connect(self.on_logo_clicked)
        logo_row.addWidget(self.logo_btn)

        self.remove_logo_btn = QPushButton("✖ Remove Logo")
        self.remove_logo_btn.clicked.connect(self.on_remove_logo_clicked)
        logo_row.addWidget(self.remove_logo_btn)
        left_layout.addLayout(logo_row)

        # Edit mode is now ALWAYS ON — preview is always interactive
        # No toggle button needed (Canva-like behavior)

        # Print buttons — three options (Print button is prominent)
        print_row = QHBoxLayout()
        # Main Print button — prominent orange/red gradient
        self.print_btn = QPushButton("🖨  PRINT\nپرنٹ")
        self.print_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff7043, stop:1 #d84315);
                color: white; padding: 14px 18px;
                font-size: 14px; font-weight: bold;
                border: none; border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff8a65, stop:1 #e64a19);
            }
            QPushButton:pressed {
                background: #bf360c;
            }
        """)
        self.print_btn.clicked.connect(self.on_print_clicked)
        print_row.addWidget(self.print_btn)

        # Quick Print — secondary green
        self.quick_print_btn = QPushButton("⚡ Quick\nفوری")
        self.quick_print_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66bb6a, stop:1 #2e7d32);
                color: white; padding: 14px;
                font-weight: bold; border: none; border-radius: 6px;
            }
            QPushButton:hover { background: #43a047; }
            QPushButton:pressed { background: #1b5e20; }
        """)
        self.quick_print_btn.clicked.connect(self.on_quick_print_clicked)
        print_row.addWidget(self.quick_print_btn)

        # PDF — tertiary amber
        self.pdf_btn = QPushButton("📄 PDF\nPDF")
        self.pdf_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffb74d, stop:1 #e68900);
                color: white; padding: 14px;
                font-weight: bold; border: none; border-radius: 6px;
            }
            QPushButton:hover { background: #f57c00; }
            QPushButton:pressed { background: #b85c00; }
        """)
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

        # ---- right: preview + (optional) inline editor ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        # Top label — preview mode or edit mode
        self.preview_label_title = QLabel("Sheet Preview / شیٹ پریویو")
        self.preview_label_title.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #1a4d8f; padding: 4px;"
        )
        right_layout.addWidget(self.preview_label_title)

        # Zoom controls row
        zoom_row = QHBoxLayout()
        zoom_row.setContentsMargins(0, 0, 0, 0)
        self.zoom_in_btn = QPushButton("🔍+")
        self.zoom_in_btn.setMaximumWidth(40)
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.clicked.connect(self.on_zoom_in)
        zoom_row.addWidget(self.zoom_in_btn)
        self.zoom_out_btn = QPushButton("🔍−")
        self.zoom_out_btn.setMaximumWidth(40)
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.on_zoom_out)
        zoom_row.addWidget(self.zoom_out_btn)
        self.zoom_actual_btn = QPushButton("1:1 (Actual Size)")
        self.zoom_actual_btn.setToolTip("Show at actual physical size (1mm screen = 1mm paper)")
        self.zoom_actual_btn.clicked.connect(self.on_zoom_actual)
        zoom_row.addWidget(self.zoom_actual_btn)
        self.zoom_fit_btn = QPushButton("Fit")
        self.zoom_fit_btn.setMaximumWidth(60)
        self.zoom_fit_btn.setToolTip("Fit to window")
        self.zoom_fit_btn.clicked.connect(self.on_zoom_fit)
        zoom_row.addWidget(self.zoom_fit_btn)
        zoom_row.addStretch(1)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("color: #555; padding: 4px;")
        zoom_row.addWidget(self.zoom_label)
        right_layout.addLayout(zoom_row)

        # Stacked widget: index 0 = preview (QLabel), index 1 = editor (QGraphicsView)
        self.preview_stack = QStackedWidget()

        # ----- Index 0: Static preview (QLabel in scroll area) -----
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setAlignment(Qt.AlignCenter)
        self.preview_scroll.setBackgroundRole(QPalette.Mid)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(200, 200)
        self.preview_label.setStyleSheet("background: #999;")
        self.preview_scroll.setWidget(self.preview_label)
        self.preview_stack.addWidget(self.preview_scroll)

        # ----- Index 1: Inline editor (QGraphicsView) -----
        from ui.sticker_editor import StickerScene
        self.editor_scene = None  # created lazily in on_edit_mode_toggled
        self.editor_view = None
        self._editor_initialized = False
        # Will create editor scene when user first enables edit mode

        right_layout.addWidget(self.preview_stack, 1)

        self.count_label = QLabel("0 stickers in sheet")
        self.count_label.setStyleSheet("padding: 4px; color: #333;")
        right_layout.addWidget(self.count_label)

        self.items_model = QStandardItemModel(0, 4)
        self.items_model.setHorizontalHeaderLabels(["#", "Barcode", "Product", "Qty"])
        self.items_table = QTableView()
        self.items_table.setModel(self.items_model)
        self.items_table.setMaximumHeight(120)
        self.items_table.setSelectionBehavior(QTableView.SelectRows)
        self.items_table.setEditTriggers(QTableView.NoEditTriggers)
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.items_table)

        del_row = QHBoxLayout()
        self.del_sel_btn = QPushButton("✖ Remove Selected Row")
        self.del_sel_btn.clicked.connect(self.on_remove_selected)
        del_row.addWidget(self.del_sel_btn)
        self.fill_sheet_btn = QPushButton("📋 Fill Sheet")
        self.fill_sheet_btn.setToolTip("Duplicate first item to fill all sticker slots on the sheet")
        self.fill_sheet_btn.setStyleSheet("background: #e8f5e9; color: #2e7d32; font-weight: bold;")
        self.fill_sheet_btn.clicked.connect(self.on_fill_sheet_clicked)
        del_row.addWidget(self.fill_sheet_btn)
        self.del_all_btn = QPushButton("✖ Clear All")
        self.del_all_btn.clicked.connect(self.on_clear_clicked)
        del_row.addWidget(self.del_all_btn)
        right_layout.addLayout(del_row)

        # ----- Properties panel (always visible — Canva-like) -----
        self.props_panel = QGroupBox("Element Properties / عنصر کی خصوصیات")
        self.props_panel.setVisible(True)
        pp_layout = QVBoxLayout(self.props_panel)

        # Element selector
        from PyQt5.QtWidgets import QFormLayout as QFL
        elem_form = QFL()
        self.elem_combo = QComboBox()
        self.elem_combo.currentIndexChanged.connect(self.on_elem_combo_changed)
        elem_form.addRow("Element:", self.elem_combo)

        # Enabled checkbox
        self.elem_enabled_chk = QCheckBox("Enabled / فعال")
        self.elem_enabled_chk.toggled.connect(self.on_elem_enabled_toggled)
        elem_form.addRow("", self.elem_enabled_chk)

        # Position + size
        unit_sym = self.unit.symbol
        self.elem_x = QDoubleSpinBox()
        self.elem_x.setRange(-100, 500); self.elem_x.setDecimals(3); self.elem_x.setSuffix(f" {unit_sym}")
        self.elem_x.valueChanged.connect(self.on_elem_geom_changed)
        elem_form.addRow("X (left):", self.elem_x)
        self.elem_y = QDoubleSpinBox()
        self.elem_y.setRange(-100, 500); self.elem_y.setDecimals(3); self.elem_y.setSuffix(f" {unit_sym}")
        self.elem_y.valueChanged.connect(self.on_elem_geom_changed)
        elem_form.addRow("Y (top):", self.elem_y)
        self.elem_w = QDoubleSpinBox()
        self.elem_w.setRange(0.5, 500); self.elem_w.setDecimals(3); self.elem_w.setSuffix(f" {unit_sym}")
        self.elem_w.valueChanged.connect(self.on_elem_geom_changed)
        elem_form.addRow("Width:", self.elem_w)
        self.elem_h = QDoubleSpinBox()
        self.elem_h.setRange(0.5, 500); self.elem_h.setDecimals(3); self.elem_h.setSuffix(f" {unit_sym}")
        self.elem_h.valueChanged.connect(self.on_elem_geom_changed)
        elem_form.addRow("Height:", self.elem_h)
        self.elem_rot = QDoubleSpinBox()
        self.elem_rot.setRange(-360, 360); self.elem_rot.setDecimals(1); self.elem_rot.setSuffix(" °")
        self.elem_rot.valueChanged.connect(self.on_elem_geom_changed)
        elem_form.addRow("Rotation:", self.elem_rot)

        # Quick rotate buttons
        qr_row = QHBoxLayout()
        for ang, lbl in [(-90, "↺90°"), (0, "0°"), (90, "↻90°"), (180, "180°")]:
            b = QPushButton(lbl)
            b.setMaximumWidth(50)
            b.clicked.connect(lambda _, a=ang: self.elem_rot.setValue(a))
            qr_row.addWidget(b)
        qr_row.addStretch(1)
        elem_form.addRow("Quick rotate:", qr_row)

        # Align buttons
        al_row = QHBoxLayout()
        for code, lbl, icon in [('left', 'Left', '⬅'), ('center', 'Center', '↔'), ('right', 'Right', '➡')]:
            b = QPushButton(f"{icon} {lbl}")
            b.clicked.connect(lambda _, c=code: self.on_elem_align_clicked(c))
            al_row.addWidget(b)
        al_row.addStretch(1)
        elem_form.addRow("Align:", al_row)

        pp_layout.addLayout(elem_form)

        # Font section (shown only for text elements)
        self.font_box = QGroupBox("Font / فونٹ")
        fb_layout = QFL(self.font_box)
        self.font_family = QComboBox()
        self.font_family.addItems(QFontDatabase().families())
        self.font_family.currentTextChanged.connect(self.on_elem_font_changed)
        fb_layout.addRow("Family:", self.font_family)
        self.font_size_spin = QDoubleSpinBox()
        self.font_size_spin.setRange(2, 72); self.font_size_spin.setDecimals(1); self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.valueChanged.connect(self.on_elem_font_changed)
        fb_layout.addRow("Size:", self.font_size_spin)
        ff_row = QHBoxLayout()
        self.bold_chk = QCheckBox("Bold")
        self.bold_chk.toggled.connect(self.on_elem_font_changed)
        ff_row.addWidget(self.bold_chk)
        self.italic_chk = QCheckBox("Italic")
        self.italic_chk.toggled.connect(self.on_elem_font_changed)
        ff_row.addWidget(self.italic_chk)
        ff_row.addStretch(1)
        fb_layout.addRow("Style:", ff_row)
        self.color_btn = QPushButton("🎨 Text Color")
        self.color_btn.clicked.connect(self.on_elem_color_clicked)
        fb_layout.addRow("Color:", self.color_btn)
        pp_layout.addWidget(self.font_box)

        # Image section (shown only for logo elements)
        self.image_box = QGroupBox("Image / تصویر")
        ib_layout = QFL(self.image_box)
        self.image_fit_combo = QComboBox()
        self.image_fit_combo.addItem("Contain (full image, may pad)", "contain")
        self.image_fit_combo.addItem("Cover (fill, may crop)", "cover")
        self.image_fit_combo.addItem("Stretch (fill, may distort)", "stretch")
        self.image_fit_combo.currentIndexChanged.connect(self.on_elem_image_fit_changed)
        ib_layout.addRow("Fit:", self.image_fit_combo)
        self.load_image_btn = QPushButton("📂 Load Image")
        self.load_image_btn.clicked.connect(self.on_elem_load_image)
        ib_layout.addRow("", self.load_image_btn)
        pp_layout.addWidget(self.image_box)

        right_layout.addWidget(self.props_panel)

        # ---- Wrap left panel in scroll area for small screens ----
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_inner)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setMinimumWidth(380)
        left_scroll.setMaximumWidth(460)

        # ---- Wrap right panel in scroll area too ----
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(right)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        right_scroll.setMinimumWidth(400)

        # ---- Add to splitter ----
        self.splitter.addWidget(left_scroll)
        self.splitter.addWidget(right_scroll)
        # Set sizes — left smaller, right bigger
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([460, 820])

        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(self.splitter)

        self._build_statusbar()
        self._update_layout_info()

        # Initialize the inline editor immediately (always interactive)
        self._init_inline_editor()
        self._populate_elem_combo()
        # Show editor view (index 1) by default
        if self.editor_view:
            self.preview_stack.setCurrentIndex(1)
            QTimer.singleShot(50, self._fit_editor_view)

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

    def on_price_enabled_toggled(self, checked: bool):
        # Enable/disable price element in template
        for e in self.template.elements:
            if e.id == 'price':
                e.enabled = bool(checked)
                break
        else:
            # Price element doesn't exist — add it
            if checked:
                from core.templates import StickerElement
                lay = self._current_layout()
                price_h = lay.sticker_h_mm * 0.12
                price_pt = max(4.0, min(14.0, lay.sticker_h_mm * 0.16))
                self.template.elements.append(StickerElement(
                    id='price',
                    label='Price / قیمت',
                    enabled=True,
                    x_mm=0.5, y_mm=lay.sticker_h_mm - price_h - 0.5,
                    w_mm=lay.sticker_w_mm - 1.0,
                    h_mm=price_h,
                    font_family='Arial',
                    font_size_pt=price_pt,
                    bold=True,
                    align='center',
                    color='#c62828',
                ))
        self.price_edit.setEnabled(checked)
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
            'price': self.price_edit.text().strip() if self.price_enabled_chk.isChecked() else '',
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

    def on_fill_sheet_clicked(self):
        """Duplicate the first item to fill all sticker slots on the current sheet."""
        if not self.current_items:
            QMessageBox.warning(self, "Empty",
                                "Please add at least one sticker first, then click Fill Sheet.")
            return
        lay = self._current_layout()
        slots = total_slots(lay)
        first = self.current_items[0]
        # Fill up to the sheet capacity
        import copy
        while len(self.current_items) < slots:
            self.current_items.append(copy.deepcopy(first))
        # If more than one sheet's worth, trim to exact multiple
        if len(self.current_items) > slots:
            self.current_items = self.current_items[:slots]
        self._refresh_preview()
        self.statusBar().showMessage(
            f"Filled sheet: {len(self.current_items)} stickers on 1 sheet",
            5000
        )

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
            # CRITICAL FIX: Regenerate the template for the new sticker dimensions.
            # Previously we only updated sticker_w_mm/h_mm but kept old element
            # positions — which were designed for a different sticker size.
            # This caused elements (especially barcode) to be at wrong positions
            # or extend beyond the sticker boundary, making them invisible.
            # Now we regenerate the template with proper positions for the new size.
            # Preserve barcode enabled/disabled state from Include Barcode checkbox.
            include_barcode = self.barcode_enabled_chk.isChecked() if hasattr(self, 'barcode_enabled_chk') else True
            include_price = self.price_enabled_chk.isChecked() if hasattr(self, 'price_enabled_chk') else False
            self.template = default_template(
                lay.sticker_w_mm, lay.sticker_h_mm,
                include_barcode=include_barcode,
                include_price=include_price,
            )
            self.db.set_setting('sticker_template_json', template_to_json(self.template))
        self._update_layout_info()
        self._refresh_preview()
        self._update_statusbar()

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
            # Render the static pixmap (for PDF preview / fallback)
            pix = render_preview(lay, self.current_items, self.template, dpi=200)
            self._preview_base_pixmap = pix
            if not hasattr(self, '_preview_zoom'):
                self._preview_zoom = 1.0
            self._apply_preview_zoom()
        except Exception as e:
            self.preview_label.setText(f"Preview error:\n{e}")
        # Also refresh the interactive editor scene
        if hasattr(self, '_editor_initialized') and self._editor_initialized:
            self._refresh_editor()

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

    # ----------------------------------------------- sticker editor (INLINE — always on)
    def on_edit_layout_clicked(self):
        """Refresh the editor view."""
        self._refresh_editor()

    def _init_inline_editor(self):
        """Lazily initialize the QGraphicsScene + QGraphicsView for inline editor."""
        if self._editor_initialized:
            return
        from ui.sticker_editor import StickerScene, ElementItem
        # Build sample data from current inputs
        if self.current_items:
            sample_data = self.current_items[0]
        else:
            sample_data = self._build_sample_data()
        lay = self._current_layout()
        self.template.sticker_w_mm = lay.sticker_w_mm
        self.template.sticker_h_mm = lay.sticker_h_mm
        self.editor_scene = StickerScene(self.template, sample_data)
        self.editor_view = ZoomableGraphicsView(self.editor_scene)
        self.editor_view.setRenderHint(QPainter.Antialiasing, True)
        self.editor_view.setBackgroundBrush(QColor('#d0d0d0'))
        self.editor_view.setMinimumSize(400, 300)
        # Connect signals
        self.editor_scene.element_selection_changed.connect(self._on_editor_selection_changed)
        self.editor_scene.element_changed.connect(self._on_editor_element_changed)
        self.preview_stack.addWidget(self.editor_view)
        self._editor_initialized = True

    def _build_sample_data(self):
        return {
            'company_name': self.company_edit.text() or 'Company Name',
            'product_name': self.product_edit.text() or 'Product Name',
            'product_code': self.code_edit.text() or 'CODE-001',
            'barcode': self.barcode_edit.text() or '501234567890',
            'mfg_date': self.mfg_date.date().toString("yyyy-MM-dd"),
            'exp_date': self.exp_date.date().toString("yyyy-MM-dd"),
            'mobile': self.mobile_edit.text() or '+92 300 1234567',
        }

    def _refresh_editor(self):
        """Rebuild the editor scene when template/layout changes."""
        if not self.editor_scene:
            return
        # Update sample data from current inputs
        if self.current_items:
            self.editor_scene.sample_data = self.current_items[0]
        else:
            self.editor_scene.sample_data = self._build_sample_data()
        lay = self._current_layout()
        self.template.sticker_w_mm = lay.sticker_w_mm
        self.template.sticker_h_mm = lay.sticker_h_mm
        self.editor_scene.template = self.template
        self.editor_scene.refresh()
        # Fit the view to the scene
        QTimer.singleShot(20, self._fit_editor_view)

    def _fit_editor_view(self):
        if not self.editor_view:
            return
        # Use a reasonable scale that makes the sticker visible but not too big
        lay = self._current_layout()
        # Target ~250-400px width for sticker
        target_w = max(250, min(450, self.editor_view.viewport().width() - 40))
        scale = target_w / (lay.sticker_w_mm * (1.0 / self.editor_scene.mm_per_px))
        self.editor_view.setTransform(QTransform.fromScale(scale, scale))

    def _populate_elem_combo(self):
        """Populate the element dropdown in the properties panel."""
        self.elem_combo.blockSignals(True)
        self.elem_combo.clear()
        for e in self.template.elements:
            label = e.label
            if not e.enabled:
                label = f"[OFF] {label}"
            self.elem_combo.addItem(label, id(e))
        self.elem_combo.blockSignals(False)
        # Select first element
        if self.template.elements:
            self.elem_combo.setCurrentIndex(0)
            self._show_elem_props(self.template.elements[0])

    def _selected_elem(self):
        """Return the currently selected element from the combo (or None)."""
        if not hasattr(self, 'elem_combo'):
            return None
        idx = self.elem_combo.currentIndex()
        if idx < 0 or idx >= len(self.template.elements):
            return None
        return self.template.elements[idx]

    def _on_editor_selection_changed(self, element):
        """Called when an element is clicked in the graphics scene."""
        # Find the index in the combo
        for i, e in enumerate(self.template.elements):
            if e is element:
                self.elem_combo.blockSignals(True)
                self.elem_combo.setCurrentIndex(i)
                self.elem_combo.blockSignals(False)
                break
        self._show_elem_props(element)

    def _on_editor_element_changed(self, element):
        """Called when an element is dragged in the graphics scene."""
        # Update the X/Y fields
        if not hasattr(self, 'elem_x'):
            return
        for w in [self.elem_x, self.elem_y]:
            w.blockSignals(True)
        self.elem_x.setValue(self.unit.from_mm(element.x_mm))
        self.elem_y.setValue(self.unit.from_mm(element.y_mm))
        for w in [self.elem_x, self.elem_y]:
            w.blockSignals(False)
        # Refresh the editor scene
        if self.editor_scene:
            self.editor_scene.invalidate()
        # Save template
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def _show_elem_props(self, element):
        """Display the properties of the given element in the properties panel."""
        if element is None:
            return
        for w in [self.elem_x, self.elem_y, self.elem_w, self.elem_h,
                  self.elem_rot, self.font_size_spin, self.font_family,
                  self.bold_chk, self.italic_chk, self.elem_enabled_chk,
                  self.image_fit_combo]:
            w.blockSignals(True)
        self.elem_x.setValue(self.unit.from_mm(element.x_mm))
        self.elem_y.setValue(self.unit.from_mm(element.y_mm))
        self.elem_w.setValue(self.unit.from_mm(element.w_mm))
        self.elem_h.setValue(self.unit.from_mm(element.h_mm))
        self.elem_rot.setValue(element.rotation)
        self.elem_enabled_chk.setChecked(element.enabled)
        # Font properties (only for text elements)
        is_text = element.id not in ('barcode', 'logo')
        is_image = element.id == 'logo' or bool(element.image_data)
        self.font_box.setVisible(is_text)
        self.image_box.setVisible(is_image)
        if is_text:
            self.font_family.setCurrentText(element.font_family)
            self.font_size_spin.setValue(element.font_size_pt)
            self.bold_chk.setChecked(element.bold)
            self.italic_chk.setChecked(element.italic)
        if is_image:
            for i in range(self.image_fit_combo.count()):
                if self.image_fit_combo.itemData(i) == element.image_fit:
                    self.image_fit_combo.setCurrentIndex(i)
                    break
        for w in [self.elem_x, self.elem_y, self.elem_w, self.elem_h,
                  self.elem_rot, self.font_size_spin, self.font_family,
                  self.bold_chk, self.italic_chk, self.elem_enabled_chk,
                  self.image_fit_combo]:
            w.blockSignals(False)

    def on_elem_combo_changed(self, idx: int):
        """Called when the element dropdown selection changes."""
        e = self._selected_elem()
        if e is None:
            return
        self._show_elem_props(e)
        # Also select it in the graphics scene
        if self.editor_scene:
            from ui.sticker_editor import ElementItem
            for it in self.editor_scene.items():
                if isinstance(it, ElementItem) and it.element is e:
                    it.setSelected(True)
                    break

    def on_elem_enabled_toggled(self, checked: bool):
        e = self._selected_elem()
        if e is None:
            return
        e.enabled = bool(checked)
        self._refresh_editor()
        self._populate_elem_combo()
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def on_elem_geom_changed(self):
        e = self._selected_elem()
        if e is None:
            return
        e.x_mm = self.unit.to_mm(self.elem_x.value())
        e.y_mm = self.unit.to_mm(self.elem_y.value())
        e.w_mm = max(1.0, self.unit.to_mm(self.elem_w.value()))
        e.h_mm = max(1.0, self.unit.to_mm(self.elem_h.value()))
        e.rotation = self.elem_rot.value()
        self._refresh_editor()
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def on_elem_font_changed(self):
        e = self._selected_elem()
        if e is None or e.id in ('barcode', 'logo'):
            return
        e.font_family = self.font_family.currentText()
        e.font_size_pt = float(self.font_size_spin.value())
        e.bold = self.bold_chk.isChecked()
        e.italic = self.italic_chk.isChecked()
        self._refresh_editor()
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def on_elem_color_clicked(self):
        from PyQt5.QtWidgets import QColorDialog
        e = self._selected_elem()
        if e is None:
            return
        c = QColorDialog.getColor(QColor(e.color), self, "Pick text color")
        if c.isValid():
            e.color = c.name()
            self._refresh_editor()
            self.db.set_setting('sticker_template_json',
                                template_to_json(self.template))

    def on_elem_align_clicked(self, code: str):
        e = self._selected_elem()
        if e is None or e.id in ('barcode', 'logo'):
            return
        e.align = code
        self._refresh_editor()
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def on_elem_image_fit_changed(self):
        e = self._selected_elem()
        if e is None:
            return
        e.image_fit = self.image_fit_combo.currentData()
        self._refresh_editor()
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def on_elem_load_image(self):
        """Load an image into the selected logo element."""
        e = self._selected_elem()
        if e is None:
            QMessageBox.information(self, "Select Element",
                "Please select the 'Logo' element first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if not path:
            return
        try:
            import base64
            # Determine format
            ext = path.lower().rsplit('.', 1)[-1] if '.' in path else 'png'
            if ext in ('jpg', 'jpeg'):
                fmt = 'JPEG'
            elif ext == 'bmp':
                fmt = 'BMP'
            elif ext == 'gif':
                fmt = 'GIF'
            else:
                fmt = 'PNG'
            with open(path, 'rb') as f:
                data = base64.b64encode(f.read()).decode('ascii')
            e.image_data = data
            e.image_format = fmt
            self._refresh_editor()
            self.db.set_setting('sticker_template_json',
                                template_to_json(self.template))
            QMessageBox.information(self, "Image Loaded",
                f"✓ Image loaded into the '{e.label}' element.\n"
                f"You can resize/reposition it using the controls above.")
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Could not load image:\n{ex}")

    # ----------------------------------------------- logo upload (top-level)
    def on_logo_clicked(self):
        """Add a logo element to the template and load an image into it."""
        # Check if a logo element already exists
        logo_elem = None
        for e in self.template.elements:
            if e.id == 'logo':
                logo_elem = e
                break
        if logo_elem is None:
            # Create a new logo element at top-left
            lay = self._current_layout()
            logo_size = min(8.0, lay.sticker_h_mm * 0.4, lay.sticker_w_mm * 0.25)
            logo_elem = StickerElement(
                id='logo',
                label='Logo / لوگو',
                enabled=True,
                x_mm=0.5, y_mm=0.5,
                w_mm=logo_size, h_mm=logo_size,
                image_data='',
                image_format='PNG',
                image_fit='contain',
            )
            self.template.elements.insert(0, logo_elem)
        # Now load the image
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if not path:
            # If user cancelled but we created the element, leave it as a placeholder
            self._refresh_preview()
            return
        try:
            import base64
            ext = path.lower().rsplit('.', 1)[-1] if '.' in path else 'png'
            if ext in ('jpg', 'jpeg'):
                fmt = 'JPEG'
            elif ext == 'bmp':
                fmt = 'BMP'
            elif ext == 'gif':
                fmt = 'GIF'
            else:
                fmt = 'PNG'
            with open(path, 'rb') as f:
                data = base64.b64encode(f.read()).decode('ascii')
            logo_elem.image_data = data
            logo_elem.image_format = fmt
            logo_elem.enabled = True
            self.db.set_setting('sticker_template_json',
                                template_to_json(self.template))
            self._refresh_preview()
            # If we're in edit mode, refresh editor + combo
            if True:
                self._refresh_editor()
                self._populate_elem_combo()
            QMessageBox.information(self, "Logo Added",
                f"✓ Logo added to the sticker.\n"
                f"Use 'Edit Layout' mode to resize/reposition it.")
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Could not load logo:\n{ex}")

    def on_remove_logo_clicked(self):
        """Remove the logo element from the template."""
        for i, e in enumerate(self.template.elements):
            if e.id == 'logo':
                del self.template.elements[i]
                self.db.set_setting('sticker_template_json',
                                    template_to_json(self.template))
                self._refresh_preview()
                if True:
                    self._refresh_editor()
                    self._populate_elem_combo()
                QMessageBox.information(self, "Logo Removed",
                    "✓ Logo removed from the sticker.")
                return
        QMessageBox.information(self, "No Logo", "There is no logo element in the sticker.")

    # ----------------------------------------------- zoom controls
    def on_zoom_in(self):
        if self.preview_stack.currentIndex() == 1 and self.editor_view:
            self.editor_view.scale(1.25, 1.25)
            self._update_zoom_label()
        else:
            # For static preview, scale the pixmap
            self._preview_zoom *= 1.25
            self._apply_preview_zoom()

    def on_zoom_out(self):
        if self.preview_stack.currentIndex() == 1 and self.editor_view:
            self.editor_view.scale(0.8, 0.8)
            self._update_zoom_label()
        else:
            self._preview_zoom *= 0.8
            self._apply_preview_zoom()

    def on_zoom_actual(self):
        """Show at actual physical size (1mm screen = 1mm paper)."""
        if self.preview_stack.currentIndex() == 1 and self.editor_view:
            # Reset to 1:1 (which means scale of 1.0 in scene coords)
            from PyQt5.QtGui import QTransform
            # The scene already has mm_per_px = 0.25 (so 1px = 0.25mm = 4px/mm)
            # To make 1mm screen = 1mm paper, we need screen_scale = 1/(mm_per_px * (25.4/96))
            # i.e., 96dpi screen, 4px/mm in scene → scale = 96/25.4/4 ≈ 0.945
            screen_dpi = 96  # approximation
            actual_scale = screen_dpi / 25.4 * 0.25  # = mm_per_px
            # Actually simpler: scale = (screen dpi) / (scene dpi)
            # scene_dpi = 25.4 / mm_per_px = 25.4 / 0.25 = 101.6
            # scale = 96 / 101.6 ≈ 0.945
            scene_dpi = 25.4 / self.editor_scene.mm_per_px
            actual_scale = screen_dpi / scene_dpi
            self.editor_view.setTransform(QTransform.fromScale(actual_scale, actual_scale))
            self._update_zoom_label(actual_scale)
        else:
            self._preview_zoom = 1.0
            self._apply_preview_zoom()

    def on_zoom_fit(self):
        if self.preview_stack.currentIndex() == 1 and self.editor_view:
            self._fit_editor_view()
            self._update_zoom_label()
        else:
            self._preview_zoom = 1.0
            self._apply_preview_zoom()

    def _update_zoom_label(self, scale: float = None):
        if scale is None and self.editor_view:
            m = self.editor_view.transform().m11()
            scale = m
        if scale:
            self.zoom_label.setText(f"{int(scale * 100)}%")

    def _apply_preview_zoom(self):
        """Apply zoom to the static preview pixmap."""
        if not hasattr(self, '_preview_zoom'):
            self._preview_zoom = 1.0
        if not hasattr(self, '_preview_base_pixmap') or self._preview_base_pixmap is None:
            return
        if self._preview_zoom < 0.1:
            self._preview_zoom = 0.1
        if self._preview_zoom > 10:
            self._preview_zoom = 10
        pm = self._preview_base_pixmap
        new_w = int(pm.width() * self._preview_zoom)
        new_h = int(pm.height() * self._preview_zoom)
        scaled = pm.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.zoom_label.setText(f"{int(self._preview_zoom * 100)}%")

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
