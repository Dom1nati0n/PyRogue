"""
Fractal Noise Map Generator - Organic Terrain with Gradient

Uses Perlin-like noise (simplex-style) for smooth, continuous terrain.
Perfect for overworlds, islands, varied elevation.

The noise is interpreted with a threshold:
- Noise > threshold → FLOOR (grassland, water, terrain)
- Noise ≤ threshold → WALL (mountains, impassable)

Multiple octaves of noise create fractal complexity.
"""

import numpy as np
from typing import Callable, Optional

from ..level_blueprint import LevelBlueprint


def _interpolate(t: float) -> float:
    """Smooth interpolation curve (fade function)"""
    return t * t * t * (t * (t * 6 - 15) + 10)


def _perlin_like_noise(x: float, y: float, seed: int = 0) -> float:
    """
    Simple Perlin-like noise function.

    Not true Perlin noise, but produces similar smooth gradients.
    For a full implementation, use the 'perlin_numpy' or 'opensimplex' package.

    This simplified version is sufficient for educational/prototype use.
    """
    # Hash function (deterministic based on seed + coordinates)
    def hash(xi: int, yi: int) -> float:
        h = seed + xi * 73856093 ^ yi * 19349663
        h = (h ^ (h >> 13)) * 1274126177
        h = h ^ (h >> 16)
        return float((h & 2147483647)) / 2147483648.0

    # Lattice coordinates
    xi = int(np.floor(x))
    yi = int(np.floor(y))

    # Fractional coordinates
    xf = x - xi
    yf = y - yi

    # Smooth interpolation
    u = _interpolate(xf)
    v = _interpolate(yf)

    # Hash corners
    n00 = hash(xi, yi)
    n10 = hash(xi + 1, yi)
    n01 = hash(xi, yi + 1)
    n11 = hash(xi + 1, yi + 1)

    # Interpolate
    nx0 = n00 * (1 - u) + n10 * u
    nx1 = n01 * (1 - u) + n11 * u
    result = nx0 * (1 - v) + nx1 * v

    return result


class NoiseGenerator:
    """
    Fractal noise generator for terrain maps.

    Uses multiple octaves of noise (fractal Brownian motion) to create
    rich, detailed terrain with smooth variation.
    """

    WALL = 1
    FLOOR = 0

    def __init__(
        self,
        width: int = 80,
        height: int = 45,
        scale: float = 50.0,
        octaves: int = 4,
        persistence: float = 0.5,
        lacunarity: float = 2.0,
        threshold: float = 0.5,
    ):
        """
        Args:
            width: Map width
            height: Map height
            scale: Noise scale (larger = more spread out features)
            octaves: Number of noise layers (more = more detail)
            persistence: How much each octave contributes (0-1)
            lacunarity: Frequency multiplier per octave (typically 2.0)
            threshold: Noise value above which tile is FLOOR
        """
        self.width = width
        self.height = height
        self.scale = scale
        self.octaves = octaves
        self.persistence = persistence
        self.lacunarity = lacunarity
        self.threshold = threshold

    def generate(self, seed: int = 0) -> LevelBlueprint:
        """
        Generate a noise-based map.

        Args:
            seed: Random seed

        Returns:
            LevelBlueprint with noise-based terrain grid
        """
        # Create noise field
        noise_field = np.zeros((self.height, self.width), dtype=np.float32)

        # Fractal Brownian Motion: combine multiple octaves
        amplitude = 1.0
        frequency = 1.0
        max_amplitude = 0.0

        for octave in range(self.octaves):
            for y in range(self.height):
                for x in range(self.width):
                    sample_x = (x / self.scale) * frequency
                    sample_y = (y / self.scale) * frequency

                    # Sample noise at this octave
                    noise_value = _perlin_like_noise(sample_x, sample_y, seed + octave)
                    noise_field[y, x] += noise_value * amplitude

            amplitude *= self.persistence
            frequency *= self.lacunarity
            max_amplitude += amplitude

        # Normalize noise to 0-1 range
        if max_amplitude > 0:
            noise_field /= max_amplitude

        # Convert to grid (threshold-based)
        grid = np.where(noise_field > self.threshold, self.FLOOR, self.WALL).astype(np.uint8)

        # Create blueprint
        blueprint = LevelBlueprint(width=self.width, height=self.height, grid=grid, seed=seed)

        return blueprint


def generate_noise_map(
    width: int = 80,
    height: int = 45,
    scale: float = 50.0,
    octaves: int = 4,
    threshold: float = 0.5,
    seed: int = 0,
) -> LevelBlueprint:
    """
    Convenience function: generate a noise map in one call.

    Args:
        width: Map width
        height: Map height
        scale: Noise scale
        octaves: Number of noise layers
        threshold: Noise threshold for floor/wall
        seed: Random seed

    Returns:
        LevelBlueprint ready for analysis
    """
    generator = NoiseGenerator(width, height, scale, octaves, threshold=threshold)
    return generator.generate(seed)
