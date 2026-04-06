#!/usr/bin/env python
"""
Simple projectile test - Fire a sling stone at a target.

Tests:
1. Projectile spawning with tags
2. Collision detection
3. Combat intent emission
4. Entity destruction on impact
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import EventBus, Event
from pyrogue_engine.core.tags import TagManager
from pyrogue_engine.systems.spatial.components import Position, Velocity
from pyrogue_engine.systems.rpg.components import Health
from pyrogue_engine.systems.rpg.projectile import (
    ProjectileSystem,
    Projectile,
    ProjectileDestroyEvent,
)
from pyrogue_engine.systems.rpg.combat_system import AttackIntentEvent


def test_projectile_fire():
    """Test firing a sling projectile at a target."""
    print("=" * 70)
    print("PROJECTILE TEST: Sling Stone")
    print("=" * 70)

    # Setup
    registry = Registry()
    event_bus = EventBus()
    tag_manager = TagManager("pyrogue_engine/core/tags/tags.json")

    # Create projectile system
    projectile_system = ProjectileSystem(registry, event_bus, tag_manager)
    print("[OK] ProjectileSystem initialized")

    # Create shooter (archer)
    shooter_id = registry.create_entity()
    registry.add_component(shooter_id, Position(0, 0, 0))
    print(f"[OK] Shooter spawned: entity {shooter_id}")

    # Create target (goblin)
    target_id = registry.create_entity()
    registry.add_component(target_id, Position(5, 0, 0))
    registry.add_component(target_id, Health(current=20, maximum=20))
    print(f"[OK] Target spawned: entity {target_id} at (5, 0, 0) with 20 HP")

    # Spawn projectile
    projectile_id = registry.create_entity()
    registry.add_component(projectile_id, Position(0, 0, 0))
    registry.add_component(projectile_id, Velocity(dx=1.0, dy=0.0))
    registry.add_component(projectile_id, Projectile(
        shooter_id=shooter_id,
        weapon_tag="Weapon.Ranged.Sling",
    ))
    print(f"[OK] Projectile spawned: entity {projectile_id}")

    # Check tags
    base_damage = tag_manager.get_property("Weapon.Ranged.Sling", "BaseDamage")
    damage_type = tag_manager.get_property("Weapon.Ranged.Sling", "DamageType")
    initial_pv = tag_manager.get_property("Weapon.Ranged.Sling", "InitialPV")
    print(f"[OK] Sling stats from tags: BaseDamage={base_damage}, DamageType={damage_type}, InitialPV={initial_pv}")

    # Track events
    attacks_fired = []
    projectiles_destroyed = []

    def on_attack(event: AttackIntentEvent):
        attacks_fired.append(event)
        print(f"[!] AttackIntentEvent: {event.attacker_id} -> {event.target_id}, {event.base_damage} {event.damage_type}")

    def on_destroy(event: ProjectileDestroyEvent):
        projectiles_destroyed.append(event)
        print(f"[!] ProjectileDestroyEvent: entity {event.entity_id} ({event.reason})")

    event_bus.subscribe("combat.attack_intent", on_attack)
    event_bus.subscribe("projectile.destroyed", on_destroy)

    # Simulate collision event (from CollisionSystem)
    print("\n[SIMULATE] CollisionSystem detects projectile hitting target...")
    from pyrogue_engine.systems.spatial.collision import CollisionEvent
    collision_event = CollisionEvent(
        entity_id=projectile_id,
        target_x=5,
        target_y=0,
        collision_type="entity",
        target_entity_id=target_id,
    )
    # Emit to event bus - ProjectileSystem listens and reacts
    event_bus.emit(collision_event)

    # Verify results
    print("\n[RESULTS]")
    print(f"  Attacks emitted: {len(attacks_fired)}")
    if attacks_fired:
        attack = attacks_fired[0]
        print(f"    - Attacker: {attack.attacker_id}")
        print(f"    - Target: {attack.target_id}")
        print(f"    - Damage: {attack.base_damage}")
        print(f"    - Type: {attack.damage_type}")

    print(f"  Projectiles destroyed: {len(projectiles_destroyed)}")
    if projectiles_destroyed:
        destroy = projectiles_destroyed[0]
        print(f"    - Entity: {destroy.entity_id}")
        print(f"    - Reason: {destroy.reason}")

    # Verify entity destruction
    alive_entities = registry._alive_entities
    print(f"  Alive entities: {sorted(alive_entities)}")

    # Test passed?
    success = (
        len(attacks_fired) == 1 and
        attacks_fired[0].base_damage == base_damage and
        attacks_fired[0].damage_type == damage_type and
        len(projectiles_destroyed) == 1 and
        projectile_id not in alive_entities
    )

    print("\n" + "=" * 70)
    if success:
        print("SUCCESS: PROJECTILE TEST PASSED")
    else:
        print("FAILURE: PROJECTILE TEST FAILED")
    print("=" * 70)

    return success


if __name__ == "__main__":
    success = test_projectile_fire()
    sys.exit(0 if success else 1)
