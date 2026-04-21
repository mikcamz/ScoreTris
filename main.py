"""
Tetris - main entry point.
Rendering bang pygame, input, game loop.
Chay: python main.py
"""

import datetime
import sys
import pygame
from game import Game
from structs import SHAPES, COLORS, PIECE_NAMES

# ============================================================
# Constants
# ============================================================
CELL = 30                       # kich thuoc 1 o (px)
COLS, ROWS = 10, 20
BOARD_W = COLS * CELL           # 300
BOARD_H = ROWS * CELL           # 600
SIDE_W = 280                    # panel ben phai (preview, hold, score, AI)
WIN_W = BOARD_W + SIDE_W + 20
WIN_H = BOARD_H + 20

BG        = (20, 20, 20)
GRID_LINE = (40, 40, 40)
GHOST_ALPHA = 80
WHITE     = (220, 220, 220)
DARK_GRAY = (60, 60, 60)
SOFT_BLUE = (100, 180, 255)
SOFT_GREEN = (130, 220, 130)

# Vi tri goc tren trai cua bang
OX, OY = 10, 10


def draw_cell(surf, r, c, color, alpha=255):
    """Ve 1 o gach"""
    x = OX + c * CELL
    y = OY + r * CELL
    if alpha < 255:
        s = pygame.Surface((CELL - 1, CELL - 1), pygame.SRCALPHA)
        s.fill((*color, alpha))
        surf.blit(s, (x, y))
    else:
        pygame.draw.rect(surf, color, (x, y, CELL - 1, CELL - 1))
        # Vien sang nhe
        pygame.draw.rect(surf, tuple(min(c + 40, 255) for c in color),
                         (x, y, CELL - 1, CELL - 1), 2)


def draw_grid(surf, grid):
    """Ve luoi va cac o da dat"""
    # Ve luoi
    for r in range(ROWS + 1):
        pygame.draw.line(surf, GRID_LINE, (OX, OY + r * CELL),
                         (OX + BOARD_W, OY + r * CELL))
    for c in range(COLS + 1):
        pygame.draw.line(surf, GRID_LINE, (OX + c * CELL, OY),
                         (OX + c * CELL, OY + BOARD_H))
    # Ve cac o da dat
    for r in range(grid.rows):
        for c in range(grid.cols):
            name = grid.cells[r][c]
            if name:
                draw_cell(surf, r, c, COLORS[name])


def draw_piece(surf, piece, alpha=255):
    """Ve 1 vien gach"""
    color = COLORS[piece.name]
    for r, c in piece.cells():
        if r >= 0:
            draw_cell(surf, r, c, color, alpha)


def draw_mini_piece(surf, name, x, y, cell_size=18):
    """Ve gach nho cho preview / hold"""
    if name is None:
        return
    block = SHAPES[name][0]
    clr = COLORS[name]
    for dr, dc in block:
        x1 = x + dc * cell_size
        y1 = y + dr * cell_size
        pygame.draw.rect(surf, clr, (x1, y1, cell_size - 1, cell_size - 1))
        pygame.draw.rect(surf, tuple(min(c + 40, 255) for c in clr),
                         (x1, y1, cell_size - 1, cell_size - 1), 1)


