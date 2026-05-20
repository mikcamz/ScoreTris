"""
grid, pieces, queue, randomizer
"""

import random


# ============================================================
# Định nghĩa 7 loại gạch (SRS standard)
# ============================================================
SHAPES = {
    'I': [
        [(0, 0), (0, 1), (0, 2), (0, 3)],
        [(0, 0), (1, 0), (2, 0), (3, 0)],
        [(0, 0), (0, 1), (0, 2), (0, 3)],
        [(0, 0), (1, 0), (2, 0), (3, 0)],
    ],
    'O': [
        [(0, 0), (0, 1), (1, 0), (1, 1)],
        [(0, 0), (0, 1), (1, 0), (1, 1)],
        [(0, 0), (0, 1), (1, 0), (1, 1)],
        [(0, 0), (0, 1), (1, 0), (1, 1)],
    ],
    'T': [
        [(0, 1), (1, 0), (1, 1), (1, 2)],
        [(0, 0), (1, 0), (1, 1), (2, 0)],
        [(0, 0), (0, 1), (0, 2), (1, 1)],
        [(0, 1), (1, 0), (1, 1), (2, 1)],
    ],
    'S': [
        [(0, 1), (0, 2), (1, 0), (1, 1)],
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(0, 1), (0, 2), (1, 0), (1, 1)],
        [(0, 0), (1, 0), (1, 1), (2, 1)],
    ],
    'Z': [
        [(0, 0), (0, 1), (1, 1), (1, 2)],
        [(0, 1), (1, 0), (1, 1), (2, 0)],
        [(0, 0), (0, 1), (1, 1), (1, 2)],
        [(0, 1), (1, 0), (1, 1), (2, 0)],
    ],
    'L': [
        [(0, 2), (1, 0), (1, 1), (1, 2)],
        [(0, 0), (1, 0), (2, 0), (2, 1)],
        [(0, 0), (0, 1), (0, 2), (1, 0)],
        [(0, 0), (0, 1), (1, 1), (2, 1)],
    ],
    'J': [
        [(0, 0), (1, 0), (1, 1), (1, 2)],
        [(0, 0), (0, 1), (1, 0), (2, 0)],
        [(0, 0), (0, 1), (0, 2), (1, 2)],
        [(0, 1), (1, 1), (2, 0), (2, 1)],
    ],
}

PIECE_NAMES = list(SHAPES.keys()) 

COLORS = {
    'I': (0, 240, 240),
    'O': (240, 240, 0),
    'T': (160, 0, 240),
    'S': (0, 240, 0),
    'Z': (240, 0, 0),
    'L': (240, 160, 0),
    'J': (0, 0, 240),
}


# ============================================================
# Grid – Bảng luới 10 cột x 20 hàng
# ============================================================
class Grid:
    def __init__(self, cols=10, rows=20):
        """Tao board kich thuoc cols x rows, ban dau toan o trong."""
        self.cols = cols
        self.rows = rows
        # Mảng 2 chiều: self.cells[row][col]
        # None = ô trống, 'I'/'O'/... = ô có gạch
        self.cells = [[None] * cols for _ in range(rows)]

    def inside(self, r, c):
        """
        Kiểm tra (r, c) có nằm trong board không?
        Input: r (row), c (col) - chỉ số
        Output: True nếu 0 <= r < rows và 0 <= c < cols
        """
        return 0 <= r < self.rows and 0 <= c < self.cols

    def empty(self, r, c):
        """
        Kiểm tra ô (r,c) có trống và nằm trong board không?
        Input: r, c
        Output: True nếu inside AND cells[r][c] is None
        """
        return self.inside(r, c) and self.cells[r][c] is None

    def place(self, r, c, name):
        """
        Đặt gạch tại (r,c).
        """
        self.cells[r][c] = name

    def clear_lines(self):
        """
        Xóa các hàng đầy, dồn mảng.
        filter hàng chưa đầy, thêm hàng trống ở đầu
        Output: số hàng đã xóa
        """
        new_cells = []
        cleared = 0

        for r in range(self.rows):
            row = self.cells[r]
            has_empty = False
            for c in range(self.cols):
                if row[c] is None:
                    has_empty = True
                    break

            if has_empty:
                new_cells.append(row)
            else:
                cleared += 1

        for _ in range(cleared):
            new_row = []
            for _ in range(self.cols):
                new_row.append(None)
            new_cells.insert(0, new_row)

        self.cells = new_cells
        return cleared

    def reset(self):
        """Reset board về trống."""
        self.cells = [[None] * self.cols for _ in range(self.rows)]

    # === Hàm hỗ trợ AI ===

    def clone(self):
        """
        Tạo bản sao của board.
        Output: Grid mới với cells là deep copy
        """
        g = Grid(self.cols, self.rows)
        g.cells = [row[:] for row in self.cells]
        return g

    def height_profile(self):
        """
        Tính chiều cao của mỗi cột.
        Output: list[10] - heights[c] = chiều cao cột c từ dưới lên (0 nếu cột trống)
        """
        heights = [0] * self.cols
        for c in range(self.cols):
            height = 0
            for r in range(self.rows):
                if self.cells[r][c] is not None:
                    height = self.rows - r
                    break
            heights[c] = height
        return heights

    def holes(self):
        """
        Đếm số "lỗ hổng" (ô trống có gạch ở trên).
        Cách: duyệt từ trên xuống mỗi cột, khi thấy gạch thì mark block_seen=True,
              sau đó đếm ô trống.
        Output: số lỗ hổng
        """
        holes = 0
        for c in range(self.cols):
            block_seen = False
            for r in range(self.rows):
                if self.cells[r][c] is not None:
                    block_seen = True
                elif block_seen:
                    holes += 1
        return holes

