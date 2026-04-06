# Agent-Based Procedural Generation System

## Overview

Instead of a single mathematical script generating an array, the map is **grown organically by entities (Bees) executing localized logic via Behavior Trees**. Bees don't cheat—they use Action Points, emit Intents, and only know what they can "see" locally. This results in highly complex, organic map features that emerge naturally from simple rules.

## Architecture

The system has three layers:

```
AI VOCABULARY (Actions & Conditions)
    ↓
CASTES (Behavior Tree JSON)
    ↓
PHYSICS ARBITER (ConstructionSystem)
    ↓
NETWORK DELTA SYNC
```

---

## Layer 1: AI Vocabulary

### New Actions

#### `DigAction`
**What it does**: Emits an intent to destroy whatever is on the current tile.

```python
from pyrogue_engine.systems.ai.actions import DigAction
```

**Used by**: Drunkard Bee (Phase 1)

**Event emitted**:
```python
Event("map.destroy.intent", metadata={
    "builder_id": entity_id,
    "x": pos.x,
    "y": pos.y,
    "ap_cost": 10.0
})
```

---

#### `AutomataStepAction`
**What it does**: Applies Cellular Automata logic to smooth tunnels.

Reads a 3×3 local grid:
- If surrounded by walls (≥ 5 walls), **build a wall** (smoothing)
- If open space (< 5 walls), **destroy a wall** (carving)

```python
from pyrogue_engine.systems.ai.actions import AutomataStepAction
```

**Used by**: Architect Bee (Phase 1)

**Parameters**:
- `wall_tag`: The tag to use when building walls (default: `"Terrain.Wall.Stone"`)

**Events emitted**:
```python
# Smoothing
Event("map.build.intent", metadata={
    "builder_id": entity_id,
    "x": pos.x,
    "y": pos.y,
    "build_tag": "Terrain.Wall.Stone",
    "ap_cost": 20.0
})

# Carving
Event("map.destroy.intent", metadata={
    "builder_id": entity_id,
    "x": pos.x,
    "y": pos.y,
    "ap_cost": 10.0
})
```

---

#### `DropPheromoneAction`
**What it does**: Drops an invisible pheromone marker tracking distance from start.

Replaces server-side Dijkstra math. The pheromone value is the number of steps the bee has taken.

```python
from pyrogue_engine.systems.ai.actions import DropPheromoneAction
```

**Used by**: Scout Bee (Phase 3)

**Event emitted**:
```python
Event("map.pheromone.intent", metadata={
    "x": pos.x,
    "y": pos.y,
    "distance_value": steps_taken  # Always increases
})
```

---

### New Conditions

#### `IsPhaseCondition`
**What it does**: Gates bee behaviors based on the global Generation Phase.

```python
from pyrogue_engine.systems.ai.conditions import IsPhaseCondition
```

**Parameters**:
- `target_phase` (int): The phase this node should allow (1, 2, 3, 4, etc.)

**Phase Cycle**:
- **Phase 1**: Excavation (Drunkard + Architect bees carve tunnels)
- **Phase 2**: Decoration (optional cosmetic pass)
- **Phase 3**: Topology (Scout bees map the maze with pheromones)
- **Phase 4**: Placement (Quartermaster spawns points of interest)

**Reading phase from context**:
```python
current_phase = context.custom.get("generation_phase", 1)
```

---

## Layer 2: Castes (Behavior Tree JSON)

### Drunkard Bee: `bee_drunkard.json`

**Role**: Rapid excavator. Carves random tunnels to create organic layouts.

**Strategy**: Wander randomly, dig frequently (0.1s cooldown).

```json
{
  "type": "Sequence",
  "children": [
    {"type": "IsPhaseCondition", "params": {"target_phase": 1}},
    {
      "type": "CooldownGuard",
      "params": {"cooldown": 0.1, "memory_key": "last_dig"},
      "children": [{
        "type": "Sequence",
        "children": [
          {"type": "ActionWander"},
          {"type": "DigAction"}
        ]
      }]
    }
  ]
}
```