def draw_sidebar(surf, game, font):
    """Ve phan ben phai: hold, preview, score, level, lines"""
    side_x = OX + BOARD_W + 15

    # --- HOLD ---
    surf.blit(font.render("HOLD", True, WHITE), (side_x, OY))
    pygame.draw.rect(surf, DARK_GRAY, (side_x, OY + 22, 80, 60), 1)
    draw_mini_piece(surf, game.hold_name, side_x + 6, OY + 28)

    # --- NEXT ---
    surf.blit(font.render("NEXT", True, WHITE), (side_x, OY + 100))
    next_list = game.preview(5)
    for i, name in enumerate(next_list):
        y_slot = OY + 125 + i * 50
        pygame.draw.rect(surf, DARK_GRAY, (side_x, y_slot, 80, 50), 1)
        draw_mini_piece(surf, name, side_x + 6, y_slot + 6, 14)

    # --- SCORE ---
    info_y = OY + 390
    for label, value in [("SCORE", game.score), ("LINES", game.lines), ("LEVEL", game.level)]:
        surf.blit(font.render(label, True, WHITE), (side_x, info_y))
        surf.blit(font.render(str(value), True, WHITE), (side_x, info_y + 18))
        info_y += 48

    # --- AI STATUS ---
    ai_x = side_x + 95
    surf.blit(font.render("AI ANALYZER", True, SOFT_BLUE), (ai_x, OY))
    surf.blit(font.render(f"Mode: {game.search_mode.upper()}", True, WHITE), (ai_x, OY + 24))
    surf.blit(font.render(f"Depth: {game.lookahead_depth}", True, WHITE), (ai_x, OY + 44))
    surf.blit(font.render(f"Beam: {game.beam_width}", True, WHITE), (ai_x, OY + 64))
    surf.blit(font.render(f"Nodes: {game.last_search_nodes}", True, WHITE), (ai_x, OY + 84))
    best_txt = "-" if game.best_eval_current is None else f"{game.best_eval_current:.2f}"
    surf.blit(font.render(f"Best Eval: {best_txt}", True, WHITE), (ai_x, OY + 104))
    surf.blit(font.render(f"Review: {game.last_move_review}", True, SOFT_GREEN), (ai_x, OY + 124))

    # --- WEIGHTS ---
    surf.blit(font.render("WEIGHT TUNING", True, SOFT_BLUE), (ai_x, OY + 160))
    for i, (name, value) in enumerate(zip(game.weight_names, game.weights)):
        txt_clr = SOFT_GREEN if i == game.weight_selected else WHITE
        surf.blit(font.render(f"w{i+1} {name[:8]}: {value:+.2f}", True, txt_clr), (ai_x, OY + 185 + i * 20))

    # --- LEADERBOARD ---
    surf.blit(font.render("LEADERBOARD", True, SOFT_BLUE), (ai_x, OY + 280))
    top3 = game.leaderboard[:3]
    for i, row in enumerate(top3):
        sc = row.get("score", 0)
        ln = row.get("lines", 0)
        ts = row.get("ts", 0)
        code = row.get("pattern_code", "-")
        day = datetime.datetime.fromtimestamp(ts).strftime("%m-%d") if ts else "--"
        surf.blit(font.render(f"{i+1}. {sc} ({ln}L) {day}", True, WHITE), (ai_x, OY + 304 + i * 32))
        surf.blit(font.render(f"    {code}", True, SOFT_GREEN), (ai_x, OY + 320 + i * 32))

    # --- HELP ---
    help_lines = [
        "Tab: toggle DFS/Beam",
        "; / ': depth -/+",
        "[ ]: select weight",
        "- / =: tune weight",
        ", / .: beam width",
        "G: toggle AI ghost",
    ]
    help_y = OY + 380
    for line in help_lines:
        surf.blit(font.render(line, True, WHITE), (ai_x, help_y))
        help_y += 18


