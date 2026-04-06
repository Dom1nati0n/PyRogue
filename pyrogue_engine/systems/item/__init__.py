"""
Item System - Game items with tag-based identification.

Provides:
  - ItemComponent: Base item with tags and durability
  - CheeseItem: Debug item for testing combat, inventory, projectiles
  - CheeseSystem: Handles cheese interactions and splitting
  - InventoryComponent: Slot-based item storage
  - InventorySystem: Handles inventory add/remove/use/drop operations
"""

from pyrogue_engine.systems.item.cheese_item import (
    ItemComponent,
    CheeseProperties,
    create_debug_cheese,
)
from pyrogue_engine.systems.item.cheese_system import CheeseSystem
from pyrogue_engine.systems.item.inventory import (
    InventoryComponent,
    InventorySystem,
    add_inventory,
)

__all__ = [
    "ItemComponent",
    "CheeseProperties",
    "CheeseSystem",
    "create_debug_cheese",
    "InventoryComponent",
    "InventorySystem",
    "add_inventory",
]
