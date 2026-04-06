# Debug Cheese Integration Guide

How to properly integrate the debug cheese item with the standard EntityFactory and have WizBot start with one.

## Step 1: Register Cheese Template

The cheese template is defined in: `templates/items/cheese_debug.json`

It uses the standard `ItemTemplate` structure with:
- **Tags**: Item.Physical, Item.Weapon, Item.Consumable, Debug.Cheese
- **Properties**: melee_damage, throw_damage, split mechanics
- **Durability**: 100 HP system for splitting mechanics

## Step 2: Load Templates in headless_server.py

```python
from pyrogue_engine.entities.entity_factory import EntityFactory
from pyrogue_engine.entities.template_registry import TemplateRegistry
from pyrogue_engine.core.tags import TagManager

# Initialize template system
tag_manager = TagManager()
template_registry = TemplateRegistry()

# Load template files (including cheese)
template_registry.load_from_directory("templates/")

# Create entity factory
entity_factory = EntityFactory(registry, event_bus, tag_manager, template_registry)

print("[*] Entity factory initialized with templates:")
print(entity_factory.debug_dump())
```

## Step 3: Initialize Cheese System

```python
from pyrogue_engine.systems.item.cheese_system import CheeseSystem

# Initialize the cheese interaction system
cheese_system = CheeseSystem(registry, event_bus, config)
```

## Step 4: Update WizBot to Spawn WITH Cheese

Modify `wiz_bot.py` to accept an entity_factory parameter:

```python
class WizBotFactory:
    def __init__(self, config_path: str = "wiz_bot.json", entity_factory=None):
        self.config_path = Path(config_path)
        self.entity_factory = entity_factory
        self.template = self._load_template()

    def spawn(self, registry: Registry, x: int, y: int, give_cheese: bool = True) -> int:
        """
        Spawn a WizBot entity at the given coordinates.

        Args:
            registry: ECS Registry
            x: Spawn X coordinate
            y: Spawn Y coordinate
            give_cheese: If True, spawn with a debug cheese item

        Returns:
            entity_id of the created WizBot
        """
        # ... existing WizBot creation code ...

        # After WizBot is created, give it cheese if factory is available
        if give_cheese and self.entity_factory:
            cheese_id = self.entity_factory.spawn_item("debug_cheese", x=x, y=y)
            print(f"[WizBot] Spawned bot {entity_id} with cheese {cheese_id}")

        return entity_id
```

## Step 5: Spawn WizBot with Cheese

In `headless_server.py`:

```python
from wiz_bot import WizBotFactory
from pyrogue_engine.systems.rpg.wiz_bot_ai import WizBotAI

# Create WizBot factory with entity_factory reference
wiz_bot_factory = WizBotFactory(entity_factory=entity_factory)

# Initialize WizBot AI system
wiz_bot_ai = WizBotAI(registry, event_bus, config)

# Spawn WizBot WITH cheese
bot_id = wiz_bot_factory.spawn(registry, x=10, y=10, give_cheese=True)
wiz_bot_ai.register_wiz_bot(bot_id)

print(f"[*] Spawned WizBot {bot_id} with debug cheese for testing")
```

## Step 6: Complete Server Initialization

Here's the full integration in `run_server()`:

```python
async def run_server():
    # === CORE SETUP ===
    config = ServerConfig.load("config.json")
    event_bus = EventBus()
    registry = Registry()

    # === ENTITY FACTORY ===
    tag_manager = TagManager()
    template_registry = TemplateRegistry()
    template_registry.load_from_directory("templates/")
    entity_factory = EntityFactory(registry, event_bus, tag_manager, template_registry)

    # === GAME SYSTEMS ===
    session_mgmt = SessionManagementSystem(registry, event_bus)
    validator = NetworkInputValidator()
    replication = ReplicationSystem(registry, event_bus, config) if config.replication.enabled else None
    sequence_tracker = SequenceTrackingSystem(registry, event_bus, config)

    # === TESTING SYSTEMS ===
    from pyrogue_engine.systems.item.cheese_system import CheeseSystem
    from pyrogue_engine.systems.rpg.wiz_bot_ai import WizBotAI
    from wiz_bot import WizBotFactory

    cheese_system = CheeseSystem(registry, event_bus, config)
    wiz_bot_ai = WizBotAI(registry, event_bus, config)
    wiz_bot_factory = WizBotFactory(entity_factory=entity_factory)

    # === SPAWN TEST INFRASTRUCTURE ===
    # Spawn multiple WizBots, each with a debug cheese
    for i in range(3):
        bot_id = wiz_bot_factory.spawn(registry, x=10+i*5, y=10, give_cheese=True)
        wiz_bot_ai.register_wiz_bot(bot_id)

    print(f"[*] Spawned {3} WizBots with debug cheese")

    # === REST OF SERVER SETUP ===
    input_queue = queue.Queue()
    outbound_queue = queue.Queue()

    sim_thread = SimulationThread(
        registry=registry,
        event_bus=event_bus,
        config=config,
        validator=validator,
        session_mgmt=session_mgmt,
        input_queue=input_queue,
        event_class=Event,
    )
    sim_thread.start()

    # === NETWORK SETUP ===
    # ... rest of network initialization ...
```

