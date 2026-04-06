# 🏗️ The PyRogue Constitution

## The Purity Doctrine

This document is the social contract of pyrogue_engine. Every feature, system, and line of code must uphold these four principles. Violate them and the engine becomes a monolith again.

---

## Principle 1: Logic is Reactive, Never Proactive

### The Rule

**Systems do not run all the time checking for work. They listen to events and respond.**

Bad:
```python
class TrapSystem(System):
    def update(self, dt):
        # ❌ This runs EVERY FRAME scanning for traps
        for entity_id, (position, trap_component) in self.registry.view(Position, Trap):
            # Check if any creatures are standing on this trap
            for other_id, (other_pos, _) in self.registry.view(Position, Creature):
                if position.x == other_pos.x and position.y == other_pos.y:
                    self._trigger_trap(entity_id, other_id)
```

Good:
```python
class TrapSystem(System):
    def __init__(self, registry, event_bus):
        super().__init__(registry, event_bus)
        # ✅ Only wake up when movement happens
        self.event_bus.on(MovementIntentEvent, self._on_movement_intent)

    def _on_movement_intent(self, event: MovementIntentEvent):
        # Move entity to new position (this is handled elsewhere)
        # Now check if there's a trap there
        target_pos = (event.entity_id.x + event.dx, event.entity_id.y + event.dy)

        # Query only the destination tile
        for trap_id, trap_component in self.registry.view_at(target_pos, Trap):
            self.event_bus.emit(TrapTriggeredEvent(trap_id, event.entity_id))
```

### Why?

- **Scalability**: With 1000 traps on the map, the bad version runs 1000 checks every frame. The good version only checks when movement happens (maybe 100 times per game session).
- **Clarity**: Event listeners make the causal chain obvious. You see immediately: movement → trap check.
- **Testing**: You can test trap logic without a full game loop. Just emit the event.

### Patterns

| Trigger | Event | System |
|---------|-------|--------|
| Player moves | MovementIntentEvent | TrapSystem, CollisionSystem |
| Player attacks | AttackIntentEvent | CombatSystem, TrapSystem (if trap reacts to damage) |
| Time passes | TimerTickEvent | StatusEffectSystem, HungerSystem |
| Entity takes damage | DamageTakenEvent | BleedingSystem, PoisonSystem |
| Entity dies | DeathEvent | LootSystem, CombatLogSystem |

---

## Principle 2: Tags are the Source of Truth

### The Rule

**Never hardcode feature numbers in code. Define them in tags.json and read them at runtime.**

Bad:
```python
class TrapSystem(System):
    SPIKE_TRAP_DAMAGE = 10  # ❌ Hardcoded in code
    POISON_TRAP_DAMAGE = 5
    SPIKE_TRAP_COOLDOWN = 3.0

    def _trigger_trap(self, trap_id, victim_id):
        trap = self.registry.get_component(trap_id, Trap)
        if trap.type == "spike":
            damage = self.SPIKE_TRAP_DAMAGE  # ❌ Have to recompile to change
```

Good:
```python
class TrapSystem(System):
    def __init__(self, registry, event_bus, tag_manager):
        super().__init__(registry, event_bus)
        self.tags = tag_manager

    def _trigger_trap(self, trap_id, victim_id):
        trap = self.registry.get_component(trap_id, Trap)
        # ✅ Read damage from tags
        damage = self.tags.get_property(trap.trap_type, "Damage", default=1.0)
```

In `tags.json`:
```json
{
  "Hazard": {
    "Trap": {
      "Spike": {
        "properties": {
          "Damage": 10,
          "Cooldown": 3.0,
          "IsLethal": false
        }
      },
      "Poison": {
        "properties": {
          "Damage": 5,
          "DamageType": "Poison",
          "Cooldown": 1.0
        }
      }
    }
  }
}
```

### Why?

- **Designer-Friendly**: Content creators can tune numbers without touching Python.
- **Data-Driven**: Balance changes happen in JSON, not in compiled bytecode.
- **Hierarchy**: Poison traps inherit from Trap, which inherits from Hazard. Shared properties automatically propagate.
- **Consistency**: All trap properties live in one place. No `POISON_DAMAGE` in TrapSystem and `poison_damage` in some other file.

### Pattern: Property Inheritance

