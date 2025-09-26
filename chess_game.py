# chess_gui_ai_tt.py
import sys
import chess
import math
import time
from dataclasses import dataclass
from PyQt6.QtWidgets import QApplication, QWidget, QMessageBox
from PyQt6.QtGui import QPainter, QColor, QFont

# -------------------------
# Heuristic + PSQT
# -------------------------
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

PAWN_TABLE = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10,-20,-20, 10, 10,  5,
     5, -5,-10,  0,  0,-10, -5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5,  5, 10, 25, 25, 10,  5,  5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
     0,  0,  0,  0,  0,  0,  0,  0
]
KNIGHT_TABLE = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
]

PSQT = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE
}

# -------------------------
# Transposition Table
# -------------------------
@dataclass
class TTEntry:
    depth: int
    value: int
    flag: str
    best_move: chess.Move

TT = {}  # Global TT

# -------------------------
# Utility
# -------------------------
def mvv_lva_score(board: chess.Board, move: chess.Move):
    if not board.is_capture(move):
        return 0
    victim = board.piece_at(move.to_square)
    attacker = board.piece_at(move.from_square)
    if not victim or not attacker:
        return 0
    return PIECE_VALUES.get(victim.piece_type, 0) - PIECE_VALUES.get(attacker.piece_type, 0)

# -------------------------
# Evaluation
# -------------------------
def evaluate_board(board: chess.Board) -> int:
    if board.is_checkmate():
        return -999999 if board.turn else 999999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for piece_type, val in PIECE_VALUES.items():
        for sq in board.pieces(piece_type, chess.WHITE):
            score += val
            if piece_type in PSQT:
                score += PSQT[piece_type][sq]
        for sq in board.pieces(piece_type, chess.BLACK):
            score -= val
            if piece_type in PSQT:
                score -= PSQT[piece_type][chess.square_mirror(sq)]
    return score

# -------------------------
# Quiescence
# -------------------------
def quiescence(board: chess.Board, alpha: int, beta: int):
    stand_pat = evaluate_board(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    moves = [m for m in board.legal_moves if board.is_capture(m)]
    moves.sort(key=lambda m: -mvv_lva_score(board, m))

    for m in moves:
        board.push(m)
        score = -quiescence(board, -beta, -alpha)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha

# -------------------------
# Alpha-Beta with TT
# -------------------------
NULL_MOVE_REDUCTION = 2

def alpha_beta(board: chess.Board, depth: int, alpha: int, beta: int, maximizing: bool):
    key = board.fen()
    if key in TT:
        entry = TT[key]
        if entry.depth >= depth:
            if entry.flag == "EXACT":
                return entry.value
            elif entry.flag == "LOWER":
                alpha = max(alpha, entry.value)
            elif entry.flag == "UPPER":
                beta = min(beta, entry.value)
            if alpha >= beta:
                return entry.value

    if depth == 0 or board.is_game_over():
        val = quiescence(board, alpha, beta)
        return val

    moves = list(board.legal_moves)
    moves.sort(key=lambda m: -mvv_lva_score(board, m))

    best_value = -math.inf
    best_move_local = None

    for m in moves:
        board.push(m)
        val = -alpha_beta(board, depth - 1, -beta, -alpha, not maximizing)
        board.pop()
        if val > best_value:
            best_value = val
            best_move_local = m
        if val > alpha:
            alpha = val
        if alpha >= beta:
            break

    flag = "EXACT"
    if best_value <= alpha:
        flag = "UPPER"
    elif best_value >= beta:
        flag = "LOWER"
    TT[key] = TTEntry(depth=depth, value=best_value, flag=flag, best_move=best_move_local)
    return best_value

# -------------------------
# Iterative deepening
# -------------------------
def find_best_move_iterative(board: chess.Board, max_depth=5, time_limit=3.0):
    best_move = None
    start_time = time.time()

    for depth in range(1, max_depth + 1):
        if time.time() - start_time > time_limit:
            break
        local_best = None
        local_best_value = -math.inf
        moves = list(board.legal_moves)
        moves.sort(key=lambda m: -mvv_lva_score(board, m))
        for m in moves:
            if time.time() - start_time > time_limit:
                break
            board.push(m)
            val = -alpha_beta(board, depth - 1, -math.inf, math.inf, False)
            board.pop()
            if val > local_best_value:
                local_best_value = val
                local_best = m
        if local_best:
            best_move = local_best
    return best_move

# -------------------------
# GUI
# -------------------------
class ChessGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Game - Human (White) vs AI (Black)")
        self.setGeometry(100, 100, 480, 480)
        self.board = chess.Board()
        self.selected_square = None
        self.valid_moves = []
        self.square_size = 60
        self.font = QFont("Arial", 28)

    def paintEvent(self, event):
        painter = QPainter(self)
        for row in range(8):
            for col in range(8):
                x, y = col * self.square_size, row * self.square_size
                color = QColor(240, 217, 181) if (row + col) % 2 == 0 else QColor(181, 136, 99)
                painter.fillRect(x, y, self.square_size, self.square_size, color)
                square = chess.square(col, 7 - row)
                piece = self.board.piece_at(square)
                if piece:
                    painter.setFont(self.font)
                    painter.drawText(x + 15, y + 45, piece.symbol())

        if self.selected_square is not None:
            col = chess.square_file(self.selected_square)
            row = 7 - chess.square_rank(self.selected_square)
            painter.setBrush(QColor(255, 255, 0, 100))
            painter.drawRect(col * self.square_size, row * self.square_size, self.square_size, self.square_size)

        painter.setBrush(QColor(0, 255, 0, 120))
        for move in self.valid_moves:
            to_square = move.to_square
            to_col = chess.square_file(to_square)
            to_row = 7 - chess.square_rank(to_square)
            center_x = to_col * self.square_size + self.square_size // 2
            center_y = to_row * self.square_size + self.square_size // 2
            painter.drawEllipse(center_x - 10, center_y - 10, 20, 20)

    def mousePressEvent(self, event):
        if self.board.turn != chess.WHITE:
            return
        col = int(event.position().x() // self.square_size)
        row = int(event.position().y() // self.square_size)
        square = chess.square(col, 7 - row)
        if self.selected_square is None:
            piece = self.board.piece_at(square)
            if piece and piece.color == self.board.turn:
                self.selected_square = square
                self.valid_moves = [m for m in self.board.legal_moves if m.from_square == square]
        else:
            candidates = [m for m in self.valid_moves if m.to_square == square]
            chosen_move = candidates[0] if candidates else None
            if chosen_move:
                self.board.push(chosen_move)
                self.selected_square = None
                self.valid_moves = []
                self.update()
                self.check_game_over()
                if self.board.turn == chess.BLACK and not self.board.is_game_over():
                    self.ai_move()
            else:
                self.selected_square = None
                self.valid_moves = []
        self.update()

    def ai_move(self):
        if self.board.is_game_over() or self.board.turn != chess.BLACK:
            return
        move = find_best_move_iterative(self.board, max_depth=3, time_limit=3.0)
        if move:
            self.board.push(move)
            self.update()
            self.check_game_over()

    def check_game_over(self):
        if self.board.is_checkmate():
            winner = "White" if self.board.turn == chess.BLACK else "Black"
            QMessageBox.information(self, "Game Over", f"Checkmate! {winner} wins.")
        elif self.board.is_stalemate() or self.board.is_insufficient_material():
            QMessageBox.information(self, "Game Over", "Draw!")

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ChessGUI()
    gui.show()
    sys.exit(app.exec())