## What Happens During Testing

1. **Server starts** → WizBots spawned at (10, 10), (15, 10), (20, 10)
2. **Each WizBot receives** → debug_cheese item spawned at same location
3. **Every tick** → WizBot searches for nearby cheese (within 3 tiles)
4. **Finding cheese** → Randomly chooses to use/throw/drop
5. **Using cheese** → Emits `item.used` event → CheeseSystem handles it
6. **Cheese durability** → Decreases, logged to console
7. **At split threshold** → Emits `cheese.split` → 3 child cheeses spawned
8. **Recursion** → Child cheeses can split further if damaged

## Debug Output

```
[WizBot] Spawned bot 5 with cheese 42
[WizBot] Spawned bot 6 with cheese 43
[WizBot] Spawned bot 7 with cheese 44
[CheeseSystem] Cheese 42 used by 5 on 5 for 5 damage
[CheeseSystem] Cheese 42 threw by 5 to (20, 15)
[CheeseSystem] Cheese 42 splitting! (durability 28 < 30)
[CheeseSystem] Spawned child cheese 45 at (9, 11)
[CheeseSystem] Spawned child cheese 46 at (11, 9)
[CheeseSystem] Spawned child cheese 47 at (8, 10)
[WizBotAI] Bot 5 | Frame  1200 | Mode exploration    | Stats: {'cheese_used': 2, 'cheese_thrown': 1, 'cheese_dropped': 1}
```

## Testing Scenarios

### Scenario 1: Single Bot with Cheese
```python
bot_id = wiz_bot_factory.spawn(registry, x=10, y=10, give_cheese=True)
wiz_bot_ai.register_wiz_bot(bot_id)
# WizBot interacts with cheese autonomously
```

### Scenario 2: Multiple Bots, Single Cheese
```python
# Spawn cheese
cheese_id = entity_factory.spawn_item("debug_cheese", x=15, y=15)

# Spawn 3 bots nearby that find and fight over the cheese
for i in range(3):
    bot_id = wiz_bot_factory.spawn(registry, x=13+i, y=15, give_cheese=False)
    wiz_bot_ai.register_wiz_bot(bot_id)
```

### Scenario 3: Stress Test (Many Bots & Cheese)
```python
# Spawn grid of cheese
for x in range(10, 30, 5):
    for y in range(10, 30, 5):
        entity_factory.spawn_item("debug_cheese", x=x, y=y)

# Spawn swarm of WizBots
for i in range(10):
    bot_id = wiz_bot_factory.spawn(registry, x=15+i, y=15, give_cheese=False)
    wiz_bot_ai.register_wiz_bot(bot_id)

# All 10 bots hunt for cheese, test system under load
```

## Key Integration Points

| Component | Integration | Location |
|-----------|-----------|----------|
| **ItemTemplate** | Defines cheese properties | `templates/items/cheese_debug.json` |
| **EntityFactory** | Spawns cheese using template | `headless_server.py` |
| **CheeseSystem** | Handles interactions (use/throw/drop/split) | `pyrogue_engine/systems/item/cheese_system.py` |
| **WizBotAI** | Autonomously interacts with cheese | `pyrogue_engine/systems/rpg/wiz_bot_ai.py` |
| **EventBus** | Routes item events to CheeseSystem | Used by all components |

## Stress Testing Modes

The WizBotAI system supports three specialized test modes for stress testing:

### 1. Cheese Multiply Test
**Purpose:** Test inventory limits and item consumption
```python
bot_id = wiz_bot_factory.spawn(registry, x=10, y=10, test_mode="cheese_multiply_test")
wiz_bot_ai.register_wiz_bot(bot_id)
```