```python
# Read a property with inheritance
damage = self.tags.get_property("Hazard.Trap.Spike", "Damage", default=1.0)

# This walks the hierarchy:
# Hazard.Trap.Spike.properties["Damage"]
#   ↑
# Hazard.Trap.properties["Damage"] (if not found above)
#   ↑
# Hazard.properties["Damage"] (if not found above)
#   ↑
# default=1.0 (if not found anywhere)
```

---

## Principle 3: Intent, Not Mutation

### The Rule

**Systems emit events that describe INTENT, not actual state changes.**

Bad:
```python
class TrapSystem(System):
    def _trigger_trap(self, trap_id, victim_id):
        victim = self.registry.get_component(victim_id, Health)
        # ❌ Directly mutate health
        victim.current -= 10
        victim.is_bleeding = True
```

Good:
```python
class TrapSystem(System):
    def _trigger_trap(self, trap_id, victim_id):
        trap = self.registry.get_component(trap_id, Trap)
        damage = self.tags.get_property(trap.trap_type, "Damage", default=1.0)

        # ✅ Emit intent
        self.event_bus.emit(AttackIntentEvent(
            attacker_id=trap_id,
            target_id=victim_id,
            base_damage=damage,
            damage_type="Physical",
            source="trap_trigger"
        ))

        # CombatSystem will process this event and actually apply damage
```

### Why?

- **Single Resolver**: CombatSystem is the ONLY place in the world where health is subtracted. This ensures:
  - Armor calculations happen consistently
  - Resistances apply everywhere
  - Damage logs are accurate
  - Healing can counteract damage predictably

- **Flexibility**: If you later add "Damage Reflection" or "On-Hit Effects", CombatSystem handles it once, and every attack (traps, melee, spells, projectiles) benefits automatically.

- **Auditability**: Every health change goes through one door. You can instrument it and see exactly why the player lost HP.

### Intent Events (Examples)

| Intent | Event | Resolver |
|--------|-------|----------|
| "I want to attack this" | AttackIntentEvent | CombatSystem |
| "I want to move here" | MovementIntentEvent | MovementSystem |
| "I want to pick up that" | PickupIntentEvent | InventorySystem |
| "I want to cast this spell" | SpellCastIntentEvent | SpellSystem |
| "I want to open this door" | InteractionIntentEvent | InteractionSystem |

### Resolution Events (Outcomes)

| Outcome | Event | Who Listens |
|---------|-------|-------------|
| "Damage was applied" | DamageTakenEvent | BleedingSystem, PoisonSystem, AudioManager |
| "Movement succeeded" | MovementEvent | AwarenessSystem (reset scent), FogOfWar |
| "Door opened" | DoorOpenedEvent | AudioManager, LightingSystem |
| "Health changed" | HealthChangedEvent | UIManager (update HUD), AudioManager |

---

## Principle 4: Client is a Mirror, Not a Controller

### The Rule

**The renderer reads engine state. It never contains logic that could affect gameplay.**

Bad:
```python
# In pyrogue_client/ui/ui_manager.py
class UIManager:
    def update(self, dt):
        health = self.registry.get_component(player_id, Health)
        if health.current < health.maximum * 0.25:
            # ❌ Client deciding to play music
            self.audio.play_ominous_music()

        # ❌ Client deciding to trigger a tutorial
        if player.level == 1 and not player.has_tutorial:
            self.show_tutorial()
```

Good:
```python
# In pyrogue_engine/prefabs/rpg/systems.py
class HealthChangeSystem(System):
    def __init__(self, registry, event_bus):
        super().__init__(registry, event_bus)
        self.event_bus.on(DamageTakenEvent, self._on_damage)

    def _on_damage(self, event):
        health = self.registry.get_component(event.target_id, Health)
        health.current = max(0, health.current - event.damage)

        # ✅ Engine decides to emit a state change event
        self.event_bus.emit(HealthChangedEvent(
            entity_id=event.target_id,
            old_health=event.damage,  # This is actually the old value
            new_health=health.current,
            is_critical=(health.current < health.maximum * 0.25)
        ))

# In pyrogue_client/audio/audio_manager.py
class AudioManager:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        # ✅ Client listens to engine events
        self.event_bus.on(HealthChangedEvent, self._on_health_changed)

    def _on_health_changed(self, event):
        if event.is_critical:
            # ✅ Client reads a flag the engine computed and plays audio
            self.play_ominous_music()
```

