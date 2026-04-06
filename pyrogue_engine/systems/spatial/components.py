"""
Base spatial components for the engine.

These are generic, reusable components that any game using pyrogue_engine
can use or extend.
"""

from dataclasses import dataclass


@dataclass
class Position:
    """Entity's position in world space"""
    x: int
    y: int
    z: int = 0  # Layer/depth (for multi-level dungeons)


@dataclass
class Velocity:
    """Entity's movement velocity (per update)"""
    dx: float = 0.0
    dy: float = 0.0


@dataclass
class SubpixelAccumulator:
    """Stores fractional movement for pixel-perfect physics"""
    sub_x: float = 0.0
    sub_y: float = 0.0


@dataclass
class Movement:
    """Physics parameters for movement (acceleration, speed, friction)"""
    max_speed: float = 200.0
    acceleration: float = 800.0
    friction: float = 0.85


@dataclass
class Facing:
    """Direction entity is facing (for animations, aiming, etc.)"""
    direction: str = "DOWN_RIGHT"
    cooldown: float = 0.0  # Time before direction can change again (hysteresis)
    # 8 cardinal directions: UP, DOWN, LEFT, RIGHT, UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT


@dataclass
class Vision:
    """FOV/perception range for entities that can see"""
    radius: int = 8
    blocks_light: bool = False


@dataclass
class VisibleTiles:
    """Cache of tiles visible from this entity's position"""
    tiles: set = None  # Set of (x, y) tuples

    def __post_init__(self):
        if self.tiles is None:
            self.tiles = set()
