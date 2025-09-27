import chess
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PyQt6.QtCore import Qt, QRect
import time

# Chess evaluation function
def evaluate_board(board):
    if board.is_checkmate():
        return -9999 if board.turn == chess.WHITE else 9999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0
    }
    
    score = 0
    for piece_type in piece_values:
        white_pieces = len(board.pieces(piece_type, chess.WHITE))
        black_pieces = len(board.pieces(piece_type, chess.BLACK))
        score += piece_values[piece_type] * (white_pieces - black_pieces)
    
    central_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    for square in central_squares:
        piece = board.piece_at(square)
        if piece:
            score += 0.1 if piece.color == chess.WHITE else -0.1
    
    return score if board.turn == chess.WHITE else -score

# Alpha-Beta Pruning
def alphabeta(board, depth, alpha, beta, maximizing_player):
    if depth == 0 or board.is_game_over():
        return evaluate_board(board)

    legal_moves = list(board.legal_moves)
    
    if maximizing_player:
        max_eval = float('-inf')
        for move in legal_moves:
            board.push(move)
            eval_score = alphabeta(board, depth - 1, alpha, beta, False)
            board.pop()
            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = float('inf')
        for move in legal_moves:
            board.push(move)
            eval_score = alphabeta(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval

# Find best AI move
def find_best_move(board, depth=4):
    best_move = None
    best_value = float('-inf') if board.turn == chess.WHITE else float('inf')
    alpha = float('-inf')
    beta = float('inf')
    
    for move in board.legal_moves:
        board.push(move)
        value = alphabeta(board, depth - 1, alpha, beta, board.turn == chess.BLACK)
        board.pop()
        
        if board.turn == chess.WHITE:
            if value > best_value:
                best_value = value
                best_move = move
            alpha = max(alpha, value)
        else:
            if value < best_value:
                best_value = value
                best_move = move
            beta = min(beta, value)
    
    return best_move

# Chessboard GUI
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
                square = chess.square(file, 7 - rank)
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
        # Only allow moves when it's White's turn and game is not over
        if self.board.turn != chess.WHITE or self.board.is_game_over():
            self.update_status("Not your turn or game is over!")
            return

        file = event.position().x() // self.square_size
        rank = 7 - (event.position().y() // self.square_size)
        square = chess.square(int(file), int(rank))

        if self.selected_square is None:
            piece = self.board.piece_at(square)
            if piece and piece.color == chess.WHITE:  # Ensure it's a White piece
                self.selected_square = square
                self.legal_moves = [move for move in self.board.legal_moves if move.from_square == square]
                self.update_status(f"Selected {chess.square_name(square)}. Choose destination.")
        else:
            move = None
            for m in self.legal_moves:
                if m.to_square == square:
                    move = m
                    break
            if move:
                # Push the move and get SAN before resetting selection
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