### Why?

- **Testability**: You can test engine logic without any client code running.
- **Reusability**: Different clients (Pygame, Terminal, Web, Headless) all work with the same engine.
- **Clarity**: The engine decides what's important. The client just displays it.

### Client Responsibilities

✅ **Do This**:
- Render components to screen
- Listen to events and update visuals
- Translate input to engine events
- Play audio in response to engine events
- Show UI based on component state

❌ **Don't Do This**:
- Decide game logic (trap damage, hunger rate, etc.)
- Mutate components directly
- Check for win/lose conditions
- Trigger tutorials or events
- Calculate pathfinding or combat outcomes

---

## The Architecture in One Picture

```
┌─────────────────────────────────────────────────────────┐
│ pyrogue_engine (Pure Simulation)                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Components:                                           │
│  ├─ Position(x, y)                                    │
│  ├─ Health(current, maximum)                         │
│  ├─ Tags(list of tag names)                          │
│  ├─ Trap(trap_type="Hazard.Trap.Spike")             │
│  └─ ... (dozens more)                                │
│                                                         │
│  Events (Intent):                                      │
│  ├─ MovementIntentEvent(entity, dx, dy)             │
│  ├─ AttackIntentEvent(attacker, target, damage)     │
│  ├─ InteractionIntentEvent(actor, target)           │
│  └─ ...                                               │
│                                                         │
│  Events (Resolution):                                  │
│  ├─ MovementEvent(entity, old_pos, new_pos)         │
│  ├─ DamageTakenEvent(target, damage, source)        │
│  ├─ DoorOpenedEvent(door, actor)                    │
│  └─ ...                                               │
│                                                         │
│  Systems (Reactive):                                   │
│  ├─ MovementSystem: listens to MovementIntentEvent  │
│  ├─ CombatSystem: listens to AttackIntentEvent      │
│  ├─ TrapSystem: listens to MovementEvent            │
│  ├─ StatusEffectSystem: listens to DamageTakenEvent│
│  └─ ...                                               │
│                                                         │
│  Tags (Data):                                          │
│  ├─ tags.json with hierarchical properties          │
│  └─ TagManager reads them at runtime                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
                          ↑
                          │ (ONE-WAY dependency)
                          │ (Registry query only)
                          │
┌─────────────────────────────────────────────────────────┐
│ pyrogue_client (Presentation Mirror)                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Input:                                               │
│  ├─ Read keyboard/mouse/network                     │
│  └─ Emit MovementIntentEvent, AttackIntentEvent    │
│                                                         │
│  Renderers (pick one):                               │
│  ├─ PygameRenderer: reads Position, draws pixels   │
│  ├─ TerminalRenderer: reads Position, draws ASCII  │
│  └─ WebRenderer: reads Position, sends JSON        │
│                                                         │
│  Event Listeners:                                     │
│  ├─ AudioManager listens to DamageTakenEvent      │
│  ├─ UIManager reads Health, displays HUD          │
│  ├─ VFXManager listens to MovementEvent           │
│  └─ ...                                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Enforcement Rules

### Code Review Checklist

When adding a new feature, ask:

1. **Is it Reactive?**
   - [ ] Does this system listen to events?
   - [ ] Does it avoid scanning all entities every frame?
   - [ ] If it needs to be proactive, is there a documented reason?

2. **Is it Tag-Driven?**
   - [ ] Are feature numbers in tags.json?
   - [ ] Does the system read properties from tags?
   - [ ] Can a designer tweak values without recompiling?

3. **Does it Emit Intent?**
   - [ ] Does the system emit intent events, not mutations?
   - [ ] Are state changes isolated to resolver systems?
   - [ ] Could another system reuse this resolver?

4. **Is the Client Pure?**
   - [ ] Does pyrogue_client/ contain only presentation code?
   - [ ] Does pyrogue_engine/ contain zero UI logic?
   - [ ] Could pyrogue_engine run headless?

---

## Example: Implementing Hunger

This is how a NEW feature should be added without breaking purity.

### 1. Define in Tags

`tags.json`:
```json
{
  "Living": {
    "properties": {
      "HungerRate": 0.1,
      "MaxHunger": 100,
      "HungerDamageThreshold": 80
    }
  }
}
```

### 2. Create Component

`pyrogue_engine/prefabs/rpg/components.py`:
```python
@dataclass
class Hunger:
    current: float = 0.0
    last_tick: float = 0.0
