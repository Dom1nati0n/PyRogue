# Phase 6: The Sensory & Threat Pipeline

## Overview

The **Sensory & Threat Pipeline** bridges Phase 1 (FOV/Perception) with Phase 5 (Decision Trees). It answers one critical question:

> **"Of all the enemies I can see, which one should I attack?"**

The pipeline runs **before** the AISystem each turn:

```
┌─────────────────┐
│  Phase 1: FOV   │  compute_shadowcast_fov() → VisibleTiles
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│  Phase 6: Awareness  │  Scan visible tiles, evaluate threats
│                      │  Write target_id to Memory
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Phase 5: Cognition  │  Decision Tree reads target_id
│                      │  Executes attack/chase logic
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Phase 2: Combat     │  CombatResolverSystem handles damage
│  Phase 1: Movement   │  KinematicMovementSystem handles positions
└──────────────────────┘
```

## Three Components

### 1. FactionRegistry

Defines who attacks who.

```python
from pyrogue_engine.prefabs.ai import FactionRegistry

# At game startup
factions = FactionRegistry()

# Goblins attack players and humans
factions.set_hostile("goblin", "player")
factions.set_hostile("goblin", "human")

# Humans and elves are allies
factions.set_allied("human", "elf", mutual=True)

# Zombies attack everything living (one-way)
factions.set_hostile("undead", ["human", "elf", "goblin"], mutual=False)
```

**Why registry-based?**
- Avoids hardcoding alignment in NPC data
- Single source of truth for faction relationships
- Easily changed at runtime (for dynamic alliances, betrayals, etc.)
- Completely decoupled from ECS

### 2. Threat Math (Pure Functions)

Pure functions that score targets. No side effects.

```python
from pyrogue_engine.prefabs.ai.threat_math import calculate_threat_score

# Rank potential targets
threats = []
for enemy_id in visible_enemies:
    distance = calculate_distance(my_x, my_y, enemy_x, enemy_y)
    health_pct = enemy.current_hp / enemy.max_hp

    score = calculate_threat_score(
        entity_id=enemy_id,
        distance=distance,
        base_threat=10.0,
        health_percent=health_pct,
        is_aggroed=False
    )
    threats.append(score)

# Pick the highest threat
best_target = select_highest_threat(threats)
```

**Threat Formula:**
```
score = (base_threat * 10.0) / distance
      × 1.5 if health < 25% (finish them!)
      × 1.2 if health < 50%
      × 1.2 if already in combat (stay focused)
```

**Why pure functions?**
- Completely testable (no dependencies)
- Easy to tweak scoring without touching ECS
- Can be profiled and optimized independently
- Easy to debug (print inputs, see outputs)

### 3. AwarenessSystem

Ties it all together: **Vision → Threat Evaluation → Memory Update**.

```python
from pyrogue_engine.prefabs.ai import AwarenessSystem, FactionRegistry

factions = FactionRegistry()
factions.set_hostile("goblin", "player")

awareness_system = AwarenessSystem(
    registry=registry,
    event_bus=event_bus,
    faction_registry=factions,
    spatial_query_fn=my_spatial_map.get_entities_on_tiles  # Optional (O(1) lookup)
)

# In main game loop, call BEFORE AISystem
awareness_system.update(delta_time)  # ← Updates Memory.data["target_id"]
ai_system.update(delta_time)         # ← Reads target_id, executes tree
```

---

## Complete Game Loop Sequence

```python
def game_loop():
    for turn in turns:
        # 1. INPUT
        player_action = get_player_input()

        # 2. PERCEPTION (Phase 1)
        perception_system.update(delta_time)
        # Updates Vision.visible_tiles for all entities

        # 3. AWARENESS (Phase 6)  ← NEW!
        awareness_system.update(delta_time)
        # Scans visible tiles, updates Memory["target_id"]

        # 4. COGNITION (Phase 5)
        ai_system.update(delta_time)
        # Decision Tree reads target_id, emits events

        # 5. COMBAT (Phase 2)
        combat_system.update(delta_time)
        # CombatResolverSystem processes attacks, applies damage

        # 6. MOVEMENT (Phase 1)
        movement_system.update(delta_time)
        # KinematicMovementSystem moves entities

        # 7. TIMERS (Phase 4)
        timer_system.process(delta_time)
        # Ticks status effects, aggro timeouts, etc.

        # 8. RENDER
        render()
```

---

## Components Involved

