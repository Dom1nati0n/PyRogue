"""
Template Dataclasses - Entity Definition Structures

Templates are immutable configuration objects loaded from JSON.
They define what components to attach and what values to use.

The factory uses these templates to instantiate entities with the correct components.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LootEntry:
    """Single entry in a loot table."""

    item_template: str
    weight: float = 1.0
    min_quantity: int = 1
    max_quantity: int = 1


@dataclass
class LootTable:
    """Loot drops when entity is destroyed."""

    drop_chance: float = 1.0  # 0.0 to 1.0
    entries: List[LootEntry] = field(default_factory=list)


@dataclass
class MindTemplate:
    """Behavioral configuration."""

    trait: Optional[str] = None  # e.g., "Mind.Trait.Aggressive"
    starting_mood: Optional[str] = None  # e.g., "Mind.Mood.Alert"
    starting_urge: Optional[str] = None  # e.g., "Mind.Urge.Hunting"


@dataclass
class BondTemplate:
    """Social relationship configuration."""

    allegiance: Optional[str] = None  # e.g., "Bond.Allegiance.Wolfpack"
    role: Optional[str] = None  # e.g., "Bond.Role.Alpha"
    group_loyalty: int = 50  # 0-100


@dataclass
class DurabilityTemplate:
    """Item durability (wear and tear)."""

    maximum: float = 100.0
    current: Optional[float] = None  # Defaults to maximum if not specified


@dataclass
class StackableTemplate:
    """Item stacking rules."""

    max_stack: int = 1


@dataclass
class CreatureTemplate:
    """
    Complete creature entity definition.

    All required fields must be present. Optional fields can be None or omitted.
    """

    template_id: str

    # Display & appearance
    display_name: str
    description: str
    sprite: str  # Single character
    sprite_color: str  # Color name

    # Classification
    tags: List[str] = field(default_factory=lambda: ["Living.Animal"])

    # Behavior
    mind: Optional[MindTemplate] = None

    # Social
    bond: Optional[BondTemplate] = None

    # Stats & properties
    properties: Dict[str, Any] = field(default_factory=dict)
    initiative_speed: float = 10.0

    # Loot
    loot: Optional[LootTable] = None


@dataclass
class ItemTemplate:
    """
    Complete item entity definition.

    Tags provide property inheritance. Template properties override inherited values.
    """

    template_id: str

    # Display & appearance
    display_name: str
    description: str
    sprite: str  # Single character
    sprite_color: str  # Color name

    # Classification (for property inheritance)
    tags: List[str] = field(default_factory=list)

    # Properties (overrides inherited tag properties)
    properties: Dict[str, Any] = field(default_factory=dict)

    # Optional mechanics
    durability: Optional[DurabilityTemplate] = None
    stackable: Optional[StackableTemplate] = None


@dataclass
class TileTemplate:
    """
    Tile entity definition.

    Tiles are typically simpler: just terrain type and optional feature.
    """

    template_id: str

    # Display
    sprite: str
    sprite_color: str

    # Classification
    tags: List[str] = field(default_factory=list)

    # Properties
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GroupTemplate:
    """
    Template for spawning a group of entities with leadership structure.

    Spawns a leader and members, establishing bonds between them.
    """

    template_id: str

    # Structure
    leader_template: str  # Creature template for leader
    member_templates: List[str]  # Creature templates for members

    # Grouping
    allegiance: Optional[str] = None  # Shared allegiance for all
    description: Optional[str] = None

    # Bonding strength (optional overrides)
    leader_to_member_strength: int = 80  # How much leader values members
    member_to_member_strength: int = 60  # How much members value each other
