"""
Gameplay Mode System - Turn-Based, Simultaneous, Live Stepping

Controls WHEN actions reach ActionResolver, not HOW they're resolved.
Server-side configuration for game speed and pacing.

Three modes:

1. Turn-Based (Traditional)
   - Only current actor can act. Sequential queue.
   - NOT affected by world tick rate.
   - Advances on explicit action completion.

2. Simultaneous (Traditional)
   - All players plan, resolve together on timer or ready.
   - NOT affected by world tick rate.
   - Phase-based (plan phase, resolution phase).

3. Live Stepping (Auto-Stepping)
   - Real-time with world tick rate controlling game speed.
   - AP regenerates based on world ticks, not on turn completion.
   - Act when energy available (if AP >= action cost).

World tick rate (0.01 to 1000.0 t/s) ONLY affects Live Stepping mode.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum

from pyrogue_engine.core.events import Event, EventBus
from pyrogue_engine.core.ecs import Registry, Component
from pyrogue_engine.systems.rpg.components import ActionPoints


class GameplayMode(Enum):
    TURN_BASED = "turn_based"
    SIMULTANEOUS = "simultaneous"
    LIVE_STEPPING = "live_stepping"


class WorldTickRate:
    """
    Configures world tick rate (ticks per second).

    Controls how frequently world.tick events are emitted.
    Default: 1.0 t/s (one tick per second)
    Range: 0.01 to 1000.0 t/s

    Entity energy components are unaffected by tick rate.
    """

    MIN_RATE = 0.01
    MAX_RATE = 1000.0
    DEFAULT_RATE = 1.0

    def __init__(self, ticks_per_second: float = DEFAULT_RATE):
        self.ticks_per_second = self._clamp(ticks_per_second)

    def _clamp(self, value: float) -> float:
        """Clamp value to valid range with 2 decimal precision"""
        clamped = max(self.MIN_RATE, min(self.MAX_RATE, value))
        # Round to 2 decimal places
        return round(clamped, 2)

    def set_rate(self, ticks_per_second: float):
        """Set world tick rate"""
        self.ticks_per_second = self._clamp(ticks_per_second)

    def get_tick_interval_ms(self) -> float:
        """Get milliseconds per tick"""
        return 1000.0 / self.ticks_per_second

    def __str__(self) -> str:
        return f"{self.ticks_per_second} t/s"


@dataclass
class InitiativeQueue(Component):
    """Turn-Based mode: tracks whose turn it is"""
    actors: List[int] = field(default_factory=list)
    current_index: int = 0

    @property
    def current_actor(self) -> Optional[int]:
        if not self.actors or self.current_index >= len(self.actors):
            return None
        return self.actors[self.current_index]

    def advance(self) -> Optional[int]:
        """Move to next actor, wrapping around. Returns new current actor."""
        if not self.actors:
            return None
        self.current_index = (self.current_index + 1) % len(self.actors)
        return self.current_actor

    def add_actor(self, entity_id: int):
        """Add actor to turn queue"""
        if entity_id not in self.actors:
            self.actors.append(entity_id)

    def remove_actor(self, entity_id: int):
        """Remove actor from turn queue"""
        if entity_id in self.actors:
            idx = self.actors.index(entity_id)
            self.actors.remove(entity_id)
            # Adjust current_index if needed
            if idx < self.current_index:
                self.current_index -= 1
            elif self.current_index >= len(self.actors):
                self.current_index = 0


@dataclass
class ActionBuffer(Component):
    """Simultaneous mode: stores actions until resolution phase"""
    buffered_actions: Dict[int, Event] = field(default_factory=dict)
    ready_players: Set[int] = field(default_factory=set)
    total_players: int = 0

    def buffer_action(self, entity_id: int, action_event: Event):
        """Store player's action for batch resolution"""
        self.buffered_actions[entity_id] = action_event

    def mark_ready(self, entity_id: int):
        """Mark player as ready"""
        self.ready_players.add(entity_id)

    def is_all_ready(self) -> bool:
        """Check if all players are ready"""
        return len(self.ready_players) == self.total_players and self.total_players > 0

    def clear(self):
        """Clear buffer and ready status"""
        self.buffered_actions.clear()
        self.ready_players.clear()


