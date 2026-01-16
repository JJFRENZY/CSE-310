import pygame
from typing import List, Optional
from game_logic import Command, run_battle
from ai import build_cpu_plan



WIDTH, HEIGHT = 900, 540
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


def command_label(cmd: Command) -> str:
    return {"A": "ATTACK", "B": "BLOCK", "C": "COUNTER", "-": "SKIP"}.get(cmd.value, "?")


def run_game(player_name: str = "Player", cpu_name: str = "CPU") -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Command Battle (12 Turns)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 26)
    big = pygame.font.SysFont(None, 40)

    # Planning state
    plan: List[Optional[Command]] = [None] * 12
    remaining = {Command.ATTACK: 5, Command.BLOCK: 2, Command.COUNTER: 1}

    selected: Optional[Command] = None
    mode = "plan"
    battle_log: List[str] = []
    battle_winner = ""
    battle_reason = ""

    def can_place(cmd: Command) -> bool:
        return remaining.get(cmd, 0) > 0

    def place_at(i: int, cmd: Command) -> None:
        nonlocal remaining
        if plan[i] is None and can_place(cmd):
            plan[i] = cmd
            remaining[cmd] -= 1

    def erase_at(i: int) -> None:
        nonlocal remaining
        if plan[i] is not None:
            old = plan[i]
            plan[i] = None
            remaining[old] += 1

    # Slot positions
    start_x = 50
    start_y = 140

    def slot_rect(i: int) -> pygame.Rect:
        row = i // 6
        col = i % 6
        x = start_x + col * (SLOT_W + SLOT_GAP)
        y = start_y + row * (SLOT_H + SLOT_GAP)
        return pygame.Rect(x, y, SLOT_W, SLOT_H)

    # Simple button rects
    btn_attack = pygame.Rect(520, 160, 320, 50)
    btn_block = pygame.Rect(520, 220, 320, 50)
    btn_counter = pygame.Rect(520, 280, 320, 50)
    btn_start = pygame.Rect(520, 360, 320, 60)

    while True:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

            if mode == "plan":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos

                    if btn_attack.collidepoint(mx, my):
                        selected = Command.ATTACK
                    elif btn_block.collidepoint(mx, my):
                        selected = Command.BLOCK
                    elif btn_counter.collidepoint(mx, my):
                        selected = Command.COUNTER
                    elif btn_start.collidepoint(mx, my):
                        if all(c is not None for c in plan):
                            # Start battle
                            player_plan = [c for c in plan]  # type: ignore
                            cpu_plan = build_cpu_plan(player_plan)
                            result = run_battle(player_name, cpu_name, player_plan, cpu_plan)
                            battle_log = result.log
                            battle_winner = result.winner or "No winner"
                            battle_reason = result.reason
                            mode = "result"
                        else:
                            # do nothing; message is drawn
                            pass
                    else:
                        # Click slots to place/erase
                        for i in range(12):
                            r = slot_rect(i)
                            if r.collidepoint(mx, my):
                                if event.button == 3:  # right click erase
                                    erase_at(i)
                                else:
                                    if selected is not None:
                                        place_at(i, selected)
                                break

            elif mode == "result":
                if event.type == pygame.KEYDOWN:
                    # Press R to reset
                    if event.key == pygame.K_r:
                        plan = [None] * 12
                        remaining = {Command.ATTACK: 5, Command.BLOCK: 2, Command.COUNTER: 1}
                        selected = None
                        battle_log = []
                        battle_winner = ""
                        battle_reason = ""
                        mode = "plan"

        # Draw
        screen.fill(BG)

        if mode == "plan":
            draw_text(screen, big, "Command Battle — Plan 12 Turns", 50, 40, ACCENT)
            draw_text(screen, font, "Left-click a slot to place the selected command. Right-click a slot to erase.", 50, 80)
            draw_text(screen, font, "Select a command on the right, then fill ALL 12 slots.", 50, 105)

            # Slots
            for i in range(12):
                r = slot_rect(i)
                pygame.draw.rect(screen, PANEL, r, border_radius=8)
                pygame.draw.rect(screen, (60, 60, 90), r, 2, border_radius=8)
                draw_text(screen, font, f"{i+1}", r.x + 6, r.y + 6, (180, 180, 200))
                if plan[i] is not None:
                    cmd = plan[i]
                    draw_text(screen, big, cmd.value, r.x + 22, r.y + 18, ACCENT)

            # Buttons
            def draw_button(rect: pygame.Rect, label: str, active: bool, enabled: bool):
                color = ACCENT if active else (90, 90, 120)
                base = (30, 40, 45) if enabled else (25, 25, 30)
                pygame.draw.rect(screen, base, rect, border_radius=10)
                pygame.draw.rect(screen, color if enabled else (70, 70, 80), rect, 2, border_radius=10)
                draw_text(screen, big, label, rect.x + 12, rect.y + 10, color if enabled else (140, 140, 150))

            draw_button(btn_attack, f"Attack (A) — left: {remaining[Command.ATTACK]}", selected == Command.ATTACK, remaining[Command.ATTACK] > 0)
            draw_button(btn_block, f"Block (B) — left: {remaining[Command.BLOCK]}", selected == Command.BLOCK, remaining[Command.BLOCK] > 0)
            draw_button(btn_counter, f"Counter (C) — left: {remaining[Command.COUNTER]}", selected == Command.COUNTER, remaining[Command.COUNTER] > 0)

            all_filled = all(c is not None for c in plan)
            pygame.draw.rect(screen, (35, 35, 45), btn_start, border_radius=12)
            pygame.draw.rect(screen, ACCENT if all_filled else WARN, btn_start, 2, border_radius=12)
            draw_text(screen, big, "START BATTLE", btn_start.x + 70, btn_start.y + 15, ACCENT if all_filled else WARN)

            if not all_filled:
                draw_text(screen, font, "Fill all 12 turns to start.", 520, 430, WARN)

            # Rules summary
            y = 460
            draw_text(screen, font, "Rules: 3 Hearts | A=5 (1 dmg) | B=2 (0.5 dmg vs A) | C=1 (reflects 1 vs A, else skip next)", 50, y)
            draw_text(screen, font, "A vs A = no damage | 12 turns then Sudden Death | Pressure knockoff if you keep taking hits without answering back", 50, y + 24)

        else:
            draw_text(screen, big, "Battle Results", 50, 30, ACCENT)
            draw_text(screen, big, f"Winner: {battle_winner}", 50, 80, TEXT)
            draw_text(screen, font, f"Reason: {battle_reason}", 50, 125, TEXT)
            draw_text(screen, font, "Press R to plan again.", 50, 155, ACCENT)

            # Log panel
            panel = pygame.Rect(50, 190, 800, 310)
            pygame.draw.rect(screen, PANEL, panel, border_radius=12)
            pygame.draw.rect(screen, (60, 60, 90), panel, 2, border_radius=12)

            # show last N lines
            lines = battle_log[-14:]
            y = panel.y + 14
            for line in lines:
                draw_text(screen, font, line[:110], panel.x + 14, y, TEXT)
                y += 22

        pygame.display.flip()
