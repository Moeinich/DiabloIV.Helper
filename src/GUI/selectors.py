import sys
from typing import Optional, Tuple

from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QCursor
from PyQt5.QtWidgets import QApplication, QWidget

from helper import logging_helper


class BaseDragSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

        self._anchor: Optional[QPoint] = None
        self._confirmed = False
        self._mouse_pos: Optional[QPoint] = None

    def paintEvent(self, event):
        if self._anchor is None or self._mouse_pos is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        shape = self._compute_shape(self._mouse_pos)
        if shape is not None:
            self._paint_shape(painter, shape)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._anchor is None:
                self._anchor = event.pos()
            else:
                self._confirmed = True
                shape = self._compute_shape(event.pos())
                self._on_confirmed(shape)
                self.close()

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.pos()
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def _compute_shape(self, mouse_pos: QPoint):
        raise NotImplementedError

    def _paint_shape(self, painter: QPainter, shape):
        raise NotImplementedError

    def _on_confirmed(self, shape):
        raise NotImplementedError

    def run(self):
        self.show()
        loop = QApplication.instance()
        if loop:
            while self.isVisible():
                loop.processEvents()


class RectDragSelector(BaseDragSelector):
    def __init__(self):
        super().__init__()
        self.result_rect: Optional[QRect] = None

    def _compute_shape(self, mouse_pos: QPoint) -> QRect:
        return QRect(self._anchor, mouse_pos).normalized()

    def _paint_shape(self, painter: QPainter, rect: QRect):
        fill = QColor(0, 200, 100, 40)
        border = QColor(255, 255, 255, 200)
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, 2))
        painter.drawRect(rect)
        painter.setPen(QPen(QColor(255, 255, 255, 220)))
        painter.setFont(QFont("Segoe UI", 10))
        label = f"{rect.width()} x {rect.height()}"
        painter.drawText(rect.topRight() + QPoint(8, 12), label)

    def _on_confirmed(self, shape):
        self.result_rect = shape

    def run(self) -> Optional[QRect]:
        super().run()
        return self.result_rect


class CircleDragSelector(BaseDragSelector):
    def __init__(self):
        super().__init__()
        self.result_center: Optional[QPoint] = None
        self.result_radius: int = 0

    def _compute_shape(self, mouse_pos: QPoint) -> Tuple[QPoint, int]:
        center = self._anchor
        dx = mouse_pos.x() - center.x()
        dy = mouse_pos.y() - center.y()
        radius = int((dx * dx + dy * dy) ** 0.5)
        return center, radius

    def _paint_shape(self, painter: QPainter, shape: Tuple[QPoint, int]):
        center, radius = shape
        fill = QColor(0, 200, 100, 40)
        border = QColor(255, 255, 255, 200)
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, 2))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1, Qt.DashLine))
        painter.drawLine(center + QPoint(-radius, 0), center + QPoint(radius, 0))
        painter.drawLine(center + QPoint(0, -radius), center + QPoint(0, radius))
        painter.setPen(QPen(QColor(0, 200, 100, 200), 3))
        painter.drawPoint(center)
        painter.setPen(QPen(QColor(255, 255, 255, 220)))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(center + QPoint(radius + 8, 6), f"r={radius}")

    def _on_confirmed(self, shape):
        center, radius = shape
        self.result_center = center
        self.result_radius = radius

    def run(self) -> Optional[Tuple[QPoint, int]]:
        super().run()
        if self.result_center is not None:
            return self.result_center, self.result_radius
        return None
