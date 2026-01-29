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


# --- Character colors (used for UI name labels, etc.)
# ✅ NORMAL is now dark grey to avoid confusion
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

# --- Character descriptions (for the info window)
CHAR_INFO = {
    Character.NORMAL: "Grey (Normal): No special rule changes.",

    Character.RED_FIGHTER: "Red (Fighter): You can plan 6 Attacks instead of 5.",

    Character.BLUE_HIJUMP:
        "Blue (Hi-Jump): If you Counter unsuccessfully, your forced recovery turn is INVINCIBLE.",

    Character.BROWN_STONE:
        "Brown (Stone): Block prevents ALL damage (no 0.5 chip).",

    Character.GREEN_PLASMA:
        "Green (Plasma): A Block/Counter that successfully stops an Attack also deals +0.5 damage back.",

    Character.WHITE_MIRROR:
        "White (Mirror): A successful Counter deals 2 hearts instead of 1.",

    Character.ORANGE_FIRE:
        "Orange (Fire): Your Attacks still land even if the opponent Counters.",

    Character.YELLOW_BEAM:
        "Yellow (Beam): If BOTH players choose IDLE on the same turn, the opponent takes 1 heart "
        "(not triggered by forced '-' recovery).",

    Character.PURPLE_NINJA:
        "Purple (Ninja): If both Attack on the same turn, your opponent still takes 0.5 damage.",
}


def draw_text(screen, font, msg, x, y, color=TEXT):
    surf = font.render(msg, True, color)
    screen.blit(surf, (x, y))


def wrap_lines(text: str, limit: int = 54) -> List[str]:
    """Word wrap helper (tighter limit to prevent overflow)."""
    words = text.split()
    lines: List[str] = []
    current: List[str] = []
    count = 0

    for w in words:
        extra = len(w) + (1 if current else 0)
        if count + extra > limit:
            lines.append(" ".join(current))
            current = [w]
            count = len(w)
        else:
            current.append(w)
            count += extra

    if current:
        lines.append(" ".join(current))
    return lines


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


def draw_arrow_button(screen, rect: pygame.Rect, label: str, font, enabled=True):
    base = (35, 35, 45) if enabled else (25, 25, 30)
    border = ACCENT if enabled else (70, 70, 80)
    pygame.draw.rect(screen, base, rect, border_radius=10)
    pygame.draw.rect(screen, border, rect, 2, border_radius=10)
    draw_text(screen, font, label, rect.x + 18, rect.y + 10, border)


