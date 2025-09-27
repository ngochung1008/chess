# chess_gui.py

import chess
import time
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PyQt6.QtCore import Qt
from chess_ai import find_best_move


class ChessBoardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = chess.Board()
        self.selected_square = None
        self.legal_moves = []
        self.square_size = 60
        self.setFixedSize(8 * self.square_size, 8 * self.square_size)
        self.piece_images = {
            chess.PAWN: {chess.WHITE: "♙", chess.BLACK: "♟"},
            chess.KNIGHT: {chess.WHITE: "♘", chess.BLACK: "♞"},
            chess.BISHOP: {chess.WHITE: "♗", chess.BLACK: "♝"},
            chess.ROOK: {chess.WHITE: "♖", chess.BLACK: "♜"},
            chess.QUEEN: {chess.WHITE: "♕", chess.BLACK: "♛"},
            chess.KING: {chess.WHITE: "♔", chess.BLACK: "♚"}
        }
        self.status_label = parent.status_label if parent else None

    def paintEvent(self, event):
        painter = QPainter(self)
        self.draw_board(painter)
        self.draw_pieces(painter)
        self.draw_selected_square(painter)
        painter.end()

    def draw_board(self, painter):
        for rank in range(8):
            for file in range(8):
                color = QColor(240, 217, 181) if (rank + file) % 2 == 0 else QColor(181, 136, 99)
                painter.fillRect(file * self.square_size, rank * self.square_size,
                                self.square_size, self.square_size, color)

    def draw_pieces(self, painter):
        painter.setFont(QFont("Arial", 30))
        for rank in range(8):
            for file in range(8):
                square = chess.square(file, 7 - rank)
                piece = self.board.piece_at(square)
                if piece:
                    symbol = self.piece_images.get(piece.piece_type, {}).get(piece.color, "")
                    painter.drawText(file * self.square_size, rank * self.square_size,
                                    self.square_size, self.square_size,
                                    Qt.AlignmentFlag.AlignCenter, symbol)

    def draw_selected_square(self, painter):
        if self.selected_square is not None:
            file = chess.square_file(self.selected_square)
            rank = 7 - chess.square_rank(self.selected_square)
            painter.setPen(QPen(QColor("blue"), 3))
            painter.drawRect(file * self.square_size, rank * self.square_size,
                            self.square_size, self.square_size)
            for move in self.legal_moves:
                to_file = chess.square_file(move.to_square)
                to_rank = 7 - chess.square_rank(move.to_square)
                painter.setBrush(QBrush(QColor(0, 255, 0, 100)))
                painter.drawEllipse(to_file * self.square_size + 20, to_rank * self.square_size + 20, 20, 20)

    def mousePressEvent(self, event):
        if self.board.turn != chess.WHITE or self.board.is_game_over():
            self.update_status("Not your turn or game is over!")
            return

        file = int(event.position().x() // self.square_size)
        rank = 7 - int(event.position().y() // self.square_size)
        square = chess.square(file, rank)

        if self.selected_square is None:
            piece = self.board.piece_at(square)
            if piece and piece.color == chess.WHITE:
                self.selected_square = square
                self.legal_moves = [m for m in self.board.legal_moves if m.from_square == square]
                self.update_status(f"Selected {chess.square_name(square)}. Choose destination.")
        else:
            move = next((m for m in self.legal_moves if m.to_square == square), None)
            if move:
                san_move = self.board.san(move)
                self.board.push(move)
                self.selected_square = None
                self.legal_moves = []
                self.update_status(f"Your move: {san_move}")
                self.repaint()
                if not self.board.is_game_over():
                    self.ai_move()
                else:
                    self.update_status(f"Game Over! Result: {self.board.result()}")
            else:
                self.selected_square = None
                self.legal_moves = []
                self.update_status("Invalid move! Select a piece.")
        self.repaint()

    def ai_move(self):
        self.update_status("AI thinking...")
        start_time = time.time()
        move = find_best_move(self.board, depth=4)
        if move:
            san_move = self.board.san(move)
            self.board.push(move)
            self.update_status(f"AI move: {san_move} (Time: {time.time() - start_time:.2f}s)")
            self.repaint()
            if self.board.is_game_over():
                self.update_status(f"Game Over! Result: {self.board.result()}")

    def update_status(self, message):
        if self.status_label:
            self.status_label.setText(message)