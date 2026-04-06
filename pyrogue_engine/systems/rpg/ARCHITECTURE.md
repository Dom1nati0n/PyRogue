# pyrogue_engine/prefabs/rpg - Complete Architecture

This is a fully-extracted, reusable RPG system library. It contains everything needed
to build a roguelike game, separated into distinct, composable layers.

## Module Structure

```
prefabs/rpg/
├── components.py              # Data containers (Health, Attributes, Defense, etc.)
├── combat_math.py             # Pure damage calculation (unit-testable)
├── combat_system.py           # Event-driven combat (AttackIntentEvent → DamageApplied)
├── action_system.py           # Request→Validate→Dispatch pipeline
├── effects.py                 # Status effects (poison, haste, etc.) via events
├── timer_integration.py       # How to connect with game's TimerSystem
├── __init__.py                # Public API
│
└── Documentation:
    ├── ARCHITECTURE.md        # This file
    ├── EFFECTS_EXAMPLE.md     # How status effects work with timers
    └── (See parent rpg/ for PIPELINE_EXAMPLE.md for combat)
```

## Four Core Subsystems

### 1. Combat System (`combat_system.py`)

**Responsibility**: Resolve attacks, apply damage, track kills.

**Pattern**: Event-driven
- `AttackIntentEvent` → CombatResolverSystem
- Calculates damage using pure math
- Emits `DamageTakenEvent` and `DeathEvent`

**Integration**: Listens for combat intents, ignores implementation details.

```python
# Any system can fire an attack
attack = AttackIntentEvent(
    attacker_id=player,
    target_id=enemy,
    base_damage=8,
    damage_type="Slashing",
    stat_key="strength"
)
event_bus.emit(attack)  # CombatSystem handles rest
```

**Why decoupled**: DoT effects, traps, and spells all emit AttackIntentEvent.
CombatSystem doesn't care where the attack came from.

---

### 2. Action System (`action_system.py`)

**Responsibility**: Validate player/AI actions and execute them.

**Pattern**: Request→Validate→Dispatch
1. Parse ActionRequest
2. Validate preconditions (actor exists, has AP, target is alive)
3. Execute: emit AttackIntentEvent
4. Deduct costs (AP spent)

**Integration**: Game loop calls `resolver.resolve_action(request)`.

```python
request = ActionRequest(actor_id=player, action_key="HEAVY_SLASH", target_id=enemy)
result = action_resolver.resolve_action(request)
# ActionResolver emits AttackIntentEvent automatically
# CombatSystem picks it up and applies damage
```

**Why decoupled**: All systems (player, AI, triggers) use the same interface.
Actions don't mutate state directly—they emit events.

---

### 3. Status Effects System (`effects.py`)

**Responsibility**: Manage temporary effects (poison, haste, slow) using global time.

**Pattern**: Listen to TimerSystem's heartbeat
1. `ApplyEffectEvent` → register timer with TimerSystem
2. TimerSystem ticks countdown
3. TimerSystem emits `TimerExpiredEvent`
4. StatusEffectSystem cleans up
5. `TurnTickEvent` → process DoT/HoT (emit damage events)

**Integration**: Pause game → all effects pause automatically (TimerSystem respects pause).

```python
# Apply poison for 5 turns
poison = EffectTemplate("poison", "DOT", magnitude=5)
effects_system.register_effect_template(poison)

event = ApplyEffectEvent(entity, poison, duration=5)
event_bus.emit(event)

# StatusEffectSystem:
# 1. Adds poison to ActiveEffects component
# 2. Tells TimerSystem: add_timer(entity, "status_effect_poison", 5)
# 3. Listens for TimerExpiredEvent
# 4. On TurnTickEvent: emits AttackIntentEvent for poison damage
```

**Why decoupled**: TimerSystem is the single source of truth for time.
Effects don't count down—they register and listen.

---

### 4. Combat Math (`combat_math.py`)

**Responsibility**: Pure mathematical damage calculation.

**Pattern**: Pure functions (no side effects)

```python
damage_roll = calculate_damage(
    base_damage=8,
    stat_modifier=2,
    armor_value=5
)
# Returns: DamageRoll(base=8, mod=2, var=6, raw=16, armor=5, final=11)
```

**Integration**: CombatSystem calls this for every attack. Completely testable.

```python
# Unit test without any ECS:
def test_damage_calculation():
    roll = calculate_damage(8, 2, 5)
    assert roll.final_damage == 5  # 8 + 2 - 5
```

**Why decoupled**: Pure functions have no external dependencies.

---

## Data Flow: A Complete Combat Sequence

