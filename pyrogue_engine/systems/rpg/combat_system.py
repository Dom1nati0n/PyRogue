"""
Combat System - Event-driven damage resolution and health management.

Following the Request → Validate → Dispatch pattern:
1. AttackIntentEvent fires (from action system, AI, or player input)
2. CombatResolverSystem validates preconditions
3. Runs pure combat_math to calculate damage
4. Emits DamageTakenEvent or DeathEvent
5. Game systems listen and respond (loot, exp, UI, etc.)

No tight coupling. Each system is independent.
"""

from dataclasses import dataclass
from typing import Optional

from pyrogue_engine.core.events import Event, EventBus
from pyrogue_engine.core.ecs import Registry, System
from .components import Health, Attributes, Defense, CombatStats
from .combat_math import calculate_damage


# ---------------------------------------------------------------------------
# Combat Events
# ---------------------------------------------------------------------------

class AttackIntentEvent(Event):
    """
    Intent to perform an attack.

    Fired by: Action system, AI, player input
    Listened to by: CombatResolverSystem
    """
    def __init__(
        self,
        attacker_id: int,
        target_id: int,
        base_damage: int,
        damage_type: str = "Slashing",
        stat_key: Optional[str] = None,
    ):
        super().__init__(event_type="combat.attack_intent")
        self.attacker_id = attacker_id
        self.target_id = target_id
        self.base_damage = base_damage
        self.damage_type = damage_type
        self.stat_key = stat_key  # Which stat to use for modifier (e.g., "RED" or "strength")


class DamageTakenEvent(Event):
    """
    Damage has been applied to a target's health.

    Fired by: CombatResolverSystem
    Listened to by: Any system that cares (durability, effects, UI, etc.)
    """
    def __init__(
        self,
        target_id: int,
        amount: int,
        damage_type: str = "Normal",
        source_entity_id: Optional[int] = None,
    ):
        super().__init__(event_type="combat.damage_taken")
        self.target_id = target_id
        self.amount = amount
        self.damage_type = damage_type
        self.source_entity_id = source_entity_id


class HealingAppliedEvent(Event):
    """Healing has been applied to a target."""
    def __init__(self, target_id: int, amount: int, source_entity_id: Optional[int] = None):
        super().__init__(event_type="combat.healing_applied")
        self.target_id = target_id
        self.amount = amount
        self.source_entity_id = source_entity_id


class DeathEvent(Event):
    """An entity has died (health <= 0)."""
    def __init__(self, entity_id: int, killer_id: Optional[int] = None):
        super().__init__(event_type="combat.death")
        self.entity_id = entity_id
        self.killer_id = killer_id


class AttackHitEvent(Event):
    """An attack successfully connected with a target."""
    def __init__(
        self,
        attacker_id: int,
        target_id: int,
        damage: int,
        damage_type: str = "Normal",
        is_critical: bool = False,
    ):
        super().__init__(event_type="combat.attack_hit")
        self.attacker_id = attacker_id
        self.target_id = target_id
        self.damage = damage
        self.damage_type = damage_type
        self.is_critical = is_critical


class AttackMissedEvent(Event):
    """An attack missed or was dodged."""
    def __init__(
        self,
        attacker_id: int,
        target_id: int,
        reason: str = "dodged",  # "dodged", "parried", "blocked", etc.
    ):
        super().__init__(event_type="combat.attack_missed")
        self.attacker_id = attacker_id
        self.target_id = target_id
        self.reason = reason


class CriticalHitEvent(Event):
    """A critical hit occurred."""
    def __init__(
        self,
        attacker_id: int,
        target_id: int,
        base_damage: int,
        final_damage: int,
        multiplier: float = 1.5,
    ):
        super().__init__(event_type="combat.critical_hit")
        self.attacker_id = attacker_id
        self.target_id = target_id
        self.base_damage = base_damage
        self.final_damage = final_damage
        self.multiplier = multiplier


class ActionResolvedEvent(Event):
    """An action has fully resolved (hit/miss/crit determined, damage applied)."""
    def __init__(
        self,
        actor_id: int,
        action_key: str,
        target_id: int,
        success: bool,
        outcome: str = "hit",  # "hit", "miss", "dodged", "blocked"
    ):
        super().__init__(event_type="combat.action_resolved")
        self.actor_id = actor_id
        self.action_key = action_key
        self.target_id = target_id
        self.success = success
        self.outcome = outcome


