"""
Debug Cheese Item - Multi-system test item for validating combat, inventory, and projectile systems.

The Debug Cheese is a highly functional test item that exercises:
  1. Inventory system (pickup, drop, split)
  2. Combat system (use as weapon, damage)
  3. Projectile system (throw, impact, split on collision)
  4. Item tagging system (structure and health)
  5. Entity spawning (when split)

Compliance:
  ✓ Tag-based: Uses item tagging system for type identification
  ✓ Event-driven: Emits item.used, item.thrown, item.split events
  ✓ Compositional: All abilities via separate components
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class ItemComponent:
    """
    Base item component using tag-based identification.

    Tags allow items to be identified and filtered without class inheritance.
    """

    item_name: str = "Item"
    item_id: int = 0  # Unique per-instance
    tags: List[str] = field(default_factory=list)  # ["debug", "weapon", "cheese", etc.]
    durability: int = 100  # Health/structure points
    max_durability: int = 100


@dataclass
class CheeseProperties:
    """
    Cheese-specific properties for debug testing.

    Attributes:
        split_threshold: Durability below which cheese splits
        split_count: How many smaller cheeses to spawn on split
        split_damage_reduction: Health of child cheeses (e.g., 0.5 = 50% of parent)
        split_generation: Current generation (0 = original, increments on split)
        max_generations: Maximum splits before cheese becomes "too small" to split
    """

    split_threshold: int = 30  # Split when durability < 30%
    split_count: int = 3  # Create 3 smaller cheeses
    split_damage_reduction: float = 0.5  # Child cheeses have 50% health
    split_generation: int = 0  # Current generation (0, 1, 2, etc.)
    max_generations: int = 3  # Max 3 splits before stopping
    throw_damage: int = 15  # Damage when thrown and impacts target
    melee_damage: int = 5  # Damage when used as melee weapon
    throw_range: int = 10  # Max distance before landing


def create_debug_cheese(x: int, y: int, size: str = "normal") -> dict:
    """
    Factory function to create a debug cheese item.

    Args:
        x: Spawn X position
        y: Spawn Y position
        size: "tiny", "small", "normal", "large" - affects durability

    Returns:
        Entity dict ready to add to registry
    """
    size_durability = {
        "tiny": 20,
        "small": 50,
        "normal": 100,
        "large": 200,
    }

    durability = size_durability.get(size, 100)

    return {
        "components": {
            "PositionComponent": {"x": x, "y": y},
            "TileSprite": {
                "char": "c",
                "fg_color": [255, 200, 0],  # Golden yellow
                "bg_color": [0, 0, 0],
                "layer": 2,
            },
            "ItemComponent": {
                "item_name": f"Debug Cheese ({size})",
                "tags": ["debug", "weapon", "throwable", "splittable", "food", "cheese"],
                "durability": durability,
                "max_durability": durability,
            },
            "CheeseProperties": {
                "split_threshold": int(durability * 0.3),  # Split at 30%
                "split_count": 3,
                "split_damage_reduction": 0.5,
                "throw_damage": 15,
                "melee_damage": 5,
                "throw_range": 10,
            },
        },
    }
