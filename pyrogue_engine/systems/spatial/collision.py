"""
Collision Detection System - Pure math for movement validation and collision events.

This module provides:
1. Pure collision check algorithms (no ECS dependencies)
2. A generic CollisionSystem prefab for ECS integration
3. Event emission when collisions occur

The game provides callbacks to check tile walkability and entity occupancy.
The system handles the rest: diagonal wall clipping prevention, collision detection, event dispatch.
"""

from typing import Callable, Optional, Tuple, Any


# ---------------------------------------------------------------------------
# Pure Collision Algorithms (No ECS)
# ---------------------------------------------------------------------------

def can_move_to(
    x: int,
    y: int,
    is_tile_walkable_cb: Callable[[int, int], bool],
    is_tile_occupied_cb: Optional[Callable[[int, int], Tuple[bool, Optional[int]]]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Check if a position is valid for movement.

    Args:
        x, y: Target position
        is_tile_walkable_cb: Callback that returns True if tile is walkable
        is_tile_occupied_cb: Optional callback that returns (is_occupied, entity_id)

    Returns:
        (can_move: bool, collision_type: str or None)
        collision_type can be: "wall", "entity", None (no collision)
    """
    # Check if tile is walkable
    if not is_tile_walkable_cb(x, y):
        return False, "wall"

    # Check if tile is occupied by an entity
    if is_tile_occupied_cb:
        is_occupied, entity_id = is_tile_occupied_cb(x, y)
        if is_occupied:
            return False, "entity"

    return True, None


def can_move_diagonal(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    is_tile_walkable_cb: Callable[[int, int], bool],
) -> Tuple[bool, Optional[str]]:
    """
    Check if diagonal movement is valid, preventing corner-clipping.

    When moving diagonally (e.g., from (0,0) to (1,1)), we must ensure
    that BOTH intermediate tiles are walkable:
    - (1, 0) must be walkable
    - (0, 1) must be walkable

    This prevents the classic roguelike bug where you squeeze through
    a one-tile-wide diagonal gap between two walls.

    Args:
        start_x, start_y: Current position
        end_x, end_y: Target position
        is_tile_walkable_cb: Callback that returns True if tile is walkable

    Returns:
        (can_move: bool, collision_type: str or None)
    """
    dx = end_x - start_x
    dy = end_y - start_y

    # Only applies to diagonal movement
    if abs(dx) != 1 or abs(dy) != 1:
        # Not diagonal, use standard check
        return can_move_to(end_x, end_y, is_tile_walkable_cb)

    # For diagonal, both intermediate tiles must be walkable
    intermediate_1 = (end_x, start_y)  # Move horizontally first
    intermediate_2 = (start_x, end_y)  # Move vertically first

    # If either intermediate is blocked, the diagonal is blocked
    if not is_tile_walkable_cb(intermediate_1[0], intermediate_1[1]):
        return False, "wall"

    if not is_tile_walkable_cb(intermediate_2[0], intermediate_2[1]):
        return False, "wall"

    # Both intermediates clear, check the target
    return can_move_to(end_x, end_y, is_tile_walkable_cb)


# ---------------------------------------------------------------------------
# 3D Collision Functions (Z-Aware)
# ---------------------------------------------------------------------------

def can_move_to_3d(
    x: int,
    y: int,
    z: int,
    is_tile_walkable_cb: Callable[[int, int, int], bool],
    is_tile_occupied_cb: Optional[Callable[[int, int, int], Tuple[bool, Optional[int]]]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Check if a 3D position is valid for movement.

    Ensures:
    - Target tile (x, y, z) is walkable
    - There is a floor below (tile at z-1 exists and is solid or z=0)
    - Target is not occupied by another entity

    Args:
        x, y, z: Target 3D position
        is_tile_walkable_cb: Callback that returns True if 3D tile is walkable
        is_tile_occupied_cb: Optional callback that returns (is_occupied, entity_id)

    Returns:
        (can_move: bool, collision_type: str or None)
    """
    # Check if tile is walkable
    if not is_tile_walkable_cb(x, y, z):
        return False, "wall"

    # Check if there's a floor below (or if z == 0, we're on bedrock)
    # For now, just allow any Z movement
    # TODO: Implement gravity/floor requirements

    # Check if tile is occupied by an entity
    if is_tile_occupied_cb:
        is_occupied, entity_id = is_tile_occupied_cb(x, y, z)
        if is_occupied:
            return False, "entity"

    return True, None


# ---------------------------------------------------------------------------
# Collision Events (Generic)
# ---------------------------------------------------------------------------

class CollisionEvent:
    """
    Event fired when movement would result in a collision.

    Can be emitted to the event bus for reactive collision handling.
    Systems that care about collisions (traps, projectiles, etc.) subscribe to this.
    """
    def __init__(
        self,
        entity_id: int,
        target_x: int,
        target_y: int,
        collision_type: str,  # "wall", "entity", etc.
        target_entity_id: Optional[int] = None,
    ):
        self.event_type = "spatial.collision"
        self.entity_id = entity_id
        self.target_x = target_x
        self.target_y = target_y
        self.collision_type = collision_type
        self.target_entity_id = target_entity_id  # If collision_type == "entity"

    def __str__(self) -> str:
        return f"Collision(entity={self.entity_id}, type={self.collision_type}, target=({self.target_x},{self.target_y}))"

    def get_full_topic(self) -> str:
        """For event bus compatibility."""
        return self.event_type


# ---------------------------------------------------------------------------
# CollisionSystem (ECS Integration)
# ---------------------------------------------------------------------------

class CollisionSystem:
    """
    ECS System that detects when movement would result in collision.
    Emits CollisionEvent to event bus for reactive collision handling.

    Follows Principle 1: Logic is Reactive, Never Proactive
    - Detects collisions during movement validation
    - Emits CollisionEvent to event bus
    - Other systems (ProjectileSystem, TrapSystem, etc.) listen and react

    Usage:
        - PhysicsSystem moves entities (Position + Velocity)
        - CollisionSystem checks if new_position would collide BEFORE PhysicsSystem applies it
        - If collision detected, CollisionSystem emits CollisionEvent
        - Reactive systems listen and respond (e.g., ProjectileSystem attacks on collision)
        - PhysicsSystem can then decide: block movement, allow collision, etc.
    """

    def __init__(self, tile_query_interface, entity_query_interface, event_bus: Optional[Any] = None):
        """
        Args:
            tile_query_interface: Object with is_tile_walkable(x, y) method
            entity_query_interface: Object with is_position_occupied(x, y) method
                                   that returns (occupied: bool, entity_id: int or None)
            event_bus: EventBus for emitting collision events (optional for backwards compat)
        """
        self.tile_query = tile_query_interface
        self.entity_query = entity_query_interface
        self.event_bus = event_bus
        self.pending_collisions = []

    def process(self, ecs_registry, dt: float) -> None:
        """
        Check for collisions during movement validation.

        Queries all entities with Position + Movement + optional Velocity,
        and checks if the proposed new position would collide.

        Emits collision events to event bus for reactive systems to handle.
        Does NOT modify position—that's the PhysicsSystem's job.
        """
        self.pending_collisions.clear()

        for entity, (pos, velocity) in ecs_registry.view(type(pos), type(velocity)):
            # Calculate new position if movement were applied
            new_x = int(pos.x + velocity.dx)
            new_y = int(pos.y + velocity.dy)

            # Skip if no movement
            if new_x == pos.x and new_y == pos.y:
                continue

            # Check for collision
            can_move, collision_type = can_move_diagonal(
                int(pos.x), int(pos.y),
                new_x, new_y,
                self.tile_query.is_tile_walkable
            )

            if not can_move:
                # Collision detected—create and emit event
                target_entity_id = None
                if collision_type == "entity":
                    _, target_entity_id = self.entity_query.is_position_occupied(new_x, new_y)

                collision_event = CollisionEvent(
                    entity_id=entity,
                    target_x=new_x,
                    target_y=new_y,
                    collision_type=collision_type,
                    target_entity_id=target_entity_id
                )
                self.pending_collisions.append(collision_event)

                # Emit to event bus for reactive systems
                if self.event_bus:
                    self.event_bus.emit(collision_event)

    def get_collisions(self):
        """Return list of collision events that occurred this frame (for backwards compatibility)"""
        return self.pending_collisions
