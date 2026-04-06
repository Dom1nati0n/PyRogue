# Debug Cheese - Multi-System Test Item

A fully functional debug item that exercises the game's inventory, combat, projectile, and item systems simultaneously. Perfect for stress-testing and validating all interaction layers.

## Features

- **Combat System**: Use cheese as a weapon (5 damage melee, 15 damage thrown)
- **Inventory System**: Pick up, drop, split cheese
- **Projectile System**: Throw cheese to distant targets
- **Item Tagging**: Built on tag-based item identification system
- **Durability/Health**: Cheese loses durability with use, impact, drop
- **Dynamic Splitting**: When durability < 30%, cheese splits into 3 smaller cheeses
- **Recursive Testing**: Child cheeses can split further (with reduced durability)
- **WizBot Integration**: Autonomous testing bots interact with cheese automatically

## Files

### Core System
- `pyrogue_engine/systems/item/cheese_item.py` - Item definition, properties, factory
- `pyrogue_engine/systems/item/cheese_system.py` - Interaction logic, splitting, damage
- `pyrogue_engine/systems/item/__init__.py` - Package exports
- `spawn_cheese.py` - Spawning utilities (single, grid, scatter, trail)

### Integration
- `wiz_bot_ai.py` (modified) - WizBot now interacts with cheese automatically
- Hooks into: `item.used`, `item.thrown`, `item.dropped`, `item.damaged` events

## Quick Start

### 1. Initialize Systems in headless_server.py

```python
from pyrogue_engine.systems.item import CheeseSystem
from spawn_cheese import spawn_cheese, SpawnCheesePattern

# After creating registry, event_bus, config:

# Initialize cheese system
cheese_system = CheeseSystem(registry, event_bus, config)
print("[*] Cheese system initialized")

# Spawn test cheese
cheese_id = spawn_cheese(registry, x=15, y=15)
print(f"[*] Spawned test cheese {cheese_id}")

# Optionally: spawn a grid of cheese for stress testing
SpawnCheesePattern.grid(registry, (20, 20), size=3, spacing=5)
```

### 2. WizBot Automatically Tests Cheese

```python
# WizBot spawning (as before)
from pyrogue_engine.systems.rpg.wiz_bot_ai import WizBotAI
from wiz_bot import WizBotFactory

wiz_bot_ai = WizBotAI(registry, event_bus, config)
wiz_bot_factory = WizBotFactory()

# Spawn bot near cheese
bot_id = wiz_bot_factory.spawn(registry, x=10, y=10)
wiz_bot_ai.register_wiz_bot(bot_id)

# WizBot will automatically:
# - Find nearby cheese
# - Use it (test combat)
# - Throw it (test projectiles)
# - Drop it (test ground items)
# - Watch it split (test item spawning)
```

### 3. Monitor Debug Output

```
[CheeseSystem] Cheese 42 used by 7 on 7 for 5 damage
[CheeseSystem] Cheese 42 thrown by 7 to (20, 15)
[CheeseSystem] Cheese 42 dropped at (10, 10)
[CheeseSystem] Cheese 42 splitting! (durability 28 < 30)
[CheeseSystem] Spawned child cheese 45 at (9, 11)
[CheeseSystem] Spawned child cheese 46 at (11, 9)
[CheeseSystem] Spawned child cheese 47 at (8, 10)
[WizBotAI] Bot 7 | Frame  5040 | Mode exploration    | Stats: {..., 'cheese_used': 3, 'cheese_thrown': 2, 'cheese_dropped': 1}
```

## Cheese Lifecycle

```
1. Spawn
   └─ Cheese created with full durability (100 for normal size)

2. Interaction
   ├─ item.used: -10 durability, deals 5 damage to target
   ├─ item.thrown: -25 durability, moves to target, deals 15 damage
   └─ item.dropped: -5 durability, placed on ground

3. Check Split Threshold
   └─ If durability < 30 (split_threshold):
      ├─ Emit cheese.split event
      ├─ Spawn 3 child cheeses nearby
      │  └─ Child durability = 50% of parent
      └─ Delete parent cheese

4. Recursion
   └─ Child cheeses can split again if damaged further
```

## Cheese Properties

Each cheese instance has:

```python
ItemComponent:
    item_name: "Debug Cheese (normal)"
    tags: ["debug", "weapon", "throwable", "splittable", "food", "cheese"]
    durability: 100
    max_durability: 100

CheeseProperties:
    split_threshold: 30          # Split at 30% health
    split_count: 3               # Create 3 children
    split_damage_reduction: 0.5  # Children have 50% health
    throw_damage: 15
    melee_damage: 5
    throw_range: 10
```

## Sizes

Cheese comes in 4 sizes for testing different scales:

| Size | Durability | Use Case |
|------|-----------|----------|
| **tiny** | 20 | Quick splitting tests, crowd spawning |
| **small** | 50 | Child cheese (after split), medium testing |
| **normal** | 100 | Standard testing, combat evaluation |
| **large** | 200 | Stress testing, many impacts before split |

