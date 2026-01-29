from __future__ import annotations
from typing import List, Optional
import random
from game_logic import Command, Character


def choose_cpu_character(
    *,
    player_character: Character,
    seed: Optional[int] = None,
) -> Character:
    """
    Pick a CPU character automatically.

    Simple approach:
    - Sometimes "counters" the player's style, sometimes random for variety.
    - You can tweak weights anytime.
    """
    if seed is not None:
        random.seed(seed)

    # A few light “matchup” ideas (not hard counters, just flavor)
    # You can change these anytime based on playtesting.
    suggested: List[Character]

    if player_character == Character.ORANGE_FIRE:
        # Fire makes counters less safe -> CPU likes Stone / Plasma / Mirror
        suggested = [Character.BROWN_STONE, Character.GREEN_PLASMA, Character.WHITE_MIRROR, Character.RED_FIGHTER]
    elif player_character == Character.WHITE_MIRROR:
        # Mirror counter is huge -> CPU likes Fire or Blue
        suggested = [Character.ORANGE_FIRE, Character.BLUE_HIJUMP, Character.BROWN_STONE]
    elif player_character == Character.YELLOW_BEAM:
        # Beam wants double idle -> CPU likes pressure tools
        suggested = [Character.RED_FIGHTER, Character.ORANGE_FIRE, Character.GREEN_PLASMA]
    elif player_character == Character.BLUE_HIJUMP:
        # Blue has safe recovery -> CPU likes Fire / Mirror
        suggested = [Character.ORANGE_FIRE, Character.WHITE_MIRROR, Character.GREEN_PLASMA]
    elif player_character == Character.BROWN_STONE:
        # Stone blocks hard -> CPU likes Fire / Mirror / Beam
        suggested = [Character.ORANGE_FIRE, Character.WHITE_MIRROR, Character.YELLOW_BEAM]
    elif player_character == Character.GREEN_PLASMA:
        suggested = [Character.WHITE_MIRROR, Character.BROWN_STONE, Character.RED_FIGHTER]
    elif player_character == Character.PURPLE_NINJA:
        suggested = [Character.RED_FIGHTER, Character.WHITE_MIRROR, Character.BLUE_HIJUMP]
    elif player_character == Character.RED_FIGHTER:
        suggested = [Character.WHITE_MIRROR, Character.BROWN_STONE, Character.BLUE_HIJUMP]
    else:
        suggested = [
            Character.RED_FIGHTER,
            Character.BLUE_HIJUMP,
            Character.BROWN_STONE,
            Character.GREEN_PLASMA,
            Character.WHITE_MIRROR,
            Character.ORANGE_FIRE,
            Character.YELLOW_BEAM,
            Character.PURPLE_NINJA,
        ]

    # 70%: pick from suggested, 30%: totally random for variety
    if random.random() < 0.70:
        return random.choice(suggested)

    all_choices = [
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
    return random.choice(all_choices)


def build_cpu_plan(
    player_plan: List[Command],
    *,
    cpu_character: Character = Character.NORMAL,
    player_character: Optional[Character] = None,  # reserved for future AI tweaks
    seed: Optional[int] = None,
) -> List[Command]:
    """
    Rule-based CPU plan (supports IDLE + Characters).

    Limits:
    - Base: ATTACK=5, BLOCK=2, COUNTER=1
    - Red (Fighter): ATTACK=6
    - Any leftover turns become IDLE (I), not NONE (-).
      (NONE is reserved for forced recovery turns only.)
    """
    if seed is not None:
        random.seed(seed)

    plan = [Command.IDLE] * 12

    # Character-based limits
    attack_limit = 6 if cpu_character == Character.RED_FIGHTER else 5

    remaining = {
        Command.ATTACK: attack_limit,
        Command.BLOCK: 2,
        Command.COUNTER: 1,
    }

    likely_attack_turns = [i for i, cmd in enumerate(player_plan) if cmd == Command.ATTACK]

    # Decide whether to use COUNTER at all
    use_counter = remaining[Command.COUNTER] > 0 and bool(likely_attack_turns)

    # Orange Fire: counter doesn't stop attacks, so counter is often a bad trade
    if cpu_character == Character.ORANGE_FIRE:
        use_counter = use_counter and (random.random() < 0.25)

    # White Mirror: counter is premium
    if cpu_character == Character.WHITE_MIRROR:
        use_counter = use_counter and True

    # 1) Counter one likely attack turn (if using counter)
    if use_counter:
        idx = random.choice(likely_attack_turns)
        plan[idx] = Command.COUNTER
        remaining[Command.COUNTER] -= 1

    # 2) Blocks
    # Brown Stone: block is perfect, so block on likely ATTACK turns first
    if cpu_character == Character.BROWN_STONE and likely_attack_turns:
        for idx in likely_attack_turns:
            if remaining[Command.BLOCK] <= 0:
                break
            if plan[idx] == Command.IDLE:
                plan[idx] = Command.BLOCK
                remaining[Command.BLOCK] -= 1

    # Prefer mid-game blocks (0-indexed 4..8)
    candidate_blocks = list(range(4, 9))
    random.shuffle(candidate_blocks)
    for idx in candidate_blocks:
        if remaining[Command.BLOCK] <= 0:
            break
        if plan[idx] == Command.IDLE:
            plan[idx] = Command.BLOCK
            remaining[Command.BLOCK] -= 1

    # Any remaining blocks go onto player ATTACK turns
    for idx in likely_attack_turns:
        if remaining[Command.BLOCK] <= 0:
            break
        if plan[idx] == Command.IDLE:
            plan[idx] = Command.BLOCK
            remaining[Command.BLOCK] -= 1

    # 3) Yellow Beam: leave some idles where player idled (slight synergy chance)
    if cpu_character == Character.YELLOW_BEAM:
        idle_turns = [i for i, cmd in enumerate(player_plan) if cmd == Command.IDLE]
        random.shuffle(idle_turns)
        for idx in idle_turns[:2]:
            if plan[idx] == Command.IDLE:
                pass  # already idle

    # 4) Fill attacks
    empty = [i for i, c in enumerate(plan) if c == Command.IDLE]
    random.shuffle(empty)

    # Purple Ninja likes being attack-heavy a bit more (chip on A vs A), so bias earlier
    if cpu_character == Character.PURPLE_NINJA:
        empty.sort()

    for idx in empty:
        if remaining[Command.ATTACK] <= 0:
            break
        plan[idx] = Command.ATTACK
        remaining[Command.ATTACK] -= 1

    return plan
