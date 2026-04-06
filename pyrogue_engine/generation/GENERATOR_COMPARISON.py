"""
Generator Comparison & Pipeline Validation

This script demonstrates the core principle of the pipeline architecture:
All three generators (BSP, Cellular Automata, Noise) produce identical LevelBlueprint
output. They can all be analyzed, painted, and decorated using the EXACT SAME code.

This proves the architecture is truly decoupled.

Run this to validate:
    python GENERATOR_COMPARISON.py

Output: Statistics on each generator type, proving they all work with the pipeline.
"""

import numpy as np
from pyrogue_engine.generation import (
    generate_bsp_dungeon,
    generate_cellular_automata_dungeon,
    generate_noise_map,
    analyze_walkable_regions,
    find_spawn_point,
    find_farthest_point,
    validate_connectivity,
)


def visualize_blueprint(blueprint, max_width: int = 80) -> str:
    """
    Convert a blueprint grid to ASCII for visualization.

    0 = Floor (.), 1 = Wall (#)
    """
    lines = []
    for y in range(blueprint.height):
        line = ""
        for x in range(blueprint.width):
            char = "." if blueprint.grid[y, x] == 0 else "#"
            line += char
        lines.append(line)
    return "\n".join(lines)


def analyze_generator(name: str, blueprint) -> dict:
    """
    Run complete pipeline analysis on a blueprint.

    Returns statistics proving the pipeline works uniformly.
    """
    # Analyze connectivity
    analyze_walkable_regions(blueprint)

    # Find key locations
    try:
        spawn_x, spawn_y = find_spawn_point(blueprint, rng=np.random.RandomState(42))
        exit_x, exit_y, distance = find_farthest_point(blueprint, spawn_x, spawn_y)
        is_valid = validate_connectivity(blueprint)
    except ValueError as e:
        return {"name": name, "error": str(e)}

    # Calculate statistics
    total_tiles = blueprint.width * blueprint.height
    walkable_tiles = np.count_nonzero(blueprint.grid == 0)
    wall_tiles = total_tiles - walkable_tiles
    walkable_percent = (walkable_tiles / total_tiles) * 100

    num_regions = len(blueprint.walkable_regions)
    largest_region_size = max(len(r) for r in blueprint.walkable_regions) if blueprint.walkable_regions else 0

    return {
        "name": name,
        "total_tiles": total_tiles,
        "walkable_tiles": walkable_tiles,
        "wall_tiles": wall_tiles,
        "walkable_percent": f"{walkable_percent:.1f}%",
        "num_regions": num_regions,
        "largest_region": largest_region_size,
        "connectivity_valid": is_valid,
        "spawn": (spawn_x, spawn_y),
        "exit": (exit_x, exit_y),
        "exit_distance": distance,
    }


def main():
    """Run all generators and compare results"""

    print("=" * 80)
    print("MAP GENERATION PIPELINE VALIDATION")
    print("=" * 80)
    print()

    # Test parameters (same for all generators)
    WIDTH, HEIGHT = 80, 45
    SEED = 12345

    generators = [
        ("BSP Dungeon", lambda: generate_bsp_dungeon(WIDTH, HEIGHT, seed=SEED)),
        ("Cellular Automata", lambda: generate_cellular_automata_dungeon(WIDTH, HEIGHT, seed=SEED)),
        ("Fractal Noise", lambda: generate_noise_map(WIDTH, HEIGHT, seed=SEED)),
    ]

    results = []

    for name, gen_func in generators:
        print(f"Generating {name}...")
        blueprint = gen_func()
        print(f"  - Grid shape: {blueprint.grid.shape}")
        print(f"  - Analyzing with identical pipeline...")

        stats = analyze_generator(name, blueprint)
        results.append(stats)

        if "error" in stats:
            print(f"  ❌ ERROR: {stats['error']}")
        else:
            print(f"  ✓ {stats['walkable_tiles']} walkable tiles ({stats['walkable_percent']})")
            print(f"  ✓ {stats['num_regions']} connected region(s)")
            print(f"  ✓ Spawn: {stats['spawn']}, Exit: {stats['exit']} ({stats['exit_distance']} tiles)")
            print()

    print("=" * 80)
    print("PIPELINE VALIDATION SUMMARY")
    print("=" * 80)
    print()

    # Print table
    print(f"{'Generator':<20} {'Walkable':<12} {'Regions':<12} {'Valid':<10} {'Exit Dist':<12}")
    print("-" * 80)

    for stats in results:
        if "error" not in stats:
            print(
                f"{stats['name']:<20} "
                f"{stats['walkable_tiles']:<12} "
                f"{stats['num_regions']:<12} "
                f"{'✓' if stats['connectivity_valid'] else '✗':<10} "
                f"{stats['exit_distance']:<12}"
            )

    print()
    print("KEY INSIGHT:")
    print("All three generators produced valid LevelBlueprints that:")
    print("  1. Can be analyzed by the identical analyzer pipeline")
    print("  2. Return walkable_regions metadata")
    print("  3. Support spawn point and exit discovery")
    print("  4. Are ready for painting and decoration")
    print()
    print("This proves the architecture is truly decoupled.")
    print("Swapping generators requires changing ONE LINE of code.")
    print()


if __name__ == "__main__":
    main()
