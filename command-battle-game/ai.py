from __future__ import annotations
from typing import List
import random
from game_logic import Command


def build_cpu_plan(player_plan: List[Command]) -> List[Command]:
    """
    Basic rule-based CPU plan:
    - Try to counter turns where player is likely to attack (if player used many attacks early).
    - Use blocks around mid-game.
    - Fill remaining with attacks.
    Still obeys limits: A=5, B=2, C=1, rest NONE.
    """
    plan = [Command.NONE] * 12

    remaining = {
        Command.ATTACK: 5,
        Command.BLOCK: 2,
        Command.COUNTER: 1,
    }

    # Guess "hot" attack turns from player plan
    likely_attack_turns = [i for i, cmd in enumerate(player_plan) if cmd == Command.ATTACK]

    # Pick one likely attack turn to counter (if any)
    if likely_attack_turns and remaining[Command.COUNTER] > 0:
        idx = random.choice(likely_attack_turns)
        plan[idx] = Command.COUNTER
        remaining[Command.COUNTER] -= 1

    # Place blocks: prefer turns 5-9, and also where player attacks
    candidate_blocks = list(range(4, 9))
    random.shuffle(candidate_blocks)
    for idx in candidate_blocks:
        if remaining[Command.BLOCK] <= 0:
            break
        if plan[idx] == Command.NONE:
            plan[idx] = Command.BLOCK
            remaining[Command.BLOCK] -= 1

    # If blocks remain, try to block on player attack turns not already used
    for idx in likely_attack_turns:
        if remaining[Command.BLOCK] <= 0:
            break
        if plan[idx] == Command.NONE:
            plan[idx] = Command.BLOCK
            remaining[Command.BLOCK] -= 1

    # Fill attacks on random empty turns
    empty = [i for i, c in enumerate(plan) if c == Command.NONE]
    random.shuffle(empty)
    for idx in empty:
        if remaining[Command.ATTACK] <= 0:
            break
        plan[idx] = Command.ATTACK
        remaining[Command.ATTACK] -= 1

    return plan