```

### 3. Create Resolver System

`pyrogue_engine/prefabs/rpg/hunger_system.py`:
```python
class HungerSystem(System):
    def __init__(self, registry, event_bus, tag_manager):
        super().__init__(registry, event_bus)
        self.tags = tag_manager
        # ✅ Only wake up on time ticks
        self.event_bus.on(TimerTickEvent, self._on_tick)

    def _on_tick(self, event: TimerTickEvent):
        # Only check entities with Hunger
        for entity_id, (hunger, tags) in self.registry.view(Hunger, Tags):
            hunger_rate = self.tags.get_property(tags, "HungerRate", 0.1)

            hunger.current = min(100, hunger.current + hunger_rate)

            # ✅ Emit event so other systems can react
            self.event_bus.emit(HungerChangedEvent(
                entity_id=entity_id,
                hunger=hunger.current,
                is_critical=(hunger.current > 80)
            ))

            # If starving, take damage
            if hunger.current >= self.tags.get_property(tags, "HungerDamageThreshold", 80):
                self.event_bus.emit(AttackIntentEvent(
                    attacker_id=entity_id,
                    target_id=entity_id,
                    base_damage=1.0,
                    damage_type="Starvation",
                    source="hunger"
                ))
```

### 4. Client Displays

`pyrogue_client/ui/ui_manager.py`:
```python
class UIManager:
    def __init__(self, registry, event_bus):
        self.registry = registry
        self.event_bus = event_bus
        # ✅ Listen for hunger updates
        self.event_bus.on(HungerChangedEvent, self._on_hunger_changed)

    def _on_hunger_changed(self, event: HungerChangedEvent):
        # Just read it and display it
        self.hunger_bar.set_value(event.hunger)

        if event.is_critical:
            self.hunger_bar.set_color((255, 0, 0))  # Red
        else:
            self.hunger_bar.set_color((200, 200, 0))  # Yellow
```

### 5. Designer Tunes in JSON

No code changes needed:

```json
{
  "Living": {
    "Humanoid": {
      "properties": {
        "HungerRate": 0.05  // Slow metabolism
      }
    },
    "Orc": {
      "properties": {
        "HungerRate": 0.2  // Fast metabolism
      }
    }
  }
}
```

---

## The Three Sacred Rules (Abbreviated)

1. **Reactive**: Listen to events, don't poll
2. **Taggable**: Define data in tags.json, not code
3. **Intent-Driven**: Emit what you want to happen, not mutations

Client corollary:
4. **Mirror-Only**: Render engine state, don't decide it

Follow these, and pyrogue_engine will remain pure for a decade.

---

## When to Break the Rules (Rarely)

There are a few cases where you might violate these principles:

### 1. Proactive Systems

If you need something to happen without an event, document why:

```python
class FOVSystem(System):
    """
    EXCEPTION TO PRINCIPLE 1: Proactive scanning.

    Reason: FOV must update when camera moves OR when terrain changes.
    Rather than listen to two dozen different events, we recompute FOV
    once per frame. This is acceptable because FOV is a pure math problem
    with no side effects.
    """
```

### 2. Hardcoded Constants

If the value will **never** change and has **no game balance implications**:

```python
class FOVSystem(System):
    MAX_VISION_RANGE = 999  # ✅ OK: This is a hard limit, not a balance knob

class CombatSystem(System):
    CRITICAL_MULTIPLIER = 1.5  # ❌ NOT OK: This affects damage balance
```

### 3. Client Logic

If it's **purely presentational** and doesn't affect outcomes:

```python
# pyrogue_client/ui/ui_manager.py
def _flash_health_bar(self):
    # ✅ OK: This is pure animation
    for i in range(5):
        self.health_bar.set_color((255, 0, 0))
        sleep(0.1)
        self.health_bar.set_color((255, 255, 255))
        sleep(0.1)
