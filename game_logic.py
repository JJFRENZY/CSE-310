from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import random


class Command(str, Enum):
    ATTACK = "A"
    BLOCK = "B"
    COUNTER = "C"
    IDLE = "I"     # player-chosen "do nothing"
    NONE = "-"     # forced skip (recovery turn)


class Character(str, Enum):
    NORMAL = "Normal"

    RED_FIGHTER = "Red (Fighter)"       # +1 Attack allowed (6 total) [enforced in UI/AI]
    BLUE_HIJUMP = "Blue (Hi-Jump)"      # failed Counter -> invincible during recovery turn
    BROWN_STONE = "Brown (Stone)"       # Block takes 0 damage
    GREEN_PLASMA = "Green (Plasma)"     # successful Block/Counter vs Attack deals +0.5 to attacker
    WHITE_MIRROR = "White (Mirror)"     # successful Counter deals 2 hearts
    ORANGE_FIRE = "Orange (Fire)"       # Attacks still land against opponent's Counter
    YELLOW_BEAM = "Yellow (Beam)"       # if both IDLE same turn, opponent takes 1 (not on forced skip)
    PURPLE_NINJA = "Purple (Ninja)"     # Attack vs Attack: opponent still takes 0.5


def get_command_limits(character: Character) -> dict[Command, int]:
    """
    Command limits for planning. (UI/AI should use this.)
    NOTE: IDLE is effectively unlimited.
    """
    attacks = 6 if character == Character.RED_FIGHTER else 5
    return {
        Command.ATTACK: attacks,
        Command.BLOCK: 2,
        Command.COUNTER: 1,
        # IDLE unlimited; NONE is forced-only
    }


@dataclass
class Fighter:
    name: str
    character: Character = Character.NORMAL

    hearts: float = 3.0
    skip_next: bool = False                # for failed counter recovery
    skip_reason: Optional[str] = None      # e.g., "failed_counter"

    # "stage pressure" system: taking hits without answering back increases pressure
    pressure: int = 0
    dealt_damage_last_turn: bool = False


@dataclass
class BattleResult:
    winner: Optional[str]
    reason: str
    log: List[str] = field(default_factory=list)


@dataclass
class TurnOutcome:
    turn_index: int
    p_cmd: Command
    c_cmd: Command
    p_delta: float
    c_delta: float
    text: str


def apply_damage(target: Fighter, amount: float) -> None:
    target.hearts = max(0.0, target.hearts - amount)