### Memory
Generic key-value store updated by AwarenessSystem:
```python
memory.set("target_id", enemy_id)
memory.set("target_position", (x, y))
memory.set("threat_score", 45.2)
memory.set("target_distance", 8.5)
```

### Faction
Entity's allegiance:
```python
from pyrogue_engine.prefabs.ai import Faction

entity = registry.create_entity()
registry.add_component(entity, Faction(name="goblin"))
```

### Vision
Created by Phase 1 (FOV system). Contains visible tiles:
```python
vision = registry.get_component(entity_id, Vision)
print(vision.visible_tiles)  # Set of (x, y) tuples
```

### ScentMemory (Optional)
Remembers last known position for out-of-sight pursuit:
```python
from pyrogue_engine.prefabs.ai import ScentMemory

scent = registry.get_component(entity_id, ScentMemory)
if scent.is_fresh():
    # Chase to scent.last_position using JPS
    path = pathfinder.find_path(my_pos, scent.last_position)
```

---

## Pattern: Out-of-Sight Pursuit

The scent mechanism enables pursuit even after LOS is broken:

```
Turn 1: Player visible
  ✓ AwarenessSystem sees player at (50, 30)
  ✓ Sets target_id, target_position
  ✓ Updates scent.last_position = (50, 30)
  ✓ AISystem chases with ActionJPSMove

Turn 2: Player moves behind wall (still visible to FOV)
  ✓ AwarenessSystem updates target_position to (55, 25)
  ✓ Scent refreshed to (55, 25)

Turn 3: Player out of FOV (not visible)
  ✗ AwarenessSystem finds no target
  ✗ Clears target_id from memory
  ✓ But scent.last_position = (55, 25) persists!

Turn 4: NPC investigates
  ✗ ConditionHasTarget fails (no target_id)
  ✓ But Decision Tree can check ConditionMemoryKey("scent_fresh")
  ✓ If fresh, ActionMoveToScent emits movement toward (55, 25)
```

**JSON Example:**
```json
{
  "type": "Fallback",
  "children": [
    {
      "type": "Routine",
      "comment": "If we see the target, attack or chase",
      "children": [
        {"type": "ConditionHasTarget"},
        {"type": "ConditionTargetAdjacent"},
        {"type": "ActionMeleeAttack"}
      ]
    },
    {
      "type": "Routine",
      "comment": "If we still see them but they're far, chase",
      "children": [
        {"type": "ConditionHasTarget"},
        {"type": "ActionJPSMove"}
      ]
    },
    {
      "type": "Routine",
      "comment": "Lost sight, but remember scent. Investigate.",
      "children": [
        {"type": "ConditionMemoryKey", "key": "scent_fresh"},
        {"type": "ActionMoveToScent"}  # Custom action
      ]
    },
    {
      "type": "ActionWander"
    }
  ]
}
```

---

## Faction Relationships

### Setting Relationships

```python
factions = FactionRegistry()

# One-way hostility (goblins attack, but humans don't specifically target goblins)
factions.set_hostile("goblin", "human", mutual=False)

# Mutual hostility (enemies)
factions.set_hostile("human", "orc", mutual=True)

# Alliance (won't attack, may coordinate)
factions.set_allied("human", "elf", mutual=True)

# Batch setup
factions.set_hostile("undead", ["human", "elf", "dwarf"], mutual=False)
```

### Querying Relationships

```python
# Direct check
if factions.is_hostile("goblin", "player"):
    print("Goblins attack players")

# Comprehensive check (considers both hostility and alliance)
if factions.should_attack("goblin", "human"):
    print("Goblins will attack humans")
```

---

## Threat Scoring Examples

### Example 1: Regular Melee Combat
```python
# Two goblins see the player
distance_a = 5.0
health_a = 1.0
score_a = calculate_threat_score(
    player_id,
    distance_a,
    base_threat=10.0,
    health_percent=health_a,
    is_aggroed=False
)
# score = (10 * 10) / 5 = 20.0

distance_b = 15.0
health_b = 1.0
score_b = calculate_threat_score(
    player_id,
    distance_b,
    base_threat=10.0,
    health_percent=health_b,
    is_aggroed=False
)
# score = (10 * 10) / 15 = 6.67

# Pick score_a (closer threat is worse)
best = select_highest_threat([score_a, score_b])
# best.entity_id = first goblin
```

