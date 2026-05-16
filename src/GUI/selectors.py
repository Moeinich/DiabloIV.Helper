import math
from enum import Enum, auto
from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PyQt5.QtWidgets import QApplication, QWidget

from helper import logging_helper

_HANDLE_SIZE = 10
_HANDLE_HIT = 14
_BTN_H = 36
_BTN_W_ACCEPT = 140
_BTN_W_CANCEL = 120
_BTN_MARGIN = 16
_BTN_GAP = 8


class _State(Enum):
    IDLE = auto()
    DRAWING = auto()
    ADJUSTING = auto()
    ACCEPTED = auto()
    CANCELLED = auto()


class BaseDragSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

        self._state = _State.IDLE
        self._anchor: Optional[QPoint] = None
        self._mouse_pos: Optional[QPoint] = None
        self._drag_mode: Optional[str] = None
        self._drag_start: Optional[QPoint] = None
        self._hovered_handle: int = -1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._state == _State.DRAWING and self._anchor and self._mouse_pos:
            shape = self._compute_shape(self._mouse_pos)
            if shape is not None:
                self._paint_shape_drawing(painter, shape)

        elif self._state == _State.ADJUSTING:
            shape = self._get_current_shape()
            if shape is not None:
                self._paint_shape_adjusting(painter, shape)
                handles = self._get_handles(shape)
                self._paint_handles(painter, handles)
                self._paint_buttons(painter)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        pos = event.pos()

        if self._state == _State.ADJUSTING:
            if self._hit_accept_btn(pos):
                self._accept()
                return
            if self._hit_cancel_btn(pos):
                self._cancel()
                return

            handle_idx = self._hit_handle(pos)
            if handle_idx >= 0:
                self._drag_mode = 'resize'
                self._active_handle = handle_idx
                self._drag_start = pos
                return

            if self._hit_shape(pos):
                self._drag_mode = 'move'
                self._drag_start = pos
                return

            return

        if self._state == _State.IDLE:
            self._anchor = pos
            self._mouse_pos = pos
            self._state = _State.DRAWING
            self.setCursor(Qt.CrossCursor)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        self._mouse_pos = pos

        if self._state == _State.DRAWING:
            self.update()
            return

        if self._state == _State.ADJUSTING:
            if self._drag_mode == 'move' and self._drag_start:
                delta = pos - self._drag_start
                self._apply_move(delta)
                self._drag_start = pos
            elif self._drag_mode == 'resize' and self._drag_start:
                self._apply_resize(self._active_handle, pos)
                self._drag_start = pos
            else:
                self._hovered_handle = self._hit_handle(pos)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        if self._state == _State.DRAWING:
            self._state = _State.ADJUSTING
            self._finalize_shape(self._mouse_pos)
            self.setCursor(Qt.ArrowCursor)
            self.update()
            return

        if self._state == _State.ADJUSTING:
            self._drag_mode = None
            self._drag_start = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._state == _State.ADJUSTING:
                self._accept()

    def _accept(self):
        self._state = _State.ACCEPTED
        self._on_confirmed()
        self.close()

    def _cancel(self):
        self._state = _State.CANCELLED
        self.close()

    def closeEvent(self, event):
        if self._state not in (_State.ACCEPTED, _State.CANCELLED):
            self._state = _State.CANCELLED
        self.releaseMouse()
        self.releaseKeyboard()
        super().closeEvent(event)

    def run(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.grabMouse()
        self.grabKeyboard()
        loop = QApplication.instance()
        if loop:
            while self.isVisible():
                loop.processEvents()
        if self._state == _State.ACCEPTED:
            return self._get_result()
        return None

    def _compute_shape(self, mouse_pos: QPoint):
        raise NotImplementedError

    def _get_current_shape(self):
        raise NotImplementedError

    def _finalize_shape(self, mouse_pos: QPoint):
        raise NotImplementedError

    def _paint_shape_drawing(self, painter, shape):
        raise NotImplementedError

    def _paint_shape_adjusting(self, painter, shape):
        raise NotImplementedError

    def _get_handles(self, shape) -> List[QRect]:
        raise NotImplementedError

    def _hit_shape(self, pos: QPoint) -> bool:
        raise NotImplementedError

    def _apply_move(self, delta: QPoint):
        raise NotImplementedError

    def _apply_resize(self, handle_idx: int, pos: QPoint):
        raise NotImplementedError

    def _on_confirmed(self):
        raise NotImplementedError

    def _get_result(self):
        raise NotImplementedError

    def _paint_handles(self, painter, handles):
        for i, h in enumerate(handles):
            if i == self._hovered_handle:
                color = QColor(255, 220, 50, 220)
                border = QColor(255, 220, 50)
            else:
                color = QColor(255, 255, 255, 200)
                border = QColor(200, 200, 200)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(border, 1))
            painter.drawRect(h)

    def _paint_buttons(self, painter):
        screen = self.geometry()
        accept_x = screen.right() - _BTN_MARGIN - _BTN_W_ACCEPT - _BTN_GAP - _BTN_W_CANCEL
        accept_y = screen.bottom() - _BTN_MARGIN - _BTN_H
        self._accept_btn_rect = QRect(accept_x, accept_y, _BTN_W_ACCEPT, _BTN_H)

        cancel_x = accept_x + _BTN_W_ACCEPT + _BTN_GAP
        self._cancel_btn_rect = QRect(cancel_x, accept_y, _BTN_W_CANCEL, _BTN_H)

        painter.setBrush(QBrush(QColor(0, 160, 80, 220)))
        painter.setPen(QPen(QColor(0, 200, 100), 2))
        painter.drawRoundedRect(self._accept_btn_rect, 6, 6)
        painter.setPen(QPen(Qt.white))
        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        painter.drawText(self._accept_btn_rect, Qt.AlignCenter, "ACCEPT (Enter)")

        painter.setBrush(QBrush(QColor(180, 40, 40, 220)))
        painter.setPen(QPen(QColor(220, 60, 60), 2))
        painter.drawRoundedRect(self._cancel_btn_rect, 6, 6)
        painter.setPen(QPen(Qt.white))
        painter.drawText(self._cancel_btn_rect, Qt.AlignCenter, "CANCEL (Esc)")

    def _hit_accept_btn(self, pos: QPoint) -> bool:
        return hasattr(self, '_accept_btn_rect') and self._accept_btn_rect.contains(pos)

    def _hit_cancel_btn(self, pos: QPoint) -> bool:
        return hasattr(self, '_cancel_btn_rect') and self._cancel_btn_rect.contains(pos)

    def _hit_handle(self, pos: QPoint) -> int:
        shape = self._get_current_shape()
        if shape is None:
            return -1
        handles = self._get_handles(shape)
        expanded = [h.adjusted(-_HANDLE_HIT // 2, -_HANDLE_HIT // 2,
                               _HANDLE_HIT // 2, _HANDLE_HIT // 2) for h in handles]
        for i, h in enumerate(expanded):
            if h.contains(pos):
                return i
        return -1

    def _paint_dim_label(self, painter, text, x, y):
        painter.setPen(QPen(QColor(255, 255, 255, 220)))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(QPoint(x, y), text)


class RectDragSelector(BaseDragSelector):
    def __init__(self):
        super().__init__()
        self.result_rect: Optional[QRect] = None
        self._rect: Optional[QRect] = None

    def _compute_shape(self, mouse_pos: QPoint) -> QRect:
        return QRect(self._anchor, mouse_pos).normalized()

    def _get_current_shape(self):
        return self._rect

    def _finalize_shape(self, mouse_pos: QPoint):
        self._rect = QRect(self._anchor, mouse_pos).normalized()

    def _paint_shape_drawing(self, painter, rect: QRect):
        painter.setBrush(QBrush(QColor(0, 200, 100, 35)))
        painter.setPen(QPen(QColor(255, 255, 255, 180), 2, Qt.DashLine))
        painter.drawRect(rect)
        self._paint_dim_label(painter, f"{rect.width()} x {rect.height()}",
                              rect.right() + 8, rect.top() + 14)

    def _paint_shape_adjusting(self, painter, rect: QRect):
        painter.setBrush(QBrush(QColor(0, 200, 100, 50)))
        painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
        painter.drawRect(rect)
        self._paint_dim_label(painter, f"{rect.width()} x {rect.height()}",
                              rect.right() + 8, rect.top() + 14)
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1, Qt.DotLine))
        cx = rect.x() + rect.width() // 2
        cy = rect.y() + rect.height() // 2
        painter.drawLine(cx, rect.top(), cx, rect.bottom())
        painter.drawLine(rect.left(), cy, rect.right(), cy)

    def _get_handles(self, rect: QRect) -> List[QRect]:
        hs = _HANDLE_SIZE
        hx = rect.x() - hs // 2
        hy = rect.y() - hs // 2
        mx = rect.x() + rect.width() // 2 - hs // 2
        my = rect.y() + rect.height() // 2 - hs // 2
        ex = rect.x() + rect.width() - hs // 2
        ey = rect.y() + rect.height() - hs // 2
        return [
            QRect(hx, hy, hs, hs),
            QRect(mx, hy, hs, hs),
            QRect(ex, hy, hs, hs),
            QRect(ex, my, hs, hs),
            QRect(ex, ey, hs, hs),
            QRect(mx, ey, hs, hs),
            QRect(hx, ey, hs, hs),
            QRect(hx, my, hs, hs),
        ]

    def _hit_shape(self, pos: QPoint) -> bool:
        if self._rect is None:
            return False
        return self._rect.contains(pos)

    def _apply_move(self, delta: QPoint):
        if self._rect:
            self._rect = self._rect.translated(delta)

    def _apply_resize(self, handle_idx: int, pos: QPoint):
        if self._rect is None:
            return
        r = QRect(self._rect)
        if handle_idx == 0:
            r.setTopLeft(pos)
        elif handle_idx == 1:
            r.setTop(pos.y())
        elif handle_idx == 2:
            r.setTopRight(pos)
        elif handle_idx == 3:
            r.setRight(pos.x())
        elif handle_idx == 4:
            r.setBottomRight(pos)
        elif handle_idx == 5:
            r.setBottom(pos.y())
        elif handle_idx == 6:
            r.setBottomLeft(pos)
        elif handle_idx == 7:
            r.setLeft(pos.x())
        self._rect = r.normalized()

    def _on_confirmed(self):
        self.result_rect = self._rect

    def _get_result(self):
        return self.result_rect


