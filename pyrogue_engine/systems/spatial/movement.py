"""
Movement and Facing Systems - Kinematic physics and directional facing.

KinematicMovementSystem: Applies velocity to position (position += velocity * dt)
DirectionalFacingSystem: Updates facing direction based on velocity

Separated by Single Responsibility Principle:
- Movement doesn't care how velocity got set (input, AI, etc.)
- Facing doesn't care about position changes—only direction
- Animation/rendering queries Facing component as needed
"""

from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# KinematicMovementSystem
# ---------------------------------------------------------------------------

class KinematicMovementSystem:
    """
    Updates entity positions based on velocity over delta_time.

    This system is completely blind to:
    - Where velocity came from (input, AI, pushback, etc.)
    - Whether movement will collide (that's CollisionSystem's job)
    - What sprite to display

    It simply does: position += velocity * dt

    Note: Collision checking happens in CollisionSystem BEFORE this runs.
    """

    def process(self, ecs_registry, dt: float) -> None:
        """
        Apply velocity to position for all moving entities.

        Args:
            ecs_registry: The ECS Registry
            dt: Delta time since last frame
        """
        # Import here to avoid circular dependency
        from .components import Position, Velocity

        for entity, (pos, velocity) in ecs_registry.view(Position, Velocity):
            if velocity.dx == 0.0 and velocity.dy == 0.0:
                continue

            # Simple kinematic update
            pos.x += velocity.dx * dt
            pos.y += velocity.dy * dt


class SubpixelKinematicMovementSystem:
    """
    Updates position with sub-pixel accumulation for pixel-perfect movement.

    Useful for games where consistent speed in all directions is important
    (e.g., speedrunning). The sub-pixel accumulator tracks fractional pixels
    so diagonal movement doesn't accumulate rounding errors.

    Usage:
        velocity = Velocity(dx=200, dy=200)  # pixels per second
        subpixel = SubpixelAccumulator(sub_x=0, sub_y=0)

        With dt=0.016 (60fps):
        - Each frame: 200 * 0.016 = 3.2 pixels
        - Frame 1: move 3, accumulate 0.2
        - Frame 2: move 3, accumulate 0.4
        - Frame 3: move 4, accumulate 0 (3+0.2+0.2=0.4, 3.2 rounds to 3, so 0.4 remains)
    """

    def process(self, ecs_registry, dt: float) -> None:
        """
        Apply velocity to position with sub-pixel accumulation.

        Args:
            ecs_registry: The ECS Registry
            dt: Delta time since last frame
        """
        # Import here to avoid circular dependency
        from .components import Position, Velocity, SubpixelAccumulator

        for entity, (pos, velocity, subpixel) in ecs_registry.view(Position, Velocity, SubpixelAccumulator):
            if velocity.dx == 0.0 and velocity.dy == 0.0:
                continue

            # Accumulate sub-pixel movement
            subpixel.sub_x += velocity.dx * dt
            subpixel.sub_y += velocity.dy * dt

            # Extract whole pixels and update position
            pixel_x = int(subpixel.sub_x)
            pixel_y = int(subpixel.sub_y)

            if pixel_x != 0 or pixel_y != 0:
                pos.x += pixel_x
                pos.y += pixel_y

                # Keep fractional part for next frame
                subpixel.sub_x -= pixel_x
                subpixel.sub_y -= pixel_y


# ---------------------------------------------------------------------------
# DirectionalFacingSystem
# ---------------------------------------------------------------------------

class DirectionalFacingSystem:
    """
    Updates facing direction based on entity velocity.

    Separate from movement so that:
    - Facing direction can be used for aiming spells (without moving)
    - Animation system queries Facing independently
    - Developers can control facing direction manually if needed

    Includes hysteresis/cooldown to prevent jittery facing changes
    from noisy input.
    """

    # 8-way direction mapping (normalized input -> facing string)
    DIRECTION_MAP = {
        (-1, -1): "UP_LEFT",
        (0, -1): "UP",
        (1, -1): "UP_RIGHT",
        (-1, 0): "LEFT",
        (0, 0): None,  # No facing change
        (1, 0): "RIGHT",
        (-1, 1): "DOWN_LEFT",
        (0, 1): "DOWN",
        (1, 1): "DOWN_RIGHT",
    }

    def __init__(self, direction_change_cooldown: float = 0.03):
        """
        Args:
            direction_change_cooldown: Minimum time before facing can change (seconds).
                                       Prevents jitter from noisy input.
        """
        self.direction_change_cooldown = direction_change_cooldown

    def process(self, ecs_registry, dt: float) -> None:
        """
        Update facing direction for all entities with Velocity + Facing.

        Args:
            ecs_registry: The ECS Registry
            dt: Delta time since last frame
        """
        # Import here to avoid circular dependency
        from .components import Velocity, Facing

        for entity, (velocity, facing) in ecs_registry.view(Velocity, Facing):
            # Decrease cooldown
            facing.cooldown = max(0.0, facing.cooldown - dt)

            # Get new direction from velocity
            new_direction = self._get_facing_from_velocity(velocity.dx, velocity.dy)

            # Only change if cooldown is ready and direction actually changed
            if new_direction is not None and new_direction != facing.direction and facing.cooldown <= 0.0:
                facing.direction = new_direction
                facing.cooldown = self.direction_change_cooldown

    def _get_facing_from_velocity(self, vx: float, vy: float) -> Optional[str]:
        """
        Map normalized velocity to a facing direction.

        Args:
            vx, vy: Velocity components (can be any magnitude)

        Returns:
            Facing direction string or None if velocity is negligible
        """
        # Check if velocity is negligible (deadzone)
        magnitude = (vx**2 + vy**2)**0.5
        if magnitude < 0.1:
            return None

        # Normalize velocity
        norm_x = vx / magnitude if magnitude > 0 else 0
        norm_y = vy / magnitude if magnitude > 0 else 0

        # Quantize to 8-way direction
        dx = 1 if norm_x > 0.4 else (-1 if norm_x < -0.4 else 0)
        dy = 1 if norm_y > 0.4 else (-1 if norm_y < -0.4 else 0)

        return self.DIRECTION_MAP.get((dx, dy))


# Add cooldown tracking to Facing component
def add_cooldown_to_facing():
    """
    Patches the Facing component to add cooldown tracking.

    This is a helper since components are typically defined in components.py
    but DirectionalFacingSystem needs to track cooldown per-entity.

    In practice, you'd just add this to the Facing dataclass:
        facing_cooldown: float = 0.0
    """
    pass
