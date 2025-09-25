"""Chứa lớp ChessGame, quản lý bàn cờ (dùng các đối tượng Piece).
Thêm logic cho nhập thành (castling) và bắt tốt qua đường (en-passant)."""

# game.py
import copy
from pieces import Pawn, Knight, Bishop, Rook, Queen, King
from pieces import UNICODE_PIECES
from utils import in_bounds, opp_color

class ChessGame:
    def __init__(self):
        # board: 8x8 of Piece instances or None
        self.board = [[None]*8 for _ in range(8)]
        self.turn_white = True
        self.move_history = []  # danh sách các bản ghi nước đi (dùng cho undo).
        # castling rights: K (white king-side), Q (white queen-side), k, q
        self.castling_rights = {'K': True, 'Q': True, 'k': True, 'q': True} # True nếu còn quyền nhập thành
        self.en_passant_target = None  # ô (r,c) có thể bị bắt bởi en-passant trong lượt này
        self.setup_start()

    def setup_start(self):
        # setup pieces
        # Black back rank (row 0)
        self.board[0] = [
            Rook(False), Knight(False), Bishop(False), Queen(False),
            King(False), Bishop(False), Knight(False), Rook(False)
        ]
        # Black pawns (row1)
        self.board[1] = [Pawn(False) for _ in range(8)]
        # empty 2..5
        for r in range(2,6):
            self.board[r] = [None]*8
        # White pawns row6
        self.board[6] = [Pawn(True) for _ in range(8)]
        # White back rank row7
        self.board[7] = [
            Rook(True), Knight(True), Bishop(True), Queen(True),
            King(True), Bishop(True), Knight(True), Rook(True)
        ]
        self.turn_white = True
        self.move_history.clear()
        self.castling_rights = {'K': True, 'Q': True, 'k': True, 'q': True}
        self.en_passant_target = None

    # getter / setter đơn giản cho board.
    def piece_at(self, r, c):
        return self.board[r][c]

    def set_piece(self, r, c, piece):
        self.board[r][c] = piece

    # tạo bản sao sâu của bàn cờ (dùng để mô phỏng nước đi và kiểm tra chiếu).
    def copy_board(self):
        # deep copy board with piece copies
        new = [[None]*8 for _ in range(8)]
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p is not None:
                    new[r][c] = p.copy()
        return new

    # tìm vị trí vua.
    def king_pos(self, white):
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p is not None and isinstance(p, King) and p.white == white:
                    return (r,c)
        return None

    # kiểm tra ô (r,c) có bị tấn công bởi bên (by_white) không.
    def is_square_attacked(self, r, c, by_white):
        # scan all enemy pieces and see if any pseudo attack includes (r,c)
        for i in range(8):
            for j in range(8):
                p = self.board[i][j]
                if p is None or p.white != by_white:
                    continue
                # For pawn attacks_only True to get only attack pattern
                if isinstance(p, Pawn):
                    moves = p.pseudo_moves(self.board, i, j, en_passant_target=None, attacks_only=True)
                elif isinstance(p, King):
                    # king attacks (no castling)
                    moves = p.pseudo_moves(self.board, i, j, attacks_only=True)
                else:
                    moves = p.pseudo_moves(self.board, i, j)
                if (r,c) in moves:
                    return True
        return False

    # kiểm tra bên (white) có bị chiếu không.
    def in_check(self, white):
        kp = self.king_pos(white)
        if not kp:
            return False
        return self.is_square_attacked(kp[0], kp[1], not white)

    # trả về danh sách các nước đi hợp lệ cho quân ở (r,c).
    # bao gồm nhập thành và bắt tốt qua đường.
    def legal_moves_for_piece(self, r, c):
        p = self.board[r][c]
        # Nếu không có quân cờ hoặc không phải lượt của bên đó, trả về danh sách rỗng.
        if p is None or p.white != self.turn_white:
            return []
        # get pseudo legal moves (including castling and en-passant treated)
        # Nếu là vua, truyền quyền nhập thành.
        if isinstance(p, King):
            pseudo = p.pseudo_moves(self.board, r, c, castling_rights=self.castling_rights)
        # Nếu là tốt, truyền ô mục tiêu en-passant.
        elif isinstance(p, Pawn):
            pseudo = p.pseudo_moves(self.board, r, c, en_passant_target=self.en_passant_target)
        # Các quân khác không cần thêm tham số.
        else:
            pseudo = p.pseudo_moves(self.board, r, c)
        legal = []
        for (nr,nc) in pseudo:
            # Nếu đây là nước nhập thành (king move 2 cột), kiểm tra điều kiện liên quan đến "chiếu" trên board hiện tại:
            if isinstance(p, King) and abs(nc - c) == 2:
                # 1) Vua không được đang bị chiếu hiện tại
                if self.is_square_attacked(r, c, not p.white):
                    continue
                # 2) Các ô vua sẽ đi qua (bao gồm ô đích) không được bị tấn công — kiểm tra trên vị thế hiện tại
                if nc > c:
                    path_squares = [(r, c+1), (r, c+2)]
                else:
                    path_squares = [(r, c-1), (r, c-2)]
                blocked = False
                for (rr, cc) in path_squares:
                    if self.is_square_attacked(rr, cc, not p.white):
                        blocked = True
                        break
                if blocked:
                    continue
            # simulate move and test king safety
            saved = self.copy_board()
            moved_piece = saved[r][c]
            target = saved[nr][nc]
            # handle en-passant capture in simulation: if pawn moves to en_passant_target, remove captured pawn
            if isinstance(moved_piece, Pawn) and self.en_passant_target == (nr,nc) and target is None and c != nc:
                # captured pawn is behind target
                cap_r = r
                cap_c = nc
                if 0 <= cap_r < 8:
                    saved[cap_r][cap_c] = None

            saved[nr][nc] = moved_piece
            saved[r][c] = None
            # also handle castling rook move in simulation
            if isinstance(moved_piece, King) and abs(nc - c) == 2:
                # king-side or queen-side
                if nc > c:
                    # king-side
                    rook_from = (r,7)
                    rook_to = (r, nc-1)
                    path_squares = [(r, c+1), (r, c+2)]  # f1,g1 hoặc f8,g8
                else:
                    rook_from = (r,0)
                    rook_to = (r, nc+1)
                    path_squares = [(r, c-1), (r, c-2)]  # d1,c1 hoặc d8,c8
                rf,cf = rook_from; rt,ct = rook_to
                rook = saved[rf][cf]
                saved[rt][ct] = rook
                saved[rf][cf] = None

            # create a temporary ChessGame for check detection
            tmp = self.__class__()  # new ChessGame
            tmp.board = saved
            tmp.castling_rights = self.castling_rights.copy()
            tmp.en_passant_target = None
            # find tmp king position for the side that moved
            king_pos = tmp.king_pos(moved_piece.white)
            if king_pos is None:
                continue
            if not tmp.is_square_attacked(king_pos[0], king_pos[1], not moved_piece.white):
                legal.append((nr,nc))
        return legal

    # trả về tất cả nước đi hợp lệ cho bên (white_side).
    def all_moves_for_side(self, white_side):
        moves = []
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p is None or p.white != white_side:
                    continue
                # temporarily set turn for legal_moves_for_piece
                old_turn = self.turn_white
                self.turn_white = white_side
                mvs = self.legal_moves_for_piece(r,c)
                self.turn_white = old_turn
                for d in mvs:
                    moves.append(((r,c), d))
        return moves

    # thực hiện nước đi từ (from_rc) đến (to_rc).
    # trả về True nếu thành công, False nếu không hợp lệ.
    # xử lý nhập thành, bắt tốt qua đường, thăng cấp.
    def make_move(self, from_rc, to_rc, promote_to=None):
        fr,fc = from_rc
        tr,tc = to_rc
        piece = self.board[fr][fc]
        if piece is None:
            return False
        # record info for undo
        move_record = {
            'from': (fr,fc), 'to': (tr,tc),
            'piece': piece, 'captured': self.board[tr][tc],
            'castling': False, 'en_passant': False,
            'prev_castling': self.castling_rights.copy(), 
            'prev_en_passant': self.en_passant_target,
            'piece_has_moved': piece.has_moved
        }

        # en-passant capture
        if isinstance(piece, Pawn):
            if self.en_passant_target == (tr,tc) and self.board[tr][tc] is None and fc != tc:
                # captured pawn behind target
                cap_r = fr
                cap_c = tc
                move_record['captured'] = self.board[cap_r][cap_c]
                move_record['en_passant'] = True
                move_record['en_passant_pos'] = (cap_r, cap_c)  # Lưu lại luôn tọa độ
                self.board[cap_r][cap_c] = None
                
        # castling: move rook as well
        if isinstance(piece, King) and abs(tc - fc) == 2:
            move_record['castling'] = True
            r = fr
            if tc > fc:
                # king-side
                rook_from = (r, 7); rook_to = (r, tc-1)
            else:
                rook_from = (r, 0); rook_to = (r, tc+1)
            rf,cf = rook_from; rt,ct = rook_to
            rook = self.board[rf][cf]
            self.board[rt][ct] = rook
            self.board[rf][cf] = None
            if rook:
                move_record['rook_has_moved'] = rook.has_moved
                rook.has_moved = True

        # move piece
        self.board[tr][tc] = piece
        self.board[fr][fc] = None

        # update moved flag
        piece.has_moved = True

        # update castling rights if king or rook moved/captured
        if isinstance(piece, King):
            if piece.white:
                self.castling_rights['K'] = False
                self.castling_rights['Q'] = False
            else:
                self.castling_rights['k'] = False
                self.castling_rights['q'] = False
        if isinstance(piece, Rook):
            # which rook moved?
            if fr == 7 and fc == 0:
                self.castling_rights['Q'] = False
            if fr == 7 and fc == 7:
                self.castling_rights['K'] = False
            if fr == 0 and fc == 0:
                self.castling_rights['q'] = False
            if fr == 0 and fc == 7:
                self.castling_rights['k'] = False
        # if a rook was captured, update opposing castling rights
        cap = move_record['captured']
        if cap is not None and isinstance(cap, Rook):
            # find where it was captured from to know which right to remove; but we have its location in move_record
            tr0,tc0 = to_rc
            # if capture was en-passant we have different coords; but simpler: iterate castling corners and if that rook is gone disable
            # check corners
            if self.board[0][0] is None:
                self.castling_rights['q'] = False
            if self.board[0][7] is None:
                self.castling_rights['k'] = False
            if self.board[7][0] is None:
                self.castling_rights['Q'] = False
            if self.board[7][7] is None:
                self.castling_rights['K'] = False

        # handle pawn double move -> set en_passant_target, else clear
        self.en_passant_target = None
        if isinstance(piece, Pawn):
            if abs(tr - fr) == 2:
                # square passed over
                passed_r = (fr + tr) // 2
                self.en_passant_target = (passed_r, fc)
        else:
            self.en_passant_target = None

        # handle promotion
        if isinstance(piece, Pawn):
            if (piece.white and tr == 0) or (not piece.white and tr == 7):
                move_record['promotion'] = True   # 👈 thêm flag
                # promote
                if promote_to is None:
                    # default to queen object
                    promoted = Queen(piece.white)
                else:
                    # promote_to expected 'Q','R','B','N' uppercase
                    if promote_to.upper() == 'Q':
                        promoted = Queen(piece.white)
                    elif promote_to.upper() == 'R':
                        promoted = Rook(piece.white)
                    elif promote_to.upper() == 'B':
                        promoted = Bishop(piece.white)
                    elif promote_to.upper() == 'N':
                        promoted = Knight(piece.white)
                    else:
                        promoted = Queen(piece.white)
                self.board[tr][tc] = promoted

        # save history
        self.move_history.append(move_record)
        # switch turn
        self.turn_white = not self.turn_white
        return True

    # hoàn tác nước đi cuối cùng.
    def undo_last(self):
        if not self.move_history:
            return
        last = self.move_history.pop()
        fr,fc = last['from']; tr,tc = last['to']
        piece = last['piece']
        # nếu là promotion thì khôi phục lại quân tốt
        if 'promotion' in last and last['promotion']:
            piece = Pawn(piece.white)
        # move back
        self.board[fr][fc] = piece
        self.board[tr][tc] = last['captured']
        piece.has_moved = last['piece_has_moved']  
        # if castling, move rook back
        if last['castling']:
            r = fr
            if tc > fc:
                # king-side
                rook_from = (r, tc-1); rook_to = (r,7)
            else:
                rook_from = (r, tc+1); rook_to = (r,0)
            rf,cf = rook_from; rt,ct = rook_to
            rook = self.board[rf][cf]
            self.board[rt][ct] = rook
            self.board[rf][cf] = None
            if rook and 'rook_has_moved' in last:
                rook.has_moved = last['rook_has_moved']
        # if en-passant capture occured, need to restore captured pawn
        if last['en_passant']:
            # captured pawn was at (from_row, to_col)
            cap_r, cap_c = last['en_passant_pos']   # 👈 dùng tọa độ đã lưu
            # it was removed during make_move, so restore from recorded piece
            self.board[cap_r][cap_c] = last['captured']
        # restore castling and en_passant
        self.castling_rights = last['prev_castling']
        self.en_passant_target = last['prev_en_passant']
        # restore turn
        self.turn_white = not self.turn_white

    # trả về biểu diễn Unicode của bàn cờ (2D array).
    def board_unicode(self):
        # returns 2D of unicode chars or '' for empty
        out = [['']*8 for _ in range(8)]
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                out[r][c] = p.unicode() if p is not None else ''
        return out