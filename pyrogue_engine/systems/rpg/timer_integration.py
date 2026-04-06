"""
Timer System Integration - Connecting StatusEffects to the global heartbeat

This module shows how to integrate StatusEffectSystem with your game's TimerSystem.
The TimerSystem is THE source of truth for all duration-based mechanics.

Key principle: Status effects don't count down timers themselves.
They register timers with TimerSystem and listen for expiration.
"""

from pyrogue_engine.core.ecs import Registry, System
from pyrogue_engine.core.events import EventBus, Event
from .effects import StatusEffectSystem, TurnTickEvent


class TimerAdapter(System):
    """
    Glue layer between pyrogue_engine and your TimerSystem.

    Your game's TimerSystem already exists and manages durations.
    This adapter makes it broadcast events that pyrogue_engine expects.

    Usage in your game:
        timer_system = YourTimerSystem(dispatcher)
        adapter = TimerAdapter(timer_system, event_bus)

        # Now when your timer_system emits TimerExpiredEvent,
        # it automatically gets converted and re-emitted on the EventBus
    """

    def __init__(self, game_timer_system, event_bus: EventBus):
        """
        Args:
            game_timer_system: Your game's TimerSystem instance
            event_bus: pyrogue_engine EventBus
        """
        self.timer_system = game_timer_system
        self.event_bus = event_bus

        # Listen to your game's dispatcher for timer events
        # (You'll need to hook this up to your EventDispatcher)
        # game_timer_system.dispatcher.subscribe(TimerExpiredEvent, self._on_timer_expired)

    def _on_timer_expired(self, event) -> None:
        """
        Receive timer expiration from your game's TimerSystem.
        Re-emit as pyrogue_engine event so StatusEffectSystem can hear it.
        """
        # Your game's TimerExpiredEvent → pyrogue_engine Event
        re_emitted = Event(event_type="timer.expired")
        re_emitted.tag_name = event.tag_name
        re_emitted.entity_id = event.entity_id
        re_emitted.target_id = event.entity_id  # Support both naming conventions

        self.event_bus.emit(re_emitted)

    def update(self, delta_time: float) -> None:
        """Not used in adapter pattern"""
        pass


class GameLoopIntegration:
    """
    How to integrate Status Effects into your main game loop.

    This shows the sequence of events that keeps everything synchronized.
    """

    def __init__(self, registry: Registry, event_bus: EventBus, timer_system):
        """
        Args:
            registry: pyrogue_engine Registry
            event_bus: pyrogue_engine EventBus
            timer_system: Your game's TimerSystem
        """
        self.registry = registry
        self.event_bus = event_bus
        self.timer_system = timer_system
        self.effects_system = StatusEffectSystem(registry, event_bus)

    def game_loop_tick(self, dt: float) -> None:
        """
        Main game loop sequence (pseudocode).

        Order matters! Timers must tick before effects process expiration.
        """
        # 1. INPUT - Handle player/AI actions
        # (not shown here)

        # 2. TIMERS - The global heartbeat
        self.timer_system.process(dt)
        # This emits TimerExpiredEvent to the game's dispatcher

        # 3. EVENTS - Process all events fired by timers
        # (your event dispatcher processes and re-emits to EventBus)

        # 4. SYSTEMS - Systems react to events
        # StatusEffectSystem already listening to TimerExpiredEvent

        # 5. TURN TICK - Notify effects that a turn has advanced
        turn_tick = TurnTickEvent()
        self.event_bus.emit(turn_tick)
        # StatusEffectSystem processes DoT/HoT

        # 6. RENDER - Update UI/visuals
        # (not shown here)

    def apply_effect(self, target_id: int, effect_id: str, duration: int) -> None:
        """
        Helper: Apply an effect through the system.

        Args:
            target_id: Entity to affect
            effect_id: Effect template ID (e.g., "poison", "haste")
            duration: Duration in turns
        """
        # Get template from registry
        template = self.effects_system.effect_templates.get(effect_id)
        if not template:
            raise ValueError(f"Unknown effect: {effect_id}")

        # Fire the apply event
        from .effects import ApplyEffectEvent

        event = ApplyEffectEvent(target_id, template, duration)
        self.event_bus.emit(event)

        # Register timer with your TimerSystem
        timer_tag = f"status_effect_{effect_id}"
        self.timer_system.add_timer(target_id, timer_tag, duration)
