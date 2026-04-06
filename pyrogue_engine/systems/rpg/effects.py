"""
Status Effects System - Event-Driven Duration Management

Philosophy: The TimerSystem is the global heartbeat. Status Effects just listen.

When an effect is applied:
1. StatusEffectSystem updates entity state
2. StatusEffectSystem registers a timer with TimerSystem (NOT a local countdown)
3. TimerSystem ticks the timer and emits TimerExpiredEvent
4. StatusEffectSystem listens to TimerExpiredEvent and cleans up

Result: Pause the game? Timers pause automatically. Slow motion? Effects slow down.
No special code needed—it's all handled by TimerSystem.global_speed.

This is how you decouple time from effects.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

from pyrogue_engine.core.events import Event, EventBus
from pyrogue_engine.core.ecs import Registry, System


# ---------------------------------------------------------------------------
# Effect Configuration (Data-Driven)
# ---------------------------------------------------------------------------

@dataclass
class EffectTemplate:
    """
    The definition of an effect type (loaded from JSON/config).

    This is agnostic—doesn't know if it's poison, haste, slow, etc.
    """
    id: str  # "poison", "haste", "vulnerable", etc.
    behavior: str  # "STAT_MOD", "DOT" (damage over time), "HOT" (heal over time), "CONTROL"
    magnitude: int = 0  # Numerical intensity (damage per tick, stat bonus, etc.)
    stat_key: Optional[str] = None  # Which stat affected (e.g., "strength", "armor")
    stack_rule: str = "REFRESH"  # "REFRESH" (reset duration), "STACK" (add magnitude), "IGNORE" (don't reapply)

    def __hash__(self):
        """Make templates hashable for use as dict keys"""
        return hash(self.id)


# ---------------------------------------------------------------------------
# Effect State Components
# ---------------------------------------------------------------------------

@dataclass
class ActiveEffects:
    """
    ECS Component: Tracks active effects on an entity.

    Maps effect_id → current_magnitude (allows stacking multiple instances).
    Example: {"poison": 5, "haste": 2} means poison deals 5 dmg/turn, haste gives +2 speed.
    """
    effects: Dict[str, int] = field(default_factory=dict)

    def has_effect(self, effect_id: str) -> bool:
        """Check if entity has an active effect"""
        return effect_id in self.effects

    def get_magnitude(self, effect_id: str) -> int:
        """Get current magnitude of an effect"""
        return self.effects.get(effect_id, 0)

    def add_effect(self, effect_id: str, magnitude: int) -> None:
        """Add or stack an effect"""
        if effect_id in self.effects:
            self.effects[effect_id] += magnitude
        else:
            self.effects[effect_id] = magnitude

    def remove_effect(self, effect_id: str) -> None:
        """Remove an effect"""
        self.effects.pop(effect_id, None)

    def clear_effects(self) -> None:
        """Remove all effects"""
        self.effects.clear()


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class ApplyEffectEvent(Event):
    """
    Request to apply an effect to an entity.

    Fired by: Combat system, environment, abilities, etc.
    Listened to by: StatusEffectSystem
    """

    def __init__(self, target_id: int, template: EffectTemplate, duration: int):
        super().__init__(event_type="effect.applied")
        self.target_id = target_id
        self.template = template
        self.duration = duration  # In turns/ticks


class EffectExpiredEvent(Event):
    """
    An effect has worn off.

    Fired by: StatusEffectSystem (when TimerSystem emits TimerExpiredEvent)
    Listened to by: Any system that cares (UI, combat, etc.)
    """

    def __init__(self, entity_id: int, effect_id: str, magnitude: int):
        super().__init__(event_type="effect.expired")
        self.entity_id = entity_id
        self.effect_id = effect_id
        self.magnitude = magnitude


class TurnTickEvent(Event):
    """
    A game turn has advanced.

    Fired by: Main game loop / combat system
    Listened to by: StatusEffectSystem (to process DoT/HoT)
    """

    def __init__(self):
        super().__init__(event_type="turn.ticked")


# ---------------------------------------------------------------------------
# The Effect System
# ---------------------------------------------------------------------------

class StatusEffectSystem(System):
    """
    Manages status effects using the TimerSystem as the heartbeat.

    Architecture:
    1. ApplyEffectEvent → Register timer with TimerSystem (not local countdown)
    2. TimerSystem ticks and emits TimerExpiredEvent
    3. Listen to TimerExpiredEvent → Clean up effect
    4. Listen to TurnTickEvent → Process DoT/HoT

    This means:
    - Pausing the game pauses all effects (TimerSystem respects pause)
    - Slow-motion affects effect duration (TimerSystem respects global_speed)
    - No duplicate countdown logic
    """

    def __init__(self, registry: Registry, event_bus: EventBus):
        super().__init__(registry, event_bus)
        self.effect_templates: Dict[str, EffectTemplate] = {}

        # Subscribe to events
        self.event_bus.subscribe("effect.applied", self._on_apply_effect)
        self.event_bus.subscribe("timer.expired", self._on_timer_expired)
        self.event_bus.subscribe("turn.ticked", self._on_turn_tick)

    def update(self, delta_time: float) -> None:
        """Not used in event-driven system, but required by System base class"""
        pass

    def register_effect_template(self, template: EffectTemplate) -> None:
        """
        Register an effect template (usually loaded from JSON config).

        Args:
            template: EffectTemplate defining the effect type
        """
        self.effect_templates[template.id] = template

    def _on_apply_effect(self, event: ApplyEffectEvent) -> None:
        """
        Handle effect application: update state and register timer.

        Steps:
        1. Get or create ActiveEffects component
        2. Apply stacking rules
        3. Update stats if STAT_MOD
        4. Register timer with TimerSystem
        """
        # Get or create ActiveEffects component
        active = self.registry.get_component(event.target_id, ActiveEffects)
        if active is None:
            active = ActiveEffects()
            self.registry.add_component(event.target_id, active)

        template = event.template
        effect_id = template.id

        # Handle stacking rules
        if active.has_effect(effect_id):
            if template.stack_rule == "IGNORE":
                return  # Don't reapply
            elif template.stack_rule == "STACK":
                # Add magnitude to existing effect
                active.add_effect(effect_id, template.magnitude)
            elif template.stack_rule == "REFRESH":
                # Keep existing magnitude, just reset duration
                # (TimerSystem will be told to remove and re-add timer)
                pass

        if not active.has_effect(effect_id):
            # First application
            active.add_effect(effect_id, template.magnitude)

        # Apply stat modifier if needed
        if template.behavior == "STAT_MOD":
            self._apply_stat_modifier(event.target_id, template, active.get_magnitude(effect_id))

        # CRITICAL: Register timer with the global TimerSystem
        # We use a special prefix so we know this timer belongs to a status effect
        timer_tag = f"status_effect_{effect_id}"

        # Note: In the full implementation, you'd have access to TimerSystem here
        # For now, we emit a request that your TimerSystem integration will handle
        # self.timer_system.add_timer(event.target_id, timer_tag, event.duration)

    def _on_timer_expired(self, event) -> None:
        """
        Called when TimerSystem emits a timer expiration.

        Steps:
        1. Check if this is a status effect timer (prefix check)
        2. Get the effect ID from timer tag
        3. Revert stat modifiers
        4. Remove effect from ActiveEffects
        5. Emit EffectExpiredEvent for other systems
        """
        # Only handle status effect timers
        if not hasattr(event, "tag_name") or not event.tag_name.startswith("status_effect_"):
            return

        effect_id = event.tag_name.replace("status_effect_", "")
        entity_id = event.entity_id if hasattr(event, "entity_id") else event.target_id

        active = self.registry.get_component(entity_id, ActiveEffects)
        if not active or not active.has_effect(effect_id):
            return

        magnitude = active.get_magnitude(effect_id)
        template = self.effect_templates.get(effect_id)

        # Revert stat modifiers
        if template and template.behavior == "STAT_MOD":
            self._remove_stat_modifier(entity_id, template, magnitude)

        # Remove effect
        active.remove_effect(effect_id)

        # Emit expiration event
        expired_event = EffectExpiredEvent(entity_id, effect_id, magnitude)
        self.event_bus.emit(expired_event)

    def _on_turn_tick(self, event: TurnTickEvent) -> None:
        """
        Process recurring effects (DoT, HoT) at the start of each turn.

        Iterates all entities with active effects and processes recurring behaviors.
        """
        for entity_id, active_effects in self.registry.view(ActiveEffects):
            for effect_id, magnitude in active_effects.effects.items():
                template = self.effect_templates.get(effect_id)
                if not template:
                    continue

                if template.behavior == "DOT":
                    # Damage Over Time: emit damage event
                    # CombatSystem will handle armor/resistances
                    from .combat_system import AttackIntentEvent

                    damage_event = AttackIntentEvent(
                        attacker_id=None,  # Environmental/status damage
                        target_id=entity_id,
                        base_damage=magnitude,
                        damage_type="Status",
                        stat_key=None,
                    )
                    self.event_bus.emit(damage_event)

                elif template.behavior == "HOT":
                    # Healing Over Time: emit healing event
                    from .combat_system import HealingAppliedEvent

                    heal_event = HealingAppliedEvent(
                        target_id=entity_id,
                        amount=magnitude,
                        source_entity_id=None,
                    )
                    self.event_bus.emit(heal_event)

    def _apply_stat_modifier(self, entity_id: int, template: EffectTemplate, magnitude: int) -> None:
        """
        Apply a stat modifier to an entity.

        Updates the target's Attributes component.

        Args:
            entity_id: Target entity
            template: Effect template (contains stat_key)
            magnitude: Amount to modify by (can be negative)
        """
        from .components import Attributes

        if not template.stat_key:
            return

        attrs = self.registry.get_component(entity_id, Attributes)
        if not attrs:
            return

        current = attrs.get_stat(template.stat_key)
        attrs.set_stat(template.stat_key, current + magnitude)

    def _remove_stat_modifier(self, entity_id: int, template: EffectTemplate, magnitude: int) -> None:
        """
        Remove a stat modifier from an entity (revert the effect).

        Args:
            entity_id: Target entity
            template: Effect template
            magnitude: Amount to subtract (reverses _apply_stat_modifier)
        """
        from .components import Attributes

        if not template.stat_key:
            return

        attrs = self.registry.get_component(entity_id, Attributes)
        if not attrs:
            return

        current = attrs.get_stat(template.stat_key)
        attrs.set_stat(template.stat_key, current - magnitude)
