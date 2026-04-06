# Systems - Reactive Game Logic

This directory contains reusable, reactive game systems organized by domain. All systems follow **THE_CONSTITUTION.md** principles:

1. **Reactive**: Systems listen to events, they don't poll
2. **Tag-Driven**: Configuration lives in tags.json, not hardcoded
3. **Intent-Based**: Systems emit intent events, not mutations
4. **Decoupled**: No system depends on another—only on shared components and the event bus

## Directory Structure

### `spatial/` — Spatial Mechanics
Movement, collision detection, field of view, and direction management.

**Key Components:**
- `Position(x, y)` — Entity location on the map
- `Velocity(dx, dy)` — Movement per frame
- `Vision(range)` — FOV parameters
- `Facing(direction)` — Which way the entity faces
- `Movement(speed, acceleration)` — Kinematic properties

**Key Systems:**
- `PerceptionSystem` — Compute visible tiles using shadowcast algorithm
- `KinematicMovementSystem` — Apply velocity to position each frame
- `CollisionSystem` — Prevent overlap and diagonal clipping
- `DirectionalFacingSystem` — Rotate sprite/model to face movement direction

**Pure Functions:**
- `compute_shadowcast_fov()` — Unit-testable FOV calculation
- `can_move_to()` — Check if a tile is walkable
- `can_move_diagonal()` — Check if diagonal movement clips walls

---

### `rpg/` — RPG Combat and Actions
Damage calculation, combat resolution, status effects, action validation.

**Key Components:**
- `Health(current, maximum)` — Hit points
- `Attributes(dict)` — Flexible stats (STR, DEX, INT, etc.)
- `Equipment(main_hand_id, armor_id, ...)` — Item slots
- `CombatStats(damage, defense, critical_chance)` — Combat modifiers
- `ActiveEffects([...])` — Status effects and their expiration

**Key Systems:**
- `CombatResolverSystem` — Resolve AttackIntentEvent → DamageTakenEvent
- `StatusEffectSystem` — Apply status effects, track expiration
- `InitiativeSystem` — Combat turn order
- `ActionResolver` — Request → Validate → Dispatch action pipeline

**Pure Functions:**
- `calculate_damage()` — Unit-testable damage math (armor, resistance, crits)
- `calculate_critical_hit()` — Crit chance and multiplier
- `calculate_dodge()` — Evasion calculation
- `calculate_healing()` — Healing amount with resistances

**Key Events:**
- `AttackIntentEvent` — "I want to attack this target"
- `DamageTakenEvent` — "Damage was applied" (resolver event)
- `DeathEvent` — Entity HP reached 0
- `HealingAppliedEvent` — Healing was resolved

---

### `ai/` — NPC Behavior and Awareness
Decision trees, threat assessment, faction systems, AI perception.

**Key Components:**
- `Brain(mindset_id)` — Which decision tree to execute
- `Memory(dict)` — Entity observations (seen enemies, landmark locations)
- `Faction(alignment)` — Faction registry for relationships
- `ScentMemory(list)` — Scent trail memory for tracking

**Key Systems:**
- `AISystem` — Execute decision trees every tick
- `AwarenessSystem` — What entities can see/smell each other

**Decision Tree Nodes:**
- **Condition Nodes:** HasTarget, TargetInRange, SelfHealthLow, etc.
- **Action Nodes:** MeleeAttack, Move, Wander, Wait, UpdateMemory

**Pure Functions:**
- `calculate_threat_score()` — Distance, alertness, visibility
- `adjusted_vision_range()` — FOV affected by lighting/alarm
- `calculate_alarm_radius()` — Sound spreads to neighboring areas

**Example Behavior:**
```json
{
  "type": "Fallback",
  "children": [
    {"type": "ConditionHasTarget"},
    {
      "type": "Routine",
      "children": [
        {"type": "ActionMeleeAttack"},
        {"type": "ActionWait"}
      ]
    },
    {"type": "ActionWander"}
  ]
}
```

---

## Design Pattern: Pure Functions + ECS

Each subsystem follows this pattern:

1. **Pure Math Module** (unit-testable)
   ```python
   # In combat_math.py
   def calculate_damage(attacker_health, defender_defense, critical):
       ...
   ```

2. **ECS System** (listens to events, uses the pure function)
   ```python
   class CombatResolverSystem(System):
       def _on_attack_intent(self, event):
           damage = calculate_damage(...)  # Pure function
           self.event_bus.emit(DamageTakenEvent(...))
   ```

3. **Configuration in Tags** (no hardcoding)
   ```json
   {
     "Humanoid": {
       "properties": {
         "BaseHealth": 100,
         "PhysicalResistance": 0.1
       }
     }
   }
   ```

---

## Adding a New System

1. **Define components** in `{domain}/components.py`
2. **Write pure math** in `{domain}/math_*.py` or `{domain}/*_math.py`
3. **Create resolver system** that:
   - Listens to an intent event
   - Calls pure functions
   - Emits resolution events
4. **Register system** in `game_init.py`
5. **Add configuration** to `tags.json`

Example: See `ENTITIES_GUIDE.md` in the parent directory for a complete example (Hunger system).

---

## Testing Pure Functions

All pure math is in standalone modules and 100% unit-testable:

```python
from pyrogue_engine.systems.rpg.combat_math import calculate_damage

assert calculate_damage(health=100, defense=10) == 80
```

No ECS, no events, no side effects. Perfect for TDD.

---

## See Also

- **THE_CONSTITUTION.md** — Design principles and enforcement rules
- **ENTITIES_GUIDE.md** — How to define and spawn entities
- **GENERATION_GUIDE.md** — Procedural dungeon generation