```
1. Player issues action
   ActionRequest(actor=player, action_key="HEAVY_SLASH", target=enemy)

2. ActionResolver validates and executes
   → Validates: player exists, has 3 AP, "HEAVY_SLASH" is legal, enemy alive
   → Executes: emit AttackIntentEvent
   → Deducts: 3 AP from player

3. CombatSystem receives AttackIntentEvent
   → Gets attacker's Strength stat (+2 modifier)
   → Gets target's armor (5 rating)
   → Calls calculate_damage(base=14, mod=2, armor=5) → final_damage=11
   → Emits DamageTakenEvent

4. HealthSystem receives DamageTakenEvent
   → Reduces health: 50 - 11 = 39 HP
   → Checks: still alive
   → Logs event to UI

5. Next turn, poison ticks
   → TurnTickEvent fired
   → StatusEffectSystem._on_turn_tick()
   → Poison behavior == "DOT" → emit AttackIntentEvent(base_damage=5)
   → CombatSystem handles poison damage (same path as step 3)
   → Enemy takes 5 damage (or less if poison bypasses armor)

6. After 3 more turns, poison expires
   → TimerSystem emits TimerExpiredEvent("status_effect_poison")
   → StatusEffectSystem removes poison from ActiveEffects
   → Emits EffectExpiredEvent for UI notification
```

---

## Composition Example: Building a Spell

Let's say you want a "Fireball" spell that:
- Deals 20 base damage (fire type)
- Applies burning for 3 turns
- Hits all enemies in a 2-tile radius

```python
# Phase 1: Define the spell action
SPELLS = {
    "FIREBALL": {
        "ap_cost": 4,
        "base_damage": 20,
        "damage_type": "Fire",
        "stat_key": "intelligence",  # Int-based spell
        "aoe_radius": 2,
        "aoe_type": "BURST",
    }
}

# Phase 2: Define the burning effect
burning = EffectTemplate(
    id="burning",
    behavior="DOT",
    magnitude=3,
    stack_rule="STACK",  # Multiple burns stack
)
effects_system.register_effect_template(burning)

# Phase 3: Execute spell (in game code, you write this)
def execute_fireball(caster_id, center_x, center_y):
    # Get all enemies in 2-tile radius of center
    enemies_in_range = find_entities_in_radius(center_x, center_y, radius=2)

    for enemy_id in enemies_in_range:
        # Emit attack intent
        attack = AttackIntentEvent(
            attacker_id=caster_id,
            target_id=enemy_id,
            base_damage=20,
            damage_type="Fire",
            stat_key="intelligence"
        )
        event_bus.emit(attack)

        # Apply burning
        burn_event = ApplyEffectEvent(enemy_id, burning, duration=3)
        event_bus.emit(burn_event)
        timer_system.add_timer(enemy_id, "status_effect_burning", 3)

# Phase 4: Systems handle everything
# - CombatSystem resolves damage
# - StatusEffectSystem manages burning timer
# - TurnTickEvent → poison deals damage every turn
# - After 3 turns, burn expires
```

**Every piece** (action validation, damage, effects, timers) is independent.
You can:
- Change how damage is calculated (math system)
- Change effect stacking rules (template)
- Add new effect behaviors (just add a case in `_on_turn_tick`)
- Modify action validation (just edit ActionResolver)

---

## Testing Strategy

Because everything is event-driven:

```python
# Test 1: Pure math (no ECS)
def test_damage_math():
    roll = calculate_damage(10, 3, 5)
    assert roll.final_damage == 8

# Test 2: Combat system in isolation
def test_combat_resolver():
    registry, bus = setup_test_world()
    system = CombatResolverSystem(registry, bus)

    # Emit attack
    attack = AttackIntentEvent(attacker=1, target=2, base_damage=10)
    system._on_attack_intent(attack)

    # Verify health decreased
    health = registry.get_component(2, Health)
    assert health.current < health.maximum

# Test 3: Effect system in isolation
def test_poison_application():
    registry, bus = setup_test_world()
    effects = StatusEffectSystem(registry, bus)

    # Apply poison
    poison = EffectTemplate("poison", "DOT", magnitude=5)
    effects.register_effect_template(poison)

    event = ApplyEffectEvent(target=1, template=poison, duration=3)
    effects._on_apply_effect(event)

    # Verify effect applied
    active = registry.get_component(1, ActiveEffects)
    assert active.has_effect("poison")
```

Each layer tested in isolation. No dependencies.

---

## Key Principles

1. **Events are the API** — Systems communicate via events, not direct calls
2. **Listeners, not loops** — No system counts down its own timers
3. **TimerSystem is king** — Single source of truth for duration
4. **Pure math is testable** — Combat calculations have no side effects
5. **Composition over monolith** — Build spells/abilities by composing events

---

## What's Missing (Your Game Writes This)

- **Painters** (Phase 3) — How to spawn tile entities from LevelBlueprint
- **Decorators** (Phase 4) — How to spawn monsters/loot in generated maps
- **Spell/Ability system** — How to chain effects with spells (you have the building blocks)
- **AI/Behavior** — How NPCs choose actions
- **Rendering** — How to display everything

But the **core simulation layer** (combat, effects, timers, actions) is complete.
It doesn't care about your game's specifics.

---

## Next Steps

1. ✅ Implement your Painter (spawn tiles from LevelBlueprint)
2. ✅ Implement your Decorator (spawn monsters from metadata)
3. ✅ Connect your game's EventDispatcher to pyrogue_engine's EventBus
4. ✅ Connect your game's TimerSystem to StatusEffectSystem
5. ✅ Build spells by composing the events (AttackIntent + ApplyEffect)
6. ✅ Test each layer independently

The engine is ready.