## Testing Scenarios

### Scenario 1: Basic Interaction
```python
# Spawn single cheese, WizBot tests use/throw/drop
cheese_id = spawn_cheese(registry, 15, 15)
# → WizBot finds it, uses it, throws it, drops it
# → Monitor durability changes
```

### Scenario 2: Cascade Splitting
```python
# Spawn large cheese, repeatedly damage it
spawn_cheese(registry, 15, 15, size="large")
# → Emit item.damaged event multiple times
# → Watch cheese split into 3 mediums
# → Each medium splits into 3 smalls
# → Verify cascade stops at tiny size
```

### Scenario 3: Grid Combat
```python
# Spawn grid of cheese, 5 WizBots attack
SpawnCheesePattern.grid(registry, (20, 20), size=5, spacing=3)
for i in range(5):
    bot_id = wiz_bot_factory.spawn(registry, x=15+i, y=15)
    wiz_bot_ai.register_wiz_bot(bot_id)
# → 5 bots attack 25 cheese simultaneously
# → Verify no crashes, correct splitting, event ordering
```

### Scenario 4: Projectile Validation
```python
# Spawn cheese, have bot throw it repeatedly
# Monitor:
# - Position updates are correct
# - Damage is applied on impact
# - Durability decreases with each impact
# - Event ordering (thrown → damaged → split)
```

## Event Flow

### Using Cheese

```
item.used
  ├─ Metadata: {item_id, user_id, target_id}
  ├─ Action: Apply melee_damage to target
  ├─ Side effect: -10 durability to cheese
  └─ Check: Should split?
```

### Throwing Cheese

```
item.thrown
  ├─ Metadata: {item_id, user_id, target_pos}
  ├─ Action: Move cheese to target_pos
  ├─ Side effect: -25 durability, emit combat.damage to nearby entities
  └─ Check: Should split?
```

### Dropping Cheese

```
item.dropped
  ├─ Metadata: {item_id, drop_pos}
  ├─ Action: Place cheese on ground
  ├─ Side effect: -5 durability
  └─ Check: Should split?
```

### Splitting

```
cheese.split (when durability < split_threshold)
  ├─ Spawn split_count child entities
  ├─ Children at: parent_pos + small random offset
  ├─ Children durability: split_damage_reduction * parent
  └─ Delete parent, keep children
```

## API Reference

### spawn_cheese()

```python
from spawn_cheese import spawn_cheese

cheese_id = spawn_cheese(registry, x=10, y=10, size="normal")
# Returns: entity_id of spawned cheese
```

### SpawnCheesePattern

```python
from spawn_cheese import SpawnCheesePattern

# Grid of 5x5 cheese at (20, 20) with 3-tile spacing
ids = SpawnCheesePattern.grid(registry, (20, 20), size=5, spacing=3)

# Random scatter of 20 cheese within radius 30
ids = SpawnCheesePattern.scatter(registry, (50, 50), count=20, radius=30)

# Trail of 10 cheese from (10, 10) to (50, 50)
ids = SpawnCheesePattern.trail(registry, (10, 10), (50, 50), count=10)
```

### CheeseSystem Events

```python
# Use cheese as weapon
event_bus.emit(Event(
    event_type="item.used",
    metadata={
        "item_id": cheese_id,
        "user_id": player_id,
        "target_id": target_id,
    }
))

# Throw cheese
event_bus.emit(Event(
    event_type="item.thrown",
    metadata={
        "item_id": cheese_id,
        "user_id": player_id,
        "target_pos": {"x": 25, "y": 30},
    }
))

# Drop cheese
event_bus.emit(Event(
    event_type="item.dropped",
    metadata={
        "item_id": cheese_id,
        "drop_pos": {"x": 10, "y": 10},
    }
))

# Damage cheese (from any source)
event_bus.emit(Event(
    event_type="item.damaged",
    metadata={
        "item_id": cheese_id,
        "damage": 20,
    }
))
```

## Performance Notes

- **Per-Cheese Overhead**: ~2KB state (ItemComponent + CheeseProperties)
- **Split Performance**: Creating 3 new entities on split is O(1), negligible cost
- **Recursion Depth**: Cheese can split 3-4 times before reaching minimum size
- **Scaling**: 100+ cheese can exist simultaneously with no issues

## Known Limitations

1. **Projectile Motion**: Cheese teleports to target instantly (not true ballistic)
2. **Inventory**: No actual inventory system yet (cheese can be "used" but not stored)
3. **Collision**: Cheese doesn't block movement (passes through entities)
4. **Durability Persistence**: Cheese state resets on split (children spawn fresh)

## Future Enhancements

- [ ] True inventory system (store cheese, manage count)
- [ ] Ballistic projectile motion (arc, bounce)
- [ ] Collision damage (cheese takes damage from falling)
- [ ] Cheese spoilage (durability decreases over time)
- [ ] Stacking (10x tiny cheese = 1x small cheese)
- [ ] Recipes (combine cheese types to create new items)