def resolve_turn(
    turn_index: int,
    player: Fighter,
    cpu: Fighter,
    planned_p: Command,
    planned_c: Command,
) -> TurnOutcome:
    """
    Resolves one turn.

    Character mechanics implemented:
    - Red (Fighter): handled via planning limits (UI/AI) -> get_command_limits()
    - Blue (Hi-Jump): failed counter => recovery turn is invincible
    - Brown (Stone): block takes 0 damage
    - Green (Plasma): successful block/counter vs attack => +0.5 damage to attacker
    - White (Mirror): successful counter deals 2 damage
    - Orange (Fire): attacks still land against opponent counter
    - Yellow (Beam): both idle => opponent takes 1 (not if either is forced skip)
    - Purple (Ninja): attack vs attack => opponent still takes 0.5 (for the Purple fighter)
    """

    # Determine if this turn is a forced skip, and whether it is invincible (Blue)
    p_invincible = False
    c_invincible = False

    if player.skip_next:
        if player.character == Character.BLUE_HIJUMP and player.skip_reason == "failed_counter":
            p_invincible = True
        p_cmd = Command.NONE
    else:
        p_cmd = planned_p

    if cpu.skip_next:
        if cpu.character == Character.BLUE_HIJUMP and cpu.skip_reason == "failed_counter":
            c_invincible = True
        c_cmd = Command.NONE
    else:
        c_cmd = planned_c

    # Clear skip flags once applied
    player.skip_next = False
    cpu.skip_next = False
    player.skip_reason = None
    cpu.skip_reason = None

    p_damage = 0.0
    c_damage = 0.0
    text_parts: List[str] = []

    # Reset "dealt damage" flags for pressure tracking
    player.dealt_damage_last_turn = False
    cpu.dealt_damage_last_turn = False

    # Make recovery visible
    if p_cmd == Command.NONE:
        if p_invincible:
            text_parts.append(f"{player.name} is recovering (SKIP) — INVINCIBLE!")
        else:
            text_parts.append(f"{player.name} is recovering (SKIP).")

    if c_cmd == Command.NONE:
        if c_invincible:
            text_parts.append(f"{cpu.name} is recovering (SKIP) — INVINCIBLE!")
        else:
            text_parts.append(f"{cpu.name} is recovering (SKIP).")

    # Yellow Beam: both IDLE (must be intentional idles, not forced skips)
    if p_cmd == Command.IDLE and c_cmd == Command.IDLE:
        if player.character == Character.YELLOW_BEAM:
            c_damage += 1.0
            player.dealt_damage_last_turn = True
            text_parts.append(f"{player.name}'s BEAM triggers on double IDLE: {cpu.name} takes 1.")
        if cpu.character == Character.YELLOW_BEAM:
            p_damage += 1.0
            cpu.dealt_damage_last_turn = True
            text_parts.append(f"{cpu.name}'s BEAM triggers on double IDLE: {player.name} takes 1.")
        # Beam does NOT apply if either is Command.NONE (forced skip), matching your rule.

    # Purple Ninja: Attack vs Attack special case
    if p_cmd == Command.ATTACK and c_cmd == Command.ATTACK:
        text_parts.append("Both attacked—clash!")

        if player.character == Character.PURPLE_NINJA:
            c_damage += 0.5
            player.dealt_damage_last_turn = True
            text_parts.append(f"{player.name}'s NINJA technique clips through: {cpu.name} takes 0.5.")

        if cpu.character == Character.PURPLE_NINJA:
            p_damage += 0.5
            cpu.dealt_damage_last_turn = True
            text_parts.append(f"{cpu.name}'s NINJA technique clips through: {player.name} takes 0.5.")

        # Apply invincibility (Blue recovery) if relevant
        if p_invincible:
            p_damage = 0.0
        if c_invincible:
            c_damage = 0.0

        apply_damage(player, p_damage)
        apply_damage(cpu, c_damage)

        def update_pressure(f: Fighter, took: float, dealt: bool) -> None:
            if took > 0 and not dealt:
                f.pressure += 1
            elif dealt:
                f.pressure = max(0, f.pressure - 1)
            else:
                f.pressure = max(0, f.pressure - 1)

        update_pressure(player, p_damage, player.dealt_damage_last_turn)
        update_pressure(cpu, c_damage, cpu.dealt_damage_last_turn)

        return TurnOutcome(turn_index, p_cmd, c_cmd, p_damage, c_damage, " ".join(text_parts))

    # === Counter resolution first (it can negate attacks unless Fire overrides) ===

    def counter_damage(counter_user: Fighter) -> float:
        return 2.0 if counter_user.character == Character.WHITE_MIRROR else 1.0

    # Player counter
    if p_cmd == Command.COUNTER:
        if c_cmd == Command.ATTACK:
            dmg = counter_damage(player)
            c_damage += dmg
            player.dealt_damage_last_turn = True
            text_parts.append(f"{player.name} COUNTERED! {cpu.name} takes {dmg:g}.")

            # Green Plasma: successful counter that shields vs attack -> +0.5 to attacker
            # (But if attacker is Orange Fire, the counter does NOT shield, so no Plasma bonus.)
            if player.character == Character.GREEN_PLASMA and cpu.character != Character.ORANGE_FIRE:
                c_damage += 0.5
                text_parts.append(f"{player.name}'s PLASMA adds +0.5: {cpu.name} takes 0.5 more.")
        else:
            player.skip_next = True
            player.skip_reason = "failed_counter"
            text_parts.append(f"{player.name} countered too early—recovery next turn.")

    # CPU counter
    if c_cmd == Command.COUNTER:
        if p_cmd == Command.ATTACK:
            dmg = counter_damage(cpu)
            p_damage += dmg
            cpu.dealt_damage_last_turn = True
            text_parts.append(f"{cpu.name} COUNTERED! {player.name} takes {dmg:g}.")

            if cpu.character == Character.GREEN_PLASMA and player.character != Character.ORANGE_FIRE:
                p_damage += 0.5
                text_parts.append(f"{cpu.name}'s PLASMA adds +0.5: {player.name} takes 0.5 more.")
        else:
            cpu.skip_next = True
            cpu.skip_reason = "failed_counter"
            text_parts.append(f"{cpu.name} countered too early—recovery next turn.")

    # Attacks: determine whether they are negated by counter
    # Normal rule: Attack is negated if opponent used Counter successfully against it.
    # Orange Fire: Attacks still land against an opponent's Counter (so NOT negated).
    player_attack_negated = (
        c_cmd == Command.COUNTER
        and p_cmd == Command.ATTACK
        and player.character != Character.ORANGE_FIRE
    )
    cpu_attack_negated = (
        p_cmd == Command.COUNTER
        and c_cmd == Command.ATTACK
        and cpu.character != Character.ORANGE_FIRE
    )

    # === Attack application ===

    # Player attack
    if p_cmd == Command.ATTACK and not player_attack_negated:
        if c_cmd == Command.BLOCK:
            # Defender damage depends on Stone
            blocked_damage = 0.0 if cpu.character == Character.BROWN_STONE else 0.5

            if blocked_damage == 0.0:
                text_parts.append(f"{player.name} ATTACK hits STONE BLOCK: {cpu.name} takes 0.")
            else:
                c_damage += blocked_damage
                player.dealt_damage_last_turn = True
                text_parts.append(f"{player.name} ATTACK hits a BLOCK: {cpu.name} takes 0.5.")

            # Green Plasma: any successful block that shields vs an attack retaliates for 0.5
            if cpu.character == Character.GREEN_PLASMA:
                p_damage += 0.5
                cpu.dealt_damage_last_turn = True
                text_parts.append(f"{cpu.name}'s PLASMA shocks back: {player.name} takes 0.5.")

        elif c_cmd in (Command.NONE, Command.IDLE, Command.ATTACK, Command.COUNTER):
            c_damage += 1.0
            player.dealt_damage_last_turn = True
            text_parts.append(f"{player.name} ATTACK lands: {cpu.name} takes 1.")

    # CPU attack
    if c_cmd == Command.ATTACK and not cpu_attack_negated:
        if p_cmd == Command.BLOCK:
            blocked_damage = 0.0 if player.character == Character.BROWN_STONE else 0.5

            if blocked_damage == 0.0:
                text_parts.append(f"{cpu.name} ATTACK hits STONE BLOCK: {player.name} takes 0.")
            else:
                p_damage += blocked_damage
                cpu.dealt_damage_last_turn = True
                text_parts.append(f"{cpu.name} ATTACK hits a BLOCK: {player.name} takes 0.5.")

            if player.character == Character.GREEN_PLASMA:
                c_damage += 0.5
                player.dealt_damage_last_turn = True
                text_parts.append(f"{player.name}'s PLASMA shocks back: {cpu.name} takes 0.5.")

        elif p_cmd in (Command.NONE, Command.IDLE, Command.ATTACK, Command.COUNTER):
            p_damage += 1.0
            cpu.dealt_damage_last_turn = True
            text_parts.append(f"{cpu.name} ATTACK lands: {player.name} takes 1.")

    # Apply invincibility after all damage computed
    if p_invincible and p_damage > 0:
        text_parts.append(f"{player.name} takes no damage due to invincibility.")
        p_damage = 0.0
    if c_invincible and c_damage > 0:
        text_parts.append(f"{cpu.name} takes no damage due to invincibility.")
        c_damage = 0.0

    def update_pressure(f: Fighter, took: float, dealt: bool) -> None:
        if took > 0 and not dealt:
            f.pressure += 1
        elif dealt:
            f.pressure = max(0, f.pressure - 1)
        else:
            f.pressure = max(0, f.pressure - 1)

    # Apply damages
    apply_damage(player, p_damage)
    apply_damage(cpu, c_damage)

    update_pressure(player, p_damage, player.dealt_damage_last_turn)
    update_pressure(cpu, c_damage, cpu.dealt_damage_last_turn)

    # Fallback if nothing meaningful happened
    if not any(
        (
            "takes" in s
            or "clash" in s
            or "COUNTERED" in s
            or "hits" in s
            or "lands" in s
            or "BEAM" in s
            or "PLASMA" in s
        )
        for s in text_parts
    ):
        if not text_parts:
            text_parts.append("No damage this turn.")

    return TurnOutcome(turn_index, p_cmd, c_cmd, p_damage, c_damage, " ".join(text_parts))


