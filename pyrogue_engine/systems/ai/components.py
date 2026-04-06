"""
AI Components - The Mental Model for Entities

Memory: A generic key-value store for what an entity knows.
Brain: Holds the active Decision Tree for this entity.
Faction: The entity's allegiance (who to attack/protect).
ScentMemory: Last known position of a target (enables out-of-sight pursuit).
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple


@dataclass
class Memory:
    """
    The entity's working memory / blackboard.

    Stores facts the entity discovers or updates:
    - "target_id": int (enemy entity ID)
    - "target_position": (x, y) tuple
    - "last_attack_time": float
    - "health_percentage": float (0.0 to 1.0)
    - Custom game-specific keys as needed

    Example:
        memory = Memory()
        memory.data["target_id"] = player_entity_id
        memory.data["target_position"] = (50, 30)

    This is updated by Perception systems and read by Decision Tree conditions.
    """

    data: Dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        """Store or update a fact in memory."""
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a fact from memory."""
        return self.data.get(key, default)

    def has(self, key: str) -> bool:
        """Check if a fact is in memory."""
        return key in self.data

    def clear(self) -> None:
        """Clear all memory."""
        self.data.clear()


@dataclass
class Brain:
    """
    Holds the Decision Tree for this entity.

    The root_node is lazily loaded from JSON when first ticked.
    This avoids parsing the same JSON multiple times for multiple entities
    of the same type.

    Attributes:
        mindset_id: Identifier for the AI behavior (e.g., "smart_assassin")
                    Used to load the correct JSON tree
        root_node: The actual DecisionNode instance (loaded on first tick)
    """

    mindset_id: str
    root_node: Optional["DecisionNode"] = None  # Lazy-loaded, imported from decision_tree module


@dataclass
class Faction:
    """
    Entity's allegiance for combat purposes.

    Determines if this entity attacks other entities based on their faction.
    Queried by AwarenessSystem via FactionRegistry.

    Attributes:
        name: Faction identifier (e.g., "player", "undead", "goblin", "human")
              String allows flexible game definitions without hardcoding enums
    """

    name: str


@dataclass
class ScentMemory:
    """
    Memory of where a target was last seen.

    Enables out-of-sight pursuit: NPC doesn't just forget, it searches
    the last known position.

    Attributes:
        last_position: (x, y) tuple of last sighting, or None if not tracking
        age_ticks: How many ticks since last update (used for scent decay)
        max_age_ticks: How long before scent becomes too old to trust (decay)
    """

    last_position: Optional[Tuple[int, int]] = None
    age_ticks: int = 0
    max_age_ticks: int = 300  # ~5 minutes at 60 ticks/second

    def update_position(self, x: int, y: int) -> None:
        """Refresh the scent with new sighting."""
        self.last_position = (x, y)
        self.age_ticks = 0

    def age(self, tick_delta: int = 1) -> None:
        """Increment age. Called each tick."""
        self.age_ticks += tick_delta

    def is_fresh(self) -> bool:
        """Check if scent is still reliable."""
        return self.last_position is not None and self.age_ticks < self.max_age_ticks

    def clear(self) -> None:
        """Forget the scent."""
        self.last_position = None
        self.age_ticks = 0