### Example 2: Low-Health Bonus
```python
# Finish off a wounded goblin?
low_health_score = calculate_threat_score(
    goblin_id,
    distance=3.0,
    base_threat=10.0,
    health_percent=0.1,  # 10% HP
    is_aggroed=False
)
# score = (10 * 10) / 3 × 1.5 = 50.0

# vs a fresh goblin
fresh_score = calculate_threat_score(
    other_goblin_id,
    distance=3.0,
    base_threat=10.0,
    health_percent=1.0,  # 100% HP
    is_aggroed=False
)
# score = (10 * 10) / 3 = 33.3

# Wounded goblin takes priority (finish them!)
# best.entity_id = wounded goblin
```

### Example 3: Aggro Bonus (Don't Panic-Switch)
```python
# Already fighting one target
current_threat_score = 30.0

# See a new target
new_threat_score = calculate_threat_score(
    new_enemy_id,
    distance=2.0,  # Very close!
    base_threat=10.0,
    health_percent=1.0,
    is_aggroed=False
)
# score = (10 * 10) / 2 = 50.0

# Switch if new threat is significantly better?
# Here: 50 > 30, so yes, switch to the closer threat

# But if we're already fighting the closer one:
current_target_score = calculate_threat_score(
    current_target_id,
    distance=2.0,
    base_threat=10.0,
    health_percent=0.8,
    is_aggroed=True  # Already fighting
)
# score = (10 * 10) / 2 × 1.2 = 60.0

# 60.0 > 50.0, so stick with current target (don't panic-switch)
```

---

## Vision Types

Different vision types see different ranges:

```python
from pyrogue_engine.prefabs.ai.threat_math import adjusted_vision_range

# Normal vision: 15 tiles
range_normal = adjusted_vision_range(15, "normal", "day")
# Returns: 15

# Infravision (heat-based): +20%
range_infra = adjusted_vision_range(15, "infravision", "day")
# Returns: 18

# Darkvision at night: +50%
range_dark_night = adjusted_vision_range(15, "darkvision", "night")
# Returns: 22

# Darkvision at day (bright light interferes): -20%
range_dark_day = adjusted_vision_range(15, "darkvision", "day")
# Returns: 12
```

---

## Integration Checklist

To integrate Phase 6 into your game:

- [ ] Define FactionRegistry at game startup
- [ ] Add `Faction` component to all combat-capable entities
- [ ] Ensure Phase 1 (FOV) is running and updating `Vision.visible_tiles`
- [ ] Create AwarenessSystem with your spatial query function
- [ ] Call `awareness_system.update()` BEFORE `ai_system.update()`
- [ ] Decision Tree nodes can now read `Memory.data["target_id"]` and `Memory.data["target_position"]`
- [ ] (Optional) Add `ScentMemory` component for out-of-sight pursuit
- [ ] (Optional) Custom action nodes for scent-based investigation

---

## Testing

```python
def test_awareness_system():
    registry = Registry()
    event_bus = EventBus()

    # Create attacker with vision
    attacker_id = registry.create_entity()
    registry.add_component(attacker_id, Position(x=0, y=0))
    registry.add_component(attacker_id, Faction(name="goblin"))
    registry.add_component(attacker_id, Memory())
    registry.add_component(attacker_id, Vision(visible_tiles={(5, 5), (5, 6)}))

    # Create target in visible range
    target_id = registry.create_entity()
    registry.add_component(target_id, Position(x=5, y=5))
    registry.add_component(target_id, Faction(name="human"))
    registry.add_component(target_id, Health(current=50, maximum=50))

    # Setup factions
    factions = FactionRegistry()
    factions.set_hostile("goblin", "human", mutual=True)

    # Run awareness
    awareness = AwarenessSystem(registry, event_bus, factions)
    awareness.update(0.016)

    # Check memory was updated
    memory = registry.get_component(attacker_id, Memory)
    assert memory.get("target_id") == target_id
    assert memory.get("target_position") == (5, 5)
    print("✓ Awareness system correctly identified target")
```

---

## Key Principles

1. **Awareness runs first** — Must update Memory before Decision Tree reads it
2. **Threat is pure math** — No ECS coupling, completely testable
3. **Faction is data** — Registry-based lookup, not hardcoded logic
4. **Vision from Phase 1** — Use real FOV, not Euclidean distance
5. **Scent enables intelligence** — NPCs remember and investigate, not just forget
6. **No mutations in AwarenessSystem** — Only reads Vision, writes to Memory (or emits events)
