"""
Height Map Generator - Creates natural terrain elevation using Perlin noise

The height map is a 2D array where each (x, y) coordinate stores the Z-height
of the natural surface at that location. Terrain exists from Z=0 up to this height.

Uses Fractal Brownian Motion (multiple octaves of Perlin-like noise) to create
realistic, varied elevation with smooth transitions.
"""

import numpy as np
from .generators.noise import NoiseGenerator
from .level_blueprint import LevelBlueprint


class HeightMapGenerator:
    """
    Generates a natural height map using Perlin noise.

    The output is a 2D array of elevation values, suitable for populating
    the LevelBlueprint.surface_map.
    """

    def __init__(
        self,
        width: int = 200,
        height: int = 200,
        max_elevation: int = 20,  # Max Z-height above sea level
        sea_level: int = 12,  # Baseline water level
        scale: float = 50.0,  # Noise scale (larger = more spread out features)
        octaves: int = 4,  # Number of noise layers
        persistence: float = 0.5,  # Amplitude falloff per octave
        lacunarity: float = 2.0,  # Frequency multiplier per octave
    ):
        """
        Initialize the height map generator.

        Args:
            width: Map width (X-axis)
            height: Map height (Y-axis)
            max_elevation: Maximum elevation above sea level
            sea_level: Baseline water level (Z-coordinate)
            scale: Noise scale
            octaves: Number of noise layers
            persistence: Amplitude falloff
            lacunarity: Frequency multiplier
        """
        self.width = width
        self.height = height
        self.max_elevation = max_elevation
        self.sea_level = sea_level
        self.scale = scale
        self.octaves = octaves
        self.persistence = persistence
        self.lacunarity = lacunarity

    def generate(self, seed: int = 0) -> np.ndarray:
        """
        Generate a height map.

        Args:
            seed: Random seed for reproducibility

        Returns:
            2D numpy array of shape (width, height) with Z-heights
        """
        # Use the existing NoiseGenerator to create a noise field
        noise_gen = NoiseGenerator(
            width=self.width,
            height=self.height,
            scale=self.scale,
            octaves=self.octaves,
            persistence=self.persistence,
            lacunarity=self.lacunarity,
            threshold=0.5,  # Not used in our elevation calculation
        )

        # Create noise field (same as in NoiseGenerator.generate)
        noise_field = np.zeros((self.height, self.width), dtype=np.float32)

        amplitude = 1.0
        frequency = 1.0
        max_amplitude = 0.0

        from .generators.noise import _perlin_like_noise

        for octave in range(self.octaves):
            for y in range(self.height):
                for x in range(self.width):
                    sample_x = (x / self.scale) * frequency
                    sample_y = (y / self.scale) * frequency

                    noise_value = _perlin_like_noise(sample_x, sample_y, seed + octave)
                    noise_field[y, x] += noise_value * amplitude

            amplitude *= self.persistence
            frequency *= self.lacunarity
            max_amplitude += amplitude

        # Normalize noise to 0-1 range
        if max_amplitude > 0:
            noise_field /= max_amplitude

        # Convert noise values to elevation heights
        # noise_field ranges 0-1, we want elevation from sea_level to sea_level + max_elevation
        height_map = np.zeros((self.width, self.height), dtype=np.uint8)

        for x in range(self.width):
            for y in range(self.height):
                noise_value = noise_field[y, x]
                # Map noise (0-1) to elevation (sea_level to sea_level + max_elevation)
                z_height = int(self.sea_level + noise_value * self.max_elevation)
                # Clamp to valid range
                z_height = min(max(0, z_height), 35)
                height_map[x, y] = z_height

        return height_map

    def populate_blueprint(self, blueprint: LevelBlueprint, seed: int = 0) -> None:
        """
        Generate a height map and populate a LevelBlueprint's surface_map.

        Args:
            blueprint: The LevelBlueprint to populate
            seed: Random seed
        """
        height_map = self.generate(seed)
        blueprint.surface_map = height_map
        print(f"[HeightMapGenerator] Generated height map (min={height_map.min()}, max={height_map.max()}, mean={height_map.mean():.1f})")


def generate_natural_height_map(
    width: int = 200,
    height: int = 200,
    max_elevation: int = 20,
    sea_level: int = 12,
    seed: int = 0,
) -> np.ndarray:
    """
    Convenience function: Generate a height map in one call.

    Args:
        width: Map width
        height: Map height
        max_elevation: Max elevation above sea level
        sea_level: Baseline water level
        seed: Random seed

    Returns:
        2D numpy array of Z-heights
    """
    gen = HeightMapGenerator(width, height, max_elevation, sea_level)
    return gen.generate(seed)