class CircleDragSelector(BaseDragSelector):
    def __init__(self):
        super().__init__()
        self.result_center: Optional[QPoint] = None
        self.result_radius: int = 0
        self._center: Optional[QPoint] = None
        self._radius: int = 0

    def _compute_shape(self, mouse_pos: QPoint) -> Tuple[QPoint, int]:
        center = self._anchor
        dx = mouse_pos.x() - center.x()
        dy = mouse_pos.y() - center.y()
        radius = int(math.sqrt(dx * dx + dy * dy))
        return center, radius

    def _get_current_shape(self):
        if self._center is not None:
            return self._center, self._radius
        return None

    def _finalize_shape(self, mouse_pos: QPoint):
        self._center = QPoint(self._anchor)
        dx = mouse_pos.x() - self._center.x()
        dy = mouse_pos.y() - self._center.y()
        self._radius = int(math.sqrt(dx * dx + dy * dy))

    def _paint_shape_drawing(self, painter, shape: Tuple[QPoint, int]):
        center, radius = shape
        painter.setBrush(QBrush(QColor(0, 200, 100, 35)))
        painter.setPen(QPen(QColor(255, 255, 255, 180), 2, Qt.DashLine))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1, Qt.DashLine))
        painter.drawLine(center + QPoint(-radius, 0), center + QPoint(radius, 0))
        painter.drawLine(center + QPoint(0, -radius), center + QPoint(0, radius))
        painter.setPen(QPen(QColor(0, 200, 100, 200), 4))
        painter.drawPoint(center)
        self._paint_dim_label(painter, f"r={radius}", center.x() + radius + 10, center.y() + 6)

    def _paint_shape_adjusting(self, painter, shape: Tuple[QPoint, int]):
        center, radius = shape
        painter.setBrush(QBrush(QColor(0, 200, 100, 50)))
        painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1, Qt.DotLine))
        painter.drawLine(center + QPoint(-radius, 0), center + QPoint(radius, 0))
        painter.drawLine(center + QPoint(0, -radius), center + QPoint(0, radius))
        painter.setPen(QPen(QColor(0, 200, 100, 220), 4))
        painter.drawPoint(center)
        self._paint_dim_label(painter, f"r={radius}", center.x() + radius + 10, center.y() + 6)

    def _get_handles(self, shape) -> List[QRect]:
        center, radius = shape
        hs = _HANDLE_SIZE
        positions = [
            QPoint(center.x() + radius, center.y()),
            QPoint(center.x(), center.y() - radius),
            QPoint(center.x() - radius, center.y()),
            QPoint(center.x(), center.y() + radius),
        ]
        return [QRect(p.x() - hs // 2, p.y() - hs // 2, hs, hs) for p in positions]

    def _hit_shape(self, pos: QPoint) -> bool:
        if self._center is None:
            return False
        dx = pos.x() - self._center.x()
        dy = pos.y() - self._center.y()
        return math.sqrt(dx * dx + dy * dy) <= self._radius

    def _apply_move(self, delta: QPoint):
        if self._center:
            self._center = self._center + delta

    def _apply_resize(self, handle_idx: int, pos: QPoint):
        if self._center is None:
            return
        dx = pos.x() - self._center.x()
        dy = pos.y() - self._center.y()
        self._radius = max(5, int(math.sqrt(dx * dx + dy * dy)))

    def _on_confirmed(self):
        self.result_center = self._center
        self.result_radius = self._radius

    def _get_result(self):
        if self.result_center is not None:
            return self.result_center, self.result_radius
        return None


class ColorPickerOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self._mouse_pos = QPoint(0, 0)
        self._clicks = []
        self._result = None
        self._done = False
        self._prompt = "Click the BRIGHT area of the orb"

    def run(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.grabMouse()
        self.grabKeyboard()
        from PyQt5.QtCore import QEventLoop
        loop = QEventLoop()
        while not self._done:
            loop.processEvents()
        self.releaseMouse()
        self.releaseKeyboard()
        self.close()
        return self._result

    def _sample_color_at(self, pos):
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(bbox=(pos.x(), pos.y(), pos.x() + 1, pos.y() + 1))
            px = img.getpixel((0, 0))
            return (px[0], px[1], px[2])
        except Exception:
            return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            color = self._sample_color_at(event.pos())
            if color is None:
                return
            self._clicks.append({'pos': event.pos(), 'color': color})
            if len(self._clicks) == 1:
                self._prompt = "Click the DARKER area of the orb"
            elif len(self._clicks) >= 2:
                self._result = (self._clicks[0]['color'], self._clicks[1]['color'])
                self._done = True
        elif event.button() == Qt.RightButton:
            if self._clicks:
                self._clicks.pop()
                self._prompt = "Click the BRIGHT area of the orb" if not self._clicks else "Click the DARKER area of the orb"

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.pos()
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._result = None
            self._done = True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 40))
        pos = self._mouse_pos
        mag_size = 80
        mag_half = mag_size // 2
        zoom = 6
        try:
            from PIL import ImageGrab
            grab_size = mag_size // zoom
            ghalf = grab_size // 2
            img = ImageGrab.grab(bbox=(pos.x() - ghalf, pos.y() - ghalf, pos.x() + ghalf, pos.y() + ghalf))
            from PyQt5.QtGui import QImage
            data = img.tobytes("raw", "RGB")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGB888)
            mag_x = pos.x() + 20
            mag_y = pos.y() - mag_size - 10
            screen = self.rect()
            if mag_x + mag_size > screen.width():
                mag_x = pos.x() - mag_size - 20
            if mag_y < 0:
                mag_y = pos.y() + 20
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawRect(mag_x - 1, mag_y - 1, mag_size + 2, mag_size + 2)
            painter.drawImage(QRect(mag_x, mag_y, mag_size, mag_size), qimg)
            center_px = mag_x + mag_half
            center_py = mag_y + mag_half
            painter.setPen(QPen(QColor(255, 255, 0), 1))
            painter.drawLine(center_px - 8, center_py, center_px + 8, center_py)
            painter.drawLine(center_px, center_py - 8, center_px, center_py + 8)
        except Exception:
            pass
        swatch_size = 24
        swatch_x = pos.x() + 20
        swatch_y = pos.y() + 20
        if swatch_x + swatch_size + 60 > screen.width():
            swatch_x = pos.x() - swatch_size - 80
        for i, click in enumerate(self._clicks):
            c = click['color']
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.setBrush(QColor(c[0], c[1], c[2]))
            painter.drawRect(swatch_x, swatch_y + i * (swatch_size + 4), swatch_size, swatch_size)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(swatch_x + swatch_size + 6, swatch_y + i * (swatch_size + 4) + 16,
                             f"R:{c[0]} G:{c[1]} B:{c[2]}")
        painter.setPen(QColor(0, 255, 100))
        painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
        painter.drawText(20, self.height() - 40, self._prompt)
        painter.setPen(QColor(200, 200, 200))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(20, self.height() - 18, "Left click: pick color | Right click: undo | ESC: cancel")
