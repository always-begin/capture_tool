from src.ui.main_window import CapToolStudio
from PyQt6.QtWidgets import QApplication
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CapToolStudio()
    window.show()
    sys.exit(app.exec())