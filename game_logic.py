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


@dataclass
class Fighter:
    name: str
    hearts: float = 3.0
    skip_next: bool = False  # for failed counter recovery
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
    # Handle skip_next (recovery)
    p_cmd = Command.NONE if player.skip_next else planned_p
    c_cmd = Command.NONE if cpu.skip_next else planned_c

    # Clear skip flags once applied
    player.skip_next = False
    cpu.skip_next = False

    p_damage = 0.0
    c_damage = 0.0
    text_parts: List[str] = []

    # Helpers for "answered back" tracking
    player.dealt_damage_last_turn = False
    cpu.dealt_damage_last_turn = False

    # Rules:
    # - Attack landed deals 1
    # - Block reduces incoming attack to 0.5
    # - Counter vs Attack reflects 1 damage to attacker, countering takes 0
    # - Counter vs non-attack: counter user skips next turn
    # - Attack vs Attack: both fail (0)
    # - IDLE means intentional no action
    # - NONE means forced skip (recovery)

    # Make recovery visible
    if p_cmd == Command.NONE:
        text_parts.append(f"{player.name} is recovering (SKIP).")
    if c_cmd == Command.NONE:
        text_parts.append(f"{cpu.name} is recovering (SKIP).")

    # Quick “no action” clarity (does not affect damage/pressure)
    if p_cmd == Command.IDLE and c_cmd == Command.IDLE:
        text_parts.append("Both idled.")

    # Attack vs Attack
    if p_cmd == Command.ATTACK and c_cmd == Command.ATTACK:
        text_parts.append("Both attacked—clash! No damage.")
        return TurnOutcome(turn_index, p_cmd, c_cmd, 0.0, 0.0, " ".join(text_parts))

    # Counter checks first (because it can negate an attack)
    # Player counter
    if p_cmd == Command.COUNTER:
        if c_cmd == Command.ATTACK:
            c_damage += 1.0
            player.dealt_damage_last_turn = True
            text_parts.append(f"{player.name} COUNTERED! {cpu.name} takes 1.")
        else:
            player.skip_next = True
            text_parts.append(f"{player.name} countered too early—recovery next turn.")

    # CPU counter
    if c_cmd == Command.COUNTER:
        if p_cmd == Command.ATTACK:
            p_damage += 1.0
            cpu.dealt_damage_last_turn = True
            text_parts.append(f"{cpu.name} COUNTERED! {player.name} takes 1.")
        else:
            cpu.skip_next = True
            text_parts.append(f"{cpu.name} countered too early—recovery next turn.")

    # Attacks (only apply if not negated by being countered)
    player_attack_negated = (c_cmd == Command.COUNTER and p_cmd == Command.ATTACK)
    cpu_attack_negated = (p_cmd == Command.COUNTER and c_cmd == Command.ATTACK)

    if p_cmd == Command.ATTACK and not player_attack_negated:
        if c_cmd == Command.BLOCK:
            c_damage += 0.5
            player.dealt_damage_last_turn = True
            text_parts.append(f"{player.name} ATTACK hits a BLOCK: {cpu.name} takes 0.5.")
        elif c_cmd in (Command.NONE, Command.IDLE, Command.ATTACK, Command.COUNTER):
            c_damage += 1.0
            player.dealt_damage_last_turn = True
            text_parts.append(f"{player.name} ATTACK lands: {cpu.name} takes 1.")

    if c_cmd == Command.ATTACK and not cpu_attack_negated:
        if p_cmd == Command.BLOCK:
            p_damage += 0.5
            cpu.dealt_damage_last_turn = True
            text_parts.append(f"{cpu.name} ATTACK hits a BLOCK: {player.name} takes 0.5.")
        elif p_cmd in (Command.NONE, Command.IDLE, Command.ATTACK, Command.COUNTER):
            p_damage += 1.0
            cpu.dealt_damage_last_turn = True
            text_parts.append(f"{cpu.name} ATTACK lands: {player.name} takes 1.")

    # Pressure update
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

    # If literally nothing happened besides idle/skip messaging, be explicit
    if not any(("takes" in s or "clash" in s or "COUNTERED" in s or "hits" in s or "lands" in s) for s in text_parts):
        # Keep a clean fallback that doesn’t overwrite recovery/idle notes
        if not text_parts:
            text_parts.append("No damage this turn.")

    return TurnOutcome(turn_index, p_cmd, c_cmd, p_damage, c_damage, " ".join(text_parts))


def run_battle(
    player_name: str,
    cpu_name: str,
    player_plan: List[Command],
    cpu_plan: List[Command],
    seed: Optional[int] = None,
) -> BattleResult:
    if seed is not None:
        random.seed(seed)

    player = Fighter(player_name)
    cpu = Fighter(cpu_name)
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
