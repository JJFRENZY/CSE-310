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

SLOT_W, SLOT_H = 60, 60
SLOT_GAP = 10


def draw_text(screen, font, msg, x, y, color=TEXT):
    surf = font.render(msg, True, color)
    screen.blit(surf, (x, y))


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


def run_game(player_name: str = "Player", cpu_name: str = "CPU") -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Command Battle (12 Turns)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 26)
    big = pygame.font.SysFont(None, 40)
    huge = pygame.font.SysFont(None, 54)

    # Character list (player selects from these)
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

    # CPU options: None means "AUTO"
    cpu_options: List[Optional[Character]] = [None] + characters

    player_char_idx = 0
    cpu_char_idx = 0  # starts at AUTO

    # Planning state
    plan: List[Optional[Command]] = [None] * 12

    # remaining counts (derived from plan + character limits)
    remaining = {
        Command.ATTACK: 5,
        Command.BLOCK: 2,
        Command.COUNTER: 1,
        Command.IDLE: 999,
    }

    selected: Optional[Command] = None
    mode = "select"  # select -> plan -> battle -> result

    # Battle playback state
    player_plan: List[Command] = []
    cpu_plan: List[Command] = []
    player = Fighter(player_name)
    cpu = Fighter(cpu_name)

    turn_index = 0  # 0..11
    intermission_ms = 1500
    next_step_ms = 0

    # On-screen "turn card"
    turn_title = ""
    turn_text = ""
    hearts_line = ""
    pressure_line = ""

    # Log panel lines
    battle_log: List[str] = []
    log_scroll = 0

    battle_winner: Optional[str] = None
    battle_reason: str = ""

    def cpu_choice_label() -> str:
        choice = cpu_options[cpu_char_idx]
        return "CPU Auto" if choice is None else character_label(choice)

    def recompute_remaining_from_plan() -> None:
        """
        Rebuild remaining counts from:
        - the player's current character limits
        - what is already placed in plan
        This prevents "changing character to cheat limits".
        """
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

        plan = [None] * 12
        selected = None
        mode = "select"

        player_plan = []
        cpu_plan = []
        player = Fighter(player_name)
        cpu = Fighter(cpu_name)
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

    # Slot positions
    start_x = 50
    start_y = 160

    def slot_rect(i: int) -> pygame.Rect:
        row = i // 6
        col = i % 6
        x = start_x + col * (SLOT_W + SLOT_GAP)
        y = start_y + row * (SLOT_H + SLOT_GAP)
        return pygame.Rect(x, y, SLOT_W, SLOT_H)

    # Buttons (plan)
    btn_attack = pygame.Rect(520, 180, 320, 50)
    btn_block = pygame.Rect(520, 240, 320, 50)
    btn_counter = pygame.Rect(520, 300, 320, 50)
    btn_idle = pygame.Rect(520, 360, 320, 50)
    btn_start = pygame.Rect(520, 430, 320, 60)

    # Buttons (select)
    btn_p_prev = pygame.Rect(50, 170, 60, 50)
    btn_p_next = pygame.Rect(360, 170, 60, 50)
    btn_c_prev = pygame.Rect(50, 290, 60, 50)
    btn_c_next = pygame.Rect(360, 290, 60, 50)
    btn_to_plan = pygame.Rect(520, 520, 320, 70)

    # Log panel rect
    log_panel = pygame.Rect(50, 360, 800, 260)

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

        p_char = characters[player_char_idx]

        # CPU pick (auto or manual)
        cpu_choice = cpu_options[cpu_char_idx]
        if cpu_choice is None:
            c_char = choose_cpu_character(player_character=p_char)
        else:
            c_char = cpu_choice

        player_plan = [c for c in plan]  # type: ignore

        # Pass character info into AI (Red gets 6 attacks, etc.)
        cpu_plan = build_cpu_plan(
            player_plan,
            cpu_character=c_char,
            player_character=p_char,
        )

        player = Fighter(player_name, character=p_char)
        cpu = Fighter(cpu_name, character=c_char)
        turn_index = 0

        battle_log = []
        log_scroll = 0
        battle_winner = None
        battle_reason = ""

        turn_title = "Get Ready!"
        turn_text = "Battle starts in 1.5 seconds..."
        hearts_line = f"Hearts: {player.name}={player.hearts} | {cpu.name}={cpu.hearts}"
        pressure_line = f"Pressure: {player.name}={player.pressure} | {cpu.name}={cpu.pressure}"

        # Character header into log
        battle_log.append(f"Player Character: {character_label(p_char)}")
        battle_log.append(f"CPU Character: {character_label(c_char)}" + (" (AUTO)" if cpu_choice is None else ""))
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

    # Initialize remaining
    recompute_remaining_from_plan()

    # Main loop
    while True:
        clock.tick(FPS)
        now_ms = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

            # Reset anytime -> back to character select
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                reset_to_select()

            # Scroll log (battle/result)
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

            # Character select clicks
            if mode == "select" and event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if btn_p_prev.collidepoint(mx, my):
                    player_char_idx = (player_char_idx - 1) % len(characters)
                    recompute_remaining_from_plan()
                elif btn_p_next.collidepoint(mx, my):
                    player_char_idx = (player_char_idx + 1) % len(characters)
                    recompute_remaining_from_plan()
                elif btn_c_prev.collidepoint(mx, my):
                    cpu_char_idx = (cpu_char_idx - 1) % len(cpu_options)
                elif btn_c_next.collidepoint(mx, my):
                    cpu_char_idx = (cpu_char_idx + 1) % len(cpu_options)
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

        # Battle playback: advance 1 turn every 1.5 seconds
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
                battle_log.append("")  # spacer

                battle_winner = check_winner_after_turn()
                if battle_winner is not None:
                    mode = "result"
                else:
                    turn_index += 1
                    next_step_ms = now_ms + intermission_ms

        # DRAW
        screen.fill(BG)

        if mode == "select":
            draw_text(screen, huge, "Choose Characters", 50, 60, ACCENT)
            draw_text(screen, font, "Press R anytime to restart. Then you plan your 12 turns.", 50, 110, (180, 180, 200))

            # Player selector
            pygame.draw.rect(screen, PANEL, pygame.Rect(50, 150, 420, 90), border_radius=12)
            pygame.draw.rect(screen, (60, 60, 90), pygame.Rect(50, 150, 420, 90), 2, border_radius=12)
            draw_text(screen, big, "Player Character", 70, 160, TEXT)
            draw_button(btn_p_prev, "<", False, True)
            draw_button(btn_p_next, ">", False, True)
            draw_text(screen, big, character_label(characters[player_char_idx]), 130, 185, ACCENT)

            # CPU selector
            pygame.draw.rect(screen, PANEL, pygame.Rect(50, 270, 420, 90), border_radius=12)
            pygame.draw.rect(screen, (60, 60, 90), pygame.Rect(50, 270, 420, 90), 2, border_radius=12)
            draw_text(screen, big, "CPU Character", 70, 280, TEXT)
            draw_button(btn_c_prev, "<", False, True)
            draw_button(btn_c_next, ">", False, True)
            draw_text(screen, big, cpu_choice_label(), 130, 305, ACCENT)

            draw_text(
                screen,
                font,
                "Tip: Red gets 6 Attacks in planning. Others change battle rules during playback.",
                50,
                390,
                (180, 180, 200),
            )

            pygame.draw.rect(screen, (35, 35, 45), btn_to_plan, border_radius=14)
            pygame.draw.rect(screen, ACCENT, btn_to_plan, 2, border_radius=14)
            draw_text(screen, huge, "PLAN TURNS", btn_to_plan.x + 70, btn_to_plan.y + 12, ACCENT)

        elif mode == "plan":
            p_char = characters[player_char_idx]
            cpu_choice = cpu_options[cpu_char_idx]

            cpu_display = "CPU Auto" if cpu_choice is None else character_label(cpu_choice)

            draw_text(screen, big, "Command Battle — Plan 12 Turns", 50, 40, ACCENT)
            draw_text(screen, font, "Left-click a slot to place the selected command. Right-click a slot to erase.", 50, 80)
            draw_text(screen, font, "Select a command on the right, then fill ALL 12 slots.", 50, 105)
            draw_text(screen, font, f"Player: {player_name} — {character_label(p_char)}", 50, 130, (180, 180, 200))
            draw_text(screen, font, f"CPU: {cpu_name} — {cpu_display}", 50, 150, (180, 180, 200))

            # Slots
            for i in range(12):
                r = slot_rect(i)
                pygame.draw.rect(screen, PANEL, r, border_radius=8)
                pygame.draw.rect(screen, (60, 60, 90), r, 2, border_radius=8)
                draw_text(screen, font, f"{i+1}", r.x + 6, r.y + 6, (180, 180, 200))
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
            draw_text(screen, font, "Rules: 3 Hearts | A=5/6 | B=2 | C=1 | I=Idle", 50, y)
            draw_text(screen, font, "1.5s delay between turns | Press R to return to character select", 50, y + 24)

        else:
            header = "Battle Playback" if mode == "battle" else "Battle Results"
            draw_text(screen, big, header, 50, 30, ACCENT)
            draw_text(screen, font, "Scroll log: wheel over log / ↑↓ / PgUp PgDn / End. Press R to restart.", 50, 60, (180, 180, 200))
            draw_text(screen, font, f"{player.name}: {character_label(player.character)}", 50, 80, (180, 180, 200))
            draw_text(screen, font, f"{cpu.name}: {character_label(cpu.character)}", 420, 80, (180, 180, 200))

            # Turn card
            card = pygame.Rect(50, 90, 800, 150)
            pygame.draw.rect(screen, PANEL, card, border_radius=12)
            pygame.draw.rect(screen, (60, 60, 90), card, 2, border_radius=12)

            draw_text(screen, big, turn_title, 65, 110, TEXT)

            wrapped = wrap_two_lines(turn_text, 78)
            draw_text(screen, font, wrapped[0], 65, 150, TEXT)
            if len(wrapped) > 1:
                draw_text(screen, font, wrapped[1], 65, 170, TEXT)

            draw_text(screen, font, hearts_line, 65, 190, ACCENT)
            draw_text(screen, font, pressure_line, 65, 215, ACCENT)

            if mode == "result":
                winner_text = battle_winner if battle_winner is not None else "No winner"
                draw_text(screen, huge, f"Winner: {winner_text}", 50, 255, ACCENT)
                draw_text(screen, big, f"Reason: {battle_reason}", 50, 310, TEXT)

            pygame.draw.rect(screen, PANEL, log_panel, border_radius=12)
            pygame.draw.rect(screen, (60, 60, 90), log_panel, 2, border_radius=12)

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
                    (180, 180, 200),
                )

        pygame.display.flip()
