"""Tạo lớp Piece cha, các lớp con Pawn, Rook, Knight, Bishop, Queen, King.
Mỗi lớp có phương thức get_moves(board, pos) để trả về nước đi (pseudo-legal)."""

# pieces.py
from utils import in_bounds

"""Bảng ký hiệu Unicode cho các quân cờ.
Ánh xạ ký hiệu chữ cái (K,Q,R,B,N,P) sang ký hiệu Unicode cờ vua.
Chữ hoa cho quân trắng, chữ thường cho quân đen."""
UNICODE_PIECES = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
}

# --------------------------
# Lớp cha Piece
class Piece:
    def __init__(self, white: bool):
        self.white = white # True nếu quân trắng, False nếu quân đen (kiểu dữ liệu bool)
        self.has_moved = False  # kiểm tra đã di chuyển (tốt, vua, xe)

    def is_white(self):
        return self.white

    def symbol(self):
        raise NotImplementedError() # trả về ký hiệu của quân (lớp con tự định nghĩa)

    def unicode(self):
        return UNICODE_PIECES.get(self.symbol()) # trả về ký hiệu Unicode

    def copy(self):
        cls = self.__class__
        p = cls(self.white)
        p.has_moved = self.has_moved
        return p

# --------------------------
# Lớp Pawn
class Pawn(Piece):
    def symbol(self):
        return 'P' if self.white else 'p'

    def pseudo_moves(self, board, r, c, en_passant_target=None, attacks_only=False):
        moves = []
        dir = -1 if self.white else 1   # trắng đi lên (row giảm), đen đi xuống (row tăng)
        start_row = 6 if self.white else 1    # trắng bắt đầu rank 2 (row=6), đen rank 7 (row=1)

        # Di chuyển tiến 1 ô
        fr = r + dir
        if in_bounds(fr, c) and not attacks_only:
            if board[fr][c] is None:
                moves.append((fr, c))
                # Di chuyển 2 ô từ hàng xuất phát
                fr2 = r + 2*dir
                if r == start_row and in_bounds(fr2, c) and board[fr2][c] is None:
                    moves.append((fr2, c))

        # Bắt chéo
        for dc in (-1, 1):
            cr, cc = r + dir, c + dc
            if in_bounds(cr, cc):
                t = board[cr][cc]
                if t is not None and t.white != self.white:
                    moves.append((cr, cc))
                # en-passant
                elif en_passant_target and (cr, cc) == en_passant_target:
                    moves.append((cr, cc))
                # attacks_only: dùng để tính vùng tấn công
                elif attacks_only:
                    moves.append((cr, cc))
        return moves

# --------------------------
# Lớp Knight
class Knight(Piece):
    def symbol(self):
        return 'N' if self.white else 'n'

    def pseudo_moves(self, board, r, c, **kwargs):
        moves = []
        for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            nr, nc = r + dr, c + dc
            if in_bounds(nr, nc):
                t = board[nr][nc]
                if t is None or t.white != self.white:
                    moves.append((nr, nc))
        return moves

# --------------------------
# Lớp Bishop
class Bishop(Piece):
    def symbol(self):
        return 'B' if self.white else 'b'

    def pseudo_moves(self, board, r, c, **kwargs):
        moves = []
        for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            nr, nc = r + dr, c + dc
            while in_bounds(nr, nc):
                t = board[nr][nc]
                if t is None:
                    moves.append((nr, nc))
                elif t.white != self.white:
                    moves.append((nr, nc))
                    break
                else:
                    break
                nr += dr
                nc += dc
        return moves

# --------------------------
# Lớp Rook
class Rook(Piece):
    def symbol(self):
        return 'R' if self.white else 'r'

    def pseudo_moves(self, board, r, c, **kwargs):
        moves = []
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r + dr, c + dc
            while in_bounds(nr, nc):
                t = board[nr][nc]
                if t is None:
                    moves.append((nr, nc))
                elif t.white != self.white:
                    moves.append((nr, nc))
                    break
                else:
                    break
                nr += dr
                nc += dc
        return moves

# --------------------------
# Lớp Queen
class Queen(Piece):
    def symbol(self):
        return 'Q' if self.white else 'q'

    def pseudo_moves(self, board, r, c, **kwargs):
        moves = []
        for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r + dr, c + dc
            while in_bounds(nr, nc):
                t = board[nr][nc]
                if t is None:
                    moves.append((nr, nc))
                elif t.white != self.white:
                    moves.append((nr, nc))
                    break
                else:
                    break
                nr += dr
                nc += dc
        return moves

# --------------------------
# Lớp King
class King(Piece):
    def symbol(self):
        return 'K' if self.white else 'k'

    def pseudo_moves(self, board, r, c, castling_rights=None, attacks_only=False, **kwargs):
        moves = []
        # 1 ô xung quanh
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if in_bounds(nr, nc):
                    t = board[nr][nc]
                    if t is None or t.white != self.white:
                        moves.append((nr, nc))

        # Castling: chỉ thêm "đề xuất" nếu ô giữa trống và có rook tương ứng chưa di chuyển
        # Lưu ý: kiểm tra "chiếu" THỰC SỰ (vua đang bị chiếu/đi qua ô bị chiếu/đến ô bị chiếu)
        # sẽ được thực hiện ở mức ChessGame (legal_moves_for_piece).
        if not attacks_only and castling_rights is not None:
            if self.white:
                row = 7  # trắng ở hàng 7 trong setup của bạn
                # King-side (K): rook ở (7,7)
                if castling_rights.get('K', False) and board[row][5] is None and board[row][6] is None:
                    rook = board[row][7]
                    if rook is not None and isinstance(rook, Rook) and rook.white == self.white and not rook.has_moved:
                        moves.append((row,6))
                # Queen-side (Q): rook ở (7,0)
                if castling_rights.get('Q', False) and board[row][1] is None and board[row][2] is None and board[row][3] is None:
                    rook = board[row][0]
                    if rook is not None and isinstance(rook, Rook) and rook.white == self.white and not rook.has_moved:
                        moves.append((row,2))
            else:
                row = 0  # đen ở hàng 0
                if castling_rights.get('k', False) and board[row][5] is None and board[row][6] is None:
                    rook = board[row][7]
                    if rook is not None and isinstance(rook, Rook) and rook.white == self.white and not rook.has_moved:
                        moves.append((row,6))
                if castling_rights.get('q', False) and board[row][1] is None and board[row][2] is None and board[row][3] is None:
                    rook = board[row][0]
                    if rook is not None and isinstance(rook, Rook) and rook.white == self.white and not rook.has_moved:
                        moves.append((row,2))
        return moves