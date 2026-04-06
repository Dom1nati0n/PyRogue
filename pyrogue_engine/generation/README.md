# Generation - Procedural Content Generation

This directory contains the procedural dungeon and level generation pipeline. The system is organized in 4 phases, each decoupled from the others.

## Pipeline Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ PHASE 1: GENERATORS (Pure Math)                              │
├──────────────────────────────────────────────────────────────┤
│ Input:  dimensions, seed                                     │
│ Output: LevelBlueprint (2D grid of 0s and 1s)               │
│ Examples: BSP, Cellular Automata, Noise                     │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PHASE 2: ANALYZERS (Topology)                                │
├──────────────────────────────────────────────────────────────┤
│ Input:  LevelBlueprint                                       │
│ Output: Metadata (spawn points, distances, regions)         │
│ Examples: flood_fill, dijkstra_distance_map                 │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PHASE 3: BUILDERS (Engine Integration - Your Game Code)     │
├──────────────────────────────────────────────────────────────┤
│ Input:  LevelBlueprint + theme                               │
│ Output: Spawned tile entities in ECS                         │
│ Example: 0 → floor tile, 1 → wall tile                      │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ PHASE 4: DECORATORS (Content Spawning - Your Game Code)     │
├──────────────────────────────────────────────────────────────┤
│ Input:  Metadata + encounter tables                          │
│ Output: Monsters, loot, traps placed on level               │
│ Example: "Place treasure at farthest point from start"      │
└──────────────────────────────────────────────────────────────┘
```

**Key Insight**: Every generator produces the same `LevelBlueprint` format, so analyzers, builders, and decorators don't care *how* the map was created. Swap generators freely.

---

## Directory Structure

### `generators/` — Phase 1: Pure Math
Create dungeon layouts using different algorithms.

**Generators:**
- `BSPGenerator` — Binary Space Partition (rectangular rooms connected by corridors)
- `CellularAutomataGenerator` — Conway's Game of Life variant (organic caves)
- `NoiseGenerator` — Perlin/Simplex noise for height maps

**Common Interface:**
```python
from pyrogue_engine.generation.generators import BSPGenerator

gen = BSPGenerator(seed=42)
blueprint = gen.generate(width=80, height=24, min_room_size=8)

# blueprint is a LevelBlueprint:
# - blueprint.grid: 2D numpy array (0=wall, 1=floor)
# - blueprint.rooms: List of Room objects
```

**Pure Functions** (unit-testable):
```python
from pyrogue_engine.generation.generators import generate_bsp_dungeon

grid = generate_bsp_dungeon(width=80, height=24, seed=42)
assert grid[0, 0] in (0, 1)  # Every tile is wall or floor
```

---

### `analyzers/` — Phase 2: Topology Analysis
Extract useful metadata from a generated level.

**Analyzers:**
- `analyze_walkable_regions()` — Find connected floor regions
- `get_largest_region()` — Get the main play area
- `validate_connectivity()` — Ensure all regions are connected
- `find_spawn_point()` — Find start position
- `dijkstra_distance_map()` — Compute distance from a point to all walkable tiles
- `find_farthest_point()` — Find the tile farthest from a location (for treasure)

**Example Usage:**
```python
from pyrogue_engine.generation.analyzers import (
    analyze_walkable_regions,
    find_spawn_point,
    dijkstra_distance_map
)

blueprint = gen.generate(width=80, height=24)

# Find all connected regions
regions = analyze_walkable_regions(blueprint)

# Find start position
start_x, start_y = find_spawn_point(blueprint, regions)

# Compute distance from start
distances = dijkstra_distance_map(blueprint, start_x, start_y)
```

---

### `builders/` — Phase 3: Engine Integration (Your Game Code)
This directory is empty—it's a placeholder for YOUR implementation.

Your code would:
1. Read the `LevelBlueprint` grid
2. Create tile entities for each floor/wall
3. Attach Position, Sprite, Collision components

**Example (pseudo-code):**
```python
def build_level(blueprint, registry, factory):
    for y in range(blueprint.height):
        for x in range(blueprint.width):
            if blueprint.grid[y, x] == 1:  # Floor
                factory.spawn_tile("stone_floor", x, y)
            else:  # Wall
                factory.spawn_tile("stone_wall", x, y)
