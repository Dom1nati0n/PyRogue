"""
Threat Math - Pure threat calculation functions

These are isolated, testable functions that rank potential targets.
Completely decoupled from ECS and events.

Use in AwarenessSystem to score all visible enemies, pick the highest threat.
"""

from typing import NamedTuple
import math


class ThreatScore(NamedTuple):
    """Result of threat evaluation."""

    entity_id: int
    score: float
    distance: float
    health_percent: float
    is_aggroed: bool  # Already in combat with this target


def calculate_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Euclidean distance between two points.

    Args:
        x1, y1: First position
        x2, y2: Second position

    Returns:
        Distance in tiles (Euclidean)
    """
    dx = x2 - x1
    dy = y2 - y1
    return math.sqrt(dx * dx + dy * dy)


def calculate_threat_score(
    entity_id: int,
    distance: float,
    base_threat: float = 10.0,
    health_percent: float = 1.0,
    is_aggroed: bool = False
) -> ThreatScore:
    """
    Calculate threat priority score for a target.

    Higher score = higher priority target.

    Scoring Formula:
    - Base: (threat / distance) — closer threats are worse
    - Low health bonus: ×1.5 if below 25% health (finish them!)
    - Aggro bonus: ×1.2 if already in combat (don't switch targets)

    Args:
        entity_id: Entity ID of target
        distance: Distance to target (tiles, Euclidean)
        base_threat: Base threat level of target (e.g., 10 for regular enemy, 50 for boss)
        health_percent: Target's current HP as fraction (0.0 to 1.0)
        is_aggroed: True if attacker already in combat with this target

    Returns:
        ThreatScore with entity_id and computed score

    Example:
        # High-threat target far away
        score1 = calculate_threat_score(1, distance=20.0, base_threat=50.0, health_percent=1.0)

        # Weak target right next to you (but already fighting)
        score2 = calculate_threat_score(2, distance=1.0, base_threat=5.0, health_percent=1.0, is_aggroed=True)

        # Fragile target about to die
        score3 = calculate_threat_score(3, distance=5.0, base_threat=10.0, health_percent=0.1)
    """
    # Prevent divide-by-zero
    safe_distance = max(1.0, distance)

    # Base score: threat divided by distance
    # At distance=1: score = base_threat * 10.0
    # At distance=10: score = base_threat * 1.0
    score = (base_threat * 10.0) / safe_distance

    # Bonus: low-health targets (finish them off)
    if health_percent < 0.25:
        score *= 1.5
    elif health_percent < 0.5:
        score *= 1.2

    # Bonus: already in combat with this target (don't panic-switch)
    if is_aggroed:
        score *= 1.2

    return ThreatScore(
        entity_id=entity_id,
        score=score,
        distance=distance,
        health_percent=health_percent,
        is_aggroed=is_aggroed
    )


def select_highest_threat(threats: list[ThreatScore]) -> ThreatScore | None:
    """
    Pick the single highest-threat target from a list.

    Args:
        threats: List of ThreatScore results

    Returns:
        ThreatScore with highest score, or None if list is empty
    """
    if not threats:
        return None
    return max(threats, key=lambda t: t.score)


def rank_threats(threats: list[ThreatScore]) -> list[ThreatScore]:
    """
    Sort threats by priority (highest first).

    Args:
        threats: List of ThreatScore results

    Returns:
        Sorted list (highest score first)
    """
    return sorted(threats, key=lambda t: t.score, reverse=True)


def should_abandon_target(
    current_distance: float,
    max_pursuit_distance: float = 50.0,
    aggro_duration_ticks: int = 1800
) -> bool:
    """
    Decide if an NPC should give up pursuing a target.

    Simple check: if target is too far away for too long, forget about it.

    Args:
        current_distance: Distance to target
        max_pursuit_distance: How far to chase before giving up
        aggro_duration_ticks: How long to stay aggroed (for reference)

    Returns:
        True if should abandon pursuit
    """
    # If target is beyond pursuit range, give up
    return current_distance > max_pursuit_distance


def should_flee(
    self_health_percent: float,
    enemy_threat: float = 10.0,
    fleeing_threshold: float = 0.2
) -> bool:
    """
    Decide if an NPC should flee based on health.

    Args:
        self_health_percent: This entity's HP as fraction (0.0 to 1.0)
        enemy_threat: Threat level of opponent (for damage potential)
        fleeing_threshold: HP percentage below which to flee (0.2 = 20%)

    Returns:
        True if should flee
    """
    return self_health_percent < fleeing_threshold


# Vision type modifiers (affects perception range)
VISION_MODIFIERS = {
    "normal": 1.0,           # Standard vision
    "infravision": 1.2,      # Heat-based (ignores light)
    "darkvision": 1.5,       # Perfect night vision
    "true_sight": 2.0,       # Magical all-seeing
    "poor": 0.7,             # Myopia or old age
}


def adjusted_vision_range(
    base_range: int,
    vision_type: str = "normal",
    time_of_day: str = "day"
) -> int:
    """
    Adjust vision range based on vision type and time of day.

    Args:
        base_range: Base vision distance in tiles
        vision_type: Type of vision ("normal", "infravision", "darkvision", "true_sight", "poor")
        time_of_day: Time ("day", "evening", "night", "dawn")

    Returns:
        Adjusted vision range in tiles

    Example:
        range = adjusted_vision_range(15, vision_type="infravision")
        # Returns: 18 (15 * 1.2)

        range = adjusted_vision_range(15, vision_type="darkvision", time_of_day="night")
        # Returns: 22 (15 * 1.5)
    """
    modifier = VISION_MODIFIERS.get(vision_type, 1.0)

    # Darkvision is better at night (penalty at day)
    if vision_type == "darkvision" and time_of_day == "day":
        modifier *= 0.8  # Slightly worse in bright light

    return int(base_range * modifier)


def calculate_alarm_radius(
    visibility: float,
    noise_level: float = 0.0,
    faction_paranoia: float = 1.0
) -> float:
    """
    Calculate how far away an NPC can detect trouble.

    Combines sight range with hearing and supernatural senses.

    Args:
        visibility: Base vision range (tiles)
        noise_level: How loud the disturbance is (0.0 = silent, 1.0 = loud)
        faction_paranoia: Multiplier for alertness (1.0 = normal, 2.0 = very paranoid)

    Returns:
        Detection radius in tiles

    Example:
        # Goblin with normal vision hears a loud crash
        radius = calculate_alarm_radius(15.0, noise_level=1.0, faction_paranoia=1.0)
        # Returns: 15 (sight-based)

        # Paranoid guards hear a whisper
        radius = calculate_alarm_radius(20.0, noise_level=0.3, faction_paranoia=2.0)
        # Returns: ~12 (some sound-based detection)
    """
    # Base detection is vision
    detection_range = visibility

    # Loud noise extends detection range
    if noise_level > 0.0:
        detection_range += (noise_level * 30.0) * faction_paranoia

    return detection_range
