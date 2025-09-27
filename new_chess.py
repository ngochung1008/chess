import chess
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PyQt6.QtCore import Qt, QRect
import time
import random
import numpy as np
from collections import defaultdict

# Transposition table and Zobrist hashing
transposition_table = defaultdict(lambda: None)
zobrist_table = {}
for square in range(64):
    for piece in range(1, 7):
        for color in [chess.WHITE, chess.BLACK]:
            zobrist_table[(square, piece, color)] = random.randint(0, 2**64 - 1)
zobrist_castling = [random.randint(0, 2**64 - 1) for _ in range(16)]
zobrist_en_passant = [random.randint(0, 2**64 - 1) for _ in range(8)]
zobrist_turn = random.randint(0, 2**64 - 1)

def get_zobrist_hash(board):
    h = 0
    for square in range(64):
        piece = board.piece_at(square)
        if piece:
            h ^= zobrist_table[(square, piece.piece_type, piece.color)]
    for castling in range(16):
        if board.castling_rights & (1 << castling):
            h ^= zobrist_castling[castling]
    if board.ep_square:
        h ^= zobrist_en_passant[chess.square_file(board.ep_square)]
    if board.turn == chess.BLACK:
        h ^= zobrist_turn
    return h

# Killer and history tables
killer_moves = defaultdict(lambda: [None, None])
history_table = defaultdict(int)

# Evaluation weights
EVAL_WEIGHTS = {
    'material': 1.0,
    'center_control': 0.1,
    'king_safety': 0.5,
    'pawn_structure': 0.3,
    'mobility': 0.2
}

# Enhanced board evaluation
def evaluate_board(board, weights=None):
    if weights is None:
        weights = EVAL_WEIGHTS

    if board.is_checkmate():
        return -9999 if board.turn == chess.WHITE else 9999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    piece_map = board.piece_map()
    score = 0
    piece_values = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}
    
    for piece in piece_map.values():
        value = piece_values[piece.piece_type]
        score += weights['material'] * (value if piece.color == chess.WHITE else -value)
    
    central_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    for square in central_squares:
        piece = piece_map.get(square)
        if piece:
            score += weights['center_control'] * (10 if piece.color == chess.WHITE else -10)
    
    for color in [chess.WHITE, chess.BLACK]:
        king_square = board.king(color)
        attacks = len(board.attackers(not color, king_square))
        score += weights['king_safety'] * (-20 * attacks if color == chess.WHITE else 20 * attacks)
    
    pawns = board.pieces(chess.PAWN, chess.WHITE)
    doubled_w = sum(1 for file in range(8) if len([p for p in pawns if chess.square_file(p) == file]) > 1)
    passed_w = sum(1 for p in pawns if not board.attackers(chess.BLACK, p) and all(
        chess.square_rank(p) < chess.square_rank(o) for o in board.pieces(chess.PAWN, chess.BLACK)))
    pawns = board.pieces(chess.PAWN, chess.BLACK)
    doubled_b = sum(1 for file in range(8) if len([p for p in pawns if chess.square_file(p) == file]) > 1)
    passed_b = sum(1 for p in pawns if not board.attackers(chess.WHITE, p) and all(
        chess.square_rank(p) > chess.square_rank(o) for o in board.pieces(chess.PAWN, chess.WHITE)))
    score += weights['pawn_structure'] * (10 * passed_w - 5 * doubled_w - 10 * passed_b + 5 * doubled_b)
    
    score += weights['mobility'] * len(list(board.legal_moves))
    
    return score if board.turn == chess.WHITE else -score

# Move ordering
def order_moves(board, moves, depth=0):
    def move_score(move):
        score = 0
        if board.is_capture(move):
            score += 100
            victim = board.piece_at(move.to_square)
            aggressor = board.piece_at(move.from_square)
            if victim and aggressor:
                score += 10 * (victim.piece_type - aggressor.piece_type)
        if move.promotion:
            score += 50
        if board.gives_check(move):
            score += 20
        if move in killer_moves[depth]:
            score += 40
        score += history_table[move.uci()]
        return score
    return sorted(moves, key=move_score, reverse=True)

# Null move heuristic
def null_move(board, depth, alpha, beta, maximizing_player):
    if depth <= 1 or board.is_check() or board.is_game_over():
        return None
    
    board.push(chess.Move.null())
    value = -alphabeta(board, depth - 3, -beta, -beta + 1, not maximizing_player)
    board.pop()
    
    if value >= beta:
        return value
    return None

# Quiescence search
def quiescence_search(board, alpha, beta, maximizing_player, q_depth=4):
    if q_depth <= 0:
        return evaluate_board(board)
    
    stand_pat = evaluate_board(board)
    if maximizing_player:
        if stand_pat >= beta:
            return beta
        alpha = max(alpha, stand_pat)
    else:
        if stand_pat <= alpha:
            return alpha
        beta = min(beta, stand_pat)
    
    capture_moves = [move for move in board.legal_moves if board.is_capture(move)]
    capture_moves = order_moves(board, capture_moves, depth=0)
    
    for move in capture_moves:
        board.push(move)
        score = -quiescence_search(board, -beta, -alpha, not maximizing_player, q_depth - 1)
        board.pop()
        
        if maximizing_player:
            alpha = max(alpha, score)
            if alpha >= beta:
                return beta
        else:
            beta = min(beta, score)
            if beta <= alpha:
                return alpha
    
    return alpha if maximizing_player else beta

