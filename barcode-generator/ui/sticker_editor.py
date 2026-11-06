"""
Interactive sticker editor (v2.2.0).

ElementItem is now Illustrator-like:
  - 8 resize handles on the corners and edges
  - 1 rotate handle above the top edge
  - Drag the body to move
  - Hover shows appropriate cursor (size/rotate/move)
  - Double-click opens a small popup toolbar for font/color/etc.

The element's position is stored via setPos() (mm-based via mm_per_px),
size via setRect(0, 0, w, h). Rotation via setRotation() around center.
"""
from typing import List, Optional

from PyQt5.QtCore import (Qt, QRectF, QPointF, QSizeF,
                           pyqtSignal, QSize, QTimer, QLineF)
from PyQt5.QtGui import (QFont, QColor, QPen, QBrush, QPainter, QPixmap,
                          QImage, QTransform, QFontDatabase, QIcon,
                          QStandardItem, QStandardItemModel, QCursor)
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QWidget, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox,
    QComboBox, QPushButton, QGroupBox, QSplitter, QMessageBox, QListWidget,
    QListWidgetItem, QFrame, QSizePolicy, QScrollArea, QSlider, QTabWidget,
    QGraphicsScene, QGraphicsView, QGraphicsRectItem, QGraphicsItem,
    QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsPixmapItem,
    QColorDialog, QToolTip, QApplication
)

from core.templates import (StickerTemplate, StickerElement,
                              default_template, get_text_for_element,
                              enabled_elements)
from core.units import (MM, IN, get_unit, format_value, pt_to_mm, mm_to_pt)
from core.barcode_gen import generate_ean13_image, make_full_ean13
from core.printer import (draw_sticker_with_template,
                            render_single_sticker_preview, _draw_element_at_origin)


# Handle size in pixels (rendered as small squares)
HANDLE_SIZE = 6      # was 8 — smaller for less visual clutter
ROTATE_HANDLE_DISTANCE = 18  # was 24 — closer to element


# Handle IDs — 4 corners + 4 edges + rotate
HANDLE_TOP_LEFT = 0
HANDLE_TOP = 1
HANDLE_TOP_RIGHT = 2
HANDLE_LEFT = 3
HANDLE_RIGHT = 4
HANDLE_BOTTOM_LEFT = 5
HANDLE_BOTTOM = 6
HANDLE_BOTTOM_RIGHT = 7
HANDLE_ROTATE = 8


class HandleItem(QGraphicsRectItem):
    """A small square (or circle) at a corner/edge for resizing or rotating."""
    def __init__(self, parent_item: 'ElementItem', handle_id: int):
        super().__init__(parent_item)
        self.handle_id = handle_id
        self.parent_item = parent_item
        self.setRect(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)
        # Visual style
        self.setBrush(QColor('#1a4d8f'))
        pen = QPen(QColor('white'), 1)
        self.setPen(pen)
        self.setZValue(100)  # above element

    def hoverEnterEvent(self, event):
        # Set cursor based on handle type
        if self.handle_id == HANDLE_ROTATE:
            self.setCursor(Qt.CrossCursor)
        elif self.handle_id in (HANDLE_TOP_LEFT, HANDLE_BOTTOM_RIGHT):
            self.setCursor(Qt.SizeFDiagCursor)
        elif self.handle_id in (HANDLE_TOP_RIGHT, HANDLE_BOTTOM_LEFT):
            self.setCursor(Qt.SizeBDiagCursor)
        elif self.handle_id in (HANDLE_LEFT, HANDLE_RIGHT):
            self.setCursor(Qt.SizeHorCursor)
        elif self.handle_id in (HANDLE_TOP, HANDLE_BOTTOM):
            self.setCursor(Qt.SizeVerCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)


