"""
Inventory System - Simple slot-based item storage for entities.

Provides:
  - InventoryComponent: Holds item IDs in fixed-size slots
  - InventorySystem: Handles add/remove/use/drop events
  - add_inventory: Factory function to create inventory on entities
"""

from dataclasses import dataclass, field
from typing import List, Optional

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import Event, EventBus


@dataclass
class InventoryComponent:
    """
    Simple slot-based inventory container.

    Stores item entity IDs in a fixed-size slot array. Supports:
    - Adding items (if space available)
    - Removing items
    - Querying item count
    - Checking if full

    Attributes:
        slots: List of item_id integers (None = empty slot)
        max_slots: Maximum items this inventory can hold
    """

    slots: List[Optional[int]] = field(default_factory=lambda: [None] * 10)
    max_slots: int = 10

    def add_item(self, item_id: int) -> bool:
        """Add item to first available slot. Return True if successful."""
        try:
            first_empty = self.slots.index(None)
            self.slots[first_empty] = item_id
            return True
        except ValueError:
            return False  # No empty slots

    def remove_item(self, item_id: int) -> bool:
        """Remove item from inventory. Return True if found."""
        try:
            self.slots[self.slots.index(item_id)] = None
            return True
        except ValueError:
            return False  # Item not in inventory

    def has_item(self, item_id: int) -> bool:
        """Check if inventory contains this item."""
        return item_id in self.slots

    def get_items(self) -> List[int]:
        """Return list of non-None item IDs currently held."""
        return [item_id for item_id in self.slots if item_id is not None]

    def count(self) -> int:
        """Return number of items in inventory."""
        return len(self.get_items())

    def is_full(self) -> bool:
        """Check if inventory is at max capacity."""
        return self.count() >= self.max_slots

    def is_empty(self) -> bool:
        """Check if inventory has no items."""
        return self.count() == 0


def add_inventory(registry: Registry, entity_id: int, max_slots: int = 10) -> None:
    """
    Add an inventory component to an entity.

    Args:
        registry: ECS registry
        entity_id: Entity to add inventory to
        max_slots: Maximum items (default 10)
    """
    inventory = InventoryComponent(
        slots=[None] * max_slots,
        max_slots=max_slots,
    )
    registry.add_component(entity_id, inventory)


class InventorySystem:
    """
    Handles inventory operations: add, remove, use, drop items.

    Listens for inventory.* events and updates InventoryComponent state.
    Emits events for item pickup/drop to integrate with world state.
    """

    def __init__(self, registry: Registry, event_bus: EventBus, config=None):
        """
        Initialize inventory system.

        Args:
            registry: ECS registry
            event_bus: Event bus for listening/emitting
            config: Server config (unused)
        """
        self.registry = registry
        self.event_bus = event_bus
        self.config = config

        # Subscribe to inventory events
        self.event_bus.subscribe("inventory.add", self._on_add_item)
        self.event_bus.subscribe("inventory.remove", self._on_remove_item)
        self.event_bus.subscribe("inventory.drop", self._on_drop_item)
        self.event_bus.subscribe("inventory.use", self._on_use_item)

        print("[InventorySystem] Initialized")

    def _on_add_item(self, event: Event) -> None:
        """
        Add an item to an entity's inventory.

        Event metadata:
            owner_id: Entity receiving the item
            item_id: Item entity to add
        """
        metadata = event.metadata or {}
        owner_id = metadata.get("owner_id")
        item_id = metadata.get("item_id")

        if not owner_id or not item_id:
            return

        inventory = self.registry.get_component(owner_id, InventoryComponent)
        if not inventory:
            return

        if inventory.add_item(item_id):
            # Move item to owner location for simplicity
            from pyrogue_engine.systems.spatial.components import Position

            owner_pos = self.registry.get_component(owner_id, Position)
            if owner_pos:
                item_pos = self.registry.get_component(item_id, Position)
                if item_pos:
                    item_pos.x = owner_pos.x
                    item_pos.y = owner_pos.y

            print(f"[InventorySystem] Item {item_id} added to {owner_id} inventory ({inventory.count()}/{inventory.max_slots})")

            self.event_bus.emit(
                Event(
                    event_type="inventory.added",
                    metadata={
                        "owner_id": owner_id,
                        "item_id": item_id,
                        "slot": inventory.slots.index(item_id),
                        "inventory_count": inventory.count(),
                    },
                )
            )
        else:
            print(f"[InventorySystem] Failed to add item {item_id}: inventory full")

    def _on_remove_item(self, event: Event) -> None:
        """
        Remove an item from inventory.

        Event metadata:
            owner_id: Entity owning the inventory
            item_id: Item to remove
        """
        metadata = event.metadata or {}
        owner_id = metadata.get("owner_id")
        item_id = metadata.get("item_id")

        if not owner_id or not item_id:
            return

        inventory = self.registry.get_component(owner_id, InventoryComponent)
        if not inventory:
            return

        if inventory.remove_item(item_id):
            print(f"[InventorySystem] Item {item_id} removed from {owner_id} inventory ({inventory.count()}/{inventory.max_slots})")

            self.event_bus.emit(
                Event(
                    event_type="inventory.removed",
                    metadata={
                        "owner_id": owner_id,
                        "item_id": item_id,
                    },
                )
            )

    def _on_drop_item(self, event: Event) -> None:
        """
        Drop an item from inventory to ground.

        Event metadata:
            owner_id: Entity dropping the item
            item_id: Item to drop
            drop_x, drop_y: Position to drop at
        """
        metadata = event.metadata or {}
        owner_id = metadata.get("owner_id")
        item_id = metadata.get("item_id")
        drop_x = metadata.get("drop_x")
        drop_y = metadata.get("drop_y")

        if not all([owner_id, item_id, drop_x is not None, drop_y is not None]):
            return

        inventory = self.registry.get_component(owner_id, InventoryComponent)
        if not inventory:
            return

        if inventory.remove_item(item_id):
            from pyrogue_engine.systems.spatial.components import Position

            item_pos = self.registry.get_component(item_id, Position)
            if item_pos:
                item_pos.x = drop_x
                item_pos.y = drop_y

            print(f"[InventorySystem] Item {item_id} dropped at ({drop_x}, {drop_y})")

            self.event_bus.emit(
                Event(
                    event_type="inventory.dropped",
                    metadata={
                        "owner_id": owner_id,
                        "item_id": item_id,
                        "drop_x": drop_x,
                        "drop_y": drop_y,
                    },
                )
            )

    def _on_use_item(self, event: Event) -> None:
        """
        Use an item from inventory.

        Event metadata:
            owner_id: Entity using the item
            item_id: Item to use
            target_id: Optional target entity
        """
        metadata = event.metadata or {}
        owner_id = metadata.get("owner_id")
        item_id = metadata.get("item_id")
        target_id = metadata.get("target_id")

        if not owner_id or not item_id:
            return

        inventory = self.registry.get_component(owner_id, InventoryComponent)
        if not inventory or not inventory.has_item(item_id):
            return

        print(f"[InventorySystem] Item {item_id} used by {owner_id}" + (f" on {target_id}" if target_id else ""))

        self.event_bus.emit(
            Event(
                event_type="item.used",
                metadata={
                    "item_id": item_id,
                    "actor_id": owner_id,
                    "user_id": owner_id,
                    "target_id": target_id,
                },
            )
        )
