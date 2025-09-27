import chess
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PyQt6.QtCore import Qt, QRect
import time
import random
from collections import defaultdict

# Expanded opening move database
OPENING_BOOK = {
    'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1': [
        (chess.Move.from_uci('e2e4'), 0.4),  # 1.e4
        (chess.Move.from_uci('d2d4'), 0.3),  # 1.d4
        (chess.Move.from_uci('g1f3'), 0.2),  # 1.Nf3
        (chess.Move.from_uci('c2c4'), 0.1),  # 1.c4
        (chess.Move.from_uci('b1c3'), 0.05)  # 1.Nc3
    ],
    'rnbqkbnr/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 1 1': [
        (chess.Move.from_uci('g1f3'), 0.5),  # 2.Nf3
        (chess.Move.from_uci('f1c4'), 0.3),  # 2.Bc4
        (chess.Move.from_uci('b1c3'), 0.2)   # 2.Nc3
    ],
    'rnbqkbnr/pp1ppppp/5n2/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 1 1': [
        (chess.Move.from_uci('g1f3'), 0.4),  # 2.Nf3
        (chess.Move.from_uci('f1c4'), 0.3),  # 2.Bc4
        (chess.Move.from_uci('d2d4'), 0.3)   # 2.d4
    ],
    'rnbqkbnr/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 1': [
        (chess.Move.from_uci('g8f6'), 0.5),  # 1...Nf6
        (chess.Move.from_uci('c7c5'), 0.3),  # 1...c5
        (chess.Move.from_uci('e7e6'), 0.2)   # 1...e6
    ]
}

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
    'pawn': {'possession': 100, 'mobility': 0, 'threats': 0, 'protects': 0, 'advancement': 1},
    'knight': {'possession': 320, 'mobility': 0, 'threats': 1, 'protects': 1},
    'bishop': {'possession': 330, 'mobility': 0, 'threats': 1, 'protects': 1},
    'rook': {'possession': 500, 'mobility': 0, 'threats': 2, 'protects': 0},
    'queen': {'possession': 900, 'mobility': 1, 'threats': 5, 'protects': 0},
    'king': {'possession': 0, 'mobility': 0, 'threats': 4, 'protects': 0}
}

# Precomputed pawn advancement scores
PAWN_ADVANCEMENT = {
    chess.WHITE: [0, 0, 1, 2, 3, 4, 5, 6],
    chess.BLACK: [6, 5, 4, 3, 2, 1, 0, 0]
}

# Incremental board state
class BoardState:
    def __init__(self, board):
        self.piece_map = board.piece_map()
        self.legal_moves = list(board.legal_moves)
        self.piece_counts = {color: {pt: 0 for pt in range(1, 7)} for color in [chess.WHITE, chess.BLACK]}
        for piece in self.piece_map.values():
            self.piece_counts[piece.color][piece.piece_type] += 1

    def update(self, board, move):
        if not move:
            return
        from_piece = board.piece_at(move.from_square)
        if from_piece is None:
            return  # Skip invalid moves
        to_piece = board.piece_at(move.to_square)
        self.piece_map = board.piece_map()
        self.legal_moves = list(board.legal_moves)
        if to_piece:
            self.piece_counts[to_piece.color][to_piece.piece_type] -= 1
        self.piece_counts[from_piece.color][from_piece.piece_type] -= 1
        new_piece_type = move.promotion if move.promotion else from_piece.piece_type
        self.piece_counts[from_piece.color][new_piece_type] += 1

# Enhanced board evaluation
def evaluate_board(board, state, weights=None):
    if weights is None:
        weights = EVAL_WEIGHTS

    if board.is_checkmate():
        return -9999 if board.turn == chess.WHITE else 9999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    
    # Possession
    for color in [chess.WHITE, chess.BLACK]:
        for piece_type in range(1, 7):
            count = state.piece_counts[color][piece_type]
            score += weights[chess.piece_name(piece_type).lower()]['possession'] * count * (1 if color == chess.WHITE else -1)
    
    # Mobility, threats, protects
    for square, piece in state.piece_map.items():
        w = weights[chess.piece_name(piece.piece_type).lower()]
        moves = sum(1 for m in state.legal_moves if m.from_square == square)
        score += w['mobility'] * moves * (1 if piece.color == chess.WHITE else -1)
        attacks = sum(1 for m in state.legal_moves if m.from_square == square and m.to_square in state.piece_map)
        score += w['threats'] * attacks * (1 if piece.color == chess.WHITE else -1)
        protectors = sum(1 for m in state.legal_moves if m.to_square == square and board.piece_at(m.from_square).color == piece.color)
        score += w['protects'] * protectors * (1 if piece.color == chess.WHITE else -1)
        if piece.piece_type == chess.PAWN:
            rank = chess.square_rank(square)
            score += w['advancement'] * PAWN_ADVANCEMENT[piece.color][rank] * (1 if piece.color == chess.WHITE else -1)
    
    return score if board.turn == chess.WHITE else -score

# Static Exchange Evaluation (SEE) approximation
def see_approx(board, move):
    if not board.is_capture(move):
        return 0
    victim = board.piece_at(move.to_square)
    aggressor = board.piece_at(move.from_square)
    if not aggressor:
        return 0
    # Handle en passant captures
    if board.is_en_passant(move):
        return 100  # Value of a pawn
    if not victim:
        return 0
    values = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}
    return values[victim.piece_type] - values[aggressor.piece_type]

# Move ordering
def order_moves(board, moves, depth=0, last_move=None):
    def move_score(move):
        score = 0
        if not board.is_capture(move) and not move.promotion and not board.gives_check(move):
            score += 200
        score += see_approx(board, move)
        if move.promotion:
            score += 500
        if board.gives_check(move):
            score += 200
        if move in killer_moves[depth]:
            score += 400
        score += history_table[move.uci()]
        return score
    return sorted(moves, key=move_score, reverse=True)

