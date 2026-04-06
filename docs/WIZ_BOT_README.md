# WizBot - Autonomous Testing Bot

A lightweight, intelligent testing entity that explores the game world autonomously and collects debug telemetry. Perfect for stress-testing the server without needing real players.

## Features

- **Autonomous Exploration**: Moves randomly across the map using standard `movement.intent` events
- **Debug Telemetry**: Collects and logs entity counts, frame numbers, and custom metrics
- **Teleport Unsticking**: Can teleport to escape corners or stuck positions
- **Zero Network Awareness**: Emits intents like a normal player; replication happens automatically
- **Lightweight**: Single component overhead; scales to 100+ simultaneous bots

## Files

- `wiz_bot.py` - Factory and spawner (executable script + module)
- `wiz_bot.json` - Entity template with all components
- `pyrogue_engine/systems/rpg/debug_component.py` - DebugComponent dataclass
- `pyrogue_engine/systems/rpg/wiz_bot_ai.py` - WizBotAI system (world.tick listener)

## Quick Start

### 1. Initialize WizBot System in headless_server.py

```python
from pyrogue_engine.systems.rpg.wiz_bot_ai import WizBotAI
from wiz_bot import WizBotFactory

# In run_server():

# After creating registry, event_bus, config:
wiz_bot_ai = WizBotAI(registry, event_bus, config)
wiz_bot_factory = WizBotFactory()

# Spawn a test bot (e.g., for stress testing)
if config.gameplay.enable_testing:
    bot_entity_id = wiz_bot_factory.spawn(registry, x=10, y=10)
    wiz_bot_ai.register_wiz_bot(bot_entity_id)
    print(f"[Server] Spawned WizBot for testing: entity {bot_entity_id}")
```

### 2. Spawn Multiple Bots

```python
# Spawn 10 bots at different locations
for i in range(10):
    x = 10 + (i % 5) * 5
    y = 10 + (i // 5) * 5
    bot_id = wiz_bot_factory.spawn(registry, x, y)
    wiz_bot_ai.register_wiz_bot(bot_id)
```

### 3. Monitor Debug Output

The WizBot logs every N frames (default 60 frames at 20 Hz = 3 seconds):

```
[WizBotAI] Bot 42 | Frame  1234 | Mode exploration    | Entities  15 | Stats: {'spawn_x': 10, 'spawn_y': 10, 'entity_count': 15}
```

## Configuration

Edit `wiz_bot.json` to customize:

- `spawn_position`: Default [x, y] coordinates
- `test_mode`: "exploration" (random walk), "fov_test" (stay in place), etc.
- `log_interval`: Print telemetry every N frames (default 60)
- `explore_chance`: Probability of moving each frame (default 0.7 = 70%)

## Testing Scenarios

### Scenario 1: Baseline Server Load (No Players)

```python
# Spawn 1 WizBot, verify it runs at consistent 20 Hz
bot_id = wiz_bot_factory.spawn(registry, 10, 10)
wiz_bot_ai.register_wiz_bot(bot_id)
# Should see steady frame increments with no frame drops
```

### Scenario 2: Stress Test

```python
# Spawn 50 WizBots
for i in range(50):
    x = 10 + random.randint(0, 50)
    y = 10 + random.randint(0, 50)
    bot_id = wiz_bot_factory.spawn(registry, x, y)
    wiz_bot_ai.register_wiz_bot(bot_id)

# Monitor CPU, memory, tick latency
# Should scale gracefully to 50+ bots without frame drops
```

### Scenario 3: FOV Validation

```python
# Change test_mode to "fov_test"
# Spawn bots in a grid, verify FOV culling works correctly
```

## API Reference

### WizBotFactory

```python
factory = WizBotFactory("wiz_bot.json")

# Spawn a bot
entity_id = factory.spawn(registry, x=10, y=10)
```

### WizBotAI

```python
wiz_bot_ai = WizBotAI(registry, event_bus, config)

# Register a bot for AI updates
wiz_bot_ai.register_wiz_bot(entity_id)

# Teleport a bot (public API)
wiz_bot_ai.teleport_bot(entity_id, x=20, y=20)
```

### DebugComponent

```python
debug = registry.get_component(entity_id, DebugComponent)

# Update a stat
debug.update_stat("custom_metric", 42)

# Queue a teleport
debug.mark_teleport(25, 25)
```

## Performance Characteristics

- **Per-Bot Overhead**: ~1KB state, ~0.1ms per tick CPU (at 20 Hz)
- **Memory**: Single DebugComponent + standard Position/Health/PlayerController
- **Network**: Emits same movement.intent events as human players; FOV culling applies normally
- **Scaling**: Linear O(N) where N = number of bots (no special optimization needed)

## Debugging Tips

1. **Check bot is moving**: Look for changing entity positions in debug output
2. **Verify AI is active**: Look for "Frame N" incrementing every tick
3. **Test teleport**: Call `wiz_bot_ai.teleport_bot(entity_id, x, y)` and verify position changes
4. **Monitor replication**: The WizBot should appear in other clients' FOV if nearby

## Future Enhancements

- [ ] Scripted test patterns (figure-8, spiral, boundary walk)
- [ ] Collision detection validation
- [ ] Combat testing (attack, take damage)
- [ ] Inventory interaction testing
- [ ] Session persistence testing (disconnect/reconnect)