```

---

### `level_blueprint.py`
Common output format used by all generators.

```python
@dataclass
class Room:
    x: int
    y: int
    width: int
    height: int

@dataclass
class LevelBlueprint:
    width: int
    height: int
    grid: np.ndarray  # 2D array, 0=wall, 1=floor
    rooms: List[Room]  # Rectangular rooms in the blueprint
```

---

### `GENERATION_GUIDE.md`
Detailed examples and patterns for generation.

---

## Quick Start

### 1. Generate a Dungeon
```python
from pyrogue_engine.generation import BSPGenerator

gen = BSPGenerator(seed=42)
blueprint = gen.generate(width=80, height=24, min_room_size=8)
```

### 2. Analyze It
```python
from pyrogue_engine.generation import (
    analyze_walkable_regions,
    find_spawn_point,
    dijkstra_distance_map
)

regions = analyze_walkable_regions(blueprint)
start_x, start_y = find_spawn_point(blueprint, regions)
distances = dijkstra_distance_map(blueprint, start_x, start_y)
```

### 3. Build It (Your Code)
```python
def build_level(blueprint, registry, factory):
    for y in range(blueprint.height):
        for x in range(blueprint.width):
            if blueprint.grid[y, x] == 1:
                factory.spawn_tile("floor", x, y)
            else:
                factory.spawn_tile("wall", x, y)

build_level(blueprint, registry, factory)
```

### 4. Decorate It (Your Code)
```python
def decorate_level(blueprint, registry, factory, distances):
    # Place treasure at the farthest point
    farthest = np.unravel_index(np.argmax(distances), distances.shape)
    factory.spawn_item("treasure_chest", farthest[1], farthest[0])

    # Place monsters at spawn points
    for room in blueprint.rooms[1:]:  # Skip first room (player start)
        cx, cy = room.center()
        factory.spawn_creature("goblin", cx, cy)

decorate_level(blueprint, registry, factory, distances)
```

---

## Comparing Generators

All three generators work the same way but create different aesthetics:

| Generator | Style | Use Case |
|-----------|-------|----------|
| **BSP** | Rectangular rooms, logical | Dungeons, castles, towns |
| **Cellular Automata** | Organic caves, natural | Caverns, wilderness |
| **Noise** | Gradient terrain | Mountains, forests, water |

Use `GENERATOR_COMPARISON.py` to visualize differences:
```bash
python pyrogue_engine/generation/GENERATOR_COMPARISON.py
```

---

## Design Pattern: Decoupled Phases

Each phase is independent:
- **Generators** don't care about analyzers
- **Analyzers** don't care about builders
- **Builders** and decorators are YOUR code

Swap generators without touching analyzers. Swap analyzers without touching builders.

This is why every generator outputs the same `LevelBlueprint` format.

---

## Pure Functions

All generation math is unit-testable:

```python
from pyrogue_engine.generation.generators import generate_bsp_dungeon

# No ECS, no registry, no side effects
grid = generate_bsp_dungeon(width=80, height=24, seed=42)

# Test the output
assert grid.shape == (24, 80)
assert np.all((grid == 0) | (grid == 1))  # Only 0s and 1s
```

---

## Advanced: Custom Analyzers

Need to find something other than spawn points? Write a custom analyzer:

```python
def find_choke_points(blueprint):
    """Find narrow corridors where entities bottleneck."""
    choke_points = []
    for x in range(1, blueprint.width - 1):
        for y in range(1, blueprint.height - 1):
            if is_narrow_corridor(blueprint, x, y):
                choke_points.append((x, y))
    return choke_points
```

Pass the result to your decorator phase.

---

## See Also

- **README.md** (systems/) — How game systems work
- **README.md** (entities/) — Spawning entities
- **GENERATION_GUIDE.md** — Deep dive with examples
- **GENERATOR_COMPARISON.py** — Visual comparison of generators
- **THE_CONSTITUTION.md** — Design principles