class CombatStartedEvent(Event):
    """Combat has started (initiative rolled, participants gathered)."""
    def __init__(self, combatant_ids: list):
        super().__init__(event_type="combat.started")
        self.combatant_ids = combatant_ids


class CombatEndedEvent(Event):
    """Combat has ended (one side eliminated or other condition)."""
    def __init__(self, survivors: list, defeated: list, reason: str = "eliminated"):
        super().__init__(event_type="combat.ended")
        self.survivors = survivors
        self.defeated = defeated
        self.reason = reason


class TurnStartedEvent(Event):
    """A combatant's turn has begun."""
    def __init__(self, actor_id: int, round_number: int, turn_in_round: int):
        super().__init__(event_type="combat.turn_started")
        self.actor_id = actor_id
        self.round_number = round_number
        self.turn_in_round = turn_in_round


class TurnEndedEvent(Event):
    """A combatant's turn has ended."""
    def __init__(self, actor_id: int, round_number: int, actions_taken: int):
        super().__init__(event_type="combat.turn_ended")
        self.actor_id = actor_id
        self.round_number = round_number
        self.actions_taken = actions_taken


# ---------------------------------------------------------------------------
# Combat System
# ---------------------------------------------------------------------------

class CombatResolverSystem(System):
    """
    Listens for AttackIntentEvents, calculates damage, applies it, and emits results.

    Pure event-driven: no state mutations except on the target's Health component.
    All side effects (loot, exp, effects) are triggered by emitted events.
    """

    def __init__(self, registry: Registry, event_bus: EventBus):
        super().__init__(registry, event_bus)

        # Subscribe to attack intents
        self.event_bus.subscribe("combat.attack_intent", self._on_attack_intent)
        self.event_bus.subscribe("combat.healing_applied", self._on_healing)

    def update(self, delta_time: float) -> None:
        """Not used for event-driven system, but required by System base class"""
        pass

    def _on_attack_intent(self, event: AttackIntentEvent) -> None:
        """
        Handle an attack intent: validate, calculate damage, apply it, emit result.

        Event flow:
        1. Calculate damage roll (includes dodge/crit checks)
        2. If dodged: emit AttackMissedEvent, return
        3. If hit: apply damage, emit AttackHitEvent
        4. If critical: emit CriticalHitEvent
        5. If dead: emit DeathEvent
        """
        # Validate target exists and is alive
        target_health = self.registry.get_component(event.target_id, Health)
        if not target_health or target_health.is_dead():
            return

        # Get attacker's attributes to extract stat modifier
        attacker_attrs = self.registry.get_component(event.attacker_id, Attributes)
        stat_modifier = 0
        if attacker_attrs and event.stat_key:
            stat_modifier = attacker_attrs.get_modifier(event.stat_key)

        # Get target's defense/armor and dodge
        target_defense = self.registry.get_component(event.target_id, Defense)
        armor_value = target_defense.armor_value if target_defense else 0
        dodge_chance = target_defense.dodge_chance if target_defense else 0.0

        # Run pure combat math (deterministic, testable)
        damage_roll = calculate_damage(
            event.base_damage,
            stat_modifier=stat_modifier,
            armor_value=armor_value,
            damage_type=event.damage_type,
            dodge_chance=dodge_chance,
        )

        # Handle dodge
        if damage_roll.dodged:
            miss_event = AttackMissedEvent(
                attacker_id=event.attacker_id,
                target_id=event.target_id,
                reason="dodged",
            )
            self.event_bus.emit(miss_event)

            # Update attacker's combat stats (tracked attempt)
            attacker_stats = self.registry.get_component(event.attacker_id, CombatStats)
            if attacker_stats:
                attacker_stats.times_acted += 1
            return

        # Apply damage to health
        actual_damage = target_health.take_damage(damage_roll.final_damage)

        # Emit hit event
        hit_event = AttackHitEvent(
            attacker_id=event.attacker_id,
            target_id=event.target_id,
            damage=actual_damage,
            damage_type=event.damage_type,
            is_critical=damage_roll.critical,
        )
        self.event_bus.emit(hit_event)

        # Emit critical hit event if applicable
        if damage_roll.critical:
            crit_event = CriticalHitEvent(
                attacker_id=event.attacker_id,
                target_id=event.target_id,
                base_damage=damage_roll.base_damage,
                final_damage=actual_damage,
                multiplier=1.5,
            )
            self.event_bus.emit(crit_event)

        # Emit legacy damage event for backwards compatibility
        damage_event = DamageTakenEvent(
            target_id=event.target_id,
            amount=actual_damage,
            damage_type=event.damage_type,
            source_entity_id=event.attacker_id,
        )
        self.event_bus.emit(damage_event)

        # Update attacker's combat stats
        attacker_stats = self.registry.get_component(event.attacker_id, CombatStats)
        if attacker_stats:
            attacker_stats.damage_dealt += actual_damage
            attacker_stats.times_acted += 1

        # Update target's combat stats
        target_stats = self.registry.get_component(event.target_id, CombatStats)
        if target_stats:
            target_stats.damage_taken += actual_damage

        # Check for death
        if target_health.is_dead():
            death_event = DeathEvent(
                entity_id=event.target_id,
                killer_id=event.attacker_id,
            )
            self.event_bus.emit(death_event)

            # Update killer's stats
            if attacker_stats:
                attacker_stats.kills += 1

    def _on_healing(self, event: HealingAppliedEvent) -> None:
        """
        Handle healing event: apply to health, emit result.
        """
        target_health = self.registry.get_component(event.target_id, Health)
        if not target_health:
            return

        actual_healing = target_health.heal(event.amount)

        # Emit healing applied event (for logging, UI, effects, etc.)
        self.event_bus.emit(
            HealingAppliedEvent(
                target_id=event.target_id,
                amount=actual_healing,
                source_entity_id=event.source_entity_id,
            )
        )