# Alpha-Beta Pruning
def alphabeta(board, depth, alpha, beta, maximizing_player):
    board_key = get_zobrist_hash(board)
    tt_entry = transposition_table.get(board_key)
    if tt_entry and tt_entry['depth'] >= depth:
        if tt_entry['type'] == 'exact':
            return tt_entry['value']
        elif tt_entry['type'] == 'lower' and tt_entry['value'] >= beta:
            return beta
        elif tt_entry['type'] == 'upper' and tt_entry['value'] <= alpha:
            return alpha
    
    if depth <= 0:
        return quiescence_search(board, alpha, beta, maximizing_player)
    
    if not board.is_check() and depth >= 3:
        null_value = null_move(board, depth, alpha, beta, maximizing_player)
        if null_value is not None:
            return null_value
    
    legal_moves = order_moves(board, list(board.legal_moves), depth)
    
    if maximizing_player:
        max_eval = float('-inf')
        for move in legal_moves:
            board.push(move)
            eval_score = alphabeta(board, depth - 1, alpha, beta, False)
            board.pop()
            if eval_score >= beta:
                killer_moves[depth] = [move, killer_moves[depth][0]]
                history_table[move.uci()] += depth ** 2
                transposition_table[board_key] = {'value': eval_score, 'depth': depth, 'type': 'lower'}
                return beta
            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
        transposition_table[board_key] = {'value': max_eval, 'depth': depth, 'type': 'exact' if alpha < max_eval < beta else 'upper'}
        return max_eval
    else:
        min_eval = float('inf')
        for move in legal_moves:
            board.push(move)
            eval_score = alphabeta(board, depth - 1, alpha, beta, True)
            board.pop()
            if eval_score <= alpha:
                killer_moves[depth] = [move, killer_moves[depth][0]]
                history_table[move.uci()] += depth ** 2
                transposition_table[board_key] = {'value': eval_score, 'depth': depth, 'type': 'upper'}
                return alpha
            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
        transposition_table[board_key] = {'value': min_eval, 'depth': depth, 'type': 'exact' if alpha < min_eval < beta else 'lower'}
        return min_eval

# Find best AI move
def find_best_move(board, max_time=2.0):
    start_time = time.time()
    best_move = None
    alpha = float('-inf')
    beta = float('inf')
    
    for depth in range(1, 10):
        if time.time() - start_time > max_time:
            break
        best_value = float('-inf') if board.turn == chess.WHITE else float('inf')
        legal_moves = order_moves(board, list(board.legal_moves), depth)
        
        for move in legal_moves:
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

# Genetic Algorithm (run separately)
def genetic_algorithm(pop_size=20, generations=50):
    def create_individual():
        return {
            'material': random.uniform(0.5, 1.5),
            'center_control': random.uniform(0.05, 0.2),
            'king_safety': random.uniform(0.3, 0.7),
            'pawn_structure': random.uniform(0.2, 0.5),
            'mobility': random.uniform(0.1, 0.3)
        }
    
    def fitness(weights, test_positions=None):
        if test_positions is None:
            test_positions = [chess.Board(), chess.Board("rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 1 1")]
        score = 0
        for board in test_positions:
            eval_score = evaluate_board(board, weights)
            score += abs(eval_score) if board.is_game_over() else -abs(eval_score - evaluate_board(board, EVAL_WEIGHTS))
        return score
    
    def crossover(parent1, parent2):
        child = {}
        for key in parent1:
            child[key] = random.choice([parent1[key], parent2[key]])
        return child
    
    def mutate(individual):
        for key in individual:
            if random.random() < 0.1:
                individual[key] += random.uniform(-0.1, 0.1)
                individual[key] = max(0.01, min(2.0, individual[key]))
        return individual
    
    population = [create_individual() for _ in range(pop_size)]
    
    for _ in range(generations):
        fitness_scores = [(ind, fitness(ind)) for ind in population]
        fitness_scores.sort(key=lambda x: x[1], reverse=True)
        population = [ind for ind, _ in fitness_scores[:pop_size // 2]]
        
        while len(population) < pop_size:
            parent1, parent2 = random.sample(population, 2)
            child = crossover(parent1, parent2)
            child = mutate(child)
            population.append(child)
    
    return max([(ind, fitness(ind)) for ind in population], key=lambda x: x[1])[0]

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
        if self.board.turn != chess.WHITE or self.board.is_game_over():
            self.update_status("Not your turn or game is over!")
            return

        file = event.position().x() // self.square_size
        rank = 7 - (event.position().y() // self.square_size)
        square = chess.square(int(file), int(rank))

        if self.selected_square is None:
            piece = self.board.piece_at(square)
            if piece and piece.color == chess.WHITE:
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
        self.repaint()
        start_time = time.time()
        move = find_best_move(self.board, max_time=2.0)
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
    # Run genetic algorithm separately to tune weights
    # best_weights = genetic_algorithm(pop_size=20, generations=50)
    # print("Best weights:", best_weights)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())