def draw_game_over(surf, font_big, font_small):
    """Ve lop mo va chu GAME OVER de bao ket thuc tran."""
    fade = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    fade.fill((0, 0, 0, 160))
    surf.blit(fade, (0, 0))
    t_big = font_big.render("GAME OVER", True, (240, 60, 60))
    t_small = font_small.render("Press R to restart", True, WHITE)
    surf.blit(t_big, (WIN_W // 2 - t_big.get_width() // 2, WIN_H // 2 - 40))
    surf.blit(t_small, (WIN_W // 2 - t_small.get_width() // 2, WIN_H // 2 + 20))


def draw_ai_suggestion(surf, piece):
    """Ve bong mo cho nuoc di AI de xuat."""
    if piece is None:
        return
    for r, c in piece.cells():
        if r >= 0:
            draw_cell(surf, r, c, SOFT_BLUE, alpha=90)


# ============================================================
# DAS / ARR (Delayed Auto Shift / Auto Repeat Rate) nhu TETR.IO
# ============================================================
DAS = 133   # ms truoc khi bat dau lap
ARR = 20    # ms moi lan lap


def main():
    """Entry point: khoi tao pygame, xu ly input, cap nhat va render game."""
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Tetris")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("monospace", 16, bold=True)
    font_big = pygame.font.SysFont("monospace", 36, bold=True)

    game = Game()

    # Gravity timer
    grav_timer = 0

    # DAS state cho left/right
    lr_dir = 0        # -1 left, 1 right, 0 none
    lr_timer = 0
    lr_ready = False

    # Soft drop state
    soft_drop_on = False

    running = True
    while running:
        dt = clock.tick(60)  # 60 FPS, dt in ms

        # ---------- Events ----------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN and not game.game_over:
                if event.key == pygame.K_LEFT:
                    game.move(0, -1)
                    lr_dir = -1
                    lr_timer = 0
                    lr_ready = False
                elif event.key == pygame.K_RIGHT:
                    game.move(0, 1)
                    lr_dir = 1
                    lr_timer = 0
                    lr_ready = False
                elif event.key == pygame.K_DOWN:
                    soft_drop_on = True
                elif event.key == pygame.K_UP or event.key == pygame.K_x:
                    game.rotate(1)
                elif event.key == pygame.K_z:
                    game.rotate(-1)
                elif event.key == pygame.K_SPACE:
                    game.hard_drop()
                    grav_timer = 0
                elif event.key == pygame.K_c or event.key == pygame.K_LSHIFT:
                    game.hold()
                elif event.key == pygame.K_TAB:
                    game.toggle_search_mode()
                elif event.key == pygame.K_LEFTBRACKET:
                    game.select_weight(-1)
                elif event.key == pygame.K_RIGHTBRACKET:
                    game.select_weight(1)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    game.adjust_selected_weight(-0.05)
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    game.adjust_selected_weight(0.05)
                elif event.key == pygame.K_COMMA:
                    game.adjust_beam_width(-2)
                elif event.key == pygame.K_PERIOD:
                    game.adjust_beam_width(2)
                elif event.key == pygame.K_SEMICOLON:
                    game.adjust_lookahead_depth(-1)
                elif event.key == pygame.K_QUOTE:
                    game.adjust_lookahead_depth(1)
                elif event.key == pygame.K_g:
                    game.toggle_ai_hint()

            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    lr_dir = 0
                    lr_timer = 0
                    lr_ready = False
                if event.key == pygame.K_DOWN:
                    soft_drop_on = False

            # Restart
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                game.restart()
                grav_timer = 0

        if game.game_over:
            # Van ve frame cuoi
            pass
        else:
            # ---------- DAS / ARR ----------
            if lr_dir != 0:
                lr_timer += dt
                if not lr_ready:
                    if lr_timer >= DAS:
                        lr_ready = True
                        lr_timer = 0
                        game.move(0, lr_dir)
                else:
                    if ARR == 0:
                        # Teleport (0 ARR)
                        while game.move(0, lr_dir):
                            pass
                    else:
                        while lr_timer >= ARR:
                            lr_timer -= ARR
                            game.move(0, lr_dir)

            # ---------- Soft drop ----------
            if soft_drop_on:
                game.soft_drop()

            # ---------- Gravity ----------
            grav_timer += dt
            interval = game.drop_interval()
            if grav_timer >= interval:
                grav_timer -= interval
                game.tick()

        # ========== DRAW ==========
        screen.fill(BG)
        draw_grid(screen, game.grid)

        if not game.game_over and game.piece:
            if game.enable_ai_hint:
                draw_ai_suggestion(screen, game.suggestion_piece)
            # Ghost
            ghost = game.ghost()
            draw_piece(screen, ghost, GHOST_ALPHA)
            # Current piece
            draw_piece(screen, game.piece)

        draw_sidebar(screen, game, font)

        if game.game_over:
            draw_game_over(screen, font_big, font)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
