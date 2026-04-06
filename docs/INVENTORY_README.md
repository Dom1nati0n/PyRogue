# Inventory System

Simple slot-based item storage for entities.

## Components

**InventoryComponent**
- `slots`: List of item IDs (None = empty slot)
- `max_slots`: Maximum items (default 10)

Methods:
- `add_item(item_id)` → bool
- `remove_item(item_id)` → bool
- `has_item(item_id)` → bool
- `get_items()` → List[int]
- `count()` → int (items held)
- `is_full()` → bool
- `is_empty()` → bool

## Setup

```python
from pyrogue_engine.systems.item import InventoryComponent, InventorySystem, add_inventory

# Initialize system
inventory_system = InventorySystem(registry, event_bus, config)

# Add inventory to entity
add_inventory(registry, entity_id, max_slots=10)

# Or manually
inventory = InventoryComponent(max_slots=10)
registry.add_component(entity_id, inventory)
```

## Events

**inventory.add** — Add item to inventory
```python
event_bus.emit(Event(
    "inventory.add",
    metadata={"owner_id": player_id, "item_id": cheese_id}
))
```

**inventory.remove** — Remove item from inventory
```python
event_bus.emit(Event(
    "inventory.remove",
    metadata={"owner_id": player_id, "item_id": cheese_id}
))
```

**inventory.drop** — Drop item to ground
```python
event_bus.emit(Event(
    "inventory.drop",
    metadata={
        "owner_id": player_id,
        "item_id": cheese_id,
        "drop_x": 10,
        "drop_y": 15
    }
))
```

**inventory.use** — Use item from inventory
```python
event_bus.emit(Event(
    "inventory.use",
    metadata={
        "owner_id": player_id,
        "item_id": cheese_id,
        "target_id": enemy_id  # optional
    }
))
```

## System Responses

InventorySystem emits confirmation events after operations:
- `inventory.added` — Item successfully added
- `inventory.removed` — Item removed
- `inventory.dropped` — Item dropped to ground
- `item.used` — Item use delegated to item system

## Example

```python
# Create player with inventory
player_id = registry.create_entity()
add_inventory(registry, player_id, max_slots=10)

# Spawn cheese
cheese_id = create_debug_cheese(5, 5)
registry.create_entity()  # Add to world...

# Pick up cheese
event_bus.emit(Event("inventory.add", metadata={
    "owner_id": player_id,
    "item_id": cheese_id
}))

# Use cheese as weapon
event_bus.emit(Event("inventory.use", metadata={
    "owner_id": player_id,
    "item_id": cheese_id,
    "target_id": enemy_id
}))

# Drop it
event_bus.emit(Event("inventory.drop", metadata={
    "owner_id": player_id,
    "item_id": cheese_id,
    "drop_x": 10,
    "drop_y": 15
}))
```

## Notes

- Items physically move to owner's position on pickup
- Inventory cannot exceed max_slots
- System is event-driven (no direct method calls needed)
- Works with any item type (cheese, weapons, potions, etc.)
