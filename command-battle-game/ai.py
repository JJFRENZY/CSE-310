from __future__ import annotations
from typing import List
import random
from game_logic import Command


def build_cpu_plan(player_plan: List[Command]) -> List[Command]:
    """
    Basic rule-based CPU plan (now supports IDLE):
    - Try to counter a turn where the player is likely to attack.
    - Use blocks around mid-game and on likely player attack turns.
    - Use up to 5 attacks on remaining turns.
    - Any leftover turns become IDLE (I), not NONE (-).
      (NONE is reserved for forced recovery turns.)
    """
    plan = [Command.IDLE] * 12

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

    # Place blocks: prefer turns 5-9
    candidate_blocks = list(range(4, 9))
    random.shuffle(candidate_blocks)
    for idx in candidate_blocks:
        if remaining[Command.BLOCK] <= 0:
            break
        if plan[idx] == Command.IDLE:
            plan[idx] = Command.BLOCK
            remaining[Command.BLOCK] -= 1

    # If blocks remain, try to block on player attack turns not already used
    for idx in likely_attack_turns:
        if remaining[Command.BLOCK] <= 0:
            break
        if plan[idx] == Command.IDLE:
            plan[idx] = Command.BLOCK
            remaining[Command.BLOCK] -= 1

    # Fill attacks on random idle turns
    empty = [i for i, c in enumerate(plan) if c == Command.IDLE]
    random.shuffle(empty)
    for idx in empty:
        if remaining[Command.ATTACK] <= 0:
            break
        plan[idx] = Command.ATTACK
        remaining[Command.ATTACK] -= 1

    return plan
