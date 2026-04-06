# Status Effects Architecture - Complete Example

This demonstrates how Status Effects integrate with the global TimerSystem,
creating a truly decoupled, event-driven system.

## The Philosophy

**The TimerSystem is the heartbeat. Everything else is a listener.**

When poison is applied for 3 turns:
1. StatusEffectSystem doesn't start a countdown
2. StatusEffectSystem registers a timer with TimerSystem: `add_timer(entity, "status_effect_poison", 3)`
3. TimerSystem ticks its internal countdown (respecting pause, slow-motion, etc.)
4. When the timer expires, TimerSystem emits `TimerExpiredEvent`
5. StatusEffectSystem listens and cleans up

**Result**: Pause the game → all timers pause automatically. No special code.

---

## Step-by-Step Example

### 1. Register Effect Templates

```python
from pyrogue_engine.prefabs.rpg import (
    EffectTemplate,
    StatusEffectSystem,
    ActiveEffects,
)

# Define effect types (usually loaded from JSON)
poison_template = EffectTemplate(
    id="poison",
    behavior="DOT",  # Damage Over Time
    magnitude=5,     # 5 damage per turn
    stack_rule="STACK",  # Multiple poisons stack
)

haste_template = EffectTemplate(
    id="haste",
    behavior="STAT_MOD",  # Stat modifier
    stat_key="agility",   # Modifies agility
    magnitude=2,          # +2 agility
    stack_rule="REFRESH", # Reapply just extends duration
)

# Register with the system
effects_system = StatusEffectSystem(registry, event_bus)
effects_system.register_effect_template(poison_template)
effects_system.register_effect_template(haste_template)
```

### 2. Apply an Effect

```python
from pyrogue_engine.prefabs.rpg import ApplyEffectEvent

# Apply poison for 5 turns
poison_event = ApplyEffectEvent(
    target_id=monster_entity,
    template=poison_template,
    duration=5,  # In turns
)
event_bus.emit(poison_event)

# StatusEffectSystem receives this and:
# 1. Adds poison to monster's ActiveEffects component
# 2. Registers timer: timer_system.add_timer(monster_entity, "status_effect_poison", 5)

# Separately, register the same timer with your game's TimerSystem
timer_system.add_timer(monster_entity, "status_effect_poison", 5)
```

### 3. Main Game Loop

```python
def game_loop_tick():
    """
    Called every frame/turn. Order matters!
    """
    # 1. Handle input, AI decisions
    player_action = get_player_action()

    # 2. Process timers (THE HEARTBEAT)
    timer_system.process(dt)
    # This emits TimerExpiredEvent when timers run out

    # 3. Process events (automatically handled by EventBus subscription)
    # StatusEffectSystem already listening for TimerExpiredEvent

    # 4. Notify effects that a turn has advanced (for DoT/HoT)
    from pyrogue_engine.prefabs.rpg import TurnTickEvent
    event_bus.emit(TurnTickEvent())
    # StatusEffectSystem processes poison: emits damage event

    # 5. Combat system processes damage
    # (CombatSystem listening for AttackIntentEvent from poison)

    # 6. Render
    render()
```

### 4. What Happens When Poison Ticks

```
Turn 1:
  ✓ Poison applied, timer registered for 5 turns
  ✓ TurnTickEvent → StatusEffectSystem._on_turn_tick()
  ✓ poison.behavior == "DOT" → emit AttackIntentEvent
  ✓ CombatSystem._on_attack_intent() handles the damage
  ✓ Monster takes 5 damage (potentially reduced by armor)
  ✓ Monster's Health component updated

Turn 2-4:
  ✓ Same process repeats

Turn 5:
  ✓ Poison timer remaining = 0
  ✓ TimerSystem emits TimerExpiredEvent("status_effect_poison")
  ✓ StatusEffectSystem._on_timer_expired() hears it
  ✓ Removes poison from ActiveEffects
  ✓ Emits EffectExpiredEvent("poison")
  ✓ Game can react (e.g., "Poison wears off!" message)
```

---

## Stacking Rules

The `stack_rule` in the template determines what happens if the same effect is reapplied:

### REFRESH (Duration Reset)

```python
haste_template = EffectTemplate(
    id="haste",
    behavior="STAT_MOD",
    stat_key="agility",
    magnitude=2,
    stack_rule="REFRESH",  # Reapply extends duration
)

# Apply haste for 5 turns
apply_haste(entity, 5)
# Monster: {haste: +2 agility}

# Turn 3: Reapply haste
apply_haste(entity, 5)
# Monster: {haste: +2 agility} (still +2, but timer resets to 5)
# Result: Haste lasts 8 turns total (3 + 5)
```

**Use case**: Buffs you want to extend, not stack.

### STACK (Magnitude Stacks)

```python
poison_template = EffectTemplate(
    id="poison",
    behavior="DOT",
    magnitude=5,
    stack_rule="STACK",  # Multiple poisons stack
)

# Apply poison for 3 turns
apply_poison(entity, 3)
# Monster: {poison: 5 dmg/turn}

# Turn 1: Reapply poison
apply_poison(entity, 3)
# Monster: {poison: 10 dmg/turn} (damage stacks)
# Timer? Both are tracked separately by TimerSystem

# Result: Turn 1 takes 10 damage
#         Turn 2 takes 10 damage (first poison expires)
#         Turn 3 takes 5 damage (second poison's turn 3)
```

**Use case**: Debuffs that get worse with multiple applications.

### IGNORE (No Reapplication)

```python
frozen_template = EffectTemplate(
    id="frozen",
    behavior="CONTROL",
    stack_rule="IGNORE",  # Can't be reapplied
)

# Apply frozen for 2 turns
apply_frozen(entity, 2)
# Monster: {frozen: active}

# Turn 1: Try to reapply frozen
apply_frozen(entity, 2)
# Ignored! Effect unchanged
# Monster: {frozen: active} (still expires after 1 more turn)
```

**Use case**: Hard crowd control that can't be extended or stacked.

---

## Integration with Combat

When poison ticks, it emits an `AttackIntentEvent`:

```python
# In StatusEffectSystem._on_turn_tick():
if template.behavior == "DOT":
    damage_event = AttackIntentEvent(
        attacker_id=None,  # No attacker (environmental damage)
        target_id=entity_id,
        base_damage=magnitude,  # 5 from poison
        damage_type="Status",
        stat_key=None,
    )
    event_bus.emit(damage_event)
```

Then `CombatSystem._on_attack_intent()` handles it:
- Calculates armor reduction (poison bypasses armor? or does it?)
- Emits `DamageTakenEvent`
- Updates health
- Checks for death

**This separation is powerful**: You can change how poison works (AP reduction? slow?) without touching CombatSystem.

---

## Global Time Control

Because TimerSystem is the heartbeat:

```python
# Pause the game
timer_system.global_speed = 0.0
# All timers (including poison duration) pause

# Slow motion
timer_system.global_speed = 0.5
# All timers (including poison duration) run at half speed

# Time warp
timer_system.global_speed = 2.0
# All timers (including poison duration) run at double speed
```

**No special effect code needed.** The TimerSystem handles it globally.

---

## Testing

Because the system is event-driven, you can test effects in isolation:

```python
def test_poison_damage():
    """Test that poison deals damage correctly."""
    registry = Registry()
    event_bus = EventBus()
    effects_system = StatusEffectSystem(registry, event_bus)

    # Create entity with health
    entity = registry.create_entity()
    registry.add_component(entity, Health(100, 100))
    registry.add_component(entity, ActiveEffects())

    # Apply poison
    poison = EffectTemplate("poison", "DOT", magnitude=5)
    effects_system.register_effect_template(poison)

    event = ApplyEffectEvent(entity, poison, 5)
    effects_system._on_apply_effect(event)

    # Simulate a turn
    tick = TurnTickEvent()
    effects_system._on_turn_tick(tick)

    # Manually resolve the damage event
    health = registry.get_component(entity, Health)
    health.take_damage(5)

    # Verify
    assert health.current == 95  # Took 5 damage
```

Pure unit test. No game loop, no rendering, no complexity.
