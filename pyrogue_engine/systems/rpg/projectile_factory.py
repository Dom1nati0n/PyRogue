"""
Projectile Factory - Utility for spawning projectiles in the world.

Simple helpers for creating sling stones, arrows, etc.
"""

import math
from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.systems.spatial.components import Position, Velocity
from .projectile import Projectile


def get_normalized_direction(source_pos: Position, target_x: int, target_y: int) -> tuple:
    """
    Calculate normalized direction vector from source to target.

    Args:
        source_pos: Position component of shooter
        target_x, target_y: Target coordinates

    Returns:
        (dx, dy) normalized to unit length
    """
    dx = target_x - source_pos.x
    dy = target_y - source_pos.y

    dist = math.sqrt(dx*dx + dy*dy)
    if dist > 0:
        dx /= dist
        dy /= dist

    return dx, dy


def spawn_projectile(
    registry: Registry,
    shooter_id: int,
    weapon_tag: str,
    x: float,
    y: float,
    z: float = 0,
    dx: float = 1.0,
    dy: float = 0.0,
) -> int:
    """
    Spawn a projectile entity in the world.

    Args:
        registry: ECS registry
        shooter_id: Entity ID of the one firing
        weapon_tag: Weapon tag (e.g., "Weapon.Ranged.Bow")
        x, y, z: Starting position
        dx, dy: Velocity direction (will be normalized if needed)

    Returns:
        Entity ID of the new projectile
    """
    projectile_id = registry.create_entity()
    registry.add_component(projectile_id, Position(int(x), int(y), int(z)))
    registry.add_component(projectile_id, Velocity(dx=dx, dy=dy))
    registry.add_component(projectile_id, Projectile(
        shooter_id=shooter_id,
        weapon_tag=weapon_tag,
    ))
    return projectile_id


def fire_sling(registry: Registry, shooter_id: int, target_x: int, target_y: int) -> int:
    """Fire a sling stone toward a target."""
    shooter_pos = registry.get_component(shooter_id, Position)
    if not shooter_pos:
        raise ValueError(f"Shooter {shooter_id} has no Position component")

    dx, dy = get_normalized_direction(shooter_pos, target_x, target_y)

    return spawn_projectile(
        registry,
        shooter_id=shooter_id,
        weapon_tag="Weapon.Ranged.Sling",
        x=shooter_pos.x,
        y=shooter_pos.y,
        z=shooter_pos.z,
        dx=dx,
        dy=dy,
    )


def fire_bow(registry: Registry, shooter_id: int, target_x: int, target_y: int) -> int:
    """Fire a bow arrow toward a target."""
    shooter_pos = registry.get_component(shooter_id, Position)
    if not shooter_pos:
        raise ValueError(f"Shooter {shooter_id} has no Position component")

    dx, dy = get_normalized_direction(shooter_pos, target_x, target_y)

    return spawn_projectile(
        registry,
        shooter_id=shooter_id,
        weapon_tag="Weapon.Ranged.Bow",
        x=shooter_pos.x,
        y=shooter_pos.y,
        z=shooter_pos.z,
        dx=dx,
        dy=dy,
    )
