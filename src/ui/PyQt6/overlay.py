import os
import sys
from datetime import datetime

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QScreen

from src.core.utils import capture_screen_area, save_settings, load_settings


class CaptureOverlay(QWidget):
    def __init__(self, parent_tk, mode, save_dir=None, on_complete=None, on_cancel=None):
        super().__init__()
        self.parent_tk   = parent_tk
        self.mode        = mode
        self.save_dir    = save_dir
        self.on_complete = on_complete
        self.on_cancel   = on_cancel

        # ウィンドウ設定
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)

        # マルチモニター対応：全画面を包含する矩形
        screens = QApplication.screens()
        left   = min(s.geometry().left()   for s in screens)
        top    = min(s.geometry().top()    for s in screens)
        right  = max(s.geometry().right()  for s in screens)
        bottom = max(s.geometry().bottom() for s in screens)
        self.setGeometry(left, top, right - left, bottom - top)
        self._origin = QPoint(left, top)

        # 状態
        self.rect            = None   # QRect（選択範囲）
        self._drag_mode      = None   # "create" or "move"
        self._start_pos      = None   # ドラッグ開始点
        self._rect_at_start  = None   # moveモード開始時のrect
        self._dragged        = False

        # 前回の選択範囲を復元
        sx, sy, sw, sh = load_settings()
        if sw > 0 and sh > 0:
            self.rect = QRect(
                sx - self._origin.x(),
                sy - self._origin.y(),
                sw, sh
            )

        self.showFullScreen()
        self.activateWindow()
        self.setFocus()

    # ------------------------------------------------------------------ paint

    def paintEvent(self, event):
        painter = QPainter(self)

        if self.rect and self.rect.isValid():
            r = self.rect.normalized()

            # 外側を半透明の黒で覆う（4分割）
            dark = QColor(0, 0, 0, 140)
            w = self.width()
            h = self.height()
            painter.fillRect(0,        0,        w,           r.top(),         dark)  # 上
            painter.fillRect(0,        r.bottom(), w,         h - r.bottom(),  dark)  # 下
            painter.fillRect(0,        r.top(),  r.left(),    r.height(),      dark)  # 左
            painter.fillRect(r.right(), r.top(), w - r.right(), r.height(),    dark)  # 右

            # 枠線
            pen = QPen(QColor("cyan"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(r)

        else:
            # 矩形なし：全体を薄く暗くする
            painter.fillRect(self.rect_(), QColor(0, 0, 0, 80))

    def rect_(self):
        """ウィジェット全体のQRect"""
        from PyQt6.QtCore import QRect
        return QRect(0, 0, self.width(), self.height())

    # ------------------------------------------------------------------ mouse

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragged = False
        pos = event.pos()

        if self.rect and self.rect.normalized().contains(pos):
            self._drag_mode     = "move"
            self._start_pos     = pos
            self._rect_at_start = QRect(self.rect)
        else:
            self._drag_mode = "create"
            self._start_pos = pos
            self.rect       = QRect(pos, pos)

    def mouseMoveEvent(self, event):
        self._dragged = True
        pos = event.pos()

        if self._drag_mode == "create":
            self.rect = QRect(self._start_pos, pos)

        elif self._drag_mode == "move":
            delta     = pos - self._start_pos
            self.rect = self._rect_at_start.translated(delta)
            self.rect = self._clamp_rect(self.rect)

        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self._dragged:
            if self._drag_mode == "move":
                self._execute_capture()
                return
        self._save_current_rect()

    def contextMenuEvent(self, event):
        """右クリックで矩形クリア"""
        self.rect = None
        self.update()

    # ------------------------------------------------------------------ keyboard

    def keyPressEvent(self, event):
        key  = event.key()
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        step = 1 if ctrl else 10

        if key == Qt.Key.Key_Escape:
            self._exit_overlay()
        elif key == Qt.Key.Key_Space:
            self._execute_capture()
        elif self.rect:
            r = self.rect.normalized()
            if key == Qt.Key.Key_Up:
                self.rect = QRect(r.topLeft(), r.bottomRight() - QPoint(0, step))
            elif key == Qt.Key.Key_Down:
                self.rect = QRect(r.topLeft(), r.bottomRight() + QPoint(0, step))
            elif key == Qt.Key.Key_Left:
                self.rect = QRect(r.topLeft(), r.bottomRight() - QPoint(step, 0))
            elif key == Qt.Key.Key_Right:
                self.rect = QRect(r.topLeft(), r.bottomRight() + QPoint(step, 0))
            self.rect = self._clamp_resize(self.rect.normalized())
            self._save_current_rect()
            self.update()

    def wheelEvent(self, event):
        if not self.rect:
            return
        ctrl  = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        step  = (1 if ctrl else 10) * (1 if event.angleDelta().y() > 0 else -1)
        r     = self.rect.normalized()

        if shift:
            self.rect = QRect(r.topLeft(), r.bottomRight() + QPoint(step, 0))
        else:
            self.rect = QRect(r.topLeft(), r.bottomRight() + QPoint(0, step))

        self.rect = self._clamp_resize(self.rect.normalized())
        self._save_current_rect()
        self.update()

    # ------------------------------------------------------------------ helpers

    def _clamp_rect(self, rect):
        """移動用：幅・高さを維持してウィジェット内に収める"""
        r  = rect.normalized()
        w  = min(r.width(),  self.width())
        h  = min(r.height(), self.height())
        x1 = max(0, min(r.left(), self.width()  - w))
        y1 = max(0, min(r.top(),  self.height() - h))
        return QRect(x1, y1, w, h)

    def _clamp_resize(self, rect):
        """サイズ変更用：左上固定で右下をウィジェット内に収める"""
        r  = rect.normalized()
        x2 = max(r.left() + 1, min(r.right(),  self.width()))
        y2 = max(r.top()  + 1, min(r.bottom(), self.height()))
        return QRect(r.topLeft(), QPoint(x2, y2))

    def _save_current_rect(self):
        if not self.rect:
            return
        r = self.rect.normalized()
        save_settings(
            self._origin.x() + r.left(),
            self._origin.y() + r.top(),
            r.width(), r.height()
        )

    # ------------------------------------------------------------------ actions

    def _execute_capture(self):
        if not self.rect:
            return
        r = self.rect.normalized()
        if r.width() <= 0 or r.height() <= 0:
            return

        monitor = {
            "left":   self._origin.x() + r.left(),
            "top":    self._origin.y() + r.top(),
            "width":  r.width(),
            "height": r.height(),
        }

        img = capture_screen_area(monitor)

        if self.mode == "normal":
            self._exit_overlay()
            if self.on_complete:
                self.on_complete(img)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = os.path.join(self.save_dir, f"capture_{timestamp}.png")
            img.save(path)
            self._flash_rect()

    def _flash_rect(self):
        """連続保存エフェクト"""
        self._flashing = True
        self.update()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(120, self._flash_end)

    def _flash_end(self):
        self._flashing = False
        self.update()

    def _exit_overlay(self):
        self.close()
        self.parent_tk.show()
        self.parent_tk.activateWindow()
        if self.on_cancel:
            self.on_cancel()