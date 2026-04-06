"""
Spatial systems and components for pyrogue_engine.

This module contains reusable, battle-tested systems for:
- Field of View (FOV) calculation
- Movement and physics
- Collision detection
- Direction/facing management

All systems follow the pattern: pure math algorithms + optional ECS systems.
"""

# Components
from .components import (
    Position,
    Velocity,
    SubpixelAccumulator,
    Movement,
    Facing,
    Vision,
    VisibleTiles,
)

# FOV System
from .fov import compute_shadowcast_fov, PerceptionSystem

# Movement Systems
from .movement import KinematicMovementSystem, DirectionalFacingSystem

# Collision System
from .collision import (
    can_move_to,
    can_move_diagonal,
    CollisionEvent,
    CollisionSystem,
)

__all__ = [
    # Components
    "Position",
    "Velocity",
    "SubpixelAccumulator",
    "Movement",
    "Facing",
    "Vision",
    "VisibleTiles",
    # FOV
    "compute_shadowcast_fov",
    "PerceptionSystem",
    # Movement
    "KinematicMovementSystem",
    "DirectionalFacingSystem",
    # Collision
    "can_move_to",
    "can_move_diagonal",
    "CollisionEvent",
    "CollisionSystem",
]