**Behavior:**
- Phase 1: Spawn cheese one-at-a-time until inventory full (10 items)
- Phase 2: Use each cheese until inventory empty
- Logs: `cheese_spawned` and `cheese_used` counters

**Expected Output:**
```
[WizBotAI] Bot 5 spawned cheese 42, inventory 1/10
[WizBotAI] Bot 5 spawned cheese 43, inventory 2/10
...
[WizBotAI] Bot 5 used cheese 42, 9 remaining
[WizBotAI] Bot 5 used cheese 43, 8 remaining
```

### 2. Cheese Replicate Test
**Purpose:** Test entity spawning rate and deletion mechanics
```python
bot_id = wiz_bot_factory.spawn(registry, x=20, y=10, test_mode="cheese_replicate_test")
wiz_bot_ai.register_wiz_bot(bot_id)
```

**Behavior:**
- Phase 1: Spawn cheese one-at-a-time until inventory full (10 items)
- Phase 2: Delete all except the first cheese
- Logs: `cheese_spawned` and `cheese_deleted` counters

**Expected Output:**
```
[WizBotAI] Bot 6 spawned cheese 44, inventory 1/10
[WizBotAI] Bot 6 spawned cheese 45, inventory 2/10
...
[WizBotAI] Bot 6 deleted cheese 45, 9 remaining
[WizBotAI] Bot 6 deleted cheese 46, 8 remaining
```

### 3. Generation Limiting (Prevents Cheese Apocalypse)
The CheeseSystem now enforces generation limits:
- **split_generation**: Current depth (0 = original, 1-3 = children)
- **max_generations**: Maximum allowed depth (default: 3)
- **Effect**: 1 cheese → 3 children → 9 grandchildren (max, cannot split further)

When a cheese tries to split at max generation:
```
[CheeseSystem] Cheese 42 too old to split (generation 3/3)
```

This prevents exponential growth: **capped at 9 entities** instead of infinite.

## Running Stress Tests

### Setup in headless_server.py:

```python
from pyrogue_engine.systems.rpg.wiz_bot_ai import WizBotAI
from wiz_bot import WizBotFactory

# Initialize systems
wiz_bot_ai = WizBotAI(registry, event_bus, config)
wiz_bot_factory = WizBotFactory()

# Spawn stress test bots
bot1 = wiz_bot_factory.spawn(registry, x=10, y=10, test_mode="cheese_multiply_test")
bot2 = wiz_bot_factory.spawn(registry, x=20, y=10, test_mode="cheese_replicate_test")

# Control group (normal exploration)
bot3 = wiz_bot_factory.spawn(registry, x=30, y=10, test_mode="exploration")

# Register all bots with AI system
for bot_id in [bot1, bot2, bot3]:
    wiz_bot_ai.register_wiz_bot(bot_id)

print(f"[*] Spawned {3} WizBots: 2 stress test modes + 1 control")
```

### Monitoring Test Progress

Every 60 frames (3 seconds at 20 Hz), each bot logs:
```
[WizBotAI] Bot 5 | Frame    60 | Mode cheese_multiply_test | Entities 1050 | Stats: {'cheese_spawned': 10, 'cheese_used': 10}
[WizBotAI] Bot 6 | Frame    60 | Mode cheese_replicate_test | Entities 1010 | Stats: {'cheese_spawned': 10, 'cheese_deleted': 9}
```

**Success Criteria:**
- Entity count stabilizes (doesn't grow unbounded)
- Both test modes complete without crashes
- Generation limits prevent exponential growth
- No memory leaks after 1000+ frames
- Replication to all clients happens smoothly

## Verification Checklist

- [ ] `templates/items/cheese_debug.json` exists and is properly formatted
- [ ] `TemplateRegistry.load_from_directory("templates/")` succeeds
- [ ] `entity_factory.spawn_item("debug_cheese", x=10, y=10)` returns valid entity_id
- [ ] WizBot finds cheese within 3 tiles
- [ ] WizBot can use/throw/drop cheese
- [ ] CheeseSystem handles all events without errors
- [ ] Cheese splits into children when durability < 30
- [ ] Child cheeses inherit split_damage_reduction ratio
- [ ] Console logs show correct sequence of events
- [ ] **Generation limits prevent infinite splitting (max 9 entities)**
- [ ] **cheese_multiply_test completes successfully (spawn then use)**
- [ ] **cheese_replicate_test completes successfully (spawn then delete)**
- [ ] **Stress tests run for 1000+ frames without server crash**
