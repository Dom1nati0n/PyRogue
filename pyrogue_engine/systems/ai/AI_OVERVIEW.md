# Decision Tree AI System - Architecture & Usage

## Philosophy

**AI is not code. AI is data.**

Rather than hardcoding Python if/else chains for every monster behavior, we define AI as JSON Decision Trees. Want a goblin to heal instead of attacking? Change the JSON, don't touch Python.

This system is completely decoupled from game logic:
- **AI doesn't know about combat.** It emits `AttackIntentEvent`; CombatSystem handles damage.
- **AI doesn't know about movement.** It emits `MovementIntentEvent`; KinematicMovementSystem handles positions.
- **AI doesn't know about rendering.** It just reads Memory and emits events.

The result: **extensible, reusable, data-driven behavior**.

---

## Core Components

### 1. Memory (Entity Component)

A generic key-value store for what an entity knows.

```python
memory = Memory()
memory.set("target_id", player_entity_id)
memory.set("target_position", (50, 30))
memory.set("alert_level", "high")
```

Updated by **PerceptionSystem** (detects enemies, updates Memory).
Read by **Decision Tree conditions** (guides decisions).

---

### 2. Brain (Entity Component)

Holds the Decision Tree for this entity.

```python
brain = Brain(mindset_id="smart_assassin")
# Tree loaded from: pyrogue_engine/prefabs/ai/examples/smart_assassin.json
```

The tree is lazily loaded on first tick. Multiple entities of the same type share the same tree in memory.

---

### 3. Decision Tree Nodes

**Three types of nodes:**

#### Fallback (Selector)
Try children until one succeeds.
```json
{
  "type": "Fallback",
  "children": [
    {"type": "ConditionTargetAdjacent"},
    {"type": "ActionMeleeAttack"},
    {"type": "ActionMoveTowardsTarget"},
    {"type": "ActionWander"}
  ]
}
```
"Attack if adjacent, else chase, else wander" — use for decision hierarchies.

#### Routine (Sequence)
Execute children in order. Stop on first failure.
```json
{
  "type": "Routine",
  "children": [
    {"type": "ConditionHasTarget"},
    {"type": "ConditionTargetAdjacent"},
    {"type": "ActionMeleeAttack"}
  ]
}
```
"Only attack if we have a target AND it's adjacent" — use for guarded actions.

#### Conditions
Check entity state. Return SUCCESS or FAILURE.

Built-in conditions:
- `ConditionHasTarget` — Memory has "target_id"
- `ConditionTargetAdjacent` — Target within 1 tile (8-directional)
- `ConditionTargetInRange` — Target within N tiles
- `ConditionTargetAlive` — Target's Health component shows alive
- `ConditionSelfAlive` — This entity is alive
- `ConditionSelfHealthLow` — Health below threshold
- `ConditionMemoryKey` — Any key exists in Memory

#### Actions
Emit events or update state. Return SUCCESS or FAILURE.

Built-in actions:
- `ActionMeleeAttack` — Emit AttackIntentEvent
- `ActionJPSMove` — Find path via JPS, emit MovementIntentEvent
- `ActionFlowFieldMove` — Read flow field, emit MovementIntentEvent
- `ActionWander` — Random adjacent direction
- `ActionWait` — Do nothing (always SUCCESS)
- `ActionUpdateMemory` — Store value in Memory

---

## Integration Example: Smart Assassin

**JSON Definition** (smart_assassin.json):
```json
{
  "type": "Fallback",
  "children": [
    {
      "type": "Routine",
      "children": [
        {"type": "ConditionHasTarget"},
        {"type": "ConditionTargetAdjacent"},
        {"type": "ActionMeleeAttack"}
      ]
    },
    {
      "type": "Routine",
      "children": [
        {"type": "ConditionHasTarget"},
        {"type": "ConditionTargetAlive"},
        {"type": "ActionJPSMove"}
      ]
    },
    {
      "type": "ActionWander"}
    }
  ]
}
```

**Behavior:**
1. **Do I have a target AND is it adjacent?** → Attack
2. **Do I have a target AND is it alive?** → Chase with JPS
3. Otherwise → Wander

**Decision Flow:**
```
Tick(smart_assassin_entity):
  Fallback tries first Routine:
    ✓ ConditionHasTarget succeeds (target_id in memory)
    ✗ ConditionTargetAdjacent fails (target is far away)
    Routine fails, Fallback continues

  Fallback tries second Routine:
    ✓ ConditionHasTarget succeeds
    ✓ ConditionTargetAlive succeeds
    ✓ ActionJPSMove emits MovementIntentEvent
    Routine succeeds, Fallback returns SUCCESS

  End of turn: KinematicMovementSystem processes MovementIntentEvent
```

---

## Integration Example: Horde Zombie

**Use Flow Fields for O(1) swarming:**

```json
{
  "type": "Fallback",
  "children": [
    {
      "type": "Routine",
      "children": [
        {"type": "ConditionHasTarget"},
        {"type": "ConditionTargetAdjacent"},
        {"type": "ActionMeleeAttack"}
      ]
    },
    {
      "type": "Routine",
      "children": [
        {"type": "ConditionHasTarget"},
        {"type": "ConditionTargetAlive"},
        {"type": "ActionFlowFieldMove"}
      ]
    },
    {
      "type": "ActionWander"}
    }
  ]
}
```

**Why Flow Fields?**
- **JPS per zombie**: 100 zombies × pathfinding = expensive
- **Flow Field per turn**: Compute once from player position, 100 zombies = O(1) dictionary lookups

