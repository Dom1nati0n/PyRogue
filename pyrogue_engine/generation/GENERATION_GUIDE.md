# Map Generation Pipeline - Complete Example

This document shows how the four phases of the pipeline work together.

## The Four Phases

```
Generator (Phase 1)
    ↓
    Creates raw 2D grid (0=walk, 1=wall)
    Output: LevelBlueprint with grid + rooms
    ↓
Analyzer (Phase 2)
    ↓
    Scans blueprint for connectivity, distances, spawn zones
    Output: LevelBlueprint with metadata (walkable_regions, entrance, exit)
    ↓
Painter (Phase 3)
    ↓
    Translates grid into game entities
    "0 at (5,3)" → spawn floor tile at (5,3)
    "1 at (5,4)" → spawn wall tile at (5,4)
    Output: Populated ECS with tile entities
    ↓
Decorator (Phase 4)
    ↓
    Uses metadata to place monsters, loot, traps
    "Entrance from analyzer" → spawn player here
    "Farthest point" → place boss here
    Output: Complete level ready to play
```

---

## Example Code

### Phase 1: Generate

```python
from pyrogue_engine.mapgen import BSPGenerator

# Pure math: no ECS, no game logic
generator = BSPGenerator(
    width=80,
    height=45,
    min_room_size=8,
    seed=12345
)

blueprint = generator.generate()
# Now blueprint has:
#  - grid: 80x45 array of 0s and 1s
#  - rooms: list of Room objects
#  - walkable_regions: empty (not yet analyzed)
```

### Phase 2: Analyze

```python
from pyrogue_engine.mapgen import (
    analyze_walkable_regions,
    find_spawn_point,
    find_farthest_point,
)

# Pure math: scans the blueprint
analyze_walkable_regions(blueprint)
# Now blueprint.walkable_regions has connected components

# Find key positions
spawn_x, spawn_y = find_spawn_point(blueprint, rng=np.random.RandomState(42))
exit_x, exit_y, distance = find_farthest_point(blueprint, spawn_x, spawn_y)

blueprint.entrance = (spawn_x, spawn_y)
blueprint.exit = (exit_x, exit_y)

print(f"Spawn at {spawn_x}, {spawn_y}")
print(f"Exit at {exit_x}, {exit_y} ({distance} tiles away)")
```

### Phase 3: Paint (Painter)

```python
# This is where YOU integrate with your ECS
# The engine doesn't provide this—you write it for your game

from pyrogue_engine import Registry

registry = Registry()

# Iterate the blueprint grid
for y in range(blueprint.height):
    for x in range(blueprint.width):
        if blueprint.grid[y, x] == 0:  # Walkable
            # Create floor entity
            floor = registry.create_entity()
            registry.add_component(floor, Position(x, y))
            registry.add_component(floor, FloorTile())
        else:  # Wall
            # Create wall entity
            wall = registry.create_entity()
            registry.add_component(wall, Position(x, y))
            registry.add_component(wall, WallTile())
```

### Phase 4: Decorate (Decorator)

```python
# Use metadata from analysis to place content

# Spawn player at entrance
player = registry.create_entity()
registry.add_component(player, Position(*blueprint.entrance))
registry.add_component(player, Health(current=100, maximum=100))

# Spawn boss at farthest point
boss = registry.create_entity()
registry.add_component(boss, Position(*blueprint.exit))
registry.add_component(boss, Health(current=50, maximum=50))

# Random monster spawning in rooms
for room in blueprint.rooms:
    if room.center != blueprint.entrance:  # Don't spawn monsters at player start
        num_monsters = np.random.randint(1, 4)
        for _ in range(num_monsters):
            x, y = random_point_in_room(room)
            monster = registry.create_entity()
            registry.add_component(monster, Position(x, y))
            registry.add_component(monster, Health(current=20, maximum=20))
```

---

## Why This Pipeline is Powerful

### Decoupling Example

You can generate the SAME blueprint in 4 different ways:
- BSPGenerator → classic square rooms
- CellularAutomataGenerator → organic caves
- VoronoiGenerator → alien structures
- NoiseGenerator → overworld

All produce identical `LevelBlueprint` output.

Then the **same Painter and Decorator code works with all of them**:

```python
# Works with any generator!
generators = [
    BSPGenerator(...),
    CellularAutomataGenerator(...),
    VoronoiGenerator(...),
]

for gen_class in generators:
    blueprint = gen_class.generate()
    analyze_walkable_regions(blueprint)
    paint_level(registry, blueprint)  # Same code!
    decorate_level(registry, blueprint)  # Same code!
```

### Theming Example

The Painter translates generic grid values to YOUR game:

```python
# Dungeon theme
DUNGEON_THEME = {
    0: (FloorTile, {"sprite": "stone_floor"}),
    1: (WallTile, {"sprite": "stone_wall"}),
}

# Spaceship theme
SPACESHIP_THEME = {
    0: (FloorTile, {"sprite": "metal_floor"}),
    1: (WallTile, {"sprite": "metal_wall"}),
}

# Same blueprint, different visuals!
paint_level(registry, blueprint, theme=DUNGEON_THEME)
# versus
paint_level(registry, blueprint, theme=SPACESHIP_THEME)
```

---

## Next Steps

The pipeline is now set up. Next phases:

1. **Phase 1 Expansion**: Add CellularAutomataGenerator, NoiseGenerator
2. **Phase 2 Expansion**: Add room detection, distance maps for AI spawning
3. **Phase 3**: Write your Painter (game-specific, not in engine)
4. **Phase 4**: Write your Decorator (monster/loot tables)

Each phase is independent. You can swap generators, add new analyzers,
change painters, all without touching the core pipeline.