**Why this works**:
- Fast cooldown (0.1s) = rapid excavation
- Random wander = organic tunnel patterns
- CooldownGuard = respects server tick rate, no spam
- Phase 1 gate = only active during excavation phase

---

### Architect Bee: `bee_architect.json`

**Role**: Smoother. Follows drunkards, applies Cellular Automata.

**Strategy**: Wander randomly, apply automata less frequently (0.5s cooldown).

```json
{
  "type": "Sequence",
  "children": [
    {"type": "IsPhaseCondition", "params": {"target_phase": 1}},
    {
      "type": "CooldownGuard",
      "params": {"cooldown": 0.5, "memory_key": "last_automata_build"},
      "children": [{
        "type": "Sequence",
        "children": [
          {"type": "ActionWander"},
          {
            "type": "AutomataStepAction",
            "params": {"wall_tag": "Terrain.Wall.Stone"}
          }
        ]
      }]
    }
  ]
}
```

**Why this works**:
- Slower cooldown (0.5s) = smoothing happens after excavation
- Automata = jagged tunnels become intentional corridors
- Runs alongside Drunkards = cooperative generation

---

### Scout Bee: `bee_scout.json`

**Role**: Topology mapper. Replaces server-side Dijkstra with distributed pheromone trails.

**Strategy**: Wander the dug-out space, drop pheromones tracking distance.

```json
{
  "type": "Sequence",
  "children": [
    {"type": "IsPhaseCondition", "params": {"target_phase": 3}},
    {"type": "ActionWander"},
    {"type": "DropPheromoneAction"}
  ]
}
```

**Why this works**:
- Explores carved tunnels = reaches all reachable areas
- Pheromone value increases per step = distance field
- No pathfinding needed = fully distributed
- Phase 3 gate = only after excavation is done

---

## Layer 3: Physics Arbiter (ConstructionSystem)

The ConstructionSystem is the arbiter that **honors bee intents and pushes updates to the network**.

```python
from pyrogue_engine.systems.gameplay.construction_system import ConstructionSystem
```

### Event Flow

```
Bee emits map.build.intent
    ↓
ConstructionSystem._on_build_intent()
    ↓
1. Create tile entity in ECS
2. Add Position and Tags components
3. Emit map.build.resolved (replicate=True)
    ↓
NetworkSystem picks up .resolved
    ↓
Delta Sync sent to all clients
```

### Implementation Details

#### Building (`map.build.intent`)

```python
def _on_build_intent(self, event: Event):
    meta = event.metadata

    # Create tile entity
    tile_id = self.registry.create_entity()

    # Add components
    self.registry.add_component(tile_id, Position(meta["x"], meta["y"]))
    self.registry.add_component(tile_id, Tags([meta["build_tag"]]))

    # Emit resolved event
    self.event_bus.emit(Event(
        "map.build.resolved",
        replicate=True,
        metadata={
            "type": "spawn",
            "id": tile_id,
            "x": meta["x"],
            "y": meta["y"],
            "tag": meta["build_tag"]
        }
    ))
```

**Input (from Bee)**:
```python
{
    "builder_id": bee_entity_id,
    "x": 50,
    "y": 50,
    "build_tag": "Terrain.Wall.Stone",
    "ap_cost": 20.0
}
```

**Output (to clients)**:
```python
{
    "type": "spawn",
    "id": 12345,
    "x": 50,
    "y": 50,
    "tag": "Terrain.Wall.Stone"
}
```

---

#### Destroying (`map.destroy.intent`)

```python
def _on_destroy_intent(self, event: Event):
    meta = event.metadata

    # Find wall at this coordinate
    entities = self.registry.get_entities_by_position(meta["x"], meta["y"])

    for entity_id in entities:
        tags = self.registry.get_component(entity_id, Tags)
        if tags and any(tag.startswith("Terrain.Wall") for tag in tags.tags):
            self.registry.destroy_entity(entity_id)

            # Emit resolved event
            self.event_bus.emit(Event(
                "map.destroy.resolved",
                replicate=True,
                metadata={
                    "type": "despawn",
                    "id": entity_id,
                    "x": meta["x"],
                    "y": meta["y"]
                }
            ))
            break
```