**Performance:**
- Flow field update: 1-2ms per turn
- 100 zombies: 0.1ms total (100 dictionary lookups)
- Total: 1-3ms to move an entire horde, compared to 50-100ms with individual pathfinding

---

## Complete System Setup

```python
# At game startup
from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import EventBus
from pyrogue_engine.prefabs.ai import (
    AISystem, TreeFactory, GLOBAL_REGISTRY, TreeContext,
    Memory, Brain
)

# Create core systems
registry = Registry()
event_bus = EventBus()

# Create AI context (pass game dependencies)
tree_context = TreeContext(
    registry=registry,
    event_bus=event_bus,
    map_system=my_game.map_system,  # For pathfinding
    custom={
        "walkable_callback": my_game.is_walkable,  # JPS needs this
        # Add your own game-specific state here
    }
)

# Create AI system
tree_factory = TreeFactory(GLOBAL_REGISTRY)
ai_system = AISystem(registry, event_bus, tree_factory, tree_context)

# Create enemy entity
enemy_id = registry.create_entity()
registry.add_component(enemy_id, Brain(mindset_id="smart_assassin"))
registry.add_component(enemy_id, Memory())
registry.add_component(enemy_id, Position(x=30, y=40))
registry.add_component(enemy_id, Health(current=50, maximum=50))
registry.add_component(enemy_id, Attributes(stats={"strength": 15}))

# In main game loop
def game_loop():
    for frame in frames:
        # ... Handle input, etc ...

        # Tick AI
        ai_system.update(delta_time)

        # Tick other systems (combat, movement, etc.)
        combat_system.update(delta_time)
        movement_system.update(delta_time)

        # Render
        render()
```

---

## Extending with Custom Nodes

Want a goblin to cast spells? Create a custom action node:

```python
# my_game/ai/actions.py
from pyrogue_engine.prefabs.ai import DecisionNode, NodeState, TreeContext

class ActionCastSpell(DecisionNode):
    def __init__(self, spell_id: str):
        self.spell_id = spell_id

    def tick(self, entity_id, memory, context):
        # Get target
        target_id = memory.get("target_id")
        if not target_id:
            return NodeState.FAILURE

        # Emit spell event
        from pyrogue_engine.prefabs.rpg.combat_system import ApplyCastEvent
        spell_event = ApplyCastEvent(
            caster_id=entity_id,
            target_id=target_id,
            spell_id=self.spell_id
        )
        context.event_bus.emit(spell_event)

        return NodeState.SUCCESS

# At game startup, register it
from pyrogue_engine.prefabs.ai import GLOBAL_REGISTRY
GLOBAL_REGISTRY.register("ActionCastSpell", ActionCastSpell)

# Use in JSON
{
  "type": "ActionCastSpell",
  "spell_id": "fireball"
}
```

---

## Updating Memory: Perception System

The **PerceptionSystem** updates Memory based on what entities see.

```python
class PerceptionSystem(System):
    def update(self, delta_time):
        for entity_id, (brain, memory, vision) in self.registry.view(Brain, Memory, Vision):
            # Compute FOV
            visible_tiles = compute_shadowcast_fov(
                vision.radius,
                is_opaque_cb
            )

            # Look for enemies in visible tiles
            for other_id, pos in self.registry.view(Position):
                if other_id == entity_id:
                    continue
                if (pos.x, pos.y) in visible_tiles:
                    # Enemy spotted!
                    memory.set("target_id", other_id)
                    memory.set("target_position", (pos.x, pos.y))
                    break
```

Now the AI wakes up when it sees an enemy, without needing to change the tree JSON.

---

## Testing Decision Trees

Unit test nodes in isolation:

```python
def test_melee_attack_node():
    from pyrogue_engine.prefabs.ai.actions import ActionMeleeAttack

    registry = Registry()
    event_bus = EventBus()
    context = TreeContext(registry, event_bus)

    # Create attacker and target
    attacker_id = registry.create_entity()
    target_id = registry.create_entity()

    registry.add_component(attacker_id, Attributes(stats={"strength": 15}))
    registry.add_component(target_id, Health(current=50, maximum=50))

    # Setup memory
    memory = Memory()
    memory.set("target_id", target_id)

    # Tick the node
    action = ActionMeleeAttack()
    state = action.tick(attacker_id, memory, context)

    assert state == NodeState.SUCCESS

    # Verify AttackIntentEvent was emitted
    # (Check event_bus queue or mock subscribers)
```

---

## Decision Tree vs Behavior Trees

This system uses the **Behavior Tree** pattern from robotics, renamed to avoid branding:

| Term | Meaning |
|------|---------|
| **Decision Tree** | The full tree structure |
| **Fallback** | "Try these options, pick first that works" (Selector in BT) |
| **Routine** | "Do these steps in order" (Sequence in BT) |
| **Memory** | "What does this entity know" (Blackboard in BT) |

The key insight: **All AI decisions are just hierarchical if-then-else trees.**

- Fallback = "if this fails, try that"
- Routine = "if this succeeds, then do that"
- Conditions = "if this is true, decide"

---

## Key Principles

1. **No AI state in Python** — All AI logic is JSON data
2. **Events are the API** — AI emits events; other systems handle them
3. **Memory is shared state** — Perception systems update it; trees read it
4. **Trees are cached** — Multiple entities share the same parsed tree
5. **Nodes are composable** — Build complex behaviors from simple nodes
6. **Extensible via registry** — Games can add custom condition/action nodes

---

## Next Steps

1. ✅ TreeFactory and core nodes (DONE)
2. 📋 Extract PerceptionSystem to populate Memory
3. 📋 Extract Threat/Faction logic (what to attack)
4. 📋 Test with full game scenario
