"""
AP Regeneration System - Regenerates ActionPoints based on world ticks.

ONLY used in Live Stepping gameplay mode.

Listens to world.tick events and increments entity AP based on configured rate.
Works in conjunction with GameplayController to enable real-time AP-based action system.
"""

from pyrogue_engine.core.events import Event, EventBus
from pyrogue_engine.core.ecs import Registry, System
from .components import ActionPoints


class APRegenerationSystem(System):
    """
    Regenerates ActionPoints for all entities on each world tick.

    Configuration:
    - ap_per_tick: How much AP to gain per world tick (default 1.0)
    - world_tick_rate: Ticks per second (set by GameplayController)

    At 1.0 t/s with 1.0 ap_per_tick: entities gain 1 AP per second
    At 10.0 t/s with 1.0 ap_per_tick: entities gain 10 AP per second

    Entity ActionPoints components are modified directly.
    """

    def __init__(self, registry: Registry, event_bus: EventBus, ap_per_tick: float = 1.0):
        """
        Initialize AP regeneration system.

        Args:
            registry: ECS registry
            event_bus: Event bus for listening to world ticks
            ap_per_tick: AP gained per world tick (default 1.0)
        """
        self.registry = registry
        self.event_bus = event_bus
        self.ap_per_tick = ap_per_tick

        # Listen for world ticks (only in Live Stepping mode)
        self.event_bus.subscribe("world.tick", self._on_world_tick)

    def _on_world_tick(self, event: Event):
        """Called on each world tick. Regenerate AP for all entities."""
        # Query all entities with ActionPoints component
        entities_with_ap = self.registry.get_entities_with(ActionPoints)

        for entity_id in entities_with_ap:
            ap = self.registry.get_component(entity_id, ActionPoints)
            if ap:
                # Regenerate AP but don't exceed maximum
                ap.current = min(ap.current + self.ap_per_tick, ap.maximum)

    def set_ap_per_tick(self, amount: float):
        """Adjust AP regeneration rate"""
        self.ap_per_tick = max(0.0, amount)
