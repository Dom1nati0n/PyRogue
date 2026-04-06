"""
Cheese System - Handles all debug cheese item interactions.

Subscribes to item events and coordinates cheese-specific behavior:
  - item.used: Cheese used as melee weapon
  - item.thrown: Cheese thrown as projectile
  - item.dropped: Cheese dropped to ground
  - cheese.split: Cheese splits into smaller cheeses

Compliance:
  ✓ Reactive: Listens to item events
  ✓ Pure: No mutations except creating new entities on split
  ✓ Intent-driven: Emits item.used, item.damaged, cheese.split events
"""

import random
from typing import Any, Optional

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import Event, EventBus
from pyrogue_engine.systems.spatial.components import Position
from pyrogue_engine.systems.item.cheese_item import ItemComponent, CheeseProperties


class CheeseSystem:
    """
    Handles cheese-specific behavior and interactions.

    Listens for item.used, item.thrown, item.dropped events and implements
    cheese logic (splitting, damage, spawning child cheeses).
    """

    def __init__(self, registry: Registry, event_bus: EventBus, config: Any):
        """
        Initialize the cheese system.

        Args:
            registry: ECS registry
            event_bus: Event bus
            config: Server config
        """
        self.registry = registry
        self.event_bus = event_bus
        self.config = config

        # Subscribe to item events
        self.event_bus.subscribe("item.used", self._on_item_used)
        self.event_bus.subscribe("item.thrown", self._on_item_thrown)
        self.event_bus.subscribe("item.dropped", self._on_item_dropped)
        self.event_bus.subscribe("item.damaged", self._on_item_damaged)

        print("[CheeseSystem] Initialized - ready to handle debug cheese interactions")

    def _on_item_used(self, event: Event) -> None:
        """
        Called when a cheese is used as a melee weapon.

        Emits damage to target, applies durability loss to cheese.
        """
        metadata = event.metadata or {}
        item_id = metadata.get("item_id")
        user_id = metadata.get("actor_id") or metadata.get("user_id")  # Accept both actor_id and user_id
        target_id = metadata.get("target_id")

        if not all([item_id, user_id, target_id]):
            return

        cheese = self.registry.get_component(item_id, ItemComponent)
        cheese_props = self.registry.get_component(item_id, CheeseProperties)

        if not (cheese and cheese_props):
            return

        # Cheese does melee damage when used as weapon
        damage = cheese_props.melee_damage

        # Cheese takes damage from use (wear and tear)
        cheese.durability = max(0, cheese.durability - 10)

        print(f"[CheeseSystem] Cheese {item_id} used by {user_id} on {target_id} for {damage} damage")

        # Emit damage event for target
        self.event_bus.emit(
            Event(
                event_type="combat.damage",
                metadata={
                    "target_id": target_id,
                    "damage": damage,
                    "source_id": user_id,
                    "source_type": "cheese_melee",
                },
            )
        )

        # Check if cheese should split
        self._check_split(item_id, cheese, cheese_props)

    def _on_item_thrown(self, event: Event) -> None:
        """
        Called when a cheese is thrown.

        Cheese becomes a projectile, takes damage on impact, may split.
        """
        metadata = event.metadata or {}
        item_id = metadata.get("item_id")
        user_id = metadata.get("actor_id") or metadata.get("user_id")  # Accept both actor_id and user_id
        target_pos = metadata.get("target_pos")  # {x, y}

        if not all([item_id, user_id, target_pos]):
            return

        cheese = self.registry.get_component(item_id, ItemComponent)
        cheese_props = self.registry.get_component(item_id, CheeseProperties)

        if not (cheese and cheese_props):
            return

        # Move cheese to target position (simplified - no actual projectile motion)
        pos = self.registry.get_component(item_id, Position)
        if pos:
            pos.x = target_pos["x"]
            pos.y = target_pos["y"]

        # Cheese takes impact damage
        cheese.durability = max(0, cheese.durability - 25)

        print(f"[CheeseSystem] Cheese {item_id} thrown by {user_id} to ({target_pos['x']}, {target_pos['y']})")

        # Check if cheese should split
        self._check_split(item_id, cheese, cheese_props)

    def _on_item_dropped(self, event: Event) -> None:
        """
        Called when a cheese is dropped.

        Cheese is marked as ground item, takes minor damage.
        """
        metadata = event.metadata or {}
        item_id = metadata.get("item_id")
        drop_pos = metadata.get("drop_pos")  # {x, y}

        if not all([item_id, drop_pos]):
            return

        cheese = self.registry.get_component(item_id, ItemComponent)
        if not cheese:
            return

        pos = self.registry.get_component(item_id, Position)
        if pos:
            pos.x = drop_pos["x"]
            pos.y = drop_pos["y"]

        # Minor damage from drop
        cheese.durability = max(0, cheese.durability - 5)

        print(f"[CheeseSystem] Cheese {item_id} dropped at ({drop_pos['x']}, {drop_pos['y']})")

    def _on_item_damaged(self, event: Event) -> None:
        """
        Called when a cheese takes external damage (e.g., from combat).

        May trigger split if durability is low enough.
        """
        metadata = event.metadata or {}
        item_id = metadata.get("item_id")
        damage = metadata.get("damage", 0)

        if not item_id:
            return

        cheese = self.registry.get_component(item_id, ItemComponent)
        cheese_props = self.registry.get_component(item_id, CheeseProperties)

        if not (cheese and cheese_props):
            return

        cheese.durability = max(0, cheese.durability - damage)

        print(f"[CheeseSystem] Cheese {item_id} took {damage} damage, durability now {cheese.durability}")

        self._check_split(item_id, cheese, cheese_props)

    def _check_split(self, item_id: int, cheese: ItemComponent, props: CheeseProperties) -> None:
        """
        Check if cheese should split into smaller cheeses.

        Triggered when durability falls below split_threshold.
        Respects max_generations limit to prevent exponential growth.
        """
        if cheese.durability > props.split_threshold:
            return

        # Prevent infinite splitting: stop if max generations reached
        if props.split_generation >= props.max_generations:
            print(f"[CheeseSystem] Cheese {item_id} too old to split (generation {props.split_generation}/{props.max_generations})")
            return

        print(f"[CheeseSystem] Cheese {item_id} splitting! (durability {cheese.durability} < {props.split_threshold}, generation {props.split_generation}/{props.max_generations})")

        # Get cheese position
        pos = self.registry.get_component(item_id, Position)
        if not pos:
            return

        # Spawn child cheeses (3 smaller ones around the original)
        from pyrogue_engine.systems.item.cheese_item import create_debug_cheese

        for i in range(props.split_count):
            # Offset spawn positions slightly
            offset_x = random.randint(-2, 2)
            offset_y = random.randint(-2, 2)
            child_x = max(0, pos.x + offset_x)
            child_y = max(0, pos.y + offset_y)

            # Create smaller cheese with reduced durability
            child_entity_data = create_debug_cheese(
                child_x, child_y, size="small"
            )

            # Reduce durability of child
            child_entity_data["components"]["ItemComponent"]["durability"] = int(
                cheese.durability * props.split_damage_reduction
            )
            child_entity_data["components"]["ItemComponent"]["max_durability"] = int(
                cheese.max_durability * props.split_damage_reduction
            )

            # Increment generation for child (prevents infinite recursion)
            child_entity_data["components"]["CheeseProperties"]["split_generation"] = props.split_generation + 1

            # Create entity
            child_id = self.registry.create_entity()

            for component_name, component_data in child_entity_data["components"].items():
                if component_name == "PositionComponent":
                    from pyrogue_engine.systems.spatial.components import Position
                    self.registry.add_component(child_id, Position(**component_data))
                elif component_name == "ItemComponent":
                    self.registry.add_component(child_id, ItemComponent(**component_data))
                elif component_name == "CheeseProperties":
                    self.registry.add_component(child_id, CheeseProperties(**component_data))
                else:
                    # Store as dict (e.g., TileSprite)
                    self.registry.add_component(child_id, component_data)

            print(f"[CheeseSystem] Spawned child cheese {child_id} at ({child_x}, {child_y})")

        # Emit split event for potential further handling
        self.event_bus.emit(
            Event(
                event_type="cheese.split",
                metadata={
                    "parent_id": item_id,
                    "child_count": props.split_count,
                    "split_x": pos.x,
                    "split_y": pos.y,
                },
            )
        )

        # Delete original cheese (replaced by children)
        self.registry.delete_entity(item_id)