```

---

## Final Mandate

> **No feature is complete until it passes the Headless Test.**
>
> Can you run pyrogue_engine without pyrogue_client and still play a full game (with text output instead of graphics)? If not, you've coupled something that shouldn't be coupled.

Sign this constitution in your heart. The purity of the engine depends on it.

---

## Machine State (as of 2026-04-04)

This is a snapshot of what is built and running. Add to it as systems are completed.

### Core

| System | Status | Notes |
|--------|--------|-------|
| ECS Registry | ✓ | Entity/component store, typed views |
| EventBus | ✓ | Priority queue, wildcard subscriptions |
| TagManager | ✓ | Hierarchical JSON tags, property inheritance |
| Config | ✓ | `config.json` drives server, gameplay, network |

### Simulation

| System | Status | Notes |
|--------|--------|-------|
| SimulationThread | ✓ | Accumulator pattern, GIL-yielding, 0.050s tick |
| Sync models | ✓ | `authoritative` / `lockstep` / `predictive` |
| Gameplay modes | ✓ | Turn-Based, Simultaneous, Live Stepping |
| AP Regeneration | ✓ | Live Stepping only, tick-driven |
| World tick rate | ✓ | 0.01–1000.0 t/s, Live Stepping only |

### Spatial

| System | Status | Notes |
|--------|--------|-------|
| Position / Movement | ✓ | Intent-based, collision-checked |
| FOV | ✓ | Shadowcast, drives replication culling |
| Collision | ✓ | Validates movement, feeds ProjectileSystem |

### RPG Systems

| System | Status | Notes |
|--------|--------|-------|
| CombatSystem | ✓ | Single resolver for all damage |
| ActionSystem | ✓ | AP cost gating |
| SpellSystem | ✓ | Spell cast pipeline |
| ProjectileSystem | ✓ | ECS entities, Sling/Bow, data-driven |
| EffectsSystem | ✓ | Status effects on DamageTakenEvent |
| SessionManagement | ✓ | 3-layer ID: session_id → entity_id → network_id |
| NetworkInputValidator | ✓ | Anti-cheat before intent |

### AI

| System | Status | Notes |
|--------|--------|-------|
| AwarenessSystem | ✓ | Sensory pipeline (sight/sound/scent) |
| DecisionTree | ✓ | Composable node trees |
| TreeFactory | ✓ | Data-driven tree construction |
| Factions | ✓ | Faction-based threat alignment |
| ThreatMath | ✓ | Weighted threat scoring |
| Modifiers | ✓ | Contextual behavior modifiers |

### Items & Inventory

| System | Status | Notes |
|--------|--------|-------|
| InventorySystem | ✓ | Classic roguelike slots |
| CheeseSystem | ✓ | Debug item: melee/throw/split/drop |
| ItemTables | ✓ | Data-driven spawn tables |

### Network

| System | Status | Notes |
|--------|--------|-------|
| HeadlessServer | ✓ | asyncio WebSocket, thread-safe input queue |
| ReplicationSystem | ✓ | FOV-culled, per-client packet dispatch |
| Replication modes | ✓ | `full_state` / `fov_culled` / `delta_compressed` |

### Generation

| System | Status | Notes |
|--------|--------|-------|
| BSP / Automata / Noise | ✓ | Three map generators |
| HeightMap | ✓ | Terrain elevation |
| LevelBlueprint | ✓ | Declarative level spec |
| FloodFill analyzer | ✓ | Connectivity validation |

### Entity Pipeline

| System | Status | Notes |
|--------|--------|-------|
| EntityFactory | ✓ | Spawns entities from templates |
| TemplateRegistry | ✓ | JSON-driven entity templates |
| Populator | ✓ | Room/area entity placement |

### Client (Mirror Layer)

| System | Status | Notes |
|--------|--------|-------|
| PygameRenderer | ✓ | Pixel rendering |
| TerminalRenderer | ✓ | ASCII rendering |
| WebRenderer | ✓ | JSON state push |
| AudioManager | ✓ | Reacts to engine events |
| InputAdapter | ✓ | Enhanced input → intent events |
| WizBot | ✓ | Autonomous stress-test bot |

### Key Numbers

- Tick rate target: **sub-50ms** (0.050s default)
- Replication scale target: **100+ simultaneous players** via FOV culling
- ID layers: **3** (session / entity / network)
- Sync models: **3** (authoritative / lockstep / predictive)
- Gameplay modes: **3** (Turn-Based / Simultaneous / Live Stepping)
- Map generators: **3** (BSP / Automata / Noise)

---

**Signed**: The Architecture Gods
**Date**: Every day you maintain this
