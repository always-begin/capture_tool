import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog,
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QImage
from PIL import Image

from src.ui.overlay import CaptureOverlay
from src.core.utils import copy_image_to_clipboard


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    """PIL Image → QPixmap"""
    rgb = img.convert("RGBA")
    data = rgb.tobytes("raw", "RGBA")
    qimg = QImage(data, rgb.width, rgb.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


class PreviewCanvas(QWidget):
    """画像プレビュー・ズーム・パン"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #000000;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.pixmap       = None
        self.zoom_level   = 1.0
        self._offset      = QPoint(0, 0)
        self._pan_start   = None
        self._offset_start = QPoint(0, 0)

    def set_image(self, img: Image.Image):
        self.pixmap     = pil_to_pixmap(img)
        self.zoom_level = 1.0
        self._offset    = QPoint(0, 0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))

        if self.pixmap is None:
            painter.setPen(QColor("#444444"))
            painter.setFont(QFont("Impact", 28))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Image")
            return

        w = int(self.pixmap.width()  * self.zoom_level)
        h = int(self.pixmap.height() * self.zoom_level)
        cx = self.width()  // 2 + self._offset.x()
        cy = self.height() // 2 + self._offset.y()
        x  = cx - w // 2
        y  = cy - h // 2
        painter.drawPixmap(x, y, w, h, self.pixmap)

    def wheelEvent(self, event):
        if self.pixmap is None:
            return
        factor   = 1.1 if event.angleDelta().y() > 0 else 0.9
        old_zoom = self.zoom_level
        self.zoom_level = max(0.1, min(self.zoom_level * factor, 10.0))
        scale    = self.zoom_level / old_zoom

        cx = self.width()  // 2 + self._offset.x()
        cy = self.height() // 2 + self._offset.y()
        mx = event.position().x() - cx
        my = event.position().y() - cy
        self._offset -= QPoint(int(mx * (scale - 1)), int(my * (scale - 1)))
        self.update()

    def mousePressEvent(self, event):
        if self.pixmap is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._pan_start    = event.pos()
            self._offset_start = QPoint(self._offset)
        elif event.button() == Qt.MouseButton.RightButton:
            self.zoom_level = 1.0
            self._offset    = QPoint(0, 0)
            self.update()

    def mouseMoveEvent(self, event):
        if self.pixmap is None or self._pan_start is None:
            return
        delta        = event.pos() - self._pan_start
        self._offset = self._offset_start + delta
        self.update()

    def mouseReleaseEvent(self, event):
        self._pan_start = None


class CapToolStudio(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CapTool")
        self.resize(800, 500)
        self.setMinimumSize(700, 450)
        self.setStyleSheet("background-color: #2b2b2b; color: white;")

        self.current_img = None

        # --- 中央ウィジェット ---
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # --- 左: プレビュー ---
        self.preview = PreviewCanvas()
        layout.addWidget(self.preview, stretch=1)

        # --- 右: コントロールパネル ---
        self.side_panel = QFrame()
        self.side_panel.setFixedWidth(280)
        self.side_panel.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border-radius: 15px;
            }
        """)
        side_layout = QVBoxLayout(self.side_panel)
        side_layout.setContentsMargins(20, 20, 20, 20)
        side_layout.setSpacing(0)
        layout.addWidget(self.side_panel)

        # MODE ラベル
        mode_label = QLabel("MODE")
        mode_label.setFont(QFont("Impact", 20))
        mode_label.setStyleSheet("color: gray;")
        mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(mode_label)
        side_layout.addSpacing(10)

        # モード切替ボタン
        mode_row = QHBoxLayout()
        self.btn_normal = QPushButton("通常モード")
        self.btn_continuous = QPushButton("連続保存")
        for btn in (self.btn_normal, self.btn_continuous):
            btn.setFont(QFont("Yu Gothic UI", 11))
            btn.setFixedHeight(36)
            btn.setCheckable(True)
            mode_row.addWidget(btn)
        self.btn_normal.setChecked(True)
        self.btn_normal.clicked.connect(lambda: self._set_mode("normal"))
        self.btn_continuous.clicked.connect(lambda: self._set_mode("continuous"))
        side_layout.addLayout(mode_row)
        self._update_mode_style()

        # 区切り線
        side_layout.addSpacing(20)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #555555;")
        side_layout.addWidget(line)
        side_layout.addSpacing(20)

        # ACTION ラベル
        action_label = QLabel("ACTION")
        action_label.setFont(QFont("Impact", 20))
        action_label.setStyleSheet("color: gray;")
        action_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(action_label)
        side_layout.addSpacing(10)

        # CAPTURE START
        self.start_btn = QPushButton("CAPTURE START")
        self.start_btn.setFont(QFont("Impact", 22))
        self.start_btn.setFixedHeight(50)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2fa572;
                color: white;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #107a4b; }
        """)
        self.start_btn.clicked.connect(self._start_capture)
        side_layout.addWidget(self.start_btn)
        side_layout.addSpacing(10)

        # コピー
        self.copy_btn = QPushButton("コピー")
        self.copy_btn.setFont(QFont("Yu Gothic UI", 13))
        self.copy_btn.setFixedHeight(40)
        self.copy_btn.clicked.connect(self._copy_to_clip)
        side_layout.addWidget(self.copy_btn)
        side_layout.addSpacing(5)

        # 画像を保存
        self.save_btn = QPushButton("画像を保存")
        self.save_btn.setFont(QFont("Yu Gothic UI", 13))
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self._save_image)
        side_layout.addWidget(self.save_btn)

        side_layout.addStretch()

        self._update_ui()

    # ------------------------------------------------------------------ mode

    def _set_mode(self, mode):
        self.btn_normal.setChecked(mode == "normal")
        self.btn_continuous.setChecked(mode == "continuous")
        self._update_mode_style()
        self._update_ui()

    def _update_mode_style(self):
        active   = "background-color: #2fa572; color: white; border-radius: 6px;"
        inactive = "background-color: #3d3d3d; color: white; border-radius: 6px;"
        self.btn_normal.setStyleSheet(active if self.btn_normal.isChecked() else inactive)
        self.btn_continuous.setStyleSheet(active if self.btn_continuous.isChecked() else inactive)

    # ------------------------------------------------------------------ UI

    def _update_ui(self):
        is_normal = self.btn_normal.isChecked()
        has_img   = self.current_img is not None
        is_win    = sys.platform.startswith("win")

        enabled_style  = "background-color: #4a4a4a; color: white; border-radius: 6px;"
        disabled_style = "background-color: #333333; color: #666666; border-radius: 6px;"

        if is_normal and has_img:
            copy_enabled = is_win
            self.copy_btn.setEnabled(copy_enabled)
            self.copy_btn.setStyleSheet(enabled_style if copy_enabled else disabled_style)
            self.save_btn.setEnabled(True)
            self.save_btn.setStyleSheet(enabled_style)
        else:
            self.copy_btn.setEnabled(False)
            self.copy_btn.setStyleSheet(disabled_style)
            self.save_btn.setEnabled(False)
            self.save_btn.setStyleSheet(disabled_style)

    # ------------------------------------------------------------------ capture

    def _start_capture(self):
        mode     = "normal" if self.btn_normal.isChecked() else "continuous"
        save_dir = None

        if mode == "continuous":
            save_dir = QFileDialog.getExistingDirectory(self, "保存先フォルダを選択")
            if not save_dir:
                return

        self.hide()
        self.overlay = CaptureOverlay(
            self, mode, save_dir,
            on_complete=self._on_capture_complete,
            on_cancel=self._on_cancel
        )

    def _on_capture_complete(self, img):
        self.current_img = img
        self.preview.set_image(img)
        self._update_ui()
        self.show()
        self.activateWindow()

    def _on_cancel(self):
        self.show()
        self.activateWindow()

    # ------------------------------------------------------------------ actions

    def _copy_to_clip(self):
        if self.current_img:
            copy_image_to_clipboard(self.current_img)

    def _save_image(self):
        if not self.current_img:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "画像を保存", "",
            "PNG (*.png);;All files (*.*)"
        )
        if path:
            self.current_img.save(path)


def main():
    app = QApplication(sys.argv)
    window = CapToolStudio()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()