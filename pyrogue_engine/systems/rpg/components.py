"""
RPG Component Definitions - Flexible, game-agnostic stat and health systems.

These components are designed to work with ANY naming scheme:
- "RED/ORANGE/YELLOW/GREEN/BLUE/PURPLE" (color system)
- "STR/DEX/INT/CON/WIS/CHA" (D&D system)
- "Might/Agility/Logic/Presence/Endurance/Perception" (custom)

The engine doesn't care what you call your stats—it just asks for modifiers.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Health:
    """Core health/damage tracking"""
    current: int
    maximum: int

    def is_alive(self) -> bool:
        """True if this entity can still act"""
        return self.current > 0

    def is_dead(self) -> bool:
        """True if health is depleted"""
        return self.current <= 0

    def heal(self, amount: int) -> int:
        """Restore health, return amount actually healed"""
        old_hp = self.current
        self.current = min(self.current + amount, self.maximum)
        return self.current - old_hp

    def take_damage(self, amount: int) -> int:
        """Reduce health, return amount actually taken"""
        old_hp = self.current
        self.current = max(0, self.current - amount)
        return old_hp - self.current


@dataclass
class Attributes:
    """
    Flexible stat dictionary. Works with any naming scheme.

    Examples:
        Attributes(stats={"RED": 15, "ORANGE": 12})  # Color system
        Attributes(stats={"STR": 18, "DEX": 14})      # D&D system
        Attributes(stats={"strength": 16, "agility": 14})  # Literal names
    """
    stats: Dict[str, int] = field(default_factory=dict)

    def get_stat(self, stat_name: str, default: int = 10) -> int:
        """Retrieve a stat value (default 10 if missing)"""
        return self.stats.get(stat_name, default)

    def get_modifier(self, stat_name: str) -> int:
        """
        Standard D&D-style modifier: (score - 10) // 2

        Examples:
            Score 10 → Modifier 0
            Score 15 → Modifier +2
            Score 8  → Modifier -1
        """
        score = self.get_stat(stat_name)
        return (score - 10) // 2

    def set_stat(self, stat_name: str, value: int) -> None:
        """Update a stat value"""
        self.stats[stat_name] = value


@dataclass
class Defense:
    """Physical armor and mitigation"""
    armor_value: int = 0  # Flat armor rating (reduces incoming damage)
    dodge_chance: float = 0.0  # Percentage chance to avoid attack (0.0 to 1.0)


@dataclass
class Equipment:
    """Item references for gear"""
    main_hand_id: Optional[str] = None  # Weapon ID
    off_hand_id: Optional[str] = None
    armor_id: Optional[str] = None  # Armor piece ID
    accessory_ids: list = field(default_factory=list)  # Ring, amulet, etc.


@dataclass
class CombatStats:
    """Per-combat statistics and history"""
    damage_dealt: int = 0
    damage_taken: int = 0
    times_acted: int = 0
    kills: int = 0
    experience_earned: int = 0


@dataclass
class ActionPoints:
    """Turn-based action economy"""
    current: int = 3
    maximum: int = 3
    per_turn: int = 3

    def can_afford(self, cost: int) -> bool:
        """Check if entity has enough AP for an action"""
        return self.current >= cost

    def spend(self, cost: int) -> bool:
        """Deduct AP, return True if successful"""
        if self.can_afford(cost):
            self.current -= cost
            return True
        return False

    def reset_turn(self) -> None:
        """Restore AP to maximum (called at start of turn)"""
        self.current = self.per_turn


@dataclass
class PlayerController:
    """
    Bridge between network session and ECS entity (Separation of Identity).

    Links a persistent session_id (stored in client localStorage) to a physical
    avatar entity_id in the ECS. This component is the ONLY place that bridges
    network volatility to game state.

    If the WebSocket drops, is_connected flips to False.
    The entity remains in the world (no deletion). AI or players can respawn
    when they reconnect.

    For predictive mode (client-side prediction):
    - Clients send input with sequence_id (1, 2, 3, ...)
    - Server processes and stores last_processed_sequence_id
    - Server includes this in replication packets so client knows which predictions were confirmed
    """
    session_id: str
    is_connected: bool = True
    reconnect_timer: float = 0.0
    last_processed_sequence_id: Optional[int] = None  # For predictive mode
