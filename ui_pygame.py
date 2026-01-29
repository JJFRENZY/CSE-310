import pygame
from typing import List, Optional
import random

from game_logic import Command, Fighter, Character, get_command_limits, resolve_turn
from ai import build_cpu_plan, choose_cpu_character


WIDTH, HEIGHT = 900, 650
FPS = 60

BG = (18, 18, 24)
PANEL = (32, 32, 44)
TEXT = (235, 235, 245)
ACCENT = (120, 220, 160)
WARN = (235, 120, 120)
SOFT = (180, 180, 200)

SLOT_W, SLOT_H = 60, 60
SLOT_GAP = 10


# --- Character colors
CHAR_COLORS = {
    Character.NORMAL: (140, 140, 150),
    Character.RED_FIGHTER: (235, 90, 90),
    Character.BLUE_HIJUMP: (90, 150, 235),
    Character.BROWN_STONE: (160, 120, 80),
    Character.GREEN_PLASMA: (90, 235, 160),
    Character.WHITE_MIRROR: (245, 245, 245),
    Character.ORANGE_FIRE: (245, 160, 80),
    Character.YELLOW_BEAM: (245, 235, 90),
    Character.PURPLE_NINJA: (180, 110, 245),
}


def draw_text(screen, font, msg, x, y, color=TEXT):
    surf = font.render(msg, True, color)
    screen.blit(surf, (x, y))


def draw_colored_vs_line(
    screen,
    font,
    left_name: str,
    left_color,
    mid_text: str,
    right_name: str,
    right_color,
    x,
    y,
):
    """Draws: <left colored> <mid text> <right colored>"""
    left_surf = font.render(left_name, True, left_color)
    mid_surf = font.render(mid_text, True, TEXT)
    right_surf = font.render(right_name, True, right_color)

    screen.blit(left_surf, (x, y))
    screen.blit(mid_surf, (x + left_surf.get_width(), y))
    screen.blit(right_surf, (x + left_surf.get_width() + mid_surf.get_width(), y))


def wrap_two_lines(text: str, limit: int = 78) -> List[str]:
    if len(text) <= limit:
        return [text]
    cut = text.rfind(" ", 0, limit)
    if cut == -1:
        cut = limit
    first = text[:cut].strip()
    second = text[cut:].strip()
    if len(second) > limit:
        second = second[:limit - 3].rstrip() + "..."
    return [first, second]


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def character_label(ch: Character) -> str:
    return ch.value


def draw_panel(screen, rect: pygame.Rect):
    pygame.draw.rect(screen, PANEL, rect, border_radius=12)
    pygame.draw.rect(screen, (60, 60, 90), rect, 2, border_radius=12)


def run_game(player_name: str = "Player", cpu_name: str = "CPU") -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Command Battle (12 Turns)")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont(None, 26)
    big = pygame.font.SysFont(None, 40)
    huge = pygame.font.SysFont(None, 54)

    characters: List[Character] = [
        Character.NORMAL,
        Character.RED_FIGHTER,
        Character.BLUE_HIJUMP,
        Character.BROWN_STONE,
        Character.GREEN_PLASMA,
        Character.WHITE_MIRROR,
        Character.ORANGE_FIRE,
        Character.YELLOW_BEAM,
        Character.PURPLE_NINJA,
    ]
    player_char_idx = 0

    plan: List[Optional[Command]] = [None] * 12
    selected: Optional[Command] = None
    mode = "select"

    remaining = {
        Command.ATTACK: 5,
        Command.BLOCK: 2,
        Command.COUNTER: 1,
        Command.IDLE: 999,
    }

    player_plan: List[Command] = []
    cpu_plan: List[Command] = []
    player = Fighter(player_name)
    cpu = Fighter(cpu_name)

    turn_index = 0
    intermission_ms = 1500
    next_step_ms = 0

    turn_title = ""
    turn_text = ""
    hearts_line = ""
    pressure_line = ""

    battle_log: List[str] = []
    log_scroll = 0

    battle_winner: Optional[str] = None
    battle_reason: str = ""

    cpu_character_choice: Character = Character.NORMAL

    def start_battle():
        nonlocal mode, player_plan, cpu_plan, player, cpu, next_step_ms
        nonlocal battle_log, battle_winner, battle_reason

        p_char = characters[player_char_idx]
        cpu_character_choice = choose_cpu_character(player_character=p_char)

        player_plan[:] = [c for c in plan]  # type: ignore
        cpu_plan[:] = build_cpu_plan(player_plan, cpu_character=cpu_character_choice)

        player = Fighter(player_name, character=p_char)
        cpu = Fighter(cpu_name, character=cpu_character_choice)

        battle_log.clear()
        battle_winner = None
        battle_reason = ""

        mode = "battle"
        next_step_ms = pygame.time.get_ticks() + intermission_ms

    while True:
        clock.tick(FPS)
        now_ms = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

        if mode == "battle" and now_ms >= next_step_ms and battle_winner is None:
            if turn_index >= 12:
                battle_winner = player.name if random.random() < 0.5 else cpu.name
                battle_reason = "Sudden Death!"
                mode = "result"
            else:
                out = resolve_turn(
                    turn_index + 1,
                    player,
                    cpu,
                    player_plan[turn_index],
                    cpu_plan[turn_index],
                )

                turn_title = f"Turn {out.turn_index}"
                turn_text = out.text
                hearts_line = f"Hearts: {player.hearts} | {cpu.hearts}"
                pressure_line = f"Pressure: {player.pressure} | {cpu.pressure}"

                battle_log.append(
                    f"Turn {out.turn_index}: {player.name}[{out.p_cmd.value}] vs {cpu.name}[{out.c_cmd.value}]"
                )
                battle_log.append(f"  {turn_text}")
                battle_log.append(f"  {hearts_line}")
                battle_log.append("")

                turn_index += 1
                next_step_ms = now_ms + intermission_ms

        screen.fill(BG)

        if mode in ("battle", "result"):
            p_color = CHAR_COLORS[player.character]
            c_color = CHAR_COLORS[cpu.character]

            draw_text(screen, big, "Battle Playback", 50, 30, ACCENT)

            draw_text(screen, font, f"{player.name}", 50, 70, p_color)
            draw_text(screen, font, f"{cpu.name}", 450, 70, c_color)

            card = pygame.Rect(50, 120, 800, 170)
            draw_panel(screen, card)

            draw_text(screen, big, turn_title, 65, 140)

            draw_colored_vs_line(
                screen,
                font,
                player.name,
                p_color,
                " attacks / defends against ",
                cpu.name,
                c_color,
                65,
                180,
            )

            wrapped = wrap_two_lines(turn_text)
            draw_text(screen, font, wrapped[0], 65, 210)
            if len(wrapped) > 1:
                draw_text(screen, font, wrapped[1], 65, 230)

            if mode == "result":
                draw_text(
                    screen,
                    huge,
                    f"Winner: {battle_winner}",
                    50,
                    320,
                    p_color if battle_winner == player.name else c_color,
                )
                draw_text(screen, big, f"Reason: {battle_reason}", 50, 370)

        pygame.display.flip()