# Null move heuristic
def null_move(board, depth, alpha, beta, maximizing_player):
    if depth <= 1 or board.is_check() or board.is_game_over() or len(board.piece_map()) < 15:
        return None
    
    board.push(chess.Move.null())
    value = -alphabeta(board, BoardState(board), depth - 3, -beta, -beta + 1, not maximizing_player, None)
    board.pop()
    
    if value >= beta:
        return value
    return None

# Quiescence search
def quiescence_search(board, state, alpha, beta, maximizing_player, last_move=None, q_depth=2):
    if q_depth <= 0:
        return evaluate_board(board, state)
    
    stand_pat = evaluate_board(board, state)
    if maximizing_player:
        if stand_pat >= beta:
            return beta
        alpha = max(alpha, stand_pat)
    else:
        if stand_pat <= alpha:
            return alpha
        beta = min(beta, stand_pat)
    
    # Handle en passant and non-pawn captures
    capture_moves = []
    for move in state.legal_moves:
        if board.is_en_passant(move):
            capture_moves.append(move)
        elif board.is_capture(move):
            victim = board.piece_at(move.to_square)
            if victim and victim.piece_type != chess.PAWN:
                capture_moves.append(move)
    
    if last_move:
        capture_moves = [move for move in capture_moves if move.from_square == last_move.to_square or (board.piece_at(move.to_square) and board.piece_at(move.to_square) == board.piece_at(last_move.to_square))]
    capture_moves = order_moves(board, capture_moves, depth=0, last_move=last_move)
    
    for move in capture_moves:
        board.push(move)
        new_state = BoardState(board)
        new_state.update(board, move)
        score = -quiescence_search(board, new_state, -beta, -alpha, not maximizing_player, move, q_depth - 1)
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
def alphabeta(board, state, depth, alpha, beta, maximizing_player, last_move=None):
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
        return quiescence_search(board, state, alpha, beta, maximizing_player, last_move)
    
    if not board.is_check() and depth >= 2 and len(board.piece_map()) >= 15:
        null_value = null_move(board, depth, alpha, beta, maximizing_player)
        if null_value is not None:
            return null_value
    
    legal_moves = order_moves(board, state.legal_moves, depth, last_move)
    
    if maximizing_player:
        max_eval = float('-inf')
        for move in legal_moves:
            board.push(move)
            new_state = BoardState(board)
            new_state.update(board, move)
            eval_score = alphabeta(board, new_state, depth - 1, alpha, beta, False, move)
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
            new_state = BoardState(board)
            new_state.update(board, move)
            eval_score = alphabeta(board, new_state, depth - 1, alpha, beta, True, move)
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
def find_best_move(board, max_time=1.0):
    fen = board.fen()
    if fen in OPENING_BOOK:
        moves, probs = zip(*OPENING_BOOK[fen])
        return random.choices(moves, weights=probs, k=1)[0]
    
    start_time = time.time()
    best_move = None
    alpha = float('-inf')
    beta = float('inf')
    state = BoardState(board)
    
    for depth in range(1, 6):
        if time.time() - start_time > max_time:
            break
        best_value = float('-inf') if board.turn == chess.WHITE else float('inf')
        legal_moves = order_moves(board, state.legal_moves, depth)
        
        for move in legal_moves:
            if not board.is_legal(move):
                continue  # Skip illegal moves
            board.push(move)
            new_state = BoardState(board)
            new_state.update(board, move)
            value = alphabeta(board, new_state, depth - 1, alpha, beta, board.turn == chess.BLACK, move)
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
    
    return best_move if best_move else random.choice(list(board.legal_moves))  # Fallback to random legal move

# Genetic Algorithm (run separately)
def genetic_algorithm(pop_size=20, generations=50):
    def create_individual():
        weights = {}
        for piece in ['pawn', 'knight', 'bishop', 'rook', 'queen', 'king']:
            weights[piece] = {
                'possession': EVAL_WEIGHTS[piece]['possession'],
                'mobility': random.randint(0, 5),
                'threats': random.randint(0, 5),
                'protects': random.randint(0, 5),
                'advancement': random.randint(0, 5) if piece == 'pawn' else 0
            }
        return weights
    
    def fitness(weights, test_positions=None):
        if test_positions is None:
            test_positions = [
                chess.Board(),
                chess.Board("rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 1 1")
            ]
        score = 0
        for board in test_positions:
            state = BoardState(board)
            eval_score = evaluate_board(board, state, weights)
            score += abs(eval_score) if board.is_game_over() else -abs(eval_score - evaluate_board(board, state, EVAL_WEIGHTS))
        return score
    
    def crossover(parent1, parent2):
        child = {}
        for piece in parent1:
            child[piece] = {}
            for key in parent1[piece]:
                child[piece][key] = random.choice([parent1[piece][key], parent2[piece][key]])
        return child
    
    def mutate(individual):
        for piece in individual:
            for key in individual[piece]:
                if key != 'possession' and random.random() < 0.1:
                    individual[piece][key] += random.randint(-1, 1)
                    individual[piece][key] = max(0, min(5, individual[piece][key]))
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
        start_time = time.time()
        move = find_best_move(self.board, max_time=1.0)
        if move:
            san_move = self.board.san(move)
            self.board.push(move)
            self.update_status(f"AI move: {san_move} (Time: {time.time() - start_time:.2f}s)")
            self.repaint()
            if self.board.is_game_over():
                self.update_status(f"Game Over! Result: {self.board.result()}")
        else:
            self.update_status("AI could not find a move!")

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