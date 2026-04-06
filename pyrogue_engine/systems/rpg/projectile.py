"""
Projectile System - Event-driven projectile mechanics.

Projectiles are real ECS entities that move via Velocity.
CollisionSystem detects when they hit something (during movement validation).
ProjectileSystem listens to collision events and emits AttackIntentEvent.

Follows Principle 1: Logic is Reactive, Never Proactive
- ProjectileSystem does NOT run every frame checking for collisions
- Instead, it listens to collision events from CollisionSystem
- Reacts only when a collision actually occurs
"""

from dataclasses import dataclass
from typing import Optional

from pyrogue_engine.core.ecs import Registry, System
from pyrogue_engine.core.events import Event, EventBus
from .combat_system import AttackIntentEvent


@dataclass
class Projectile:
    """Flying projectile entity. Attached to a position-tracked entity."""
    shooter_id: int
    weapon_tag: str  # e.g., "Weapon.Ranged.Bow"


@dataclass
class Deflector:
    """Shield that can block incoming projectiles."""
    active: bool = False
    arc_degrees: float = 90.0  # Angular coverage of the shield


class ProjectileDestroyEvent(Event):
    """Projectile has been destroyed (hit something or expired)."""
    def __init__(self, entity_id: int, reason: str = "impact"):
        super().__init__(event_type="projectile.destroyed")
        self.entity_id = entity_id
        self.reason = reason  # "impact", "wall", "expire", etc.


class ProjectileSystem(System):
    """
    Reacts to collision events. If a projectile hit something, emit AttackIntentEvent.

    Listens to: CollisionEvent (from CollisionSystem)
    Emits to: AttackIntentEvent (for CombatResolverSystem), ProjectileDestroyEvent

    Purely reactive - only runs when a collision actually happens.
    """

    def __init__(self, registry: Registry, event_bus: EventBus, tag_manager):
        super().__init__(registry, event_bus)
        self.tags = tag_manager
        # React to collisions
        self.event_bus.subscribe("spatial.collision", self._on_collision)
        # React to destroy events
        self.event_bus.subscribe("projectile.destroyed", self._on_projectile_destroyed)

    def _on_collision(self, event) -> None:
        """
        Handle collision event. If a projectile collided, emit AttackIntentEvent.

        Event from CollisionSystem contains:
        - entity_id: thing that collided
        - collision_type: "wall" or "entity"
        - target_entity_id: if collision_type == "entity", who did we hit
        """
        projectile = self.registry.get_component(event.entity_id, Projectile)
        if not projectile:
            return  # Not a projectile, ignore

        # Hit a wall
        if event.collision_type == "wall":
            self.event_bus.emit(ProjectileDestroyEvent(event.entity_id, "wall"))
            return

        # Hit an entity
        if event.collision_type != "entity":
            return

        target_id = event.target_entity_id
        if not target_id:
            return

        # Projectile hit a target - resolve the impact
        self._resolve_impact(event.entity_id, target_id, projectile)
        self.event_bus.emit(ProjectileDestroyEvent(event.entity_id, "impact"))

    def _resolve_impact(self, proj_id: int, target_id: int, projectile: Projectile) -> None:
        """
        Handle projectile impact: emit attack intent for combat system to process.
        Data (damage) comes from tags.json, not hardcoded.
        """
        # Get damage stats from tags (Principle 2: Tags are Source of Truth)
        base_damage = self.tags.get_property(projectile.weapon_tag, "BaseDamage", 1)
        damage_type = self.tags.get_property(projectile.weapon_tag, "DamageType", "Piercing")

        # Emit intent, not mutation (Principle 3: Intent, Not Mutation)
        # CombatResolverSystem will process this event and handle damage application
        self.event_bus.emit(AttackIntentEvent(
            attacker_id=projectile.shooter_id,
            target_id=target_id,
            base_damage=base_damage,
            damage_type=damage_type
        ))

    def _on_projectile_destroyed(self, event: ProjectileDestroyEvent) -> None:
        """Remove projectile entity from the world."""
        self.registry.destroy_entity(event.entity_id)

    def update(self, delta_time: float) -> None:
        """Not used. System is purely event-driven."""
        pass
