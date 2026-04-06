"""
Field of View (FOV) System - Pure shadowcasting algorithm + ECS integration.

The pure algorithm (compute_shadowcast_fov) is completely decoupled from ECS.
It takes only:
- Source position
- Max radius
- A callback to check if a tile blocks vision

The PerceptionSystem wraps this for ECS integration.
"""

from typing import Callable, Set, Tuple


# ---------------------------------------------------------------------------
# Pure FOV Algorithm (No ECS Dependencies)
# ---------------------------------------------------------------------------

def compute_shadowcast_fov(
    source_x: int,
    source_y: int,
    max_radius: int,
    is_opaque_cb: Callable[[int, int], bool],
) -> Set[Tuple[int, int]]:
    """
    Calculate field of view using 8-way raycasting shadowcasting.

    Pure mathematical implementation with NO ECS knowledge.
    Caller provides a callback to check tile opacity.

    Args:
        source_x, source_y: Position to calculate FOV from
        max_radius: How far vision extends
        is_opaque_cb: Callback(x, y) -> bool. True if tile blocks vision.

    Returns:
        Set of (x, y) tuples representing visible tiles.

    Example:
        def is_opaque(x, y):
            return tile_system.blocks_vision(tile_system.get_tile_at(x, y, 0))

        visible = compute_shadowcast_fov(10, 10, 8, is_opaque)
    """
    visible_tiles = {(source_x, source_y)}

    # Cast rays in 8 directions
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue

            # Trace along this ray
            x, y = source_x + dx, source_y + dy
            for distance in range(1, max_radius + 1):
                # Mark as visible
                visible_tiles.add((x, y))

                # If tile blocks vision, stop tracing this ray
                if is_opaque_cb(x, y):
                    break

                # Continue in this direction
                x += dx
                y += dy

    return visible_tiles


# ---------------------------------------------------------------------------
# PerceptionSystem (ECS Integration)
# ---------------------------------------------------------------------------

class PerceptionSystem:
    """
    ECS System that calculates FOV for entities with Vision component.

    Does NOT emit game-specific events like "CreatureSensed".
    Simply calculates FOV and stores result in VisibleTiles component.

    The game can:
    - Query VisibleTiles component directly
    - Listen for custom events based on what's in visible tiles
    - Use this data for rendering, AI, etc.
    """

    def __init__(self, tile_query_interface):
        """
        Args:
            tile_query_interface: Object with blocks_vision(tile_id) method
        """
        self.tile_query = tile_query_interface

    def process(self, ecs_registry) -> None:
        """
        Update VisibleTiles for all entities with Vision + Position.

        Queries the ECS registry for entities that have both Vision and
        VisibleTiles components, and updates the visible tiles cache.
        """
        # Import here to avoid circular dependency
        from .components import Position, Vision, VisibleTiles

        for entity, (pos, vision, visible_cache) in ecs_registry.view(Position, Vision, VisibleTiles):
            # Use the pure math function with a callback to tile query
            visible_tiles = compute_shadowcast_fov(
                source_x=pos.x,
                source_y=pos.y,
                max_radius=vision.radius,
                is_opaque_cb=self.tile_query.blocks_vision
            )

            # Update the cache
            visible_cache.tiles = visible_tiles
