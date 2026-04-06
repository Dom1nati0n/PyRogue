# Projectile System

## Overview

The Projectile System is a purely event-driven, server-authoritative implementation for ranged combat. Projectiles are real ECS entities that move via physics, and **CollisionSystem detects impacts**. ProjectileSystem **reacts** to collision events by emitting combat intents.

**Follows The Constitution**: Principle 1 (Reactive), Principle 2 (Tags), Principle 3 (Intent)

## Architecture

### Components

**Projectile**
- `shooter_id`: The entity that fired the projectile
- `weapon_tag`: Tag reference (e.g., "Weapon.Ranged.Bow") for damage/type lookup

**Deflector** (optional, for shields)
- `active`: Is the shield up?
- `arc_degrees`: Angular coverage of the shield

### System Flow

1. **Spawn**: Create projectile entity (Position, Velocity, Projectile components)
2. **Move**: PhysicsSystem moves projectile via Position + Velocity
3. **Detect**: CollisionSystem detects collision during movement validation
4. **Emit**: CollisionSystem emits CollisionEvent to event bus
5. **React**: ProjectileSystem listens to CollisionEvent
6. **Impact**: If projectile hit something, emit AttackIntentEvent
7. **Resolve**: CombatResolverSystem calculates damage
8. **Cleanup**: Projectile destroyed

**Key**: ProjectileSystem does NOT run every frame. It only activates when a collision actually occurs.

### Data-Driven Weapons (Principle 2: Tags are Source of Truth)

All weapon stats live in `tags.json`. ProjectileSystem reads these at runtime—no hardcoding.

Example (Sling):
```json
"Sling": {
  "properties": {
    "DamageType": "Bludgeoning",
    "BaseDamage": 6,
    "BaseIntegrity": 40,
    "InitialPV": 2,
    "Speed": 100.0
  }
}
```

**Properties read by ProjectileSystem**:
- `BaseDamage`: Damage value when hitting
- `DamageType`: Type of damage (Piercing, Bludgeoning, etc.)

Add new weapons by editing `tags.json`—no code changes needed.

## Usage

### Basic Fire

```python
from pyrogue_engine.systems.rpg.projectile_factory import fire_bow, fire_sling

# Fire a bow arrow from archer at goblin
arrow_id = fire_bow(registry, shooter_id=archer_id, target_x=5, target_y=3)

# Fire a sling stone
stone_id = fire_sling(registry, shooter_id=slinger_id, target_x=10, target_y=10)
```

### Manual Spawn

```python
from pyrogue_engine.systems.rpg.projectile import Projectile
from pyrogue_engine.systems.spatial.components import Position, Velocity

# Create projectile manually
projectile_id = registry.create_entity()
registry.add_component(projectile_id, Position(x=5, y=5, z=0))
registry.add_component(projectile_id, Velocity(dx=1.0, dy=0.5))
registry.add_component(projectile_id, Projectile(
    shooter_id=archer_id,
    weapon_tag="Weapon.Ranged.Bow"
))
```

### Initialize ProjectileSystem

```python
from pyrogue_engine.systems.rpg.projectile import ProjectileSystem

# In your server setup (headless_server.py, etc.)
projectile_system = ProjectileSystem(registry, event_bus, tag_manager)

# Call in your game loop alongside other systems:
# projectile_system.update(delta_time)
```

## Design Aligned with The Constitution

### Principle 1: Logic is Reactive, Never Proactive
- **Not**: ProjectileSystem running every frame checking for collisions
- **Instead**: CollisionSystem detects collisions, emits events, ProjectileSystem reacts
- **Benefit**: Collision handling only runs when collisions occur (not every frame)

### Principle 2: Tags are Source of Truth
- All weapon stats in `tags.json` (BaseDamage, DamageType, etc.)
- ProjectileSystem reads tags at runtime
- Balance changes in JSON, no code recompilation needed
- New weapons don't require code changes

### Principle 3: Intent, Not Mutation
- ProjectileSystem emits `AttackIntentEvent` (not damage directly)
- CombatResolverSystem applies damage (single source of truth for all combat)
- Reuses all armor, resistance, critical hit mechanics automatically
- Other systems can hook into damage events (bleeding, poison, UI, etc.)

### Principle 4: Server Authority
- Projectiles are server entities with real Position + Velocity
- Clients render them as moving objects (no client-side logic)
- No client-side hit detection or damage calculation
- Prevents cheating (can't modify local position to fake hits)

## Weapons Included

### Sling
- **Damage**: 6 (Bludgeoning)
- **InitialPV**: 2
- **Speed**: 100.0
- **Use**: Simple melee-range projectile weapon

### Bow
- **Damage**: 10 (Piercing)
- **InitialPV**: 5
- **Speed**: 150.0
- **Use**: Mid-range ranged weapon

### Heavy Crossbow
- **Damage**: 18 (Piercing)
- **InitialPV**: 12
- **Speed**: 300.0
- **Use**: High damage, slow weapon

## Next: Ammo System

To extend this with an ammo/inventory system:
1. Add `AmmoComponent` to entities
2. Check ammo in `fire_bow()` before spawning
3. Consume ammo on fire
4. Different ammo types (broadhead, blunt, etc.) override weapon stats

Example tag for arrow ammo:
```json
"Arrow": {
  "properties": {
    "Type": "Ammo",
    "AmmoFor": "Weapon.Ranged.Bow",
    "ModifyDamage": 1.0
  }
}
```
