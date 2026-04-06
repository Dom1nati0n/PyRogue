#!/usr/bin/env python3
"""
Cheese Spawner - Factory for spawning debug cheese items in the world.

Usage:
    from spawn_cheese import spawn_cheese, SpawnCheesePattern

    # Spawn single cheese
    cheese_id = spawn_cheese(registry, x=10, y=10)

    # Spawn grid of cheese for testing
    SpawnCheesePattern.grid(registry, top_left=(10, 10), size=5, spacing=3)

    # Spawn random scatter
    SpawnCheesePattern.scatter(registry, center=(50, 50), count=20, radius=30)
"""

from typing import List, Tuple
from pyrogue_engine.core.ecs import Registry, Entity
from pyrogue_engine.systems.item.cheese_item import create_debug_cheese, ItemComponent, CheeseProperties


def spawn_cheese(registry: Registry, x: int, y: int, size: str = "normal") -> int:
    """
    Spawn a debug cheese item at the given coordinates.

    Args:
        registry: ECS Registry
        x: Spawn X coordinate
        y: Spawn Y coordinate
        size: "tiny", "small", "normal", "large"

    Returns:
        entity_id of the spawned cheese
    """
    entity_data = create_debug_cheese(x, y, size)

    entity = Entity()
    for component_name, component_data in entity_data["components"].items():
        if component_name == "PositionComponent":
            from pyrogue_engine.systems.spatial.components import Position
            entity.add_component(Position(**component_data))
        elif component_name == "ItemComponent":
            entity.add_component(ItemComponent(**component_data))
        elif component_name == "CheeseProperties":
            entity.add_component(CheeseProperties(**component_data))
        else:
            # Store as dict (e.g., TileSprite)
            entity.components[component_name] = component_data

    entity_id = registry.create_entity(entity)
    return entity_id


class SpawnCheesePattern:
    """Factory for spawning cheese in organized patterns."""

    @staticmethod
    def grid(
        registry: Registry,
        top_left: Tuple[int, int],
        size: int = 5,
        spacing: int = 3,
        cheese_size: str = "normal",
    ) -> List[int]:
        """
        Spawn cheese in a grid pattern.

        Args:
            registry: ECS Registry
            top_left: (x, y) starting position
            size: Grid size (e.g., 5 = 5x5 grid)
            spacing: Distance between cheese
            cheese_size: Size of each cheese

        Returns:
            List of entity_ids
        """
        entity_ids = []
        x0, y0 = top_left

        for i in range(size):
            for j in range(size):
                x = x0 + i * spacing
                y = y0 + j * spacing
                entity_id = spawn_cheese(registry, x, y, size=cheese_size)
                entity_ids.append(entity_id)

        print(f"[spawn_cheese] Spawned grid of {len(entity_ids)} cheese at {top_left}")
        return entity_ids

    @staticmethod
    def scatter(
        registry: Registry,
        center: Tuple[int, int],
        count: int = 20,
        radius: int = 30,
    ) -> List[int]:
        """
        Spawn cheese in a random scatter pattern.

        Args:
            registry: ECS Registry
            center: (x, y) center of scatter
            count: Number of cheese to spawn
            radius: Maximum distance from center

        Returns:
            List of entity_ids
        """
        import random

        entity_ids = []
        cx, cy = center

        for _ in range(count):
            # Random position within radius
            angle = random.uniform(0, 2 * 3.14159)
            r = random.uniform(0, radius)
            x = int(cx + r * (angle / 3.14159))
            y = int(cy + r * (angle / 3.14159))

            # Random size
            size = random.choice(["tiny", "small", "normal"])

            entity_id = spawn_cheese(registry, x, y, size=size)
            entity_ids.append(entity_id)

        print(f"[spawn_cheese] Spawned scatter of {len(entity_ids)} cheese at {center}")
        return entity_ids

    @staticmethod
    def trail(
        registry: Registry,
        start: Tuple[int, int],
        end: Tuple[int, int],
        count: int = 10,
    ) -> List[int]:
        """
        Spawn cheese in a trail from start to end.

        Args:
            registry: ECS Registry
            start: (x, y) start position
            end: (x, y) end position
            count: Number of cheese in trail

        Returns:
            List of entity_ids
        """
        entity_ids = []
        x0, y0 = start
        x1, y1 = end

        for i in range(count):
            t = i / max(count - 1, 1)  # 0 to 1
            x = int(x0 + (x1 - x0) * t)
            y = int(y0 + (y1 - y0) * t)
            entity_id = spawn_cheese(registry, x, y)
            entity_ids.append(entity_id)

        print(f"[spawn_cheese] Spawned trail of {len(entity_ids)} cheese from {start} to {end}")
        return entity_ids


if __name__ == "__main__":
    print("[spawn_cheese] Cheese spawner utility")
    print("Import and use:")
    print("  from spawn_cheese import spawn_cheese, SpawnCheesePattern")
    print("  spawn_cheese(registry, x=10, y=10)")
    print("  SpawnCheesePattern.grid(registry, (10, 10), size=5)")