def run_battle(
    player_name: str,
    cpu_name: str,
    player_plan: List[Command],
    cpu_plan: List[Command],
    player_character: Character = Character.NORMAL,
    cpu_character: Character = Character.NORMAL,
    seed: Optional[int] = None,
) -> BattleResult:
    """
    Runs a 12-turn battle and returns a BattleResult.

    Backward compatible:
    - If you don't pass characters, both default to NORMAL.
    - UI can later pass chosen player_character / cpu_character.
    """
    if seed is not None:
        random.seed(seed)

    player = Fighter(player_name, character=player_character)
    cpu = Fighter(cpu_name, character=cpu_character)

    log: List[str] = []
    winner: Optional[str] = None
    reason = "Battle ended."

    for t in range(12):
        out = resolve_turn(t + 1, player, cpu, player_plan[t], cpu_plan[t])
        log.append(f"Turn {out.turn_index}: P[{out.p_cmd.value}] vs CPU[{out.c_cmd.value}] -> {out.text}")
        log.append(f"    Hearts: {player.name}={player.hearts} | {cpu.name}={cpu.hearts}")
        log.append(f"    Pressure: {player.name}={player.pressure} | {cpu.name}={cpu.pressure}")

        # KO by hearts
        if player.hearts <= 0 and cpu.hearts <= 0:
            winner = None
            reason = "Double KO!"
            break
        if cpu.hearts <= 0:
            winner = player.name
            reason = "Opponent hearts reached 0."
            break
        if player.hearts <= 0:
            winner = cpu.name
            reason = "Player hearts reached 0."
            break

        # Knockoff by pressure (stage loss)
        if cpu.pressure >= 4:
            winner = player.name
            reason = "Opponent was knocked off the stage (pressure)."
            break
        if player.pressure >= 4:
            winner = cpu.name
            reason = "Player was knocked off the stage (pressure)."
            break

    # Sudden Death
    if winner is None and player.hearts > 0 and cpu.hearts > 0:
        log.append("Sudden Death! Each fighter has a 50% chance to land a KO strike.")
        if random.random() < 0.5:
            winner = player.name
            reason = "Sudden Death KO strike landed by player."
        else:
            winner = cpu.name
            reason = "Sudden Death KO strike landed by CPU."

    return BattleResult(winner=winner, reason=reason, log=log)
