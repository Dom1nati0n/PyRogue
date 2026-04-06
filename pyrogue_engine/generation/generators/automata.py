"""
Cellular Automata Map Generator - Organic, Cave-Like Structures

Pure math implementation of Conway-inspired cellular automata rules.
Generates highly organic, winding caves without worrying about connectivity.

The Pipeline handles disconnected regions:
- Generator produces raw grid (might have isolated caves)
- Analyzer finds connected regions via flood_fill
- Game uses largest region (or all regions, depending on design)

This separation of concerns is what makes the pipeline powerful:
The generator doesn't need to know about playability—just math.
"""

import numpy as np
from typing import Optional

from ..level_blueprint import LevelBlueprint


class CellularAutomataGenerator:
    """
    Generates organic, cave-like dungeons using Cellular Automata.

    Algorithm:
    1. Initialize random noise (roughly 48% filled)
    2. Apply smoothing rules repeatedly
    3. Classic ruleset: B5678/S45678 (cells become floor if surrounded by mostly floor)
    """

    # Grid values
    WALL = 1
    FLOOR = 0

    def __init__(
        self,
        width: int = 80,
        height: int = 45,
        fill_probability: float = 0.48,
        smoothing_iterations: int = 5,
        border_width: int = 2,
    ):
        """
        Args:
            width: Map width
            height: Map height
            fill_probability: Initial chance of spawning a floor tile (0-1)
            smoothing_iterations: Number of CA smoothing passes
            border_width: Thickness of solid wall border (prevents edge issues)
        """
        self.width = width
        self.height = height
        self.fill_probability = fill_probability
        self.smoothing_iterations = smoothing_iterations
        self.border_width = border_width

    def generate(self, seed: int = 0) -> LevelBlueprint:
        """
        Generate a complete cave system.

        Args:
            seed: Random seed for reproducibility

        Returns:
            LevelBlueprint with raw cave grid (might have disconnected regions)
        """
        rng = np.random.RandomState(seed)

        # Step 1: Initialize random noise
        # Start with solid walls everywhere
        grid = np.full((self.height, self.width), self.WALL, dtype=np.uint8)

        # Carve random floor tiles in the interior (leave border as walls)
        for y in range(self.border_width, self.height - self.border_width):
            for x in range(self.border_width, self.width - self.border_width):
                if rng.random() < self.fill_probability:
                    grid[y, x] = self.FLOOR

        # Step 2: Apply cellular automata smoothing
        for iteration in range(self.smoothing_iterations):
            grid = self._smooth_iteration(grid)

        # Step 3: Return blueprint (analyzer will handle connectivity)
        blueprint = LevelBlueprint(width=self.width, height=self.height, grid=grid, seed=seed)

        return blueprint

    def _smooth_iteration(self, grid: np.ndarray) -> np.ndarray:
        """
        Apply one iteration of cellular automata smoothing.

        Rules (Classic Cave Ruleset):
        - A WALL becomes FLOOR if surrounded by >4 FLOOR neighbors
        - A FLOOR becomes WALL if surrounded by <5 FLOOR neighbors

        This creates organic, connected caves through repeated application.
        """
        new_grid = np.copy(grid)

        for y in range(1, self.height - 1):
            for x in range(1, self.width - 1):
                floor_neighbors = self._count_floor_neighbors(grid, x, y)

                # Classic cave rules: B5678/S45678
                if grid[y, x] == self.WALL:
                    # Wall becomes floor if mostly surrounded by floors
                    new_grid[y, x] = self.FLOOR if floor_neighbors >= 5 else self.WALL
                else:
                    # Floor becomes wall if too many walls nearby
                    new_grid[y, x] = self.FLOOR if floor_neighbors >= 4 else self.WALL

        return new_grid

    def _count_floor_neighbors(self, grid: np.ndarray, x: int, y: int) -> int:
        """
        Count FLOOR tiles in the 3x3 neighborhood (including center).

        This is fast because we use NumPy slicing.
        """
        neighborhood = grid[y - 1 : y + 2, x - 1 : x + 2]
        return np.count_nonzero(neighborhood == self.FLOOR)


def generate_cellular_automata_dungeon(
    width: int = 80,
    height: int = 45,
    fill_probability: float = 0.48,
    smoothing_iterations: int = 5,
    seed: int = 0,
) -> LevelBlueprint:
    """
    Convenience function: generate a CA dungeon in one call.

    Args:
        width: Map width
        height: Map height
        fill_probability: Initial fill ratio
        smoothing_iterations: CA smoothing passes
        seed: Random seed

    Returns:
        LevelBlueprint ready for analysis
    """
    generator = CellularAutomataGenerator(
        width, height, fill_probability, smoothing_iterations
    )
    return generator.generate(seed)