class InitiativeSystem(System):
    """
    Turn-based initiative: roll at combat start, determine turn order.

    Emits: CombatStartedEvent, TurnStartedEvent, TurnEndedEvent
    """

    def __init__(self, registry: Registry, event_bus: EventBus):
        super().__init__(registry, event_bus)
        self.turn_order = []
        self.current_turn_index = 0
        self.round_number = 0
        self.active = False

    def update(self, delta_time: float) -> None:
        pass

    def roll_initiative(self, entity_ids: list, agility_stat_key: str = "agility") -> list:
        """
        Roll initiative for all entities in combat, emit CombatStartedEvent.

        Args:
            entity_ids: List of entity IDs entering combat
            agility_stat_key: Which stat to use for initiative modifier

        Returns:
            Sorted list of (entity_id, initiative_roll) tuples
        """
        import random

        initiatives = []
        for entity_id in entity_ids:
            attrs = self.registry.get_component(entity_id, Attributes)
            mod = attrs.get_modifier(agility_stat_key) if attrs else 0
            roll = random.randint(1, 8) + mod
            initiatives.append((entity_id, roll))

        # Sort by roll (highest first)
        self.turn_order = sorted(initiatives, key=lambda x: x[1], reverse=True)
        self.current_turn_index = 0
        self.round_number = 1
        self.active = True

        # Emit combat started event
        self.event_bus.emit(CombatStartedEvent(combatant_ids=entity_ids))

        # Emit first turn started
        if self.turn_order:
            self.event_bus.emit(
                TurnStartedEvent(
                    actor_id=self.turn_order[0][0],
                    round_number=self.round_number,
                    turn_in_round=1,
                )
            )

        return self.turn_order

    def get_current_actor(self) -> Optional[int]:
        """Get the entity ID of who's turn it is"""
        if self.current_turn_index >= len(self.turn_order):
            return None
        return self.turn_order[self.current_turn_index][0]

    def advance_turn(self) -> bool:
        """Move to next actor's turn. Emits TurnEndedEvent and TurnStartedEvent."""
        current_actor = self.get_current_actor()

        # Emit turn ended for current actor
        if current_actor is not None:
            self.event_bus.emit(
                TurnEndedEvent(
                    actor_id=current_actor,
                    round_number=self.round_number,
                    actions_taken=0,  # Could track from CombatStats if needed
                )
            )

        self.current_turn_index += 1

        # Check if we need to start a new round
        if self.current_turn_index >= len(self.turn_order):
            self.current_turn_index = 0
            self.round_number += 1

        # Emit turn started for next actor
        next_actor = self.get_current_actor()
        if next_actor is not None:
            turn_in_round = self.current_turn_index + 1
            self.event_bus.emit(
                TurnStartedEvent(
                    actor_id=next_actor,
                    round_number=self.round_number,
                    turn_in_round=turn_in_round,
                )
            )

        return self.current_turn_index < len(self.turn_order) or self.round_number == 1

    def end_combat(self, survivors: list, defeated: list, reason: str = "eliminated") -> None:
        """End combat and emit CombatEndedEvent."""
        self.active = False
        self.event_bus.emit(CombatEndedEvent(survivors=survivors, defeated=defeated, reason=reason))
