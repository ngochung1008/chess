# chess_ai.py

import chess
import math

# -------------------------
# Giá trị quân cơ bản
# -------------------------
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 100000,
}

# -------------------------
# Piece-Square Tables
# -------------------------
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

BISHOP_TABLE = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
]

ROOK_TABLE = [
     0,  0,  0,  5,  5,  0,  0,  0,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     5, 10, 10, 10, 10, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
]

QUEEN_TABLE = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20
]

KING_TABLE = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20
]

PSQT = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE
}

# -------------------------
# Hàm đánh giá
# -------------------------
def evaluate(board):
    score = 0
    
    # material + PSQT
    for piece_type in PIECE_VALUES:
        for sq in board.pieces(piece_type, chess.WHITE):
            score += PIECE_VALUES[piece_type] + PSQT[piece_type][sq]
        for sq in board.pieces(piece_type, chess.BLACK):
            score -= PIECE_VALUES[piece_type] + PSQT[piece_type][chess.square_mirror(sq)]
    
    # mobility
    score += len(list(board.legal_moves)) * (10 if board.turn == chess.WHITE else -10)

    # castling rights bonus
    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        score += 20
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        score -= 20
    
    return score

# -------------------------
# Move ordering (ưu tiên bắt quân)
# -------------------------
def order_moves(board, moves):
    return sorted(moves, key=lambda m: capture_value(board, m), reverse=True)

def capture_value(board, move):
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        attacker = board.piece_at(move.from_square)
        if captured and attacker:
            # MVV-LVA: ưu tiên bắt quân giá trị lớn bởi attacker giá trị nhỏ
            return PIECE_VALUES[captured.piece_type] * 100 - PIECE_VALUES[attacker.piece_type]
    return 0

# -------------------------
# Alpha-Beta
# -------------------------
def alpha_beta(board, depth, alpha, beta, maximizing_player):
    if depth == 0 or board.is_game_over():
        return evaluate(board)

    moves = order_moves(board, list(board.legal_moves))

    if maximizing_player:
        max_eval = -math.inf
        for move in moves:
            board.push(move)

            # ---- Bonus cho move đặc biệt ----
            move_bonus = 0
            if board.is_castling(move):
                move_bonus += 50
            if board.is_en_passant(move):
                move_bonus += 30

            eval = alpha_beta(board, depth-1, alpha, beta, False) + move_bonus
            board.pop()

            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = math.inf
        for move in moves:
            board.push(move)

            move_bonus = 0
            if board.is_castling(move):
                move_bonus -= 50
            if board.is_en_passant(move):
                move_bonus -= 30

            eval = alpha_beta(board, depth-1, alpha, beta, True) + move_bonus
            board.pop()

            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha:
                break
        return min_eval

# -------------------------
# Tìm nước đi tốt nhất
# -------------------------
def find_best_move(board, depth=3):
    best_move = None
    if board.turn == chess.WHITE:
        max_eval = -math.inf
        for move in order_moves(board, list(board.legal_moves)):
            board.push(move)

            move_bonus = 0
            if board.is_castling(move):
                move_bonus += 50
            if board.is_en_passant(move):
                move_bonus += 30

            eval = alpha_beta(board, depth-1, -math.inf, math.inf, False) + move_bonus
            board.pop()

            if eval > max_eval:
                max_eval = eval
                best_move = move
    else:
        min_eval = math.inf
        for move in order_moves(board, list(board.legal_moves)):
            board.push(move)

            move_bonus = 0
            if board.is_castling(move):
                move_bonus -= 50
            if board.is_en_passant(move):
                move_bonus -= 30

            eval = alpha_beta(board, depth-1, -math.inf, math.inf, True) + move_bonus
            board.pop()

            if eval < min_eval:
                min_eval = eval
                best_move = move
    return best_move