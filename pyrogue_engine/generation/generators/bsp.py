"""
BSP Tree Map Generator - Classic Dungeon Generation

Binary Space Partitioning recursively divides the dungeon into rectangles,
then carves rooms within each leaf, and connects adjacent rooms with corridors.

This is pure math—no ECS, no game-specific logic. Just:
Input: width, height, min_room_size, seed
Output: LevelBlueprint with valid dungeon grid

Key features:
- Deterministic (seeded RNG)
- Produces rooms connected by corridors
- No isolated dead-ends (all areas are connected)
- Scalable (simple recursive subdivision)
"""

import numpy as np
from typing import List, Tuple, Optional

from ..level_blueprint import LevelBlueprint, Room


class BSPNode:
    """A node in the BSP tree"""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.left: Optional[BSPNode] = None
        self.right: Optional[BSPNode] = None
        self.room: Optional[Room] = None  # Leaf nodes contain rooms

    def is_leaf(self) -> bool:
        """True if this is a leaf node (no children)"""
        return self.left is None and self.right is None

    def __repr__(self) -> str:
        return f"<BSPNode({self.x}, {self.y}, {self.width}x{self.height})>"


class BSPGenerator:
    """
    Generates dungeons using Binary Space Partitioning.

    Algorithm:
    1. Start with root node covering entire map
    2. Recursively split nodes (horizontally or vertically)
    3. Stop when nodes reach min_room_size
    4. Create rooms in leaf nodes
    5. Connect adjacent rooms with corridors
    """

    def __init__(
        self,
        width: int = 80,
        height: int = 45,
        min_room_size: int = 8,
        max_room_size: Optional[int] = None,
        h_split_chance: float = 0.5,
        seed: int = 0,
    ):
        """
        Args:
            width: Map width
            height: Map height
            min_room_size: Minimum room dimension (prevents tiny rooms)
            max_room_size: Maximum room dimension (None = no limit)
            h_split_chance: Probability of horizontal split vs vertical (0.5 = 50/50)
            seed: Random seed for reproducibility
        """
        self.width = width
        self.height = height
        self.min_room_size = min_room_size
        self.max_room_size = max_room_size
        self.h_split_chance = h_split_chance
        self.seed = seed
        self.rng = np.random.RandomState(seed)

    def generate(self) -> LevelBlueprint:
        """
        Generate a complete dungeon blueprint.

        Returns:
            LevelBlueprint with fully carved dungeon
        """
        # Start with solid walls
        blueprint = LevelBlueprint(
            width=self.width,
            height=self.height,
            grid=np.ones((self.height, self.width), dtype=np.uint8),
            seed=self.seed,
        )

        # Build BSP tree
        root = BSPNode(0, 0, self.width, self.height)
        self._partition_space(root)

        # Create rooms in leaf nodes
        self._carve_rooms(root, blueprint)

        # Connect rooms with corridors
        self._connect_rooms(root, blueprint)

        return blueprint

    def _partition_space(self, node: BSPNode) -> None:
        """
        Recursively partition the space using BSP.

        Stops when node is small enough or randomly chooses not to split.
        """
        # Base case: node is small enough
        if node.width <= self.min_room_size * 2 and node.height <= self.min_room_size * 2:
            return

        # Randomly decide to split (encourages variety)
        if self.rng.random() < 0.25:
            return

        # Decide split direction
        split_horizontally = self.rng.random() < self.h_split_chance

        # Calculate split position (with randomness)
        if split_horizontally:
            # Can't split if height is too small
            if node.height < self.min_room_size * 2:
                return

            # Split somewhere in middle third
            split_y = node.y + self.min_room_size + self.rng.randint(0, node.height - self.min_room_size * 2)

            # Create left (top) and right (bottom) children
            node.left = BSPNode(node.x, node.y, node.width, split_y - node.y)
            node.right = BSPNode(node.x, split_y, node.width, node.height - (split_y - node.y))
        else:
            # Can't split if width is too small
            if node.width < self.min_room_size * 2:
                return

            # Split somewhere in middle third
            split_x = node.x + self.min_room_size + self.rng.randint(0, node.width - self.min_room_size * 2)

            # Create left and right (vertical split)
            node.left = BSPNode(node.x, node.y, split_x - node.x, node.height)
            node.right = BSPNode(split_x, node.y, node.width - (split_x - node.x), node.height)

        # Recursively partition children
        if node.left:
            self._partition_space(node.left)
        if node.right:
            self._partition_space(node.right)

    def _carve_rooms(self, node: BSPNode, blueprint: LevelBlueprint) -> None:
        """
        Create a room in each leaf node.

        Rooms are smaller than their BSP nodes (leaves margin for walls).
        """
        if not node.is_leaf():
            # Recursively carve children
            if node.left:
                self._carve_rooms(node.left, blueprint)
            if node.right:
                self._carve_rooms(node.right, blueprint)
            return

        # Create room in leaf node
        # Room is slightly smaller than node (margin for walls)
        margin = 1
        room_width = max(self.min_room_size, node.width - margin * 2)
        room_height = max(self.min_room_size, node.height - margin * 2)

        # Center room in node (with randomness)
        room_x = node.x + margin + self.rng.randint(0, max(1, node.width - room_width - margin))
        room_y = node.y + margin + self.rng.randint(0, max(1, node.height - room_height - margin))

        # Clamp to max_room_size if set
        if self.max_room_size:
            room_width = min(room_width, self.max_room_size)
            room_height = min(room_height, self.max_room_size)

        # Create and carve room
        room = Room(room_x, room_y, room_width, room_height)
        node.room = room
        blueprint.carve_room(room, fill_value=0)
        blueprint.rooms.append(room)

    def _connect_rooms(self, node: BSPNode, blueprint: LevelBlueprint) -> None:
        """
        Connect rooms with corridors by recursively connecting child rooms.
        """
        if node.is_leaf():
            return

        # Get rooms from left and right subtrees
        left_room = self._get_leaf_room(node.left)
        right_room = self._get_leaf_room(node.right)

        if left_room and right_room:
            # Connect the two rooms with a corridor
            c1 = left_room.center
            c2 = right_room.center
            blueprint.carve_corridor(c1[0], c1[1], c2[0], c2[1])

        # Recursively connect children
        if node.left:
            self._connect_rooms(node.left, blueprint)
        if node.right:
            self._connect_rooms(node.right, blueprint)

    def _get_leaf_room(self, node: Optional[BSPNode]) -> Optional[Room]:
        """
        Recursively find a room in the given subtree.

        Returns the rightmost leaf room (for consistent corridor placement).
        """
        if node is None:
            return None
        if node.is_leaf():
            return node.room
        # Prefer right subtree (creates more interesting patterns)
        right_room = self._get_leaf_room(node.right)
        if right_room:
            return right_room
        return self._get_leaf_room(node.left)


def generate_bsp_dungeon(
    width: int = 80,
    height: int = 45,
    min_room_size: int = 8,
    seed: int = 0,
) -> LevelBlueprint:
    """
    Convenience function: generate a BSP dungeon in one call.

    Args:
        width: Map width
        height: Map height
        min_room_size: Minimum room size
        seed: Random seed

    Returns:
        LevelBlueprint ready for analysis/painting
    """
    generator = BSPGenerator(width, height, min_room_size, seed=seed)
    return generator.generate()
