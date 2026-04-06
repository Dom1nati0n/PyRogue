"""
Entities - Data-Driven Entity Factory System

The entities module automates entity instantiation from JSON templates.
It bridges the gap between game data (JSON) and engine logic (ECS components).

Components:
- TemplateRegistry: Load and cache JSON templates
- EntityFactory: Dynamically spawn entities with correct components
- Template dataclasses: Type-safe template definitions

Workflow:
1. Load templates: registry.load_creatures("creatures.json")
2. Create factory: factory = EntityFactory(registry, event_bus, tag_manager, template_registry)
3. Spawn entities: entity_id = factory.spawn_creature("wolf", x=10, y=20)

Example:
    from pyrogue_engine.entities import EntityFactory, TemplateRegistry

    # Load templates
    templates = TemplateRegistry()
    templates.load_creatures("content/creatures.json")
    templates.load_items("content/items.json")

    # Create factory
    factory = EntityFactory(registry, event_bus, tag_manager, templates)

    # Spawn entities
    wolf_id = factory.spawn_creature("wolf", x=10, y=20)
    iron_sword_id = factory.spawn_item("iron_longsword", x=15, y=25)

    # Spawn groups (leader + members)
    leader_id, member_ids = factory.spawn_group("wolfpack", x=30, y=40)
"""

from .template import (
    CreatureTemplate,
    ItemTemplate,
    TileTemplate,
    GroupTemplate,
    MindTemplate,
    BondTemplate,
    LootTable,
    LootEntry,
    DurabilityTemplate,
    StackableTemplate,
)
from .template_registry import TemplateRegistry
from .entity_factory import EntityFactory

__all__ = [
    # Templates
    "CreatureTemplate",
    "ItemTemplate",
    "TileTemplate",
    "GroupTemplate",
    "MindTemplate",
    "BondTemplate",
    "LootTable",
    "LootEntry",
    "DurabilityTemplate",
    "StackableTemplate",
    # Registry & Factory
    "TemplateRegistry",
    "EntityFactory",
]