@dataclass
class EnergySystem(Component):
    """Live Stepping mode: queries entity ActionPoints component

    Speed multiplier controls TimerSystem tick rate, not energy values.
    Entity energy components are unchanged.
    """
    tracked_actors: Set[int] = field(default_factory=set)

    def add_actor(self, entity_id: int):
        """Register actor for tracking"""
        self.tracked_actors.add(entity_id)

    def remove_actor(self, entity_id: int):
        """Unregister actor"""
        self.tracked_actors.discard(entity_id)

    def can_act(self, registry: Registry, entity_id: int, action_cost: float) -> bool:
        """Check if entity has enough AP (queries ActionPoints component)"""
        ap_component = registry.get_component(entity_id, ActionPoints)
        if not ap_component:
            return False
        return ap_component.current >= action_cost

    def deduct_energy(self, registry: Registry, entity_id: int, cost: float) -> bool:
        """Deduct AP from entity"""
        ap_component = registry.get_component(entity_id, ActionPoints)
        if not ap_component:
            return False
        if ap_component.current >= cost:
            ap_component.current -= cost
            return True
        return False


class GameplayModeConfig:
    """Server-side gameplay configuration"""

    def __init__(self, mode: GameplayMode, world_tick_rate: float = 1.0):
        self.mode = mode
        self.world_tick_rate = WorldTickRate(world_tick_rate)

    def set_world_tick_rate(self, ticks_per_second: float):
        """
        Change world tick rate at runtime.

        Args:
            ticks_per_second: Ticks per second (0.01 to 1000.0)
        """
        self.world_tick_rate.set_rate(ticks_per_second)

    def set_mode(self, mode: GameplayMode):
        """Switch gameplay mode at runtime"""
        self.mode = mode