def run_game(player_name: str = "Player", cpu_name: str = "CPU") -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Command Battle (12 Turns)")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont(None, 26)
    big = pygame.font.SysFont(None, 40)
    huge = pygame.font.SysFont(None, 54)

    # Available characters (player picks; CPU auto-picks)
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

    # Planning state
    plan: List[Optional[Command]] = [None] * 12
    selected: Optional[Command] = None
    mode = "select"  # select -> plan -> battle -> result

    remaining = {
        Command.ATTACK: 5,
        Command.BLOCK: 2,
        Command.COUNTER: 1,
        Command.IDLE: 999,
    }

    # Battle playback state
    player_plan: List[Command] = []
    cpu_plan: List[Command] = []
    player = Fighter(player_name)
    cpu = Fighter(cpu_name)

    turn_index = 0
    intermission_ms = 1500
    next_step_ms = 0

    # On-screen "turn card"
    turn_title = ""
    turn_text = ""
    hearts_line = ""
    pressure_line = ""

    battle_log: List[str] = []
    log_scroll = 0

    battle_winner: Optional[str] = None
    battle_reason: str = ""

    cpu_character_choice: Character = Character.NORMAL

    def recompute_remaining_from_plan() -> None:
        nonlocal remaining
        limits = get_command_limits(characters[player_char_idx])
        used_attack = sum(1 for c in plan if c == Command.ATTACK)
        used_block = sum(1 for c in plan if c == Command.BLOCK)
        used_counter = sum(1 for c in plan if c == Command.COUNTER)
        remaining = {
            Command.ATTACK: max(0, limits[Command.ATTACK] - used_attack),
            Command.BLOCK: max(0, limits[Command.BLOCK] - used_block),
            Command.COUNTER: max(0, limits[Command.COUNTER] - used_counter),
            Command.IDLE: 999,
        }

    def can_place(cmd: Command) -> bool:
        if cmd == Command.IDLE:
            return True
        return remaining.get(cmd, 0) > 0

    def place_at(i: int, cmd: Command) -> None:
        if plan[i] is None and can_place(cmd):
            plan[i] = cmd
            recompute_remaining_from_plan()

    def erase_at(i: int) -> None:
        if plan[i] is not None:
            plan[i] = None
            recompute_remaining_from_plan()

    def reset_to_select() -> None:
        nonlocal plan, selected, mode
        nonlocal player_plan, cpu_plan, player, cpu, turn_index, next_step_ms
        nonlocal turn_title, turn_text, hearts_line, pressure_line
        nonlocal battle_log, battle_winner, battle_reason, log_scroll
        nonlocal cpu_character_choice

        plan = [None] * 12
        selected = None
        mode = "select"

        player_plan = []
        cpu_plan = []
        player = Fighter(player_name)
        cpu = Fighter(cpu_name)
        cpu_character_choice = Character.NORMAL

        turn_index = 0
        next_step_ms = 0

        turn_title = ""
        turn_text = ""
        hearts_line = ""
        pressure_line = ""

        battle_log = []
        log_scroll = 0
        battle_winner = None
        battle_reason = ""

        recompute_remaining_from_plan()

    def reset_to_plan() -> None:
        nonlocal plan, selected, mode, log_scroll
        plan = [None] * 12
        selected = None
        log_scroll = 0
        recompute_remaining_from_plan()
        mode = "plan"

    # Slots
    start_x = 50
    start_y = 160

    def slot_rect(i: int) -> pygame.Rect:
        row = i // 6
        col = i % 6
        x = start_x + col * (SLOT_W + SLOT_GAP)
        y = start_y + row * (SLOT_H + SLOT_GAP)
        return pygame.Rect(x, y, SLOT_W, SLOT_H)

    # Plan buttons
    btn_attack = pygame.Rect(520, 180, 320, 50)
    btn_block = pygame.Rect(520, 240, 320, 50)
    btn_counter = pygame.Rect(520, 300, 320, 50)
    btn_idle = pygame.Rect(520, 360, 320, 50)
    btn_start = pygame.Rect(520, 430, 320, 60)

    # Select screen layout
    select_panel_player = pygame.Rect(50, 140, 520, 120)
    btn_p_prev = pygame.Rect(select_panel_player.x + 20, select_panel_player.y + 55, 60, 50)
    btn_p_next = pygame.Rect(select_panel_player.right - 80, select_panel_player.y + 55, 60, 50)

    # ✅ Taller info panel so Blue/Green fit cleanly
    info_panel = pygame.Rect(50, 280, 520, 170)

    btn_to_plan = pygame.Rect(600, 520, 250, 70)

    # ✅ Log panel moved DOWN so the winner/reason + bigger card don’t overlap it
    log_panel = pygame.Rect(50, 395, 800, 230)

    def draw_button(rect: pygame.Rect, label: str, active: bool, enabled: bool):
        color = ACCENT if active else (90, 90, 120)
        base = (30, 40, 45) if enabled else (25, 25, 30)
        pygame.draw.rect(screen, base, rect, border_radius=10)
        pygame.draw.rect(screen, color if enabled else (70, 70, 80), rect, 2, border_radius=10)
        draw_text(screen, big, label, rect.x + 12, rect.y + 10, color if enabled else (140, 140, 150))

    def start_battle() -> None:
        nonlocal mode, player_plan, cpu_plan, player, cpu, turn_index, next_step_ms
        nonlocal battle_log, battle_winner, battle_reason, log_scroll
        nonlocal turn_title, turn_text, hearts_line, pressure_line
        nonlocal cpu_character_choice

        p_char = characters[player_char_idx]
        cpu_character_choice = choose_cpu_character(player_character=p_char)

        player_plan = [c for c in plan]  # type: ignore

        cpu_plan = build_cpu_plan(
            player_plan,
            cpu_character=cpu_character_choice,
            player_character=p_char,
        )

        player = Fighter(player_name, character=p_char)
        cpu = Fighter(cpu_name, character=cpu_character_choice)
        turn_index = 0

        battle_log = []
        log_scroll = 0
        battle_winner = None
        battle_reason = ""

        turn_title = "Get Ready!"
        turn_text = "Battle starts in 1.5 seconds..."
        hearts_line = f"Hearts: {player.name}={player.hearts} | {cpu.name}={cpu.hearts}"
        pressure_line = f"Pressure: {player.name}={player.pressure} | {cpu.name}={cpu.pressure}"

        battle_log.append(f"Player Character: {character_label(p_char)}")
        battle_log.append(f"CPU Character: {character_label(cpu_character_choice)}")
        battle_log.append("")

        mode = "battle"
        next_step_ms = pygame.time.get_ticks() + intermission_ms

    def check_winner_after_turn() -> Optional[str]:
        nonlocal battle_reason

        if player.hearts <= 0 and cpu.hearts <= 0:
            battle_reason = "Double KO!"
            return None
        if cpu.hearts <= 0:
            battle_reason = "Opponent hearts reached 0."
            return player.name
        if player.hearts <= 0:
            battle_reason = "Player hearts reached 0."
            return cpu.name

        if cpu.pressure >= 4:
            battle_reason = "Opponent was knocked off the stage (pressure)."
            return player.name
        if player.pressure >= 4:
            battle_reason = "Player was knocked off the stage (pressure)."
            return cpu.name

        return None

    def do_sudden_death() -> None:
        nonlocal battle_winner, battle_reason
        battle_log.append("Sudden Death! Each fighter has a 50% chance to land a KO strike.")
        if random.random() < 0.5:
            battle_winner = player.name
            battle_reason = "Sudden Death KO strike landed by player."
        else:
            battle_winner = cpu.name
            battle_reason = "Sudden Death KO strike landed by CPU."

    def max_scroll(lines_per_page: int) -> int:
        return max(0, len(battle_log) - lines_per_page)

    recompute_remaining_from_plan()

    while True:
        clock.tick(FPS)
        now_ms = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                reset_to_select()

            # Scroll log
            if mode in ("battle", "result"):
                if event.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    if log_panel.collidepoint(mx, my):
                        log_scroll += (-event.y) * 2
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        log_scroll += 2
                    elif event.key == pygame.K_DOWN:
                        log_scroll -= 2
                    elif event.key == pygame.K_PAGEUP:
                        log_scroll += 10
                    elif event.key == pygame.K_PAGEDOWN:
                        log_scroll -= 10
                    elif event.key == pygame.K_END:
                        log_scroll = 0

            # Select clicks
            if mode == "select" and event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if btn_p_prev.collidepoint(mx, my):
                    player_char_idx = (player_char_idx - 1) % len(characters)
                    recompute_remaining_from_plan()
                elif btn_p_next.collidepoint(mx, my):
                    player_char_idx = (player_char_idx + 1) % len(characters)
                    recompute_remaining_from_plan()
                elif btn_to_plan.collidepoint(mx, my):
                    reset_to_plan()

            # Plan clicks
            if mode == "plan" and event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if btn_attack.collidepoint(mx, my):
                    selected = Command.ATTACK
                elif btn_block.collidepoint(mx, my):
                    selected = Command.BLOCK
                elif btn_counter.collidepoint(mx, my):
                    selected = Command.COUNTER
                elif btn_idle.collidepoint(mx, my):
                    selected = Command.IDLE
                elif btn_start.collidepoint(mx, my):
                    if all(c is not None for c in plan):
                        start_battle()
                else:
                    for i in range(12):
                        r = slot_rect(i)
                        if r.collidepoint(mx, my):
                            if event.button == 3:
                                erase_at(i)
                            else:
                                if selected is not None:
                                    place_at(i, selected)
                            break

        # Battle playback
        if mode == "battle" and now_ms >= next_step_ms and battle_winner is None:
            if turn_index >= 12:
                do_sudden_death()
                mode = "result"
            else:
                p_cmd = player_plan[turn_index]
                c_cmd = cpu_plan[turn_index]
                out = resolve_turn(turn_index + 1, player, cpu, p_cmd, c_cmd)

                turn_title = (
                    f"Turn {out.turn_index}: {player.name}[{out.p_cmd.value}] "
                    f"vs {cpu.name}[{out.c_cmd.value}]"
                )
                turn_text = out.text
                hearts_line = f"Hearts: {player.name}={player.hearts} | {cpu.name}={cpu.hearts}"
                pressure_line = f"Pressure: {player.name}={player.pressure} | {cpu.name}={cpu.pressure}"

                battle_log.append(turn_title)
                battle_log.append(f"    {turn_text}")
                battle_log.append(f"    {hearts_line}")
                battle_log.append(f"    {pressure_line}")
                battle_log.append("")

                battle_winner = check_winner_after_turn()
                if battle_winner is not None:
                    mode = "result"
                else:
                    turn_index += 1
                    next_step_ms = now_ms + intermission_ms

        # DRAW
        screen.fill(BG)

        if mode == "select":
            p_char = characters[player_char_idx]
            p_color = CHAR_COLORS.get(p_char, TEXT)

            draw_text(screen, huge, "Choose Your Character Color", 50, 60, ACCENT)
            draw_text(screen, font, "Press R anytime to restart. CPU picks its color automatically.", 50, 110, SOFT)

            # Player selection panel
            draw_panel(screen, select_panel_player)
            draw_text(screen, big, "Player Character", select_panel_player.x + 20, select_panel_player.y + 15, TEXT)

            draw_arrow_button(screen, btn_p_prev, "<", big, enabled=True)
            draw_arrow_button(screen, btn_p_next, ">", big, enabled=True)

            name_area = pygame.Rect(
                btn_p_prev.right + 10,
                btn_p_prev.y,
                btn_p_next.x - (btn_p_prev.right + 10),
                btn_p_prev.height,
            )
            label = character_label(p_char)
            label_surf = big.render(label, True, p_color)
            label_x = name_area.x + (name_area.width - label_surf.get_width()) // 2
            label_y = name_area.y + (name_area.height - label_surf.get_height()) // 2
            screen.blit(label_surf, (label_x, label_y))

            # Info panel
            draw_panel(screen, info_panel)
            draw_text(screen, big, "What this color does:", info_panel.x + 20, info_panel.y + 15, TEXT)

            info_text = CHAR_INFO.get(p_char, "")
            lines = wrap_lines(info_text, limit=54)

            line_height = 24
            text_top = info_panel.y + 55
            max_lines = (info_panel.height - (text_top - info_panel.y) - 14) // line_height

            shown = lines[:max_lines]
            if len(lines) > max_lines and shown:
                shown[-1] = shown[-1].rstrip() + " ..."

            y = text_top
            for line in shown:
                draw_text(screen, font, line, info_panel.x + 20, y, SOFT)
                y += line_height

            draw_text(
                screen,
                font,
                "CPU: AUTO (it will pick a color at battle start based on yours).",
                50,
                info_panel.bottom + 10,
                SOFT,
            )

            pygame.draw.rect(screen, (35, 35, 45), btn_to_plan, border_radius=14)
            pygame.draw.rect(screen, ACCENT, btn_to_plan, 2, border_radius=14)
            draw_text(screen, huge, "PLAN", btn_to_plan.x + 70, btn_to_plan.y + 12, ACCENT)

        elif mode == "plan":
            p_char = characters[player_char_idx]
            p_color = CHAR_COLORS.get(p_char, TEXT)

            draw_text(screen, big, "Command Battle — Plan 12 Turns", 50, 40, ACCENT)
            draw_text(screen, font, "Left-click a slot to place the selected command. Right-click to erase.", 50, 80)
            draw_text(screen, font, "Fill ALL 12 slots, then start battle.", 50, 105)

            draw_text(screen, font, f"Player: {player_name} — {character_label(p_char)}", 50, 130, p_color)
            draw_text(screen, font, "CPU: AUTO (chooses at battle start)", 50, 150, SOFT)

            for i in range(12):
                r = slot_rect(i)
                pygame.draw.rect(screen, PANEL, r, border_radius=8)
                pygame.draw.rect(screen, (60, 60, 90), r, 2, border_radius=8)
                draw_text(screen, font, f"{i+1}", r.x + 6, r.y + 6, SOFT)
                if plan[i] is not None:
                    draw_text(screen, big, plan[i].value, r.x + 22, r.y + 18, ACCENT)

            draw_button(btn_attack, f"Attack (A) — left: {remaining[Command.ATTACK]}", selected == Command.ATTACK, remaining[Command.ATTACK] > 0)
            draw_button(btn_block, f"Block (B) — left: {remaining[Command.BLOCK]}", selected == Command.BLOCK, remaining[Command.BLOCK] > 0)
            draw_button(btn_counter, f"Counter (C) — left: {remaining[Command.COUNTER]}", selected == Command.COUNTER, remaining[Command.COUNTER] > 0)
            draw_button(btn_idle, "Idle (I) — no action", selected == Command.IDLE, True)

            all_filled = all(c is not None for c in plan)
            pygame.draw.rect(screen, (35, 35, 45), btn_start, border_radius=12)
            pygame.draw.rect(screen, ACCENT if all_filled else WARN, btn_start, 2, border_radius=12)
            draw_text(screen, big, "START BATTLE", btn_start.x + 70, btn_start.y + 15, ACCENT if all_filled else WARN)

            if not all_filled:
                draw_text(screen, font, "Fill all 12 turns to start.", 520, 510, WARN)

            y = 560
            draw_text(screen, font, "Rules: 3 Hearts | A=5/6 | B=2 | C=1 | I=Idle", 50, y, SOFT)
            draw_text(screen, font, "1.5s delay between turns | Press R to restart", 50, y + 24, SOFT)

        else:
            p_color = CHAR_COLORS.get(player.character, TEXT)
            c_color = CHAR_COLORS.get(cpu.character, TEXT)

            header = "Battle Playback" if mode == "battle" else "Battle Results"
            draw_text(screen, big, header, 50, 30, ACCENT)
            draw_text(screen, font, "Scroll log: wheel over log / ↑↓ / PgUp PgDn / End. Press R to restart.", 50, 60, SOFT)

            # ✅ These labels are now safe (card starts at y=120)
            draw_text(screen, font, f"{player.name}: {character_label(player.character)}", 50, 80, p_color)
            draw_text(screen, font, f"{cpu.name}: {character_label(cpu.character)}", 450, 80, c_color)

            # ✅ Turn card moved DOWN and made taller
            card = pygame.Rect(50, 120, 800, 170)
            draw_panel(screen, card)

            draw_text(screen, big, turn_title, 65, card.y + 20, TEXT)

            wrapped = wrap_two_lines(turn_text, 78)
            draw_text(screen, font, wrapped[0], 65, card.y + 60, TEXT)
            if len(wrapped) > 1:
                draw_text(screen, font, wrapped[1], 65, card.y + 80, TEXT)

            draw_text(screen, font, hearts_line, 65, card.y + 105, ACCENT)
            draw_text(screen, font, pressure_line, 65, card.y + 130, ACCENT)

            # ✅ Results moved down too (so it stays below the bigger card)
            if mode == "result":
                winner_text = battle_winner if battle_winner is not None else "No winner"
                draw_text(screen, huge, f"Winner: {winner_text}", 50, 305, ACCENT)
                draw_text(screen, big, f"Reason: {battle_reason}", 50, 360, TEXT)

            draw_panel(screen, log_panel)

            lines_per_page = (log_panel.height - 28) // 22
            max_s = max_scroll(lines_per_page)
            log_scroll = clamp(log_scroll, 0, max_s)

            end = len(battle_log) - log_scroll
            start = max(0, end - lines_per_page)
            view = battle_log[start:end]

            y = log_panel.y + 14
            for line in view:
                draw_text(screen, font, line[:110], log_panel.x + 14, y, TEXT)
                y += 22

            if len(battle_log) > lines_per_page:
                draw_text(
                    screen,
                    font,
                    f"Log: lines {start + 1}-{end} of {len(battle_log)} (scroll {log_scroll})",
                    log_panel.x + 14,
                    log_panel.bottom - 24,
                    SOFT,
                )

        pygame.display.flip()
