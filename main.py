from src.ui.main_window import CapToolStudio

# for tkinter
if __name__ == "__main__":
    app = CapToolStudio()
    app.mainloop()

# for PyQt6
# from PyQt6.QtWidgets import QApplication
# import sys

# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = CapToolStudio()
#     window.show()
#     sys.exit(app.exec())