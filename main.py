import sys
from PyQt6.QtWidgets import QApplication
from ui import ChessWindow

def main():
    app = QApplication(sys.argv)
    w = ChessWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