class TurnBasedValidator:
    """Gatekeeper for Turn-Based mode"""

    def __init__(self, registry: Registry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus
        self.initiative_queue = None

    def init_queue(self, actor_ids: List[int]):
        """Initialize turn queue with actors sorted by initiative"""
        self.initiative_queue = InitiativeQueue(actors=actor_ids, current_index=0)

    def can_act(self, entity_id: int) -> bool:
        """Check if entity is current actor"""
        if not self.initiative_queue:
            return True
        return entity_id == self.initiative_queue.current_actor

    def on_action_completed(self):
        """Advance turn after action completes"""
        if self.initiative_queue:
            next_actor = self.initiative_queue.advance()
            self.event_bus.emit(Event("turn.changed", actor_id=next_actor))

    def add_actor(self, entity_id: int):
        """Add actor to turn queue"""
        if self.initiative_queue:
            self.initiative_queue.add_actor(entity_id)

    def remove_actor(self, entity_id: int):
        """Remove actor from turn queue"""
        if self.initiative_queue:
            self.initiative_queue.remove_actor(entity_id)


class SimultaneousValidator:
    """Gatekeeper for Simultaneous mode"""

    def __init__(self, registry: Registry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus
        self.action_buffer = ActionBuffer()
        self.resolution_pending = False

        # Listen for resolution triggers
        self.event_bus.subscribe("phase.ready_check", self._on_ready_check)
        self.event_bus.subscribe("timer.phase_expired", self._on_phase_timeout)

    def can_buffer_action(self, entity_id: int) -> bool:
        """Always allow buffering in simultaneous mode"""
        return True

    def buffer_action(self, entity_id: int, action_event: Event):
        """Store action instead of executing immediately"""
        self.action_buffer.buffer_action(entity_id, action_event)

    def mark_player_ready(self, entity_id: int):
        """Mark player as ready"""
        self.action_buffer.mark_ready(entity_id)

        # Check if all ready
        if self.action_buffer.is_all_ready():
            self._resolve_phase()

    def _on_ready_check(self, event: Event):
        """Called by game phase system"""
        self.mark_player_ready(event.entity_id)

    def _on_phase_timeout(self, event: Event):
        """Called by TimerSystem if timer expires"""
        self._resolve_phase()

    def _resolve_phase(self):
        """Resolve all buffered actions"""
        if self.resolution_pending:
            return

        self.resolution_pending = True

        # Emit all buffered actions in order
        for entity_id, action_event in self.action_buffer.buffered_actions.items():
            self.event_bus.emit(action_event)

        # Clear for next phase
        self.action_buffer.clear()
        self.resolution_pending = False

        # Start new phase
        self.event_bus.emit(Event("phase.started"))


class LiveSteppingValidator:
    """
    Gatekeeper for Live Stepping mode (Auto-Stepping).

    ONLY this mode is affected by world tick rate.

    Queries entity ActionPoints components. World tick rate controls how frequently
    entity AP regenerates (via separate APRegenerationSystem listening to world.tick events).
    Entity components are never modified directly.
    """

    def __init__(self, registry: Registry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus
        self.energy_system = EnergySystem()

    def can_act(self, entity_id: int, action_cost: float) -> bool:
        """Check if entity has enough AP to perform action"""
        return self.energy_system.can_act(self.registry, entity_id, action_cost)

    def execute_action(self, entity_id: int, action_cost: float) -> bool:
        """Deduct AP cost from entity if sufficient"""
        return self.energy_system.deduct_energy(self.registry, entity_id, action_cost)

    def add_actor(self, entity_id: int):
        """Register actor for tracking"""
        self.energy_system.add_actor(entity_id)

    def remove_actor(self, entity_id: int):
        """Unregister actor"""
        self.energy_system.remove_actor(entity_id)


class GameplayController:
    """Manages gameplay mode and world tick rate configuration"""

    def __init__(self, registry: Registry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus
        self.config = GameplayModeConfig(GameplayMode.TURN_BASED, world_tick_rate=1.0)

        # Initialize validators for all modes
        self.turn_based = TurnBasedValidator(registry, event_bus)
        self.simultaneous = SimultaneousValidator(registry, event_bus)
        self.live_stepping = LiveSteppingValidator(registry, event_bus)

        self.event_bus.subscribe("action.requested", self._on_action_requested)
        self.event_bus.subscribe("action.completed", self._on_action_completed)

    def set_mode(self, mode: GameplayMode):
        """Switch gameplay mode at runtime"""
        self.config.set_mode(mode)
        self.event_bus.emit(Event("gameplay.mode_changed", mode=mode.value))

    def set_world_tick_rate(self, ticks_per_second: float):
        """
        Change world tick rate (ticks per second).

        Controls how frequently world.tick events are emitted.
        Entity energy components are unaffected.

        Args:
            ticks_per_second: Rate from 0.01 to 1000.0 t/s
                0.5 = half speed
                1.0 = normal (default)
                10.0 = 10x speed
                100.0 = very fast
        """
        old_rate = self.config.world_tick_rate.ticks_per_second
        self.config.set_world_tick_rate(ticks_per_second)
        new_rate = self.config.world_tick_rate.ticks_per_second

        if old_rate != new_rate:
            self.event_bus.emit(Event(
                "world.tick_rate_changed",
                ticks_per_second=new_rate,
                interval_ms=self.config.world_tick_rate.get_tick_interval_ms()
            ))

    def _on_action_requested(self, event: Event):
        """Validate action based on current mode"""
        entity_id = event.actor_id
        action_cost = event.ap_cost or 100  # Default cost

        if self.config.mode == GameplayMode.TURN_BASED:
            if self.turn_based.can_act(entity_id):
                self.event_bus.emit(Event("action.validated", actor_id=entity_id))
            else:
                self.event_bus.emit(Event("action.blocked", actor_id=entity_id, reason="not_your_turn"))

        elif self.config.mode == GameplayMode.SIMULTANEOUS:
            if self.simultaneous.can_buffer_action(entity_id):
                self.simultaneous.buffer_action(entity_id, event)
                self.event_bus.emit(Event("action.buffered", actor_id=entity_id))

        elif self.config.mode == GameplayMode.LIVE_STEPPING:
            if self.live_stepping.can_act(entity_id, action_cost):
                if self.live_stepping.execute_action(entity_id, action_cost):
                    self.event_bus.emit(Event("action.validated", actor_id=entity_id))
                else:
                    self.event_bus.emit(Event("action.blocked", actor_id=entity_id, reason="insufficient_energy"))
            else:
                self.event_bus.emit(Event("action.blocked", actor_id=entity_id, reason="insufficient_energy"))

    def _on_action_completed(self, event: Event):
        """Update mode state after action"""
        if self.config.mode == GameplayMode.TURN_BASED:
            self.turn_based.on_action_completed()
