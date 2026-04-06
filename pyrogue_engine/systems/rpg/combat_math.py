"""
Combat Math - Pure, unit-testable damage calculations.

No game state mutations. All functions are pure math functions.
"""

import random
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class DamageRoll:
    """Result of a damage calculation."""
    base_damage: int
    modifiers: int = 0
    resistance: int = 0
    critical: bool = False
    dodged: bool = False
    final_damage: int = 0

    def __post_init__(self):
        """Calculate final damage."""
        if self.dodged:
            self.final_damage = 0
        else:
            self.final_damage = max(0, self.base_damage + self.modifiers - self.resistance)
            if self.critical:
                self.final_damage = int(self.final_damage * 1.5)


def calculate_damage(
    base_damage: int,
    stat_modifier: int = 0,
    armor_value: int = 0,
    damage_type: str = "physical",
    crit_chance: float = 0.2,
    dodge_chance: float = 0.0,
) -> DamageRoll:
    """
    Calculate final damage after modifiers and armor.

    Args:
        base_damage: Starting damage value
        stat_modifier: Attacker's stat modifier (e.g., strength or agility bonus)
        armor_value: Target's armor/defense (flat damage reduction)
        damage_type: Type of damage (physical, fire, ice, etc.)
        crit_chance: Probability of critical hit (0.0-1.0)
        dodge_chance: Probability of dodging (0.0-1.0)

    Returns:
        DamageRoll with final damage
    """
    # Check dodge first
    is_dodged = random.random() < dodge_chance

    # Critical hit chance
    is_critical = random.random() < crit_chance and not is_dodged

    return DamageRoll(
        base_damage=base_damage,
        modifiers=stat_modifier,
        resistance=armor_value,
        critical=is_critical,
        dodged=is_dodged,
    )


def apply_damage_type_resistance(damage: int, damage_type: str, resistances: dict) -> int:
    """
    Apply damage type specific resistances.

    Args:
        damage: Base damage
        damage_type: Type (fire, ice, physical, etc.)
        resistances: Dict of {type: resistance_value}

    Returns:
        Final damage after resistance
    """
    if not resistances:
        return damage

    resist = resistances.get(damage_type, 0)
    return max(0, damage - resist)


def calculate_critical_hit(base_damage: int, crit_chance: float = 0.2, crit_multiplier: float = 1.5) -> Tuple[int, bool]:
    """
    Calculate if a hit is critical and damage multiplier.

    Args:
        base_damage: Base damage value
        crit_chance: Probability of crit (0.0-1.0)
        crit_multiplier: Damage multiplier on crit (e.g., 1.5x for 50% bonus)

    Returns:
        (final_damage, is_critical)
    """
    is_critical = random.random() < crit_chance
    final_damage = int(base_damage * crit_multiplier) if is_critical else base_damage
    return final_damage, is_critical


def calculate_dodge(base_dodge_chance: float, agility: int = 0) -> bool:
    """
    Calculate if an attack is dodged.

    Args:
        base_dodge_chance: Base dodge probability (0.0-1.0)
        agility: Agility stat (increases dodge by 1% per point)

    Returns:
        True if dodged, False if hit
    """
    final_dodge_chance = base_dodge_chance + (agility * 0.01)
    final_dodge_chance = min(0.9, final_dodge_chance)  # Cap at 90%
    return random.random() < final_dodge_chance


def calculate_healing(base_healing: int, healer_stats: Optional[dict] = None) -> int:
    """
    Calculate final healing amount.

    Args:
        base_healing: Starting healing value
        healer_stats: Dict with stat modifiers (e.g., {"wisdom": 5})

    Returns:
        Final healing amount
    """
    healer_stats = healer_stats or {}

    modifiers = 0
    if healer_stats:
        # Sum all healing/support stats
        modifiers = sum(v for k, v in healer_stats.items() if 'wisdom' in k or 'healing' in k)

    return max(1, base_healing + modifiers)
