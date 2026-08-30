"""
Interactive sticker editor dialog (v2.0.1+).

The editor lets the user:
  - Click on any element (company name, barcode, dates, mobile, etc.)
    to select it.
  - Drag selected element with the mouse to move it (any distance).
  - Use arrow keys to nudge (1 mm normal, 0.1 mm with Shift).
  - Press Delete/Backspace to disable element.
  - Resize via the property panel (W / H in mm or inches).
  - Rotate via the property panel (0..360 degrees) or quick buttons.
  - Toggle element on/off.
  - Change font family, font size, bold, italic, alignment per element.
  - Switch the active unit (mm / in).
  - Reset to default template.
  - Save and Apply changes.
"""
from typing import List, Optional

from PyQt5.QtCore import (Qt, QRectF, QPointF, QSizeF,
                           pyqtSignal, QSize, QTimer)
from PyQt5.QtGui import (QFont, QColor, QPen, QBrush, QPainter, QPixmap,
                          QImage, QTransform, QFontDatabase, QIcon,
                          QStandardItem, QStandardItemModel)
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QWidget, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox,
    QComboBox, QPushButton, QGroupBox, QSplitter, QMessageBox, QListWidget,
    QListWidgetItem, QFrame, QSizePolicy, QScrollArea, QSlider, QTabWidget,
    QGraphicsScene, QGraphicsView, QGraphicsRectItem, QGraphicsItem,
    QGraphicsTextItem, QColorDialog
)

from core.templates import (StickerTemplate, StickerElement,
                              default_template, get_text_for_element,
                              enabled_elements)
from core.units import (MM, IN, get_unit, format_value, pt_to_mm, mm_to_pt)
from core.barcode_gen import generate_ean13_image, make_full_ean13
from core.printer import (draw_sticker_with_template,
                            render_single_sticker_preview, _draw_element_at_origin)


# ---------------------------------------------------- graphics items
class ElementItem(QGraphicsRectItem):
    """
    A selectable, draggable rectangle representing a sticker element.
    Position is stored in element.x_mm / element.y_mm (relative to sticker
    top-left). We use QGraphicsItem.setPos() for the actual scene position
    and setRect() for the size only (rect's top-left is always (0,0)).

    This way, when the user drags the item, Qt updates pos() automatically,
    and we read pos() back into element.x_mm/y_mm via itemChange().
    """
    def __init__(self, element: StickerElement, mm_per_px: float,
                 parent_view: 'StickerScene'):
        super().__init__()
        self.element = element
        self.mm_per_px = mm_per_px
        self.parent_view = parent_view
        self.setFlags(QGraphicsItem.ItemIsSelectable
                      | QGraphicsItem.ItemIsMovable
                      | QGraphicsItem.ItemSendsGeometryChanges
                      | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)
        self._update_geometry()

    def _update_geometry(self):
        px_per_mm = 1.0 / self.mm_per_px
        x = self.element.x_mm * px_per_mm
        y = self.element.y_mm * px_per_mm
        w = self.element.w_mm * px_per_mm
        h = self.element.h_mm * px_per_mm
        self.setPos(x, y)
        self.setRect(QRectF(0, 0, w, h))
        self.setTransformOriginPoint(w / 2, h / 2)
        self.setRotation(self.element.rotation)

    def refresh(self):
        self._update_geometry()
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        pen = QPen(QColor('#1a4d8f') if self.isSelected() else QColor('#888888'))
        pen.setWidthF(0.7 if self.isSelected() else 0.5)
        if not self.isSelected():
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

        data = self.parent_view.sample_data
        px_per_mm = 1.0 / self.mm_per_px
        _draw_element_at_origin(painter, self.element, data, px_per_mm, rect)

        if self.isSelected():
            badge_w = max(40, len(self.element.label) * 7)
            badge_h = 14
            label_rect = QRectF(rect.left(), rect.top() - badge_h - 2,
                                 badge_w, badge_h)
            painter.setBrush(QColor('#1a4d8f'))
            painter.setPen(Qt.NoPen)
            painter.drawRect(label_rect)
            painter.setPen(QColor('#FFFFFF'))
            f = QFont('Arial', 7)
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(label_rect, Qt.AlignCenter, self.element.label)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            px_per_mm = 1.0 / self.mm_per_px
            self.element.x_mm = self.pos().x() / px_per_mm
            self.element.y_mm = self.pos().y() / px_per_mm
            self.parent_view.element_changed.emit(self.element)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.parent_view.element_selection_changed.emit(self.element)
            if self.isSelected():
                self.setFocus()
        return super().itemChange(change, value)

    def keyPressEvent(self, event):
        """Arrow keys nudge the element. Shift = small step (0.1mm)."""
        step_mm = 0.1 if (event.modifiers() & Qt.ShiftModifier) else 1.0
        step_px = step_mm * (1.0 / self.mm_per_px)
        key = event.key()
        if key == Qt.Key_Left:
            self.moveBy(-step_px, 0)
            event.accept()
        elif key == Qt.Key_Right:
            self.moveBy(step_px, 0)
            event.accept()
        elif key == Qt.Key_Up:
            self.moveBy(0, -step_px)
            event.accept()
        elif key == Qt.Key_Down:
            self.moveBy(0, step_px)
            event.accept()
        elif key == Qt.Key_Delete or key == Qt.Key_Backspace:
            self.element.enabled = False
            self.parent_view.element_changed.emit(self.element)
            self.parent_view.refresh()
            event.accept()
        else:
            super().keyPressEvent(event)