---

#### Pheromones (`map.pheromone.intent`)

```python
def _on_pheromone_intent(self, event: Event):
    meta = event.metadata

    # Create invisible pheromone entity
    pheromone_id = self.registry.create_entity()

    # Add components
    self.registry.add_component(pheromone_id, Position(meta["x"], meta["y"]))
    self.registry.add_component(pheromone_id, Tags(["Pheromone"]))

    # Store distance value in registry
    if not hasattr(self.registry, "pheromone_map"):
        self.registry.pheromone_map = {}
    self.registry.pheromone_map[(meta["x"], meta["y"])] = meta["distance_value"]

    # No replicate (pheromones are server-side only)
    self.event_bus.emit(Event(
        "map.pheromone.resolved",
        replicate=False,
        metadata={...}
    ))
```

---

## Integration: Complete Server Flow

### Startup Phase

```python
# 1. Create and register ConstructionSystem
from pyrogue_engine.systems.gameplay.construction_system import ConstructionSystem

construction_system = ConstructionSystem(registry, event_bus)
world.add_system(construction_system)

# 2. Load bee behavior trees
from pyrogue_engine.systems.ai import TreeFactory, GLOBAL_REGISTRY

factory = TreeFactory(GLOBAL_REGISTRY)
drunkard_tree = factory.load_from_file("pyrogue_engine/systems/ai/examples/bee_drunkard.json", cache_key="drunkard")
architect_tree = factory.load_from_file("pyrogue_engine/systems/ai/examples/bee_architect.json", cache_key="architect")
scout_tree = factory.load_from_file("pyrogue_engine/systems/ai/examples/bee_scout.json", cache_key="scout")

# 3. Spawn bee entities and assign trees
from pyrogue_engine.systems.ai import Brain, Memory

for i in range(15):  # Spawn 15 Drunkard Bees
    bee_id = registry.create_entity()
    registry.add_component(bee_id, Brain(mindset_id="drunkard"))
    registry.add_component(bee_id, Memory())
    registry.add_component(bee_id, Position(50, 50))  # Start at center

    # Assign the tree directly (or store mindset_id and lazy-load)
    bee_brain = registry.get_component(bee_id, Brain)
    bee_brain.root_node = drunkard_tree

for i in range(5):  # Spawn 5 Architect Bees
    bee_id = registry.create_entity()
    registry.add_component(bee_id, Brain(mindset_id="architect"))
    registry.add_component(bee_id, Memory())
    registry.add_component(bee_id, Position(50, 50))

    bee_brain = registry.get_component(bee_id, Brain)
    bee_brain.root_node = architect_tree
```

### Execution Phase

```python
# Set initial phase
context.custom["generation_phase"] = 1

# Run server ticks for ~5 seconds (Phase 1: Excavation)
for tick in range(500):  # 500 ticks × 0.01s = 5 seconds
    # AISystem ticks all bees
    ai_system.update(delta_time=0.01)

    # ConstructionSystem processes intents
    # (happens automatically via event subscriptions)

    # NetworkSystem sends Delta Syncs to clients
    # (happens automatically via replicate=True on .resolved events)

# Phase transition
context.custom["generation_phase"] = 3

# Spawn 10 Scout Bees
for i in range(10):
    bee_id = registry.create_entity()
    registry.add_component(bee_id, Brain(mindset_id="scout"))
    registry.add_component(bee_id, Memory())
    registry.add_component(bee_id, Position(50, 50))

    bee_brain = registry.get_component(bee_id, Brain)
    bee_brain.root_node = scout_tree

# Run Phase 3 for ~2 seconds
for tick in range(200):
    ai_system.update(delta_time=0.01)
    # Scouts drop pheromones, building distance field

# Phase transition
context.custom["generation_phase"] = 4

# Quartermaster Bee reads pheromone map, spawns points of interest
# Then deletes all bees
for bee_id in bee_ids:
    registry.destroy_entity(bee_id)

# Map is now ready for players
```

