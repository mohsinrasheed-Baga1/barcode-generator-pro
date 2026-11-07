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


APP_TITLE = "Barcode Generator Pro"
APP_VERSION = "5.1.0"


class ZoomableGraphicsView(QGraphicsView):
    """QGraphicsView with direct mouse wheel zoom toward cursor (Canva-like).
    Zoom is limited to 10%-500% to prevent elements from disappearing."""
    MIN_ZOOM = 0.10  # 10% — don't zoom out further than this
    MAX_ZOOM = 5.0   # 500% — don't zoom in further than this

    def __init__(self, scene=None, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self._total_zoom = 1.0

    def _update_zoom_label(self, scale: float = None):
        if scale is None:
            scale = self.transform().m11()
        pct = int(scale * 100)
        # Find the main window to update the label
        parent = self.parent()
        while parent and not hasattr(parent, 'zoom_label'):
            parent = parent.parent()
        if parent and hasattr(parent, 'zoom_label'):
            parent.zoom_label.setText(f"{pct}%")

    def wheelEvent(self, event):
        # Zoom toward cursor — wrapped in try/except to prevent crash
        try:
            if not self.scene() or self.scene().sceneRect().isNull():
                super().wheelEvent(event)
                return
            cursor_scene = self.mapToScene(event.pos())
            view_center = self.mapToScene(self.viewport().rect().center())
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1/1.15
            new_zoom = self._total_zoom * factor
            if new_zoom < self.MIN_ZOOM or new_zoom > self.MAX_ZOOM:
                event.accept()
                return
            self._total_zoom *= factor
            self.scale(factor, factor)
            # Compensate so cursor stays at same scene point
            new_cursor = self.mapToScene(event.pos())
            shift_x = new_cursor.x() - cursor_scene.x()
            shift_y = new_cursor.y() - cursor_scene.y()
            self.centerOn(QPointF(view_center.x() + shift_x,
                                  view_center.y() + shift_y))
            self._update_zoom_label()
            event.accept()
        except Exception:
            # If anything goes wrong, just do normal scroll
            super().wheelEvent(event)

    def reset_zoom(self):
        """Reset zoom to 100% and center on scene."""
        self.resetTransform()
        self._total_zoom = 1.0
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
        # Recalculate total_zoom after fitInView
        self._total_zoom = self.transform().m11()


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
        # v4.0: No more left panel — full-width canvas with top + bottom bars
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== TOP BAR (dark, modern — barcode + font + zoom) =====
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(6, 4, 6, 4)
        top_bar.setSpacing(6)

        # Barcode input + type + include
        top_bar.addWidget(QLabel("Barcode:"))
        self.barcode_edit = QLineEdit()
        self.barcode_edit.setMaximumWidth(100)
        self.barcode_edit.setPlaceholderText("Number")
        self.barcode_edit.textChanged.connect(lambda _: self._live_update())
        top_bar.addWidget(self.barcode_edit)
        self.barcode_type_combo = QComboBox()
        from core.barcode_gen import get_barcode_types_list
        for key, label in get_barcode_types_list():
            self.barcode_type_combo.addItem(label, key)
        self.barcode_type_combo.setMaximumWidth(110)
        self.barcode_type_combo.currentIndexChanged.connect(lambda _: self._on_barcode_type_changed())
        top_bar.addWidget(self.barcode_type_combo)
        self.barcode_enabled_chk = QCheckBox("BC")
        self.barcode_enabled_chk.setChecked(True)
        self.barcode_enabled_chk.setToolTip("Include Barcode")
        self.barcode_enabled_chk.toggled.connect(self.on_barcode_enabled_toggled)
        top_bar.addWidget(self.barcode_enabled_chk)

        # T — Text tool button (add custom text on canvas)
        self.text_tool_btn = QPushButton("T")
        self.text_tool_btn.setMaximumWidth(30)
        self.text_tool_btn.setToolTip("Add Text (click to insert text element)")
        self.text_tool_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.text_tool_btn.clicked.connect(self._add_text_element)
        top_bar.addWidget(self.text_tool_btn)

        top_bar.addWidget(self._make_separator())

        # Font controls
        self.toolbar_font = QComboBox()
        self.toolbar_font.addItems(QFontDatabase().families())
        self.toolbar_font.setMaximumWidth(130)
        self.toolbar_font.currentTextChanged.connect(self._toolbar_font_changed)
        top_bar.addWidget(self.toolbar_font)
        self.toolbar_size = QDoubleSpinBox()
        self.toolbar_size.setRange(2, 72); self.toolbar_size.setDecimals(1)
        self.toolbar_size.setSuffix("pt"); self.toolbar_size.setMaximumWidth(60)
        self.toolbar_size.valueChanged.connect(self._toolbar_font_changed)
        top_bar.addWidget(self.toolbar_size)
        self.toolbar_bold = QPushButton("B")
        self.toolbar_bold.setCheckable(True); self.toolbar_bold.setMaximumWidth(28)
        self.toolbar_bold.setStyleSheet("font-weight: bold;")
        self.toolbar_bold.toggled.connect(self._toolbar_font_changed)
        top_bar.addWidget(self.toolbar_bold)
        self.toolbar_italic = QPushButton("I")
        self.toolbar_italic.setCheckable(True); self.toolbar_italic.setMaximumWidth(28)
        self.toolbar_italic.toggled.connect(self._toolbar_font_changed)
        top_bar.addWidget(self.toolbar_italic)

        top_bar.addWidget(self._make_separator())

        # Align + color + rotate + border
        for code, icon, tip in [('left', '⬅', 'Left'), ('center', '↔', 'Center'), ('right', '➡', 'Right')]:
            b = QPushButton(icon); b.setMaximumWidth(28); b.setToolTip(tip)
            b.clicked.connect(lambda _, c=code: self._toolbar_align(c))
            top_bar.addWidget(b)
            if code == 'left': self.toolbar_align_left = b
            elif code == 'center': self.toolbar_align_center = b
            elif code == 'right': self.toolbar_align_right = b
        self.toolbar_color = QPushButton("🎨"); self.toolbar_color.setMaximumWidth(32)
        self.toolbar_color.clicked.connect(self.on_elem_color_clicked)
        top_bar.addWidget(self.toolbar_color)
        self.toolbar_rot_left = QPushButton("↺"); self.toolbar_rot_left.setMaximumWidth(28)
        self.toolbar_rot_left.clicked.connect(lambda: self._toolbar_rotate(-90))
        top_bar.addWidget(self.toolbar_rot_left)
        self.toolbar_rot_right = QPushButton("↻"); self.toolbar_rot_right.setMaximumWidth(28)
        self.toolbar_rot_right.clicked.connect(lambda: self._toolbar_rotate(90))
        top_bar.addWidget(self.toolbar_rot_right)
        self.toolbar_border = QPushButton("🔲"); self.toolbar_border.setMaximumWidth(32)
        self.toolbar_border.setToolTip("Border"); self.toolbar_border.clicked.connect(self._toggle_border)
        top_bar.addWidget(self.toolbar_border)

        top_bar.addWidget(self._make_separator())

        # Zoom
        self.zoom_out_btn = QPushButton("−"); self.zoom_out_btn.setMaximumWidth(28)
        self.zoom_out_btn.clicked.connect(self.on_zoom_out)
        top_bar.addWidget(self.zoom_out_btn)
        self.zoom_label = QLabel("100%"); self.zoom_label.setMinimumWidth(40)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        top_bar.addWidget(self.zoom_label)
        self.zoom_in_btn = QPushButton("+"); self.zoom_in_btn.setMaximumWidth(28)
        self.zoom_in_btn.clicked.connect(self.on_zoom_in)
        top_bar.addWidget(self.zoom_in_btn)
        self.zoom_fit_btn = QPushButton("Fit"); self.zoom_fit_btn.setMaximumWidth(36)
        self.zoom_fit_btn.clicked.connect(self.on_zoom_fit)
        top_bar.addWidget(self.zoom_fit_btn)

        top_bar.addStretch(1)

        # Selected element indicator
        self.selected_elem_label = QLabel("Click element to select")
        self.selected_elem_label.setStyleSheet("color: #aaa; font-size: 11px;")
        top_bar.addWidget(self.selected_elem_label)

        top_bar.addWidget(self._make_separator())
        # Powered by
        powered = QLabel("⚡ Powered by Mohsin Rasheed Baga")
        powered.setStyleSheet("color: #4fc3f7; font-size: 10px; font-weight: bold;")
        top_bar.addWidget(powered)

        top_widget = QWidget()
        top_widget.setLayout(top_bar)
        top_widget.setStyleSheet("""
            QWidget { background: #1e1e2e; }
            QLabel { color: #cdd6f4; font-size: 11px; }
            QPushButton { background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                          border-radius: 3px; padding: 3px 8px; font-size: 11px; }
            QPushButton:hover { background: #45475a; }
            QPushButton:pressed { background: #181825; }
            QPushButton:checked { background: #1a4d8f; color: white; }
            QComboBox { background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                        border-radius: 3px; padding: 2px 6px; font-size: 11px; }
            QDoubleSpinBox { background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                             border-radius: 3px; padding: 2px 4px; font-size: 11px; }
            QLineEdit { background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                        border-radius: 3px; padding: 2px 6px; font-size: 11px; }
            QCheckBox { color: #cdd6f4; }
            QFrame { background: #45475a; }
        """)
        main_layout.addWidget(top_widget)

        # ===== CANVAS (full width, dark background) =====
        self.preview_stack = QStackedWidget()
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setAlignment(Qt.AlignCenter)
        self.preview_scroll.setStyleSheet("background: #181825;")
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_scroll.setWidget(self.preview_label)
        self.preview_stack.addWidget(self.preview_scroll)

        self.editor_scene = None
        self.editor_view = None
        self._editor_initialized = False

        main_layout.addWidget(self.preview_stack, 1)

        # ===== BOTTOM BAR (layout + size + logo + print) =====
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(6, 4, 6, 4)
        bottom_bar.setSpacing(6)

        # Layout selector
        self.layout_combo = QComboBox()
        for key, lay in SHEET_PRESETS.items():
            self.layout_combo.addItem(lay.name, key)
        for key, lay in LABEL_PRESETS.items():
            self.layout_combo.addItem(lay.name, key)
        self.layout_combo.addItem("Custom...", "__custom__")
        self.layout_combo.setMaximumWidth(200)
        idx = self.layout_combo.findData(self.layout_key)
        if idx >= 0: self.layout_combo.setCurrentIndex(idx)
        self.layout_combo.currentIndexChanged.connect(self.on_layout_changed)
        bottom_bar.addWidget(QLabel("Layout:"))
        bottom_bar.addWidget(self.layout_combo)

        # Manual size
        self.sticker_w_input = QDoubleSpinBox()
        self.sticker_w_input.setRange(5, 500); self.sticker_w_input.setDecimals(1)
        self.sticker_w_input.setSuffix("mm"); self.sticker_w_input.setMaximumWidth(70)
        self.sticker_w_input.valueChanged.connect(self._on_manual_size_changed)
        bottom_bar.addWidget(QLabel("W:"))
        bottom_bar.addWidget(self.sticker_w_input)
        self.sticker_h_input = QDoubleSpinBox()
        self.sticker_h_input.setRange(3, 500); self.sticker_h_input.setDecimals(1)
        self.sticker_h_input.setSuffix("mm"); self.sticker_h_input.setMaximumWidth(70)
        self.sticker_h_input.valueChanged.connect(self._on_manual_size_changed)
        bottom_bar.addWidget(QLabel("H:"))
        bottom_bar.addWidget(self.sticker_h_input)

        # Stickers per row (1/2/3/4) — roll layout
        bottom_bar.addWidget(QLabel("Per Row:"))
        self.stickers_per_row = QSpinBox()
        self.stickers_per_row.setRange(1, 4)
        self.stickers_per_row.setValue(1)
        self.stickers_per_row.setMaximumWidth(40)
        self.stickers_per_row.setToolTip("Stickers per row on the roll")
        self.stickers_per_row.valueChanged.connect(self._on_stickers_per_row_changed)
        bottom_bar.addWidget(self.stickers_per_row)

        # Logo
        self.logo_btn = QPushButton("🖼 Logo")
        self.logo_btn.clicked.connect(self.on_logo_clicked)
        bottom_bar.addWidget(self.logo_btn)
        self.remove_logo_btn = QPushButton("✖")
        self.remove_logo_btn.setMaximumWidth(28)
        self.remove_logo_btn.clicked.connect(self.on_remove_logo_clicked)
        bottom_bar.addWidget(self.remove_logo_btn)

        bottom_bar.addWidget(self._make_separator())

        # Save/Open project
        self.save_project_btn = QPushButton("💾 Save")
        self.save_project_btn.setToolTip("Save Project")
        self.save_project_btn.clicked.connect(self._save_project)
        bottom_bar.addWidget(self.save_project_btn)
        self.open_project_btn = QPushButton("📂 Open")
        self.open_project_btn.setToolTip("Open Project")
        self.open_project_btn.clicked.connect(self._open_project)
        bottom_bar.addWidget(self.open_project_btn)

        bottom_bar.addWidget(self._make_separator())

        # CSV
        self.import_btn = QPushButton("📂 CSV")
        self.import_btn.clicked.connect(self.on_import_csv)
        bottom_bar.addWidget(self.import_btn)
        self.template_btn = QPushButton("📝 Template")
        self.template_btn.clicked.connect(self.on_save_template)
        bottom_bar.addWidget(self.template_btn)
        self.fill_sheet_btn = QPushButton("📋 Fill")
        self.fill_sheet_btn.setMaximumWidth(50)
        self.fill_sheet_btn.clicked.connect(self.on_fill_sheet_clicked)
        bottom_bar.addWidget(self.fill_sheet_btn)

        bottom_bar.addStretch(1)

        # Print buttons
        self.print_btn = QPushButton("🖨 PRINT")
        self.print_btn.setStyleSheet("""
            QPushButton { background: #f38ba8; color: #1e1e2e; font-weight: bold;
                          border-radius: 4px; padding: 6px 16px; font-size: 12px; }
            QPushButton:hover { background: #eba0ac; }
        """)
        self.print_btn.clicked.connect(self.on_print_clicked)
        bottom_bar.addWidget(self.print_btn)
        self.pdf_btn = QPushButton("📄 PDF")
        self.pdf_btn.setStyleSheet("""
            QPushButton { background: #fab387; color: #1e1e2e; font-weight: bold;
                          border-radius: 4px; padding: 6px 12px; font-size: 12px; }
            QPushButton:hover { background: #f5b895; }
        """)
        self.pdf_btn.clicked.connect(self.on_save_pdf_clicked)
        bottom_bar.addWidget(self.pdf_btn)
        self.quick_print_btn = QPushButton("⚡ Quick")
        self.quick_print_btn.setStyleSheet("""
            QPushButton { background: #a6e3a1; color: #1e1e2e; font-weight: bold;
                          border-radius: 4px; padding: 6px 12px; font-size: 12px; }
            QPushButton:hover { background: #b3e6ad; }
        """)
        self.quick_print_btn.clicked.connect(self.on_quick_print_clicked)
        bottom_bar.addWidget(self.quick_print_btn)

        bottom_widget = QWidget()
        bottom_widget.setLayout(bottom_bar)
        bottom_widget.setStyleSheet("""
            QWidget { background: #1e1e2e; }
            QLabel { color: #cdd6f4; font-size: 11px; }
            QPushButton { background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                          border-radius: 3px; padding: 4px 10px; font-size: 11px; }
            QPushButton:hover { background: #45475a; }
            QComboBox { background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                        border-radius: 3px; padding: 2px 6px; font-size: 11px; }
            QDoubleSpinBox { background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                             border-radius: 3px; padding: 2px 4px; font-size: 11px; }
            QFrame { background: #45475a; }
        """)
        main_layout.addWidget(bottom_widget)

        # Hidden form fields (kept for data compatibility, not visible)
        self.company_edit = QLineEdit(self.default_company)
        self.product_edit = QLineEdit()
        self.code_edit = QLineEdit()
        self.mobile_edit = QLineEdit(self.default_mobile)
        self.price_edit = QLineEdit()
        self.mfg_date = QDateEdit()
        self.mfg_date.setDate(QDate.currentDate())
        self.exp_date = QDateEdit()
        self.exp_date.setDate(QDate.currentDate().addMonths(12))
        self.copies_spin = QSpinBox()
        self.copies_spin.setValue(1)
        self.qty_spin = QSpinBox()
        self.qty_spin.setValue(1)
        self.add_btn = QPushButton()
        self.clear_btn = QPushButton()
        self.edit_layout_btn = QPushButton()
        self.settings_btn = QPushButton()
        self.history_btn = QPushButton()
        self.preview_btn = QPushButton()
        self.del_sel_btn = QPushButton()
        self.del_all_btn = QPushButton()
        self.price_enabled_chk = QCheckBox()
        self.price_enabled_chk.setChecked(False)
        self.company_enabled_chk = QCheckBox(); self.company_enabled_chk.setChecked(True)
        self.product_name_enabled_chk = QCheckBox(); self.product_name_enabled_chk.setChecked(True)
        self.code_enabled_chk = QCheckBox(); self.code_enabled_chk.setChecked(True)
        self.dates_enabled_chk = QCheckBox(); self.dates_enabled_chk.setChecked(True)
        self.mobile_enabled_chk = QCheckBox(); self.mobile_enabled_chk.setChecked(True)
        self.bulk_status = QLabel()
        self.items_model = QStandardItemModel(0, 3)
        self.items_model.setHorizontalHeaderLabels(["#", "Barcode", "Product"])
        self.items_table = QTableView()
        self.items_table.setModel(self.items_model)
        self.items_table.setMaximumHeight(0)  # hidden
        self.count_label = QLabel("0 stickers")
        self.layout_info = QLabel()

        # Keep references for compatibility
        self.props_panel = None
        self.elem_combo = None
        self.elem_enabled_chk = None
        self.elem_x = None; self.elem_y = None; self.elem_w = None; self.elem_h = None
        self.elem_rot = None
        self.font_box = None
        self.font_family = self.toolbar_font
        self.font_size_spin = self.toolbar_size
        self.bold_chk = self.toolbar_bold
        self.italic_chk = self.toolbar_italic
        self.image_box = None
        self.image_fit_combo = None
        self.load_image_btn = None
        self.preview_label_title = QLabel()

        # Status bar
        self._build_statusbar()

        # Keyboard shortcuts
        self._setup_shortcuts()

        # Initialize editor
        self._init_inline_editor()
        # CRITICAL: Show editor (index 1), not static preview (index 0)
        if self.preview_stack.count() > 1:
            self.preview_stack.setCurrentIndex(1)
        QTimer.singleShot(50, self._fit_editor_view)
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
    def _add_text_element(self):
        """T button — add a custom text element at the center of the first sticker slot."""
        from core.templates import StickerElement
        lay = self._current_layout()
        # Position at center of first sticker
        cx = lay.sticker_w_mm / 2 - 10  # offset so text is roughly centered
        cy = lay.sticker_h_mm / 2 - 2
        # Create a unique ID
        import time
        elem_id = f"text_{int(time.time() * 1000)}"
        new_elem = StickerElement(
            id=elem_id,
            label='Text / ٹیکسٹ',
            enabled=True,
            x_mm=cx, y_mm=cy,
            w_mm=20, h_mm=4,
            font_family='Arial',
            font_size_pt=7.0,
            bold=False,
            align='center',
        )
        # Set the text content by adding it to sample_data
        # We use a special key that matches the element id
        if not hasattr(self, '_custom_texts'):
            self._custom_texts = {}
        self._custom_texts[elem_id] = "Click to edit text"
        self.template.elements.append(new_elem)
        self._refresh_editor()
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))
        self.statusBar().showMessage("Text added — click on it to select, then change text in toolbar", 3000)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts: Ctrl+C/V/X/Z/A/D/Delete."""
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        QShortcut(QKeySequence.Copy, self, self._copy_element)
        QShortcut(QKeySequence.Paste, self, self._paste_element)
        QShortcut(QKeySequence.Cut, self, self._cut_element)
        QShortcut(QKeySequence.Undo, self, self._undo_change)
        QShortcut(QKeySequence.SelectAll, self, self._select_all)
        QShortcut(QKeySequence("Ctrl+D"), self, self._delete_selected)
        QShortcut(QKeySequence.Delete, self, self._delete_selected)

    def _delete_selected(self):
        """Ctrl+D / Delete — delete all selected elements from template."""
        if not self.editor_scene:
            return
        from ui.sticker_editor import ElementItem
        to_delete = []
        for it in self.editor_scene.items():
            if isinstance(it, ElementItem) and it.isSelected():
                to_delete.append(it.element)
        if not to_delete:
            return
        for elem in to_delete:
            if elem in self.template.elements:
                self.template.elements.remove(elem)
            # Also clean up custom texts
            if hasattr(self, '_custom_texts') and elem.id in self._custom_texts:
                del self._custom_texts[elem.id]
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))
        self._refresh_editor()
        self.statusBar().showMessage(f"Deleted {len(to_delete)} element(s)", 2000)

    def _copy_element(self):
        """Ctrl+C — copy selected element."""
        e = self._selected_elem()
        if e:
            import copy
            self._clipboard = copy.deepcopy(e)
            self.statusBar().showMessage(f"Copied: {e.label}", 2000)

    def _paste_element(self):
        """Ctrl+V — paste copied element."""
        if hasattr(self, '_clipboard') and self._clipboard:
            import copy
            new_elem = copy.deepcopy(self._clipboard)
            new_elem.x_mm += 2  # offset
            new_elem.y_mm += 2
            new_elem.id = f"custom_{id(new_elem)}"
            new_elem.label = f"{self._clipboard.label} (copy)"
            self.template.elements.append(new_elem)
            self._refresh_editor()
            self.db.set_setting('sticker_template_json',
                                template_to_json(self.template))
            self.statusBar().showMessage(f"Pasted: {new_elem.label}", 2000)

    def _cut_element(self):
        """Ctrl+X — cut selected element."""
        self._copy_element()
        e = self._selected_elem()
        if e and e.id not in ('barcode', 'barcode_digits'):
            self.template.elements.remove(e)
            self._refresh_editor()
            self.statusBar().showMessage(f"Cut: {e.label}", 2000)

    def _undo_change(self):
        """Ctrl+Z — undo (revert to last saved template)."""
        saved = self.db.get_setting('sticker_template_json', '')
        if saved:
            self.template = template_from_json(saved)
            self._refresh_editor()
            self.statusBar().showMessage("Undo", 2000)

    def _select_all(self):
        """Ctrl+A — select all elements."""
        if self.editor_scene:
            from ui.sticker_editor import ElementItem
            for it in self.editor_scene.items():
                if isinstance(it, ElementItem):
                    it.setSelected(True)

    def _make_separator(self):
        """Create a vertical separator line for the toolbar."""
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setMaximumWidth(2)
        return sep

    def _toggle_border(self):
        """Toggle sticker border on/off."""
        if self.template.border_width_mm > 0:
            self.template.border_width_mm = 0
            self.toolbar_border.setStyleSheet("")
        else:
            self.template.border_width_mm = 0.3
            self.template.border_color = '#000000'
            self.toolbar_border.setStyleSheet("background: #1a4d8f; color: white;")
        self._refresh_editor()
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def _toolbar_font_changed(self):
        """Called when font family, size, bold, or italic changes in toolbar.
        For text elements: changes font properties.
        For barcode: adjusts barcode height proportionally to 'size' value.
        For logo: adjusts image size."""
        e = self._selected_elem()
        if e is None:
            return
        if e.id == 'barcode':
            # For barcode, the 'size' spinner controls barcode height
            # Bigger size = taller barcode (better scanability)
            new_h = max(2.0, float(self.toolbar_size.value()))
            e.h_mm = new_h
        elif e.id == 'logo':
            # For logo, size controls both width and height equally
            new_size = max(2.0, float(self.toolbar_size.value()))
            e.w_mm = new_size
            e.h_mm = new_size
        else:
            # Text element — change font properties
            e.font_family = self.toolbar_font.currentText()
            e.font_size_pt = float(self.toolbar_size.value())
            e.bold = self.toolbar_bold.isChecked()
            e.italic = self.toolbar_italic.isChecked()
        self._refresh_editor()
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def _toolbar_align(self, code: str):
        e = self._selected_elem()
        if e is None or e.id in ('barcode', 'logo'):
            return
        e.align = code
        self._refresh_editor()
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def _toolbar_rotate(self, delta: float):
        """Rotate selected element by delta degrees."""
        e = self._selected_elem()
        if e is None:
            return
        new_rot = e.rotation + delta
        while new_rot > 360:
            new_rot -= 360
        while new_rot < -360:
            new_rot += 360
        e.rotation = new_rot
        self._refresh_editor()
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def _live_update(self):
        """Live update — typing in form fields updates ALL stickers in real-time."""
        data = self._build_sample_data()
        if not self.current_items:
            # Auto-create items so preview shows content immediately
            lay = self._current_layout()
            n_slots = total_slots(lay)
            for i in range(n_slots):
                self.current_items.append(dict(data))
        else:
            # Update ALL items with current form data (all stickers same)
            for item in self.current_items:
                item.update(data)
        # Refresh editor (updates all sticker previews)
        if hasattr(self, 'editor_scene') and self.editor_scene:
            self.editor_scene.sample_data = data
        self._refresh_preview()

    def _toggle_element(self, element_id: str, enabled: bool):
        """Enable/disable an element in the template."""
        for e in self.template.elements:
            if e.id == element_id:
                e.enabled = bool(enabled)
                break
        self._refresh_preview()
        self._update_statusbar()

    def _on_barcode_type_changed(self):
        """Update barcode type in template when dropdown changes."""
        bc_type = self.barcode_type_combo.currentData()
        for e in self.template.elements:
            if e.id == 'barcode':
                e.barcode_type = bc_type
                break
        self._refresh_preview()

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
                price_pt = max(7.0, min(16.0, lay.sticker_h_mm * 0.20))
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
        """Duplicate the first item to fill all sticker slots."""
        self._ensure_items()
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

    def _on_stickers_per_row_changed(self):
        """When stickers per row changes, create a custom multi-column layout."""
        n = self.stickers_per_row.value()
        sw = self.sticker_w_input.value()
        sh = self.sticker_h_input.value()
        gap = 3.0  # 3mm gap between stickers
        margin = 2.0  # 2mm margin
        paper_w = margin * 2 + sw * n + gap * (n - 1) if n > 1 else sw
        paper_h = sh
        # Create custom layout
        from core.layouts import custom_layout, StickerLayout
        self.custom_layout = StickerLayout(
            name=f'Custom Roll — {n} stickers per row ({sw}×{sh}mm)',
            paper_w_mm=paper_w, paper_h_mm=paper_h,
            margin_x_mm=margin, margin_y_mm=0,
            gap_x_mm=gap if n > 1 else 0, gap_y_mm=0,
            sticker_w_mm=sw, sticker_h_mm=sh,
            cols=n, rows=1, is_label=True,
        )
        self.layout_key = '__custom__'
        # Regenerate template
        include_barcode = self.barcode_enabled_chk.isChecked()
        include_price = self.price_enabled_chk.isChecked() if hasattr(self, 'price_enabled_chk') else False
        bc_type = self.barcode_type_combo.currentData() if hasattr(self, 'barcode_type_combo') else 'ean13'
        self.template = default_template(sw, sh, include_barcode=include_barcode,
                                          include_price=include_price, barcode_type=bc_type)
        self.db.set_setting('sticker_template_json', template_to_json(self.template))
        self._update_layout_info()
        self._refresh_preview()
        self._refresh_editor()
        self._update_statusbar()
        self.statusBar().showMessage(f"Layout: {n} stickers per row, each {sw}×{sh}mm", 3000)

    def _save_project(self):
        """Save current project (template + items + layout) to .bgp file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "Barcode Project (*.bgp)")
        if not path:
            return
        try:
            import json
            project = {
                'version': APP_VERSION,
                'template': json.loads(template_to_json(self.template)),
                'items': self.current_items,
                'layout_key': self.layout_key,
                'custom_layout': {
                    'paper_w_mm': self._current_layout().paper_w_mm,
                    'paper_h_mm': self._current_layout().paper_h_mm,
                    'sticker_w_mm': self._current_layout().sticker_w_mm,
                    'sticker_h_mm': self._current_layout().sticker_h_mm,
                    'cols': self._current_layout().cols,
                    'rows': self._current_layout().rows,
                    'is_label': self._current_layout().is_label,
                } if self.layout_key == '__custom__' else None,
                'stickers_per_row': self.stickers_per_row.value() if hasattr(self, 'stickers_per_row') else 1,
                'custom_texts': getattr(self, '_custom_texts', {}),
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(project, f, indent=2)
            self.statusBar().showMessage(f"Project saved: {path}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save project:\n{e}")

    def _open_project(self):
        """Open a .bgp project file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "Barcode Project (*.bgp)")
        if not path:
            return
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                project = json.load(f)
            # Load template
            self.template = template_from_json(json.dumps(project['template']))
            # Load items
            self.current_items = project.get('items', [])
            # Load layout
            cl = project.get('custom_layout')
            if cl:
                from core.layouts import StickerLayout
                self.custom_layout = StickerLayout(
                    name='Loaded Custom',
                    paper_w_mm=cl['paper_w_mm'], paper_h_mm=cl['paper_h_mm'],
                    margin_x_mm=2.0, margin_y_mm=0,
                    gap_x_mm=3.0 if cl.get('cols', 1) > 1 else 0, gap_y_mm=0,
                    sticker_w_mm=cl['sticker_w_mm'], sticker_h_mm=cl['sticker_h_mm'],
                    cols=cl.get('cols', 1), rows=cl.get('rows', 1),
                    is_label=cl.get('is_label', True),
                )
                self.layout_key = '__custom__'
            else:
                self.layout_key = project.get('layout_key', 'SPEEDX-32x25')
                idx = self.layout_combo.findData(self.layout_key)
                if idx >= 0:
                    self.layout_combo.blockSignals(True)
                    self.layout_combo.setCurrentIndex(idx)
                    self.layout_combo.blockSignals(False)
            # Load stickers per row
            if hasattr(self, 'stickers_per_row'):
                self.stickers_per_row.blockSignals(True)
                self.stickers_per_row.setValue(project.get('stickers_per_row', 1))
                self.stickers_per_row.blockSignals(False)
            # Load custom texts
            if project.get('custom_texts'):
                self._custom_texts = project['custom_texts']
            # Update size inputs
            lay = self._current_layout()
            if hasattr(self, 'sticker_w_input'):
                self.sticker_w_input.blockSignals(True)
                self.sticker_h_input.blockSignals(True)
                self.sticker_w_input.setValue(lay.sticker_w_mm)
                self.sticker_h_input.setValue(lay.sticker_h_mm)
                self.sticker_w_input.blockSignals(False)
                self.sticker_h_input.blockSignals(False)
            # Refresh
            self._refresh_preview()
            self._refresh_editor()
            self._update_statusbar()
            self.statusBar().showMessage(f"Project loaded: {path}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Could not open project:\n{e}")

    def _on_manual_size_changed(self):
        """Update sticker size from manual input."""
        lay = self._current_layout()
        new_w = self.sticker_w_input.value()
        new_h = self.sticker_h_input.value()
        if abs(new_w - lay.sticker_w_mm) < 0.1 and abs(new_h - lay.sticker_h_mm) < 0.1:
            return  # no change
        # Update layout sticker size
        lay.sticker_w_mm = new_w
        lay.sticker_h_mm = new_h
        # Regenerate template for new size
        include_barcode = self.barcode_enabled_chk.isChecked()
        include_price = self.price_enabled_chk.isChecked()
        self.template = default_template(new_w, new_h, include_barcode=include_barcode, include_price=include_price)
        self.db.set_setting('sticker_template_json', template_to_json(self.template))
        self._refresh_preview()
        self._refresh_editor()
        self._update_statusbar()

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
            include_company = self.company_enabled_chk.isChecked() if hasattr(self, 'company_enabled_chk') else True
            include_product_name = self.product_name_enabled_chk.isChecked() if hasattr(self, 'product_name_enabled_chk') else True
            include_product_code = self.code_enabled_chk.isChecked() if hasattr(self, 'code_enabled_chk') else True
            include_dates = self.dates_enabled_chk.isChecked() if hasattr(self, 'dates_enabled_chk') else True
            include_mobile = self.mobile_enabled_chk.isChecked() if hasattr(self, 'mobile_enabled_chk') else True
            bc_type = self.barcode_type_combo.currentData() if hasattr(self, 'barcode_type_combo') else 'ean13'
            self.template = default_template(
                lay.sticker_w_mm, lay.sticker_h_mm,
                include_barcode=include_barcode,
                include_price=include_price,
                include_company=include_company,
                include_product_name=include_product_name,
                include_product_code=include_product_code,
                include_dates=include_dates,
                include_mobile=include_mobile,
                barcode_type=bc_type,
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
        # Update manual size inputs (block signals to avoid feedback loop)
        if hasattr(self, 'sticker_w_input'):
            self.sticker_w_input.blockSignals(True)
            self.sticker_h_input.blockSignals(True)
            self.sticker_w_input.setValue(lay.sticker_w_mm)
            self.sticker_h_input.setValue(lay.sticker_h_mm)
            self.sticker_w_input.blockSignals(False)
            self.sticker_h_input.blockSignals(False)
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
    def _ensure_items(self):
        """Auto-create items from current form data if queue is empty.
        This removes the need for 'Add to Sheet' — print directly."""
        if not self.current_items:
            data = self._build_sample_data()
            lay = self._current_layout()
            n_slots = total_slots(lay)
            for i in range(n_slots):
                self.current_items.append(dict(data))
        return True

    def on_print_clicked(self):
        """Print button — shows print summary then PrintSetupDialog."""
        self._ensure_items()
        lay = self._current_layout()

        # Print summary dialog — shows count, layout, and order
        n_items = len(self.current_items)
        per_sheet = total_slots(lay)
        n_sheets = (n_items + per_sheet - 1) // per_sheet
        copies = self.copies_spin.value()
        total_labels = n_items * copies

        summary = (f"📋 Print Summary / پرنٹ کی تفصیل\n\n"
                   f"Layout: {lay.name}\n"
                   f"Sticker size: {lay.sticker_w_mm} × {lay.sticker_h_mm} mm\n"
                   f"Stickers per sheet: {per_sheet}\n"
                   f"Items in queue: {n_items}\n"
                   f"Copies: {copies}\n\n"
                   f"Sheets to print: {n_sheets}\n"
                   f"Total labels: {total_labels}\n\n"
                   f"Item list:\n")
        for i, item in enumerate(self.current_items[:10]):
            bc = item.get('barcode', '') or '(no barcode)'
            pn = item.get('product_name', '') or item.get('company_name', '')
            summary += f"  {i+1}. {pn} — {bc}\n"
        if n_items > 10:
            summary += f"  ... and {n_items - 10} more\n"

        reply = QMessageBox.question(
            self, "Print Confirmation / پرنٹ کی تصدیق",
            summary,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            self.statusBar().showMessage("Print cancelled by user.", 3000)
            return

        # Show our custom print setup dialog
        try:
            dlg = PrintSetupDialog(
                lay,
                default_copies=copies,
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
        self._ensure_items()
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
        self._ensure_items()
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
        self._ensure_items()
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
        self.editor_scene = StickerScene(self.template, sample_data, layout=lay)
        self.editor_view = ZoomableGraphicsView(self.editor_scene)
        self.editor_view.setRenderHint(QPainter.Antialiasing, True)
        self.editor_view.setBackgroundBrush(QColor('#d0d0d0'))
        self.editor_view.setMinimumSize(400, 300)
        # Connect signals
        self.editor_scene.element_selection_changed.connect(self._on_editor_selection_changed)
        self.editor_scene.element_changed.connect(self._on_editor_element_changed)
        self.editor_scene.element_double_clicked.connect(self._on_element_double_clicked)
        self.preview_stack.addWidget(self.editor_view)
        self._editor_initialized = True

    def _build_sample_data(self):
        data = {
            'company_name': self.company_edit.text() or '',
            'product_name': self.product_edit.text() or '',
            'product_code': self.code_edit.text() or '',
            'barcode': self.barcode_edit.text() or '501234567890',
            'mfg_date': self.mfg_date.date().toString("yyyy-MM-dd"),
            'exp_date': self.exp_date.date().toString("yyyy-MM-dd"),
            'mobile': self.mobile_edit.text() or '',
            'price': self.price_edit.text() if hasattr(self, 'price_edit') and self.price_enabled_chk.isChecked() else '',
        }
        # Add custom text elements
        if hasattr(self, '_custom_texts'):
            data.update(self._custom_texts)
        return data

    def _refresh_editor(self):
        """Rebuild the editor scene — preserves element selection."""
        if not self.editor_scene:
            return
        # Remember which element was selected before rebuild
        selected_elem_id = None
        from ui.sticker_editor import ElementItem
        for it in self.editor_scene.items():
            if isinstance(it, ElementItem) and it.isSelected():
                selected_elem_id = id(it.element)
                break
        # Update sample data
        if self.current_items:
            self.editor_scene.sample_data = self.current_items[0]
        else:
            self.editor_scene.sample_data = self._build_sample_data()
        lay = self._current_layout()
        self.template.sticker_w_mm = lay.sticker_w_mm
        self.template.sticker_h_mm = lay.sticker_h_mm
        self.editor_scene.template = self.template
        self.editor_scene.layout = lay
        self.editor_scene.refresh()
        # Re-select the element that was selected before
        if selected_elem_id is not None:
            for it in self.editor_scene.items():
                if isinstance(it, ElementItem) and id(it.element) == selected_elem_id:
                    it.setSelected(True)
                    it.setFocus()
                    break
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
        """No-op — element selection is now via clicking on canvas, not combo."""
        pass

    def _selected_elem(self):
        """Return the currently selected element from the graphics scene."""
        if not self.editor_scene:
            return None
        from ui.sticker_editor import ElementItem
        for it in self.editor_scene.items():
            if isinstance(it, ElementItem) and it.isSelected():
                return it.element
        return None

    def _on_element_double_clicked(self, element):
        """Double-click on text element → show edit dialog."""
        if element.id in ('barcode', 'logo'):
            return
        # Get current text
        data = self._build_sample_data()
        current_text = data.get(element.id, '')
        if not current_text and element.id in ('company_name', 'product_name',
                                                'product_code', 'mobile', 'price'):
            # For standard elements, use get_text_for_element
            from core.templates import get_text_for_element
            current_text = get_text_for_element(element.id, data)
            # Strip prefixes like "Code: " or "Contact: "
            for prefix in ['Code: ', 'Contact: ', 'Rs. ']:
                if current_text.startswith(prefix):
                    current_text = current_text[len(prefix):]
                    break
        # Show input dialog
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(
            self, "Edit Text / ٹیکسٹ ایڈٹ کریں",
            f"Text for '{element.label}':",
            text=current_text
        )
        if ok and text != current_text:
            # Update the text
            if element.id.startswith('text_'):
                # Custom text element
                if not hasattr(self, '_custom_texts'):
                    self._custom_texts = {}
                self._custom_texts[element.id] = text
            elif element.id == 'company_name':
                self.company_edit.setText(text)
            elif element.id == 'product_name':
                self.product_edit.setText(text)
            elif element.id == 'product_code':
                self.code_edit.setText(text)
            elif element.id == 'mobile':
                self.mobile_edit.setText(text)
            elif element.id == 'price':
                self.price_edit.setText(text)
            self._live_update()
            self.statusBar().showMessage(f"Text updated: {text[:30]}", 2000)

    def _on_editor_selection_changed(self, element):
        """Called when an element is clicked in the graphics scene."""
        self._show_elem_props(element)

    def _on_editor_element_changed(self, element):
        """Called when an element is dragged in the graphics scene."""
        # No X/Y spinboxes to update anymore — canvas handles everything
        if self.editor_scene:
            self.editor_scene.invalidate()
        # Save template
        self.db.set_setting('sticker_template_json',
                            template_to_json(self.template))

    def _show_elem_props(self, element):
        """Update toolbar to reflect the selected element's properties."""
        if element is None:
            self.selected_elem_label.setText("No element selected — click on sticker")
            return
        self.selected_elem_label.setText(f"Selected: {element.label}")
        for w in [self.toolbar_font, self.toolbar_size, self.toolbar_bold, self.toolbar_italic]:
            w.blockSignals(True)
        is_text = element.id not in ('barcode', 'logo')
        if is_text:
            self.toolbar_font.setCurrentText(element.font_family)
            self.toolbar_size.setValue(element.font_size_pt)
            self.toolbar_bold.setChecked(element.bold)
            self.toolbar_italic.setChecked(element.italic)
            # Enable font controls
            self.toolbar_font.setEnabled(True)
            self.toolbar_bold.setEnabled(True)
            self.toolbar_italic.setEnabled(True)
            self.toolbar_align_left.setEnabled(True)
            self.toolbar_align_center.setEnabled(True)
            self.toolbar_align_right.setEnabled(True)
            self.toolbar_color.setEnabled(True)
        elif element.id == 'barcode':
            # For barcode: only size (height) matters
            self.toolbar_size.setValue(element.h_mm)
            self.toolbar_font.setEnabled(False)
            self.toolbar_bold.setEnabled(False)
            self.toolbar_italic.setEnabled(False)
            self.toolbar_align_left.setEnabled(False)
            self.toolbar_align_center.setEnabled(False)
            self.toolbar_align_right.setEnabled(False)
            self.toolbar_color.setEnabled(False)
            # Size IS enabled — controls barcode height
            self.toolbar_size.setEnabled(True)
        elif element.id == 'logo':
            # For logo: only size matters
            self.toolbar_size.setValue(element.w_mm)
            self.toolbar_font.setEnabled(False)
            self.toolbar_bold.setEnabled(False)
            self.toolbar_italic.setEnabled(False)
            self.toolbar_align_left.setEnabled(False)
            self.toolbar_align_center.setEnabled(False)
            self.toolbar_align_right.setEnabled(False)
            self.toolbar_color.setEnabled(False)
            self.toolbar_size.setEnabled(True)
        for w in [self.toolbar_font, self.toolbar_size, self.toolbar_bold, self.toolbar_italic]:
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