class StickerScene(QGraphicsScene):
    element_selection_changed = pyqtSignal(object)
    element_changed = pyqtSignal(object)

    def __init__(self, template: StickerTemplate, sample_data: dict,
                 parent=None):
        super().__init__(parent)
        self.template = template
        self.sample_data = sample_data
        self.mm_per_px = 0.25
        self._build_items()

    def _build_items(self):
        self.clear()
        px_per_mm = 1.0 / self.mm_per_px
        sw = self.template.sticker_w_mm * px_per_mm
        sh = self.template.sticker_h_mm * px_per_mm
        bg = QGraphicsRectItem(0, 0, sw, sh)
        bg.setBrush(QColor('#FFFFFF'))
        bg.setPen(QPen(QColor('#000000'), 0.5))
        bg.setZValue(-1)
        self.addItem(bg)
        for elem in self.template.elements:
            item = ElementItem(elem, self.mm_per_px, self)
            item.setZValue(1)
            self.addItem(item)
        self.setSceneRect(0, 0, sw, sh)

    def refresh(self):
        self._build_items()


# ---------------------------------------------------- editor dialog
class StickerEditorDialog(QDialog):
    def __init__(self, template: StickerTemplate, sample_data: dict,
                 sticker_w_mm: float, sticker_h_mm: float,
                 unit_code: str = 'mm',
                 parent=None):
        super().__init__(parent)
        self.template = template
        self.template.sticker_w_mm = sticker_w_mm
        self.template.sticker_h_mm = sticker_h_mm
        self.sample_data = dict(sample_data)
        self.unit = get_unit(unit_code)

        self.setWindowTitle("Sticker Layout Editor / اسٹیکر لی آؤٹ ایڈیٹر")
        self.resize(1180, 720)

        self._build_ui()
        self._refresh_scene()
        self._on_selection_changed(None)

    # ---------------------------------------------------------- UI
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # Left: graphics view
        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Click an element to select it, then drag to move. / "
                       "عنصر کو منتخب کرنے کے لیے کلک کریں، پھر منتقل کرنے کے لیے drag کریں۔\n"
                       "Arrow keys: nudge 1mm (Shift = 0.1mm). Delete: disable element.")
        title.setStyleSheet("color: #1a4d8f; font-weight: bold;")
        title.setWordWrap(True)
        left_layout.addWidget(title)

        self.scene = StickerScene(self.template, self.sample_data)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing, True)
        self.view.setBackgroundBrush(QColor('#d0d0d0'))
        self.view.setMinimumSize(540, 400)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        left_layout.addWidget(self.view, 1)

        zoom_row = QHBoxLayout()
        self.zoom_in_btn = QPushButton("🔍+  Zoom In")
        self.zoom_in_btn.clicked.connect(self.on_zoom_in)
        zoom_row.addWidget(self.zoom_in_btn)
        self.zoom_out_btn = QPushButton("🔍−  Zoom Out")
        self.zoom_out_btn.clicked.connect(self.on_zoom_out)
        zoom_row.addWidget(self.zoom_out_btn)
        self.fit_btn = QPushButton("⊡  Fit to Window")
        self.fit_btn.clicked.connect(self.on_fit)
        zoom_row.addWidget(self.fit_btn)
        zoom_row.addStretch(1)
        left_layout.addLayout(zoom_row)

        root.addWidget(left_box, 1)

        # Right: property panel
        right = QWidget()
        right.setFixedWidth(380)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        list_box = QGroupBox("Elements / عناصر")
        ll = QVBoxLayout(list_box)
        self.element_list = QListWidget()
        self.element_list.currentRowChanged.connect(self.on_list_row_changed)
        ll.addWidget(self.element_list)
        right_layout.addWidget(list_box)

        props_box = QGroupBox("Properties / خصوصیات")
        props_layout = QVBoxLayout(props_box)

        self.enabled_chk = QCheckBox("Enabled / فعال")
        self.enabled_chk.toggled.connect(self.on_enabled_toggled)
        props_layout.addWidget(self.enabled_chk)

        pos_grid = QFormLayout()
        pos_grid.setLabelAlignment(Qt.AlignRight)
        unit_sym = self.unit.symbol
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-100, 500)
        self.x_spin.setDecimals(3)
        self.x_spin.setSuffix(f" {unit_sym}")
        self.x_spin.valueChanged.connect(self.on_geom_changed)
        pos_grid.addRow("X (left):", self.x_spin)

        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-100, 500)
        self.y_spin.setDecimals(3)
        self.y_spin.setSuffix(f" {unit_sym}")
        self.y_spin.valueChanged.connect(self.on_geom_changed)
        pos_grid.addRow("Y (top):", self.y_spin)

        self.w_spin = QDoubleSpinBox()
        self.w_spin.setRange(0.5, 500)
        self.w_spin.setDecimals(3)
        self.w_spin.setSuffix(f" {unit_sym}")
        self.w_spin.valueChanged.connect(self.on_geom_changed)
        pos_grid.addRow("Width:", self.w_spin)

        self.h_spin = QDoubleSpinBox()
        self.h_spin.setRange(0.5, 500)
        self.h_spin.setDecimals(3)
        self.h_spin.setSuffix(f" {unit_sym}")
        self.h_spin.valueChanged.connect(self.on_geom_changed)
        pos_grid.addRow("Height:", self.h_spin)

        self.rot_spin = QDoubleSpinBox()
        self.rot_spin.setRange(-360, 360)
        self.rot_spin.setDecimals(1)
        self.rot_spin.setSuffix(" °")
        self.rot_spin.valueChanged.connect(self.on_geom_changed)
        pos_grid.addRow("Rotation:", self.rot_spin)

        rot_row = QHBoxLayout()
        for angle, label in [(-90, "↺ 90°"), (0, "0°"), (90, "↻ 90°"),
                              (180, "⇅ 180°")]:
            b = QPushButton(label)
            b.clicked.connect(lambda _, a=angle: self.rot_spin.setValue(a))
            rot_row.addWidget(b)
        rot_row.addStretch(1)
        pos_grid.addRow("Quick rotate:", rot_row)

        align_row = QHBoxLayout()
        for code, label, icon in [('left', 'Left', '⬅'), ('center', 'Center', '↔'), ('right', 'Right', '➡')]:
            b = QPushButton(f"{icon} {label}")
            b.clicked.connect(lambda _, c=code: self.on_align_clicked(c))
            align_row.addWidget(b)
        align_row.addStretch(1)
        pos_grid.addRow("Align:", align_row)

        props_layout.addLayout(pos_grid)

        font_box = QGroupBox("Font / فونٹ")
        fl = QFormLayout(font_box)
        fl.setLabelAlignment(Qt.AlignRight)
        self.font_combo = QComboBox()
        self.font_combo.addItems(QFontDatabase().families())
        self.font_combo.currentTextChanged.connect(self.on_font_changed)
        fl.addRow("Family:", self.font_combo)

        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(2, 72)
        self.font_size.setDecimals(1)
        self.font_size.setSuffix(" pt")
        self.font_size.valueChanged.connect(self.on_font_changed)
        fl.addRow("Size:", self.font_size)

        font_flags = QHBoxLayout()
        self.bold_chk = QCheckBox("Bold")
        self.bold_chk.toggled.connect(self.on_font_changed)
        font_flags.addWidget(self.bold_chk)
        self.italic_chk = QCheckBox("Italic")
        self.italic_chk.toggled.connect(self.on_font_changed)
        font_flags.addWidget(self.italic_chk)
        font_flags.addStretch(1)
        fl.addRow("Style:", font_flags)

        self.color_btn = QPushButton("🎨 Text Color")
        self.color_btn.clicked.connect(self.on_color_clicked)
        fl.addRow("Color:", self.color_btn)

        props_layout.addWidget(font_box)

        self.elem_info = QLabel("")
        self.elem_info.setStyleSheet("color: #555; font-size: 11px;")
        self.elem_info.setWordWrap(True)
        props_layout.addWidget(self.elem_info)
        props_layout.addStretch(1)

        right_layout.addWidget(props_box, 1)

        actions = QHBoxLayout()
        self.reset_btn = QPushButton("↺ Reset to Default")
        self.reset_btn.clicked.connect(self.on_reset_clicked)
        actions.addWidget(self.reset_btn)
        right_layout.addLayout(actions)

        root.addWidget(right, 0)

        # Bottom action buttons
        btns_box = QWidget()
        btns_layout = QHBoxLayout(btns_box)
        btns_layout.setContentsMargins(0, 0, 0, 0)
        btns_layout.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btns_layout.addWidget(self.cancel_btn)
        self.apply_btn = QPushButton("✓ Save & Apply")
        self.apply_btn.setStyleSheet("background: #1a4d8f; color: white; padding: 8px 16px; font-weight: bold;")
        self.apply_btn.clicked.connect(self.accept)
        btns_layout.addWidget(self.apply_btn)
        root.addWidget(btns_box, 0)

        # Connect scene signals
        self.scene.element_selection_changed.connect(self._on_selection_changed)
        self.scene.element_changed.connect(self._on_element_changed)

        self._populate_element_list()
        QTimer.singleShot(50, self.on_fit)

    def _populate_element_list(self):
        self.element_list.blockSignals(True)
        self.element_list.clear()
        for e in self.template.elements:
            label = e.label
            if not e.enabled:
                label = f"[OFF] {label}"
            self.element_list.addItem(QListWidgetItem(label))
        self.element_list.blockSignals(False)

    def on_zoom_in(self):
        self.view.scale(1.25, 1.25)

    def on_zoom_out(self):
        self.view.scale(0.8, 0.8)

    def on_fit(self):
        sw = self.template.sticker_w_mm * (1.0 / self.scene.mm_per_px)
        sh = self.template.sticker_h_mm * (1.0 / self.scene.mm_per_px)
        margin = 20
        vw = self.view.viewport().width() - 2 * margin
        vh = self.view.viewport().height() - 2 * margin
        if sw <= 0 or sh <= 0:
            return
        sx = vw / sw
        sy = vh / sh
        s = min(sx, sy)
        self.view.setTransform(QTransform.fromScale(s, s))

    def on_list_row_changed(self, row: int):
        if row < 0 or row >= len(self.template.elements):
            return
        elem = self.template.elements[row]
        for it in self.scene.items():
            if isinstance(it, ElementItem) and it.element is elem:
                it.setSelected(True)
                break

    def _on_selection_changed(self, element: Optional[StickerElement]):
        if element is None:
            self.elem_info.setText("No element selected.\n"
                                   "Click on an element in the preview to edit it.")
            return
        for i, e in enumerate(self.template.elements):
            if e is element:
                self.element_list.blockSignals(True)
                self.element_list.setCurrentRow(i)
                self.element_list.blockSignals(False)
                break
        for w in [self.x_spin, self.y_spin, self.w_spin, self.h_spin,
                  self.rot_spin, self.font_size, self.font_combo,
                  self.bold_chk, self.italic_chk, self.enabled_chk]:
            w.blockSignals(True)
        self.x_spin.setValue(self.unit.from_mm(element.x_mm))
        self.y_spin.setValue(self.unit.from_mm(element.y_mm))
        self.w_spin.setValue(self.unit.from_mm(element.w_mm))
        self.h_spin.setValue(self.unit.from_mm(element.h_mm))
        self.rot_spin.setValue(element.rotation)
        self.font_combo.setCurrentText(element.font_family)
        self.font_size.setValue(element.font_size_pt)
        self.bold_chk.setChecked(element.bold)
        self.italic_chk.setChecked(element.italic)
        self.enabled_chk.setChecked(element.enabled)
        self.elem_info.setText(
            f"Selected: {element.label}\n"
            f"Type: {'Text' if element.id != 'barcode' else 'Barcode image'}"
        )
        for w in [self.x_spin, self.y_spin, self.w_spin, self.h_spin,
                  self.rot_spin, self.font_size, self.font_combo,
                  self.bold_chk, self.italic_chk, self.enabled_chk]:
            w.blockSignals(False)

    def _on_element_changed(self, element: StickerElement):
        for w in [self.x_spin, self.y_spin]:
            w.blockSignals(True)
        self.x_spin.setValue(self.unit.from_mm(element.x_mm))
        self.y_spin.setValue(self.unit.from_mm(element.y_mm))
        for w in [self.x_spin, self.y_spin]:
            w.blockSignals(False)
        self.scene.invalidate()

    def on_geom_changed(self):
        sel = self._selected_element()
        if sel is None:
            return
        sel.x_mm = self.unit.to_mm(self.x_spin.value())
        sel.y_mm = self.unit.to_mm(self.y_spin.value())
        sel.w_mm = max(1.0, self.unit.to_mm(self.w_spin.value()))
        sel.h_mm = max(1.0, self.unit.to_mm(self.h_spin.value()))
        sel.rotation = self.rot_spin.value()
        self._refresh_scene()

    def on_font_changed(self):
        sel = self._selected_element()
        if sel is None:
            return
        sel.font_family = self.font_combo.currentText()
        sel.font_size_pt = float(self.font_size.value())
        sel.bold = self.bold_chk.isChecked()
        sel.italic = self.italic_chk.isChecked()
        self._refresh_scene()

    def on_color_clicked(self):
        sel = self._selected_element()
        if sel is None:
            return
        c = QColorDialog.getColor(QColor(sel.color), self, "Pick text color")
        if c.isValid():
            sel.color = c.name()
            self._refresh_scene()

    def on_enabled_toggled(self, checked: bool):
        sel = self._selected_element()
        if sel is None:
            return
        sel.enabled = bool(checked)
        self._refresh_scene()
        self._populate_element_list()

    def on_align_clicked(self, code: str):
        sel = self._selected_element()
        if sel is None:
            return
        sel.align = code
        self._refresh_scene()

    def on_reset_clicked(self):
        ok = QMessageBox.question(
            self, "Confirm",
            "Reset all elements to default positions? This discards all custom edits."
        )
        if ok != QMessageBox.Yes:
            return
        new_t = default_template(self.template.sticker_w_mm,
                                   self.template.sticker_h_mm)
        self.template.elements = new_t.elements
        self._refresh_scene()
        self._populate_element_list()

    def _selected_element(self) -> Optional[StickerElement]:
        for it in self.scene.items():
            if isinstance(it, ElementItem) and it.isSelected():
                return it.element
        return None

    def _refresh_scene(self):
        sel = self._selected_element()
        self.scene.refresh()
        if sel is not None:
            for it in self.scene.items():
                if isinstance(it, ElementItem) and it.element is sel:
                    it.setSelected(True)
                    break
        self.scene.invalidate()
