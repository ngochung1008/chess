# chess_main.py

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from chess_gui import ChessBoardWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess with AI")
        self.setGeometry(100, 100, 600, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.status_label = QLabel("Your turn (White)")
        self.board_widget = ChessBoardWidget(self)
        layout.addWidget(self.board_widget)
        layout.addWidget(self.status_label)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())