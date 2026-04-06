"""
LevelBlueprint - The Universal 3D Map Representation

Extended to support 3D worlds with natural surface topology.

This is the Rosetta Stone of the map generation pipeline. Every generator,
analyzer, and painter works with this standardized format.

Architecture:
    - grid: 3D numpy array (width x height x depth) for tile states
    - surface_map: 2D array (width x height) storing the Z-coordinate of natural surface
    - Terrain can exist from Z=0 up to surface_map[x,y]
    - Above the surface = empty air

Grid Convention:
    0 = Empty (walkable)
    1 = Solid wall (impassable)
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import numpy as np


@dataclass
class Room:
    """A rectangular region within the dungeon (XY plane)"""
    x: int
    y: int
    width: int
    height: int
    z_min: int = 0  # Min depth of room
    z_max: int = 36  # Max depth of room

    @property
    def center(self) -> Tuple[int, int]:
        """Return the center point of this room (XY)"""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        """Return (x1, y1, x2, y2) bounds"""
        return (self.x, self.y, self.x + self.width - 1, self.y + self.height - 1)

    def contains(self, px: int, py: int) -> bool:
        """Check if point is inside this room (ignores Z)"""
        return self.x <= px < self.x + self.width and self.y <= py < self.y + self.height


@dataclass
class LevelBlueprint:
    """
    3D map representation with natural surface topology.

    Attributes:
        width (int): Map width (X-axis)
        height (int): Map height (Y-axis)
        depth (int): Map depth (Z-axis, 0 to depth)

        grid (np.ndarray): 3D array (width, height, depth) where 0=walkable, 1=wall
        surface_map (np.ndarray): 2D height map (width, height) storing surface Z at each XY

        seed (int): RNG seed for reproducibility
        rooms (List[Room]): Detected rooms
        walkable_regions (List[set]): Connected walkable components
        distance_map (Optional[np.ndarray]): Dijkstra distance from entrance

        entrance (Optional[Tuple[int, int, int]]): Starting position (3D)
        exit (Optional[Tuple[int, int, int]]): Goal position (3D)
    """
    width: int
    height: int
    depth: int

    grid: np.ndarray = field(default_factory=lambda: np.zeros((0, 0, 0), dtype=np.uint8))
    surface_map: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.uint8))

    seed: int = 0
    rooms: List[Room] = field(default_factory=list)
    walkable_regions: List[set] = field(default_factory=list)
    distance_map: Optional[np.ndarray] = None

    entrance: Optional[Tuple[int, int, int]] = None
    exit: Optional[Tuple[int, int, int]] = None

    def __post_init__(self):
        """Initialize 3D grid and surface map if not already set"""
        if self.grid.size == 0:
            self.grid = np.zeros((self.width, self.height, self.depth), dtype=np.uint8)
        if self.surface_map.size == 0:
            # Default surface is middle of depth
            self.surface_map = np.full((self.width, self.height), self.depth // 2, dtype=np.uint8)

        # Validate integrity
        if self.grid.shape != (self.width, self.height, self.depth):
            raise ValueError(
                f"Grid shape {self.grid.shape} doesn't match dimensions {self.width}x{self.height}x{self.depth}"
            )
        if self.surface_map.shape != (self.width, self.height):
            raise ValueError(
                f"Surface map shape {self.surface_map.shape} doesn't match XY dimensions {self.width}x{self.height}"
            )

    def get_surface_z(self, x: int, y: int) -> int:
        """
        Returns the Z-coordinate of the natural surface at (x, y).
        Terrain exists from Z=0 up to this value.
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            return 0
        return int(self.surface_map[x, y])

    def set_surface_z(self, x: int, y: int, z: int) -> None:
        """Set the surface Z height at (x, y)"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.surface_map[x, y] = min(max(0, z), self.depth - 1)

    def is_walkable(self, x: int, y: int, z: int) -> bool:
        """Check if a 3D tile is walkable (in bounds and not a wall)"""
        if not (0 <= x < self.width and 0 <= y < self.height and 0 <= z < self.depth):
            return False
        return self.grid[x, y, z] == 0

    def set_tile(self, x: int, y: int, z: int, value: int) -> None:
        """Set a 3D tile value"""
        if 0 <= x < self.width and 0 <= y < self.height and 0 <= z < self.depth:
            self.grid[x, y, z] = value

    def get_tile(self, x: int, y: int, z: int) -> int:
        """Get a 3D tile value"""
        if not (0 <= x < self.width and 0 <= y < self.height and 0 <= z < self.depth):
            return 1  # Out of bounds = wall
        return int(self.grid[x, y, z])

    def carve_room(self, room: Room, fill_value: int = 0) -> None:
        """
        Carve out a rectangular room in 3D space.

        Args:
            room (Room): The room bounds
            fill_value (int): Value to set (0=walk, 1=wall)
        """
        x1, y1, x2, y2 = room.bounds
        z1, z2 = room.z_min, room.z_max
        self.grid[x1:x2+1, y1:y2+1, z1:z2+1] = fill_value

    def fill_all(self, value: int) -> None:
        """Fill entire 3D grid with a value"""
        self.grid[:] = value

    def get_random_walkable_tile(self, rng, z_layer: Optional[int] = None) -> Tuple[int, int, int]:
        """
        Get a random walkable tile. Optionally constrain to a specific Z layer.

        Args:
            rng: numpy random generator
            z_layer: If specified, only search this Z-layer

        Returns:
            (x, y, z) of a random walkable tile
        """
        if z_layer is not None:
            # Search only one Z layer
            walkable_tiles = np.argwhere(self.grid[:, :, z_layer] == 0)
            if len(walkable_tiles) == 0:
                raise ValueError(f"No walkable tiles at Z={z_layer}")
            idx = rng.randint(0, len(walkable_tiles))
            x, y = walkable_tiles[idx]
            return (int(x), int(y), int(z_layer))
        else:
            # Search entire 3D grid
            walkable_tiles = np.argwhere(self.grid == 0)
            if len(walkable_tiles) == 0:
                raise ValueError("No walkable tiles in blueprint")
            idx = rng.randint(0, len(walkable_tiles))
            x, y, z = walkable_tiles[idx]
            return (int(x), int(y), int(z))
