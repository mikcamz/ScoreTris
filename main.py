"""
Tetris - main entry point.
Rendering bang pygame, input, game loop.
UI (Menu, History) dung Dear ImGui.
Chay: python main.py
"""

import datetime
import sys
import pygame
from pygame.locals import DOUBLEBUF, OPENGL
from OpenGL.GL import *
import imgui
from imgui.integrations.pygame import PygameRenderer

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

# ============================================================
# Theme Settings
# ============================================================
THEMES = {
    "DARK": {
        "bg": (20, 20, 20),
        "grid": (40, 40, 40),
        "text": (220, 220, 220),
        "panel": (60, 60, 60),
    },
    "LIGHT": {
        "bg": (240, 240, 240),
        "grid": (200, 200, 200),
        "text": (20, 20, 20),
        "panel": (200, 200, 200),
    }
}
current_theme = "DARK"

GHOST_ALPHA = 80
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
        full_color = (*color, 255)
        pygame.draw.rect(surf, full_color, (x, y, CELL - 1, CELL - 1))
        # Vien sang nhe
        light_color = tuple(min(v + 40, 255) for v in color) + (255,)
        pygame.draw.rect(surf, light_color, (x, y, CELL - 1, CELL - 1), 2)


def draw_grid(surf, grid):
    """Ve luoi va cac o da dat"""
    theme = THEMES[current_theme]
    # Ve luoi
    for r in range(ROWS + 1):
        pygame.draw.line(surf, theme["grid"], (OX, OY + r * CELL),
                         (OX + BOARD_W, OY + r * CELL))
    for c in range(COLS + 1):
        pygame.draw.line(surf, theme["grid"], (OX + c * CELL, OY),
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
    theme = THEMES[current_theme]
    side_x = OX + BOARD_W + 15

    # --- HOLD ---
    surf.blit(font.render("HOLD", True, theme["text"]), (side_x, OY))
    pygame.draw.rect(surf, theme["panel"], (side_x, OY + 22, 80, 60), 1)
    draw_mini_piece(surf, game.hold_name, side_x + 6, OY + 28)

    # --- NEXT ---
    surf.blit(font.render("NEXT", True, theme["text"]), (side_x, OY + 100))
    next_list = game.preview(5)
    for i, name in enumerate(next_list):
        y_slot = OY + 125 + i * 50
        pygame.draw.rect(surf, theme["panel"], (side_x, y_slot, 80, 50), 1)
        draw_mini_piece(surf, name, side_x + 6, y_slot + 6, 14)

    # --- SCORE ---
    info_y = OY + 390
    for label, value in [("SCORE", game.score), ("LINES", game.lines), ("LEVEL", game.level)]:
        surf.blit(font.render(label, True, theme["text"]), (side_x, info_y))
        surf.blit(font.render(str(value), True, theme["text"]), (side_x, info_y + 18))
        info_y += 48

    # --- AI STATUS ---
    ai_x = side_x + 95
    surf.blit(font.render("AI ANALYZER", True, SOFT_BLUE), (ai_x, OY))
    surf.blit(font.render(f"Mode: {game.search_mode.upper()}", True, theme["text"]), (ai_x, OY + 24))
    surf.blit(font.render(f"Depth: {game.lookahead_depth}", True, theme["text"]), (ai_x, OY + 44))
    surf.blit(font.render(f"Beam: {game.beam_width}", True, theme["text"]), (ai_x, OY + 64))
    surf.blit(font.render(f"Nodes: {game.last_search_nodes}", True, theme["text"]), (ai_x, OY + 84))
    best_txt = "-" if game.best_eval_current is None else f"{game.best_eval_current:.2f}"
    surf.blit(font.render(f"Best Eval: {best_txt}", True, theme["text"]), (ai_x, OY + 104))
    surf.blit(font.render(f"Review: {game.last_move_review}", True, SOFT_GREEN), (ai_x, OY + 124))

    # --- WEIGHTS ---
    surf.blit(font.render("WEIGHT TUNING", True, SOFT_BLUE), (ai_x, OY + 160))
    for i, (name, value) in enumerate(zip(game.weight_names, game.weights)):
        txt_clr = SOFT_GREEN if i == game.weight_selected else theme["text"]
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
        surf.blit(font.render(f"{i+1}. {sc} ({ln}L) {day}", True, theme["text"]), (ai_x, OY + 304 + i * 32))
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
        surf.blit(font.render(line, True, theme["text"]), (ai_x, help_y))
        help_y += 18


def draw_game_over(surf, font_big, font_small):
    """Ve lop mo va chu GAME OVER de bao ket thuc tran."""
    theme = THEMES[current_theme]
    fade = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    fade.fill((0, 0, 0, 160))
    surf.blit(fade, (0, 0))
    t_big = font_big.render("GAME OVER", True, (240, 60, 60))
    t_small = font_small.render("Press R to restart", True, theme["text"])
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
    """Entry point: khoi tao pygame, imgui, xu ly input, cap nhat va render game."""
    pygame.init()
    pygame.display.set_mode((WIN_W, WIN_H), DOUBLEBUF | OPENGL)
    screen = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    pygame.display.set_caption("Tetris")
    clock = pygame.time.Clock()

    # Create texture to render the screen surface
    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

    font = pygame.font.SysFont("monospace", 16, bold=True)
    font_big = pygame.font.SysFont("monospace", 36, bold=True)

    imgui.create_context()
    impl = PygameRenderer()
    io = imgui.get_io()
    io.display_size = (WIN_W, WIN_H)

    game = Game()

    # Thoi gian va state cho Game
    grav_timer = 0
    lr_dir = 0
    lr_timer = 0
    lr_ready = False
    soft_drop_on = False

    # App state
    app_state = "MENU" # MENU, PLAYING, REVIEW
    global current_theme

    running = True
    while running:
        dt = clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            impl.process_event(event)

            # Xu ly Game Input neu dang PLAYING va ImGui khong chiem keyboard
            if app_state == "PLAYING" and not imgui.get_io().want_capture_keyboard:
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
                    elif event.key in (pygame.K_UP, pygame.K_x):
                        game.rotate(1)
                    elif event.key == pygame.K_z:
                        game.rotate(-1)
                    elif event.key == pygame.K_SPACE:
                        game.hard_drop()
                        grav_timer = 0
                    elif event.key in (pygame.K_c, pygame.K_LSHIFT):
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
                    elif event.key == pygame.K_ESCAPE:
                        app_state = "MENU"

                if event.type == pygame.KEYUP:
                    if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        lr_dir = 0
                        lr_timer = 0
                        lr_ready = False
                    if event.key == pygame.K_DOWN:
                        soft_drop_on = False

                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    game.restart()
                    grav_timer = 0

        # Cap nhat Logic Game
        if app_state == "PLAYING" and not game.game_over:
            if lr_dir != 0:
                lr_timer += dt
                if not lr_ready:
                    if lr_timer >= DAS:
                        lr_ready = True
                        lr_timer = 0
                        game.move(0, lr_dir)
                else:
                    if ARR == 0:
                        while game.move(0, lr_dir): pass
                    else:
                        while lr_timer >= ARR:
                            lr_timer -= ARR
                            game.move(0, lr_dir)

            if soft_drop_on:
                game.soft_drop()

            grav_timer += dt
            interval = game.drop_interval()
            if grav_timer >= interval:
                grav_timer -= interval
                game.tick()

        # Render
        theme_bg = THEMES[current_theme]["bg"]
        screen.fill((*theme_bg, 255))

        if app_state == "PLAYING":
            draw_grid(screen, game.grid)
            if not game.game_over and game.piece:
                if game.enable_ai_hint:
                    draw_ai_suggestion(screen, game.suggestion_piece)
                ghost = game.ghost()
                draw_piece(screen, ghost, GHOST_ALPHA)
                draw_piece(screen, game.piece)
            draw_sidebar(screen, game, font)
            if game.game_over:
                draw_game_over(screen, font_big, font)

        # ImGui logic
        impl.process_inputs()
        imgui.new_frame()

        if app_state == "MENU":
            imgui.set_next_window_size(300, 250)
            imgui.set_next_window_position((WIN_W // 2) - 150, (WIN_H // 2) - 125)
            imgui.begin("Main Menu", flags=imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_MOVE)
            if imgui.button("Start Game", width=280, height=40):
                app_state = "PLAYING"
                game.restart()
            if imgui.button("Past Play Review", width=280, height=40):
                app_state = "REVIEW"
            if imgui.button(f"Theme: {current_theme}", width=280, height=40):
                current_theme = "LIGHT" if current_theme == "DARK" else "DARK"
            if imgui.button("Exit", width=280, height=40):
                running = False
            imgui.end()

        elif app_state == "REVIEW":
            imgui.set_next_window_size(500, 400)
            imgui.set_next_window_position((WIN_W // 2) - 250, (WIN_H // 2) - 200)
            imgui.begin("Past Play Review", flags=imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_MOVE)
            
            if imgui.button("Back to Menu"):
                app_state = "MENU"
                
            imgui.separator()
            imgui.text("Leaderboard & Match History:")
            imgui.begin_child("HistoryScroll", 0, 0, border=True)
            for idx, r in enumerate(game.leaderboard):
                day = datetime.datetime.fromtimestamp(r.get("ts", 0)).strftime("%Y-%m-%d %H:%M:%S")
                imgui.text(f"{idx+1}. Score: {r.get('score', 0)} | Lines: {r.get('lines', 0)} | {day}")
                imgui.text_colored(f"Code: {r.get('pattern_code', '-')}", 0.4, 0.8, 0.4)
                imgui.separator()
            imgui.end_child()
            
            imgui.end()
            
        elif app_state == "PLAYING" and game.game_over:
            # Overlap menu for Game Over
            imgui.set_next_window_size(200, 100)
            imgui.set_next_window_position((WIN_W // 2) - 100, (WIN_H // 2) - 50)
            imgui.begin("Game Over", flags=imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_MOVE)
            if imgui.button("Restart Game", width=180, height=30):
                game.restart()
                grav_timer = 0
            if imgui.button("Main Menu", width=180, height=30):
                app_state = "MENU"
            imgui.end()

        # The hien 1 floating window cho huong dan khi dang choi
        if app_state == "PLAYING":
            imgui.set_next_window_position(10, 10, imgui.ONCE)
            imgui.begin("Menu Overlay", flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE | imgui.WINDOW_NO_FOCUS_ON_APPEARING | imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_MOVE)
            if imgui.button("Pause / Return to Menu"):
                app_state = "MENU"
            imgui.end()

        # Draw Pygame surface to OpenGL texture
        texture_data = pygame.image.tostring(screen, "RGBA", False)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, WIN_W, WIN_H, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        
        glClearColor(0.1, 0.1, 0.1, 1)
        glClear(GL_COLOR_BUFFER_BIT)
        
        # Render the Pygame surface behind ImGui
        imgui.set_next_window_size(WIN_W, WIN_H)
        imgui.set_next_window_position(0, 0)
        imgui.begin("Background", flags=imgui.WINDOW_NO_DECORATION | imgui.WINDOW_NO_BACKGROUND | imgui.WINDOW_NO_BRING_TO_FRONT_ON_FOCUS | imgui.WINDOW_NO_INPUTS)
        imgui.image(texture_id, WIN_W, WIN_H)
        imgui.end()

        imgui.render()
        impl.render(imgui.get_draw_data())

        pygame.display.flip()

    impl.shutdown()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