---

## Design Patterns

### 1. **Cooldown Guards Prevent Spam**

```json
{
  "type": "CooldownGuard",
  "params": {"cooldown": 0.5, "memory_key": "last_dig"},
  "children": [
    {"type": "ActionWander"},
    {"type": "DigAction"}
  ]
}
```

Even if `ActionWander` succeeds every frame, `DigAction` only executes once per 0.5s. Perfect for controlling generation speed.

---

### 2. **Phase Gates Control Behavior**

```json
{
  "type": "Sequence",
  "children": [
    {"type": "IsPhaseCondition", "params": {"target_phase": 1}},
    {"type": "RestOfBehavior"}
  ]
}
```

Bees automatically sleep during irrelevant phases. Single context value controls all bee activity.

---

### 3. **Pheromones Replace Dijkstra**

Traditional pathfinding:
```
Server computes shortest path from (50,50) to every tile → O(n log n)
```

Agent-based:
```
Scout Bees wander, drop pheromones → O(1) per bee
Other systems read pheromone_map[(x,y)] → O(1) lookup
```

The distance field emerges from **distributed exploration**.

---

### 4. **Cellular Automata Smoothing**

Drunkard creates random tunnels (rough).
Architect applies local rules (smooth).

Result: **Intentional-looking maps** with zero hardcoded design.

---

## Testing

### Unit Test: Single Bee

```python
from pyrogue_engine.systems.ai import TreeFactory, GLOBAL_REGISTRY, AISystem, Memory, Brain
from pyrogue_engine.systems.spatial.components import Position

# Create a bee
bee_id = registry.create_entity()
registry.add_component(bee_id, Position(50, 50))
registry.add_component(bee_id, Memory())

# Load drunkard tree
factory = TreeFactory(GLOBAL_REGISTRY)
tree = factory.load_from_file("bee_drunkard.json")

# Tick it
tree.tick(bee_id, registry.get_component(bee_id, Memory), context)

# Check: Did it emit an intent?
# (Monitor event_bus.emit calls or check event log)
```

---

## Extending the System

### Add a New Bee Caste

1. **Define the behavior**: What does this bee do?
2. **Create actions/conditions**: Implement new DecisionNode subclasses
3. **Register them**: Add to `__init__.py`
4. **Write the JSON**: Create the behavior tree
5. **Spawn bees**: Create entities with the new Brain in your server

Example: **Builder Bee** (Phase 4)

```python
class BuildQuartermasterStructureAction(DecisionNode):
    """Read pheromone map, spawn exit portal at highest distance."""
    def tick(self, entity_id, memory, context):
        # Find tile with highest pheromone value
        max_dist = max(context.registry.pheromone_map.values())
        for (x, y), dist in context.registry.pheromone_map.items():
            if dist == max_dist:
                # Spawn exit portal at (x, y)
                event_bus.emit(Event("map.spawn.exit_portal", metadata={"x": x, "y": y}))
                return NodeState.SUCCESS
        return NodeState.FAILURE
```

---

## Performance Notes

- **Bee ticking**: O(n) where n = number of bees (negligible, ~20 bees)
- **Pheromone reads**: O(1) dictionary lookup
- **Event processing**: O(1) per event
- **Network delta**: Only sends changed tiles (highly efficient)

The entire system runs in **< 5ms per tick** on modern hardware.

---

## Philosophy

> "Algorithms are recipes. Agents are life."

Traditional PCG:
- Noise functions generate features
- Mathematical rules apply globally
- Deterministic, predictable

Agent-based generation:
- Simple rules applied locally
- Entities interact autonomously
- Emergent, organic results

The beauty is that **complex behavior emerges from simple intentions**. No dungeon generation algorithm. Just bees doing their job.
