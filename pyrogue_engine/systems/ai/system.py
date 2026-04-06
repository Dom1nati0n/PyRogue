"""
AISystem - The Decision Tree Ticker

Responsible for:
1. Iterating all entities with Brain and Memory components
2. Lazy-loading Decision Trees from JSON (on first tick)
3. Calling tick() on each entity's tree
4. Caching parsed trees to avoid re-parsing

Integration with game loop:
    # In your game's main loop
    ai_system.update(delta_time)  # Called once per frame/turn

Trees are parsed once and cached, so 100 NPCs of the same type share the same
tree in memory and just pass their unique entity_id and Memory into tick().
"""

from pyrogue_engine.core.ecs import Registry, System
from pyrogue_engine.core.events import EventBus

from .components import Brain, Memory
from .decision_tree import TreeContext
from .tree_factory import TreeFactory


class AISystem(System):
    """
    Processes Decision Trees for all AI-controlled entities.

    Called once per game turn/frame.

    Usage:
        # At startup
        registry = Registry()
        event_bus = EventBus()
        factory = TreeFactory(GLOBAL_REGISTRY)
        tree_context = TreeContext(
            registry=registry,
            event_bus=event_bus,
            map_system=my_game.map_system,
            custom={"walkable_callback": my_game.is_walkable}
        )
        ai_system = AISystem(registry, event_bus, factory, tree_context)

        # In main game loop
        ai_system.update(delta_time)
    """

    def __init__(
        self,
        registry: Registry,
        event_bus: EventBus,
        tree_factory: TreeFactory,
        tree_context: TreeContext
    ):
        """
        Initialize AI system.

        Args:
            registry: ECS Registry
            event_bus: EventBus for emitting intents
            tree_factory: TreeFactory for parsing JSON trees
            tree_context: Shared context passed to all nodes (dependencies)
        """
        super().__init__(registry, event_bus)
        self.tree_factory = tree_factory
        self.tree_context = tree_context

    def update(self, delta_time: float) -> None:
        """
        Tick all AI-controlled entities.

        Iterates all entities with Brain and Memory, calls tick() on their tree.

        Args:
            delta_time: Time since last frame (unused, but required by System interface)
        """
        for entity_id, (brain, memory) in self.registry.view(Brain, Memory):
            # Lazy-load tree from JSON on first tick
            if not brain.root_node:
                brain.root_node = self.tree_factory.build_tree(
                    brain.mindset_id,
                    cache_key=brain.mindset_id
                )

            # Tick the brain
            brain.root_node.tick(entity_id, memory, self.tree_context)