class ElementItem(QGraphicsRectItem):
    """
    Selectable, movable, resizable, rotatable element on the canvas.
    Position: setPos() (scene coords, includes slot offset)
    Size: setRect(0, 0, w, h) — local coords, top-left at (0,0)
    Rotation: setRotation() — around center of rect
    """
    def __init__(self, element: StickerElement, mm_per_px: float,
                 parent_view: 'StickerScene',
                 slot_x: float = 0.0, slot_y: float = 0.0):
        super().__init__()
        self.element = element
        self.mm_per_px = mm_per_px
        self.parent_view = parent_view
        self.slot_x = slot_x  # slot offset in mm (first slot's position)
        self.slot_y = slot_y

        self.setFlags(QGraphicsItem.ItemIsSelectable
                      | QGraphicsItem.ItemIsMovable
                      | QGraphicsItem.ItemSendsGeometryChanges
                      | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

        # Interaction state
        self._resize_handle = None  # which handle is being dragged
        self._rotate_dragging = False
        self._resize_start_rect = QRectF()
        self._resize_start_pos = QPointF()
        self._resize_start_rot = 0.0
        self._resize_start_center = QPointF()

        # Build handles (8 resize + 1 rotate)
        self.handles: List[HandleItem] = []
        for hid in range(9):  # 0..8
            h = HandleItem(self, hid)
            self.handles.append(h)

        # Hide handles initially — show only when selected
        self._set_handles_visible(False)
        self._update_geometry()
        # Connect scene's selection change if needed

    def _update_geometry(self):
        px_per_mm = 1.0 / self.mm_per_px
        # Position includes slot offset (for full-sheet view)
        x = (self.slot_x + self.element.x_mm) * px_per_mm
        y = (self.slot_y + self.element.y_mm) * px_per_mm
        w = self.element.w_mm * px_per_mm
        h = self.element.h_mm * px_per_mm
        self.setPos(x, y)
        self.setRect(QRectF(0, 0, w, h))
        self.setTransformOriginPoint(w / 2, h / 2)
        self.setRotation(self.element.rotation)
        # Update handle positions
        self._update_handles()

    def _update_handles(self):
        """Position the 8 resize handles at corners/edges + rotate handle."""
        r = self.rect()
        cx = r.center().x()
        cy = r.center().y()
        # Corners
        self.handles[HANDLE_TOP_LEFT].setPos(r.left(), r.top())
        self.handles[HANDLE_TOP_RIGHT].setPos(r.right(), r.top())
        self.handles[HANDLE_BOTTOM_LEFT].setPos(r.left(), r.bottom())
        self.handles[HANDLE_BOTTOM_RIGHT].setPos(r.right(), r.bottom())
        # Edges (midpoints)
        self.handles[HANDLE_TOP].setPos(cx, r.top())
        self.handles[HANDLE_BOTTOM].setPos(cx, r.bottom())
        self.handles[HANDLE_LEFT].setPos(r.left(), cy)
        self.handles[HANDLE_RIGHT].setPos(r.right(), cy)
        # Rotate handle — above the top edge
        self.handles[HANDLE_ROTATE].setPos(cx, r.top() - ROTATE_HANDLE_DISTANCE)
        # Draw a line from top edge to rotate handle (via parent's paint)

    def _set_handles_visible(self, visible: bool):
        for h in self.handles:
            h.setVisible(visible)

    def refresh(self):
        self._update_geometry()
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        # Selection border
        if self.isSelected():
            pen = QPen(QColor('#1a4d8f'), 0.5)  # thinner border (was 1.0)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
            # Line from top edge to rotate handle
            cx = rect.center().x()
            painter.drawLine(QPointF(cx, rect.top()),
                             QPointF(cx, rect.top() - ROTATE_HANDLE_DISTANCE))
        else:
            # Unselected: thin dashed border
            pen = QPen(QColor('#999'), 0.5, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

        # Draw content (text, barcode, or logo)
        data = self.parent_view.sample_data
        px_per_mm = 1.0 / self.mm_per_px
        _draw_element_at_origin(painter, self.element, data, px_per_mm, rect)

    # ------------------------------------------------------ Selection
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._set_handles_visible(self.isSelected())
            self.parent_view.element_selection_changed.emit(self.element)
            if self.isSelected():
                self.setFocus()
        elif change == QGraphicsItem.ItemPositionHasChanged:
            # pos changed due to drag — update element.x_mm/y_mm
            # Subtract slot offset to get position relative to sticker
            px_per_mm = 1.0 / self.mm_per_px
            self.element.x_mm = (self.pos().x() / px_per_mm) - self.slot_x
            self.element.y_mm = (self.pos().y() / px_per_mm) - self.slot_y
            self.parent_view.element_changed.emit(self.element)
        return super().itemChange(change, value)

    # ------------------------------------------------------ Hover cursor
    def hoverMoveEvent(self, event):
        # Show move cursor over body when selected
        if self.isSelected():
            pos = event.pos()  # local coords
            # If not over a handle, show move cursor
            over_handle = False
            for h in self.handles:
                if h.isVisible() and h.contains(h.mapFromItem(self, pos)):
                    over_handle = True
                    break
            if not over_handle:
                self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    # ------------------------------------------------------ Mouse press
    def mousePressEvent(self, event):
        # Right-click starts rotation mode
        if event.button() == Qt.RightButton and self.isSelected():
            self._rotate_dragging = True
            self._resize_start_mouse = event.scenePos()
            event.accept()
            return
        # Check if press is on a handle
        if self.isSelected():
            pos = event.pos()  # local coords
            for h in self.handles:
                if h.isVisible():
                    h_pos = h.mapFromItem(self, pos)
                    if h.rect().contains(h_pos) or h.contains(h_pos):
                        # Start resize or rotate
                        if h.handle_id == HANDLE_ROTATE:
                            self._rotate_dragging = True
                        else:
                            self._resize_handle = h.handle_id
                        # Store starting state
                        self._resize_start_rect = QRectF(self.rect())
                        self._resize_start_pos = QPointF(self.pos())
                        self._resize_start_rot = self.rotation()
                        self._resize_start_center = self.mapToScene(
                            self._resize_start_rect.center())
                        # Save mouse scene position at start
                        self._resize_start_mouse = event.scenePos()
                        event.accept()
                        return
        # Otherwise, default behavior (move/select)
        super().mousePressEvent(event)

    # ------------------------------------------------------ Mouse move
    def mouseMoveEvent(self, event):
        if self._resize_handle is not None:
            self._do_resize(event)
            event.accept()
        elif self._rotate_dragging:
            self._do_rotate(event)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    # ------------------------------------------------------ Mouse release
    def mouseDoubleClickEvent(self, event):
        """Double-click on text element → edit text."""
        if self.element.id in ('barcode', 'logo'):
            super().mouseDoubleClickEvent(event)
            return
        # Emit signal to scene → main window handles text editing
        self.parent_view.element_double_clicked.emit(self.element)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._resize_handle is not None or self._rotate_dragging:
            self._resize_handle = None
            self._rotate_dragging = False
            # Notify scene + save
            self.parent_view.element_changed.emit(self.element)
            self.parent_view.element_layout_changed.emit(self.element)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # ------------------------------------------------------ Resize logic
    def _do_resize(self, event):
        """Simple resize — changes only w_mm/h_mm, position stays FIXED.
        No complex rotation math, no jumping."""
        px_per_mm = 1.0 / self.mm_per_px
        # Mouse delta from start position (in scene coords → mm)
        mouse = event.scenePos()
        delta_x_mm = (mouse.x() - self._resize_start_mouse.x()) / px_per_mm
        delta_y_mm = (mouse.y() - self._resize_start_mouse.y()) / px_per_mm
        # Start dimensions (in mm)
        start_w = self._resize_start_rect.width() / px_per_mm
        start_h = self._resize_start_rect.height() / px_per_mm
        min_size = 1.0  # mm minimum
        hid = self._resize_handle
        # Compute new width/height based on which handle is dragged
        # Position (x_mm, y_mm) NEVER changes — no jumping!
        if hid == HANDLE_BOTTOM_RIGHT:
            self.element.w_mm = max(min_size, start_w + delta_x_mm)
            self.element.h_mm = max(min_size, start_h + delta_y_mm)
        elif hid == HANDLE_RIGHT:
            self.element.w_mm = max(min_size, start_w + delta_x_mm)
        elif hid == HANDLE_BOTTOM:
            self.element.h_mm = max(min_size, start_h + delta_y_mm)
        elif hid == HANDLE_TOP_LEFT:
            self.element.w_mm = max(min_size, start_w - delta_x_mm)
            self.element.h_mm = max(min_size, start_h - delta_y_mm)
        elif hid == HANDLE_TOP:
            self.element.h_mm = max(min_size, start_h - delta_y_mm)
        elif hid == HANDLE_LEFT:
            self.element.w_mm = max(min_size, start_w - delta_x_mm)
        elif hid == HANDLE_TOP_RIGHT:
            self.element.w_mm = max(min_size, start_w + delta_x_mm)
            self.element.h_mm = max(min_size, start_h - delta_y_mm)
        elif hid == HANDLE_BOTTOM_LEFT:
            self.element.w_mm = max(min_size, start_w - delta_x_mm)
            self.element.h_mm = max(min_size, start_h + delta_y_mm)
        # Update geometry (position stays the same, only size changes)
        self._update_geometry()
        self.update()
        self.parent_view.element_changed.emit(self.element)

    # ------------------------------------------------------ Rotate logic
    def _do_rotate(self, event):
        """Rotate the element — ONLY changes rotation, does NOT move element.
        Uses scenePos() for reliable mouse tracking (independent of rotation)."""
        import math
        # Get center in scene coords — this is stable because rotation is
        # around the center, so mapToScene(rect.center()) doesn't change
        # when rotation changes.
        center_scene = self.mapToScene(self.rect().center())
        # Use event.scenePos() — NOT mapToScene(event.pos()), because
        # pos() is in local coords which changes with rotation.
        mouse_scene = event.scenePos()
        # Angle from center to mouse
        dx = mouse_scene.x() - center_scene.x()
        dy = mouse_scene.y() - center_scene.y()
        angle_rad = math.atan2(dy, dx)
        angle_deg = angle_rad * 180 / math.pi
        # "up" (negative y in screen coords) = 0 degrees, clockwise positive
        new_rot = angle_deg + 90
        # Normalize to -180..180
        while new_rot > 180:
            new_rot -= 360
        while new_rot < -180:
            new_rot += 360
        # ONLY set rotation — do NOT change position
        self.element.rotation = new_rot
        self.setRotation(new_rot)
        self.update()
        self.parent_view.element_changed.emit(self.element)

    # ------------------------------------------------------ Keyboard
    def keyPressEvent(self, event):
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
    element_layout_changed = pyqtSignal(object)
    element_double_clicked = pyqtSignal(object)  # for text editing

    def __init__(self, template: StickerTemplate, sample_data: dict,
                 layout=None, parent=None):
        """If layout is provided, shows the full sheet (paper) with all sticker slots.
        Elements are editable on the first slot; all slots render the same template."""
        super().__init__(parent)
        self.template = template
        self.sample_data = sample_data
        self.layout = layout  # StickerLayout or None
        self.mm_per_px = 0.15  # was 0.25 — higher resolution (6.67px per mm)
        self._build_items()

    def _build_items(self):
        self.clear()
        px_per_mm = 1.0 / self.mm_per_px

        # Determine paper dimensions
        if self.layout:
            paper_w = self.layout.paper_w_mm
            paper_h = self.layout.paper_h_mm
        else:
            paper_w = self.template.sticker_w_mm
            paper_h = self.template.sticker_h_mm

        pw = paper_w * px_per_mm
        ph = paper_h * px_per_mm

        # White paper background
        bg = QGraphicsRectItem(0, 0, pw, ph)
        bg.setBrush(QColor('#FFFFFF'))
        bg.setPen(QPen(QColor('#000000'), 0.5))
        bg.setZValue(-2)
        self.addItem(bg)

        # Draw all sticker slots
        if self.layout:
            from core.layouts import sticker_positions, total_slots
            slots = sticker_positions(self.layout)
            n_slots = total_slots(self.layout)
        else:
            slots = [(0, 0)]
            n_slots = 1

        for idx, (sx, sy) in enumerate(slots):
            slot_w_px = self.template.sticker_w_mm * px_per_mm
            slot_h_px = self.template.sticker_h_mm * px_per_mm
            slot_x_px = sx * px_per_mm
            slot_y_px = sy * px_per_mm

            # Slot outline (dashed)
            slot_rect = QGraphicsRectItem(slot_x_px, slot_y_px,
                                           slot_w_px, slot_h_px)
            slot_rect.setPen(QPen(QColor('#cccccc'), 0.5, Qt.DashLine))
            slot_rect.setBrush(QBrush(Qt.NoBrush))
            slot_rect.setZValue(-1)
            self.addItem(slot_rect)

            if idx == 0:
                # First slot: add INTERACTIVE ElementItems (editable)
                for elem in self.template.elements:
                    item = ElementItem(elem, self.mm_per_px, self,
                                       slot_x=sx, slot_y=sy)
                    item.setZValue(10)
                    self.addItem(item)
            else:
                # Other slots: render STATIC preview of sticker content
                # using draw_sticker_with_template into a QPixmap
                try:
                    from core.printer import draw_sticker_with_template
                    # Use HIGH DPI for static previews so quality matches first sticker
                    render_dpi = 300  # was 200 — higher quality for other slots
                    render_scale = render_dpi / 25.4
                    sticker_w_render = int(self.template.sticker_w_mm * render_scale)
                    sticker_h_render = int(self.template.sticker_h_mm * render_scale)
                    pm = QPixmap(sticker_w_render, sticker_h_render)
                    pm.fill(Qt.transparent)
                    p = QPainter(pm)
                    p.setRenderHint(QPainter.Antialiasing, True)
                    rect = QRectF(0, 0, sticker_w_render, sticker_h_render)
                    draw_sticker_with_template(p, rect, self.sample_data,
                                                self.template, render_scale)
                    p.end()
                    # Scale pixmap to scene size and position at slot
                    pix_item = QGraphicsPixmapItem(pm)
                    # Scale from render resolution to scene resolution
                    scene_scale = px_per_mm / render_scale
                    pix_item.setScale(scene_scale)
                    pix_item.setPos(slot_x_px, slot_y_px)
                    pix_item.setZValue(5)  # above outlines, below interactive elements
                    pix_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                    pix_item.setFlag(QGraphicsItem.ItemIsMovable, False)
                    self.addItem(pix_item)
                except Exception:
                    pass  # If rendering fails, just show the outline

        self.setSceneRect(0, 0, pw, ph)

    def refresh(self):
        self._build_items()


# ---------------------------------------------------- editor dialog (legacy)
class StickerEditorDialog(QDialog):
    """Legacy dialog — kept for backwards compat. Use the inline editor in
    the main window instead."""
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
        self.resize(800, 600)
        v = QVBoxLayout(self)
        self.scene = StickerScene(self.template, self.sample_data)
        from PyQt5.QtWidgets import QGraphicsView
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing, True)
        v.addWidget(self.view)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)
