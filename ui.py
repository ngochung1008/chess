"""Chứa ChessWindow (giao diện PyQt6)."""

# ui.py
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QVBoxLayout, QLabel,
    QMessageBox, QInputDialog, QHBoxLayout
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from game import ChessGame
import sys

class ChessWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cờ vua - Chess")
        self.game = ChessGame()
        self.buttons = [[None]*8 for _ in range(8)]
        self.selected = None
        self.valid_moves = []
        self.init_ui()
        self.update_board()

    def init_ui(self):
        main = QVBoxLayout()
        top = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setFont(QFont('Arial', 12))
        top.addWidget(self.status_label)
        btn_undo = QPushButton("Undo")
        btn_undo.clicked.connect(self.undo_move)
        top.addWidget(btn_undo)
        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self.reset_game)
        top.addWidget(btn_reset)
        main.addLayout(top)

        grid = QGridLayout()
        grid.setSpacing(0)

        # Nhãn cột (a-h) ở trên và dưới
        for c, letter in enumerate("abcdefgh"):
            top_lbl = QLabel(letter)
            bot_lbl = QLabel(letter)
            for lbl in (top_lbl, bot_lbl):
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setFont(QFont('Arial', 10, QFont.Weight.Bold))
                lbl.setContentsMargins(0, 5, 0, 5)  # tạo khoảng cách dọc
            grid.addWidget(top_lbl, 0, c+1)   # hàng trên cùng
            grid.addWidget(bot_lbl, 9, c+1)   # hàng dưới cùng

        # Nhãn hàng (8-1) ở trái và phải
        for r in range(8):
            left_lbl = QLabel(str(8-r))
            right_lbl = QLabel(str(8-r))
            for lbl in (left_lbl, right_lbl):
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setFont(QFont('Arial', 10, QFont.Weight.Bold))
                lbl.setContentsMargins(5, 0, 5, 0)  # tạo khoảng cách ngang
            grid.addWidget(left_lbl, r+1, 0)   # cột trái
            grid.addWidget(right_lbl, r+1, 9)  # cột phải

        # Tạo nút bàn cờ (ô cờ nằm trong lưới 1..8,1..8)
        for r in range(8):
            for c in range(8):
                btn = QPushButton()
                btn.setFixedSize(64, 64)
                btn.setFont(QFont('Arial', 28))
                btn.setStyleSheet(self.style_for_square(r, c))
                btn.clicked.connect(self.make_handle(r, c))
                self.buttons[r][c] = btn
                grid.addWidget(btn, r+1, c+1)

        main.addLayout(grid)
        self.setLayout(main)
        self.setFixedSize(self.sizeHint())

    def style_for_square(self, r, c, highlight=False, valid=False):
        base = "#F0D9B5" if (r+c)%2==0 else "#B58863"
        if highlight:
            base = "#AAAA00"
        if valid:
            base = "#43A047"
            return f"background-color: {base}; border: 1px solid #222;"
        return f"background-color: {base}; border: none;"

    def make_handle(self, r, c):
        def handler():
            self.on_click(r,c)
        return handler

    def on_click(self, r, c):
        g = self.game
        p = g.piece_at(r,c)
        # select
        if self.selected is None:
            if p is None: return
            if p.white != g.turn_white: return
            self.selected = (r,c)
            self.valid_moves = g.legal_moves_for_piece(r,c)
            self.update_board()
            return
        # if clicking same -> deselect
        fr,fc = self.selected
        if (r,c) == (fr,fc):
            self.selected = None
            self.valid_moves = []
            self.update_board()
            return
        # if clicked own piece -> switch selection
        if p is not None and p.white == g.piece_at(fr,fc).white:
            self.selected = (r,c)
            self.valid_moves = g.legal_moves_for_piece(r,c)
            self.update_board()
            return
        # attempt move
        if (r,c) in self.valid_moves:
            # check promotion
            piece = g.piece_at(fr,fc)
            promote_choice = None
            if piece is not None and piece.__class__.__name__ == 'Pawn':
                if (piece.white and r == 0) or (not piece.white and r == 7):
                    promote_choice = self.ask_promotion(piece.white)
            g.make_move((fr,fc),(r,c), promote_to=promote_choice)
            self.selected = None
            self.valid_moves = []
            self.update_board()
            self.after_move_checks()
        else:
            self.selected = None
            self.valid_moves = []
            self.update_board()

    def update_board(self):
        board = self.game.board_unicode()
        for r in range(8):
            for c in range(8):
                btn = self.buttons[r][c]
                btn.setText(board[r][c])
                if self.selected == (r, c):
                    btn.setStyleSheet(self.style_for_square(r, c, highlight=True))
                elif (r, c) in self.valid_moves:
                    btn.setStyleSheet(self.style_for_square(r, c, valid=True))
                else:
                    btn.setStyleSheet(self.style_for_square(r, c))
        side = "Trắng" if self.game.turn_white else "Đen"
        self.status_label.setText(f"Lượt: {side}")

    def after_move_checks(self):
        g = self.game
        opponent_white = g.turn_white
        if g.in_check(opponent_white):
            # does opponent have any legal move?
            moves = g.all_moves_for_side(opponent_white)
            legal_exist = False
            for (src,dst) in moves:
                r,c = src
                if g.legal_moves_for_piece(r,c):
                    legal_exist = True
                    break
            if not legal_exist:
                QMessageBox.information(self, "Checkmate", f"Checkmate! {'Đen' if not g.turn_white else 'Trắng'} thua. {'Trắng' if g.turn_white else 'Đen'} thắng!")
            else:
                QMessageBox.information(self, "Check", "Chiếu!")
        else:
            # stalemate?
            moves = g.all_moves_for_side(opponent_white)
            any_legal = False
            for src,dst in moves:
                r,c = src
                if g.legal_moves_for_piece(r,c):
                    any_legal = True
                    break
            if not any_legal:
                QMessageBox.information(self, "Hòa", "Hòa (stalemate)!")

    def ask_promotion(self, is_white):
        items = ["Q - Hậu", "R - Xe", "B - Tượng", "N - Mã"]
        item, ok = QInputDialog.getItem(self, "Phong cấp", "Chọn quân phong cấp:", items, 0, False)
        if ok and item:
            letter = item.split()[0]
            return letter
        else:
            return 'Q'

    def undo_move(self):
        self.game.undo_last()
        self.selected = None
        self.valid_moves = []
        self.update_board()

    def reset_game(self):
        self.game.setup_start()
        self.selected = None
        self.valid_moves = []
        self.update_board()
