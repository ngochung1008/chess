"""Chứa các hàm tiện ích như in_bounds(r,c), is_white(piece)."""

# utils.py
# Hàm kiểm tra xem tọa độ (r,c) của quân cờ có nằm trong bàn cờ hay không
def in_bounds(r, c):
    return 0 <= r <= 7 and 0 <= c <= 7

def opp_color(is_white):
    return not is_white
