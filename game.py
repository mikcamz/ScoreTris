"""Logic chinh cho Tetris.

File nay gom:
- Di chuyen, xoay SRS, lock piece, clear line, tinh diem
- Heuristic de cham board va review nuoc di
- Tim nuoc theo DFS hoac Beam Search
- Goi y nuoc di (AI ghost)
- Luu leaderboard va mau pattern vao JSON
"""

from __future__ import annotations

import json
import os
import time

from structs import Grid, Piece, SevenBag, SHAPES

# ============================================================
# SRS Wall Kick data
# (rotation_from, rotation_to): list offsets (dc, dr)
# ============================================================
WALL_KICKS = {
    (0, 1): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (1, 0): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (1, 2): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (2, 1): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (2, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (3, 2): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (3, 0): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (0, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
}

WALL_KICKS_I = {
    (0, 1): [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
    (1, 0): [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
    (1, 2): [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)],
    (2, 1): [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
    (2, 3): [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
    (3, 2): [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
    (3, 0): [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
    (0, 3): [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)],
}

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
LEADERBOARD_FILE = os.path.join(THIS_DIR, "leaderboard.json")
PATTERNS_FILE = os.path.join(THIS_DIR, "patterns.json")


def _load_json(path, default_value):
    """Doc file JSON an toan.

    Neu file khong ton tai hoac hong JSON thi tra ve default_value.
    """
    if not os.path.exists(path):
        return default_value
    try:
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except (json.JSONDecodeError, OSError):
        return default_value


def _save_json(path, data):
    """Luu data ra file JSON voi indent de de nhin."""
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)


def _to_base36(n):
    """Chuyen so nguyen sang chuoi base36 gon hon de encode."""
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    n = int(n)
    if n == 0:
        return "0"
    sign = "" if n >= 0 else "-"
    n = abs(n)
    out = []
    while n:
        n, rem = divmod(n, 36)
        out.append(digits[rem])
    return sign + "".join(reversed(out))


class Game:
    def __init__(self):
        """Khoi tao 1 van game moi, nap du lieu leaderboard/pattern."""
        self.grid = Grid()
        self.bag = SevenBag()
        self.piece = None
        self.hold_name = None
        self.hold_used = False

        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self._score_saved = False

        # Heuristic tuning: score = -w1*height - w2*holes - w3*bumpiness + w4*line_clear
        self.weight_names = ["height", "holes", "bumpiness", "line_clear"]
        self.weights = [0.45, 0.95, 0.30, 1.15]

        # Review thresholds
        self.OPTIMAL_THRESHOLD = 0.5
        self.GOOD_THRESHOLD = 3.0
        self.RISKY_THRESHOLD = 8.0

        # Search config
        self.search_mode = "beam"  # beam | dfs
        self.lookahead_depth = 2
        self.beam_width = 24
        self.enable_ai_hint = True

        # Analysis state
        self.best_move = None
        self.best_eval_current = None
        self.suggestion_piece = None
        self.last_move_review = "-"
        self.last_search_nodes = 0

        # Encoded run trace used in leaderboard pattern code.
        self.move_trace = []

        # Persistence
        self.leaderboard = _load_json(LEADERBOARD_FILE, [])
        self.patterns = _load_json(PATTERNS_FILE, [])

        self._spawn()

    # ---------- spawn ----------
    def _spawn(self):
        """Lay piece moi tu bag va spawn len dau board."""
        name = self.bag.next()
        self.piece = Piece(name, col_offset=3, row_offset=0)
        self.hold_used = False
        if not self._is_valid(self.piece):
            self.game_over = True
            self._save_score_once()
            return
        self.refresh_ai_suggestion()

    def _is_valid_placement(self, grid, piece):
        """Check piece co hop le tren grid da cho hay khong."""
        for r, c in piece.cells():
            if not grid.inside(r, c):
                return False
            if not grid.empty(r, c):
                return False
        return True

    def _is_valid(self, piece):
        """Shortcut check hop le tren board hien tai."""
        return self._is_valid_placement(self.grid, piece)

    # ---------- movement ----------
    def move(self, dr, dc):
        """Di chuyen piece theo do lech hang/cot neu hop le."""
        test = self.piece.copy()
        test.row += dr
        test.col += dc
        if self._is_valid(test):
            self.piece.row = test.row
            self.piece.col = test.col
            self._update_live_ghost()
            return True
        return False

    def _try_180_rotation(self):
        """Thu xoay 180° (chi thu offset (0,0) vi SRS khong co bang kick rieng)."""
        test = self.piece.copy()
        test.rotation = (test.rotation + 2) % 4
        if self._is_valid(test):
            self.piece.rotation = test.rotation
            self._update_live_ghost()
            return True
        return False

    def rotate(self, direction=1):
        """Xoay piece theo SRS wall kick.

        direction = 1: xoay phai, -1: xoay trai, 2: xoay 180.
        """
        if direction == 2:
            return self._try_180_rotation()

        test = self.piece.copy()
        old_rot = test.rotation
        test.rotation = (test.rotation + direction) % 4
        kicks = WALL_KICKS_I if test.name == "I" else WALL_KICKS
        key = (old_rot, test.rotation)
        for dc, dr in kicks.get(key, [(0, 0)]):
            test2 = self.piece.copy()
            test2.rotation = test.rotation
            test2.col += dc
            test2.row -= dr
            if self._is_valid(test2):
                self.piece.rotation = test2.rotation
                self.piece.col = test2.col
                self.piece.row = test2.row
                self._update_live_ghost()
                return True
        return False

    # ---------- drops ----------
    def hard_drop(self):
        """Tha nhanh xuong day, cong diem theo tung o roi, roi lock."""
        while self.move(1, 0):
            self.score += 2
        self._lock()

    def soft_drop(self):
        """Tha mem 1 o, neu duoc thi cong diem nho."""
        if self.move(1, 0):
            self.score += 1
            return True
        return False

    def ghost(self):
        """Tra ve vi tri bong (ghost) cua piece neu tha thang."""
        return self.piece.drop_to_bottom(self.grid)

    def _update_live_ghost(self):
        """Khong lam gi – AI chi chay khi spawn piece moi."""
        pass

    # ---------- lock / clear / scoring ----------
    def _lock(self):
        """Khoa piece vao board, clear line, tinh diem, spawn piece moi."""
        if self.piece is None:
            return

        pre_grid = self.grid.clone()
        placed_piece = self.piece.copy()

        for r, c in self.piece.cells():
            self.grid.place(r, c, self.piece.name)

        cleared = self.grid.clear_lines()
        self._add_score(cleared)
        self.lines += cleared
        self.level = self.lines // 10 + 1
        self._record_move_token(placed_piece, cleared)

        actual_eval = self.evaluate_grid(self.grid, cleared)
        self._review_last_move(actual_eval)
        self._maybe_store_pattern(pre_grid, cleared)

        self._spawn()

    def _add_score(self, cleared):
        """Cong diem dua vao so dong clear va level hien tai."""
        points = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}
        self.score += points.get(cleared, 0) * self.level

    def _review_last_move(self, actual_eval):
        """Danh gia nuoc vua danh so voi best eval tim duoc truoc do."""
        if self.best_eval_current is None:
            self.last_move_review = "No baseline"
            return
        gap = self.best_eval_current - actual_eval
        if gap <= self.OPTIMAL_THRESHOLD:
            self.last_move_review = "Optimal"
        elif gap <= self.GOOD_THRESHOLD:
            self.last_move_review = "Good"
        elif gap <= self.RISKY_THRESHOLD:
            self.last_move_review = "Risky"
        else:
            self.last_move_review = "Blunder"

    def _record_move_token(self, piece, cleared):
        """Ghi token ngan gon cho nuoc vua danh de tao pattern code."""
        # token format: <piece><rot><col36><clr>, e.g. T1B0
        # col is shifted by +8 to avoid sign in compact encoding.
        col_code = _to_base36(piece.col + 8)
        token = f"{piece.name}{piece.rotation}{col_code}{cleared}"
        self.move_trace.append(token)

    def _encoded_run_pattern(self):
        """Tra ve trace dang chuoi, moi token cach nhau boi dau cham."""
        if not self.move_trace:
            return "-"
        return ".".join(self.move_trace)

    def _pattern_code(self):
        """Tao pattern code gon de show tren leaderboard."""
        if not self.move_trace:
            return "-"
        core = ""
        for token in self.move_trace:
            core += token

        value = 0
        i = 0
        for ch in core:
            value += (i + 1) * ord(ch)
            i += 1
        return f"P{_to_base36(value)}-{len(self.move_trace)}"

    # ---------- hold ----------
    def hold(self):
        """Doi piece vao hold (moi turn chi duoc 1 lan)."""
        if self.hold_used:
            return
        self.hold_used = True
        current_name = self.piece.name
        if self.hold_name is None:
            self.hold_name = current_name
            self._spawn()
        else:
            self.hold_name, name = current_name, self.hold_name
            self.piece = Piece(name, col_offset=3, row_offset=0)
        if not self._is_valid(self.piece):
            self.game_over = True
            self._save_score_once()
            return
        self.refresh_ai_suggestion()

    # ---------- gravity ----------
    def tick(self):
        """Nhip roi theo gravity; khong roi duoc thi lock."""
        if not self.move(1, 0):
            self._lock()

    def drop_interval(self):
        """Tinh khoang thoi gian roi tu dong theo level (ms).
        Giong Classic Tetris: toc do tang nhanh qua tung level.
        """
        # NES Tetris frames per drop (60 fps) approximate curve
        frames_per_drop = [
            48, 43, 38, 33, 28, 23, 18, 13, 8, 6,
            5, 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2,
            2, 2, 2, 2, 2, 2, 2, 1
        ]
        lvl_idx = max(0, min(self.level - 1, len(frames_per_drop) - 1))
        frames = frames_per_drop[lvl_idx]
        return (frames / 60.0) * 1000.0

    def preview(self, n=5):
        """Xem truoc n piece tiep theo trong queue."""
        return self.bag.peek(n)

    # ---------- heuristic ----------
    def evaluate_grid(self, grid, cleared_hint=0):
        """Cham diem board bang weighted sum.

        Cong thuc: -height -holes -bumpiness +line_clear_reward
        (he so tuy chinh boi self.weights).
        """
        heights = grid.height_profile()
        h_sum = sum(heights)
        holes = grid.holes()
        bump = 0
        i = 0
        while i < len(heights) - 1:
            bump += abs(heights[i] - heights[i + 1])
            i += 1
        line_bonus = max(cleared_hint, 0)

        w1, w2, w3, w4 = self.weights
        return -w1 * h_sum - w2 * holes - w3 * bump + w4 * line_bonus

    # ---------- placement generation ----------
    def _rotation_candidates(self, name):
        """Lay tap rotation can thu theo tung loai piece."""
        if name == "O":
            return [0]
        if name in ("I", "S", "Z"):
            return [0, 1]
        return [0, 1, 2, 3]

    def _simulate_placement(self, grid, piece_name, rotation, col):
        """Mo phong dat 1 piece vao cot col voi rotation cho truoc.

        Tra ve thong tin move (grid moi + score) neu hop le,
        nguoc lai tra ve None.
        """
        p = Piece(piece_name, col_offset=col, row_offset=0)
        p.rotation = rotation

        if not self._is_valid_placement(grid, p):
            return None

        p = p.drop_to_bottom(grid)

        g2 = grid.clone()
        for r, c in p.cells():
            g2.place(r, c, piece_name)
        cleared = g2.clear_lines()
        score = self.evaluate_grid(g2, cleared)
        return {
            "grid": g2,
            "piece": piece_name,
            "rotation": rotation,
            "col": p.col,
            "row": p.row,
            "cleared": cleared,
            "score": score,
        }

    def _enumerate_moves(self, grid, piece_name):
        """Sinh tat ca nuoc dat hop le cho 1 piece tren grid.

        Chi thu cac cot ma piece thuc su co the nam trong board
        (tinh theo bounding box cua rotation).
        """
        all_moves = []
        for rot in self._rotation_candidates(piece_name):
            shape = SHAPES[piece_name][rot]
            min_dc = min(dc for _, dc in shape)
            max_dc = max(dc for _, dc in shape)
            col_lo = -min_dc
            col_hi = grid.cols - 1 - max_dc
            for col in range(col_lo, col_hi + 1):
                placement = self._simulate_placement(grid, piece_name, rot, col)
                if placement is not None:
                    all_moves.append(placement)
        return all_moves

    # ---------- DFS / Beam ----------
    def _search_dfs(self, pieces):
        """Tim duong di tot nhat bang DFS look-ahead day du."""
        best_score = float("-inf")
        best_path = []
        self.last_search_nodes = 0

        def rec(index, grid, path):
            nonlocal best_score, best_path
            self.last_search_nodes += 1
            if index >= len(pieces):
                score = self.evaluate_grid(grid)
                if score > best_score:
                    best_score = score
                    best_path = path[:]
                return

            for move in self._enumerate_moves(grid, pieces[index]):
                rec(index + 1, move["grid"], path + [move])

        rec(0, self.grid.clone(), [])
        return {"score": best_score, "path": best_path}

    def _search_beam(self, pieces, beam_width):
        """Tim duong di bang Beam Search (giu top N moi tang)."""
        self.last_search_nodes = 0
        states = [{"grid": self.grid.clone(), "path": [], "score": self.evaluate_grid(self.grid)}]

        for piece_name in pieces:
            next_states = []

            for state in states:
                moves = self._enumerate_moves(state["grid"], piece_name)
                for move in moves:
                    self.last_search_nodes += 1
                    score = self.evaluate_grid(move["grid"], move["cleared"])
                    cand = {
                        "grid": move["grid"],
                        "path": state["path"] + [move],
                        "score": score,
                    }
                    next_states.append(cand)

            if not next_states:
                break

            next_states.sort(key=lambda item: item["score"], reverse=True)

            states = []
            i = 0
            while i < len(next_states) and i < beam_width:
                states.append(next_states[i])
                i += 1

        if not states:
            return {"score": float("-inf"), "path": []}

        best_state = states[0]
        for st in states:
            if st["score"] > best_state["score"]:
                best_state = st
        return {"score": best_state["score"], "path": best_state["path"]}

    def refresh_ai_suggestion(self):
        """Chay search va cap nhat nuoc goi y hien tai."""
        if self.game_over or self.piece is None:
            self.best_move = None
            self.suggestion_piece = None
            self.best_eval_current = None
            return

        peek_names = [self.piece.name] + self.preview(max(0, self.lookahead_depth - 1))

        if self.search_mode == "dfs":
            result = self._search_dfs(peek_names)
        else:
            result = self._search_beam(peek_names, self.beam_width)

        self.best_eval_current = result["score"]
        self.best_move = result["path"][0] if result["path"] else None

        if self.enable_ai_hint and self.best_move is not None:
            p = Piece(self.piece.name, col_offset=self.best_move["col"], row_offset=self.best_move["row"])
            p.rotation = self.best_move["rotation"]
            self.suggestion_piece = p
        else:
            self.suggestion_piece = None

    def toggle_search_mode(self):
        """Doi qua lai giua DFS va Beam mode."""
        self.search_mode = "dfs" if self.search_mode == "beam" else "beam"
        self.refresh_ai_suggestion()

    def adjust_beam_width(self, delta):
        """Tinh chinh do rong beam trong khoang [4, 128]."""
        self.beam_width = max(4, min(128, self.beam_width + delta))
        if self.search_mode == "beam":
            self.refresh_ai_suggestion()

    def adjust_lookahead_depth(self, delta):
        """Tinh chinh do sau look-ahead trong khoang [1, 4]."""
        self.lookahead_depth = max(1, min(4, self.lookahead_depth + delta))
        self.refresh_ai_suggestion()

    def toggle_ai_hint(self):
        """Bat/tat phan bong goi y tu AI."""
        self.enable_ai_hint = not self.enable_ai_hint
        self.refresh_ai_suggestion()

    # ---------- persistence ----------
    def _save_score_once(self):
        """Luu ket qua tran choi 1 lan khi game over/restart."""
        if self._score_saved or self.score <= 0:
            return
        self._score_saved = True
        encoded_route = self._encoded_run_pattern()
        self.leaderboard.append(
            {
                "score": self.score,
                "lines": self.lines,
                "level": self.level,
                "ts": int(time.time()),
                "pattern_code": self._pattern_code(),
                "pattern_route": encoded_route,
            }
        )
        self.leaderboard.sort(key=lambda x: (x.get("score", 0), x.get("lines", 0)), reverse=True)
        self.leaderboard = self.leaderboard[:20]
        _save_json(LEADERBOARD_FILE, self.leaderboard)

    def _maybe_store_pattern(self, pre_grid, cleared):
        """Luu 1 mau board vao patterns trong mot vai truong hop noi bat.

        Hien tai uu tien luu khi clear >= 3 hoac review qua tot/qua te.
        """
        if cleared < 3 and self.last_move_review not in ("Optimal", "Blunder"):
            return

        snapshot_rows = []
        for row in self.grid.cells[-8:]:
            row_txt = ""
            for cell in row:
                if cell is None:
                    row_txt += "."
                else:
                    row_txt += "#"
            snapshot_rows.append(row_txt)

        w_out = []
        for w in self.weights:
            w_out.append(round(w, 3))

        self.patterns.append(
            {
                "piece": self.piece.name,
                "cleared": cleared,
                "review": self.last_move_review,
                "search_mode": self.search_mode,
                "weights": w_out,
                "score": self.score,
                "snapshot": snapshot_rows,
                "ts": int(time.time()),
            }
        )

        if len(self.patterns) > 80:
            self.patterns = self.patterns[len(self.patterns) - 80:]
        _save_json(PATTERNS_FILE, self.patterns)

    # ---------- restart ----------
    def restart(self):
        """Reset game state de choi tran moi (giu leaderboard/pattern)."""
        self._save_score_once()
        self.grid.reset()
        self.bag.reset()
        self.piece = None
        self.hold_name = None
        self.hold_used = False
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self._score_saved = False
        self.best_move = None
        self.best_eval_current = None
        self.suggestion_piece = None
        self.last_move_review = "-"
        self.last_search_nodes = 0
        self.move_trace = []
        self._spawn()
