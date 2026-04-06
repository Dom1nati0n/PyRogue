"""
Map Generation Pipeline for pyrogue_engine

The pipeline architecture separates math from game logic:

1. GENERATORS (Pure Math)
   Input: dimensions, seed
   Output: LevelBlueprint with grid of 0s and 1s
   Example: BSPGenerator creates rooms connected by corridors

2. ANALYZERS (Topology)
   Input: LevelBlueprint
   Output: Metadata (regions, spawn points, distances)
   Example: flood_fill identifies connected components

3. PAINTERS (Engine Integration)
   Input: LevelBlueprint + theme dictionary
   Output: Spawned entities in your ECS
   Example: "0" → floor tile, "1" → wall tile

4. DECORATORS (Content Spawning)
   Input: LevelBlueprint + encounter tables
   Output: Monsters, loot, traps placed by metadata
   Example: "Place treasure at farthest point"

Every generator produces the same LevelBlueprint format, so analyzers,
painters, and decorators don't care HOW the map was created.
"""

from .level_blueprint import LevelBlueprint, Room
from .generators import (
    BSPGenerator,
    generate_bsp_dungeon,
    CellularAutomataGenerator,
    generate_cellular_automata_dungeon,
    NoiseGenerator,
    generate_noise_map,
)
from .analyzers import (
    analyze_walkable_regions,
    get_largest_region,
    validate_connectivity,
    find_spawn_point,
    dijkstra_distance_map,
    find_farthest_point,
)

__all__ = [
    # Types
    "LevelBlueprint",
    "Room",
    # Generators
    "BSPGenerator",
    "generate_bsp_dungeon",
    "CellularAutomataGenerator",
    "generate_cellular_automata_dungeon",
    "NoiseGenerator",
    "generate_noise_map",
    # Analyzers
    "analyze_walkable_regions",
    "get_largest_region",
    "validate_connectivity",
    "find_spawn_point",
    "dijkstra_distance_map",
    "find_farthest_point",
]