# ============================================================
# Piece – Vien gạch đang rơi
# ============================================================
class Piece:
    def __init__(self, name, col_offset=3, row_offset=0):
        """Khoi tao 1 piece dang roi voi vi tri spawn mac dinh."""
        self.name = name
        self.rotation = 0          # 0-3
        self.row = row_offset
        self.col = col_offset

    def cells(self):
        """
        Tính tọa độ tuyệt đối của 4 ô gạch.
        Input: self.name, self.rotation, self.row, self.col
        Output: list[(row, col)] tọa độ tuyệt đối 4 ô
        """
        shape = SHAPES[self.name][self.rotation]
        out = []
        for dr, dc in shape:
            out.append((self.row + dr, self.col + dc))
        return out

    def copy(self):
        """
        Tạo bản sao piece.
        Output: Piece mới với cùng name, rotation, row, col
        """
        p = Piece(self.name, self.col, self.row)
        p.rotation = self.rotation
        return p

    def drop_to_bottom(self, grid):
        """
        Thả piece xuống đáy grid, trả về bản sao piece đã ở vị trí đáy.
        Dùng chung cho ghost(), hard_drop, simulate_placement.
        """
        g = self.copy()
        while True:
            g.row += 1
            valid = True
            for r, c in g.cells():
                if not grid.inside(r, c) or not grid.empty(r, c):
                    valid = False
                    break
            if not valid:
                g.row -= 1
                break
        return g


# ============================================================
# ArrayQueue – Hàng đợi tử cài (O(1) amortized pop)
# ============================================================
class ArrayQueue:
    """Hàng đợi chuẩn dùng mảng động với head pointer."""

    def __init__(self):
        """Khoi tao queue bang list + head pointer."""
        self._items = []
        self._front = 0

    def __len__(self):
        """Tra ve so phan tu hien tai trong queue."""
        return len(self._items) - self._front

    def push(self, value):
        """
        Thêm phần tử vào cuối hàng đợi.
        """
        self._items.append(value)

    def pop(self):
        """
        Lấy phần tử từ đầu hàng đợi.
        Output: phần tử đầu tiên
        Exception: IndexError nếu hàng đợi trống
        """
        if len(self) == 0:
            raise IndexError("pop from empty queue")
        value = self._items[self._front]
        self._front += 1
        if self._front > 64 and self._front * 2 > len(self._items):
            self._items = self._items[self._front:]
            self._front = 0
        return value

    def peek_many(self, n):
        """Xem n phần tử tiếp theo mà không lấy ra."""
        out = []
        i = self._front
        end = self._front + n
        while i < end and i < len(self._items):
            out.append(self._items[i])
            i += 1
        return out

    def clear(self):
        """Xóa hàng đợi."""
        self._items.clear()
        self._front = 0


# ============================================================
# SevenBag – Bộ phát ngẫu nhiên chuẩn (7-Bag)
# ============================================================
class SevenBag:
    """
    Standard 7-bag randomizer:
    - Mỗi "bag" chứa đủ 7 loại gạch, xáo trộn
    - Khi hết bag, tạo bag mới
    - Luôn giữ đủ phần tử để preview
    """

    def __init__(self):
        """Khoi tao randomizer va nap san 2 bag dau tien."""
        self.queue = ArrayQueue()
        self._fill()
        self._fill()

    def _fill(self):
        """
        Tạo 1 bag mới và thêm vào queue.
        Cách:
        - bag = list(PIECE_NAMES)
        - random.shuffle(bag)
        - push từng piece vào queue
        """
        bag = list(PIECE_NAMES)
        random.shuffle(bag)
        for name in bag:
            self.queue.push(name)

    def next(self):
        """
        Lấy gạch tiếp theo từ queue.
        - Nếu queue có ít hơn 7 phần tử, tạo bag mới
        - Return phần tử từ pop()
        """
        if len(self.queue) < 7:
            self._fill()
        return self.queue.pop()

    def peek(self, n=5):
        """Xem trước n gạch tiếp theo."""
        while len(self.queue) < n:
            self._fill()
        return self.queue.peek_many(n)

    def reset(self):
        """Reset randomizer."""
        self.queue.clear()
        self._fill()
        self._fill()

