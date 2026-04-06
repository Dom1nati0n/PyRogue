"""
Flood Fill Analyzer - Topology Analysis

Scans the level blueprint to find connected components (regions of walkable tiles).
This metadata is essential for:
- Validating that the map is fully connected
- Finding spawn zones away from each other
- Detecting unreachable areas
- Placing key features (stairs, treasure)

Pure math: Input grid → Output: list of regions
"""

from typing import Set, List, Tuple
import numpy as np

from ..level_blueprint import LevelBlueprint


def flood_fill_region(
    grid: np.ndarray,
    start_x: int,
    start_y: int,
    walkable_value: int = 0,
) -> Set[Tuple[int, int]]:
    """
    Flood fill from a starting position, finding all connected walkable tiles.

    Uses iterative BFS (breadth-first search) instead of recursion to avoid
    stack overflow on large regions.

    Args:
        grid: 2D array (height, width)
        start_x, start_y: Starting position
        walkable_value: Which grid value represents walkable (default 0)

    Returns:
        Set of (x, y) tuples representing the connected region
    """
    height, width = grid.shape
    visited = set()
    region = set()
    queue = [(start_x, start_y)]

    while queue:
        x, y = queue.pop(0)

        # Skip if already visited or out of bounds
        if (x, y) in visited:
            continue
        if not (0 <= x < width and 0 <= y < height):
            continue
        if grid[y, x] != walkable_value:
            continue

        # Mark as visited and add to region
        visited.add((x, y))
        region.add((x, y))

        # Add neighbors (4-way connectivity)
        queue.append((x + 1, y))
        queue.append((x - 1, y))
        queue.append((x, y + 1))
        queue.append((x, y - 1))

    return region


def analyze_walkable_regions(blueprint: LevelBlueprint) -> List[Set[Tuple[int, int]]]:
    """
    Find all connected walkable regions in the blueprint.

    Updates blueprint.walkable_regions in place.

    Args:
        blueprint: LevelBlueprint to analyze

    Returns:
        List of regions, where each region is a Set of (x, y) tuples

    Example:
        >>> regions = analyze_walkable_regions(blueprint)
        >>> largest_region = max(regions, key=len)
        >>> if len(regions) > 1:
        >>>     print(f"WARNING: {len(regions)} disconnected regions!")
    """
    visited = set()
    regions = []

    for y in range(blueprint.height):
        for x in range(blueprint.width):
            if (x, y) in visited or blueprint.grid[y, x] != 0:
                continue

            # Found new region—flood fill it
            region = flood_fill_region(blueprint.grid, x, y)
            regions.append(region)
            visited.update(region)

    # Update blueprint
    blueprint.walkable_regions = regions

    return regions


def get_largest_region(regions: List[Set[Tuple[int, int]]]) -> Set[Tuple[int, int]]:
    """
    Return the largest connected region (usually the main dungeon).

    Args:
        regions: List of regions from analyze_walkable_regions()

    Returns:
        The region with the most tiles

    Useful for: Placing player spawn point in main area, not isolated pockets
    """
    if not regions:
        return set()
    return max(regions, key=len)


def validate_connectivity(blueprint: LevelBlueprint) -> bool:
    """
    Check if the level is fully connected.

    A valid dungeon should have only ONE connected region of walkable tiles.

    Args:
        blueprint: LevelBlueprint to validate

    Returns:
        True if fully connected, False if isolated regions exist
    """
    regions = analyze_walkable_regions(blueprint)
    return len(regions) == 1


def find_spawn_point(
    blueprint: LevelBlueprint,
    prefer_region: Set[Tuple[int, int]] = None,
    rng: np.random.RandomState = None,
) -> Tuple[int, int]:
    """
    Find a good spawn point in the largest walkable region.

    Args:
        blueprint: LevelBlueprint to analyze
        prefer_region: If set, pick from this region. Otherwise use largest.
        rng: Random number generator (uses numpy RandomState)

    Returns:
        (x, y) coordinate for spawning
    """
    if rng is None:
        rng = np.random.RandomState()

    # Get target region
    if prefer_region is None:
        regions = analyze_walkable_regions(blueprint)
        prefer_region = get_largest_region(regions)

    if not prefer_region:
        raise ValueError("No valid spawn region found")

    # Pick random tile from region
    tiles = list(prefer_region)
    idx = rng.randint(0, len(tiles))
    return tiles[idx]


def dijkstra_distance_map(
    blueprint: LevelBlueprint,
    start_x: int,
    start_y: int,
) -> np.ndarray:
    """
    Create a Dijkstra distance map from a starting position.

    Useful for:
    - Finding the furthest walkable point (place stairs there)
    - Creating heatmaps for AI spawning
    - Validating map connectivity

    Args:
        blueprint: LevelBlueprint
        start_x, start_y: Starting position

    Returns:
        2D array where each cell contains distance to start (or -1 if unreachable)
    """
    import heapq

    distance_map = np.full((blueprint.height, blueprint.width), -1, dtype=np.int16)
    distance_map[start_y, start_x] = 0

    # Priority queue: (distance, x, y)
    heap = [(0, start_x, start_y)]

    while heap:
        dist, x, y = heapq.heappop(heap)

        # Skip if we've already found a better path
        if distance_map[y, x] != -1 and distance_map[y, x] < dist:
            continue

        # Check all 4 neighbors
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < blueprint.width and 0 <= ny < blueprint.height):
                continue
            if blueprint.grid[ny, nx] != 0:  # Not walkable
                continue

            new_dist = dist + 1
            if distance_map[ny, nx] == -1 or distance_map[ny, nx] > new_dist:
                distance_map[ny, nx] = new_dist
                heapq.heappush(heap, (new_dist, nx, ny))

    return distance_map


def find_farthest_point(
    blueprint: LevelBlueprint,
    start_x: int,
    start_y: int,
) -> Tuple[int, int, int]:
    """
    Find the walkable tile furthest from a starting point.

    Useful for placing stairs, bosses, treasure at max distance from spawn.

    Args:
        blueprint: LevelBlueprint
        start_x, start_y: Starting position

    Returns:
        (x, y, distance) of the farthest reachable tile
    """
    dist_map = dijkstra_distance_map(blueprint, start_x, start_y)

    # Find max reachable distance
    max_dist = np.max(dist_map)
    if max_dist <= 0:
        raise ValueError("No reachable tiles from start point")

    # Find all tiles at max distance
    farthest_tiles = np.argwhere(dist_map == max_dist)
    if len(farthest_tiles) == 0:
        raise ValueError("No farthest tiles found")

    # Pick random one if multiple
    idx = np.random.randint(0, len(farthest_tiles))
    y, x = farthest_tiles[idx]

    return (int(x), int(y), int(max_dist))
