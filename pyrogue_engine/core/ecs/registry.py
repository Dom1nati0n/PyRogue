"""
Entity Component System (Registry & Logic Base)

The central database of the game. Handles the creation of Entities (IDs),
the attachment of Components (Data), and the execution of Systems (Logic).
"""

from typing import TypeVar, Type, Any, Optional, Iterator

# We use TypeVar to help Python's type checker understand that when we ask
# for a specific Component class, we get that exact class back.
C = TypeVar('C')

# ---------------------------------------------------------------------------
# The Registry (The Database)
# ---------------------------------------------------------------------------
class Registry:
    """
    The master database holding all Entities and their attached Components.
    It provides fast lookups for Systems to find exactly what they need to process.
    """
    def __init__(self) -> None:
        # The next available Entity ID. Starts at 1.
        self._next_entity_id: int = 1

        # A set to keep track of all currently "alive" entities.
        self._alive_entities: set[int] = set()

        # The core database structure.
        # It maps a Component Class -> {Entity ID -> Component Instance}
        # Example: {PositionComponent: {1: Position(x=5, y=5), 42: Position(x=10, y=2)}}
        self._components: dict[Type[Any], dict[int, Any]] = {}

    def create_entity(self) -> int:
        """
        Spawns a new, empty entity into the world.
        Returns: The unique integer ID of the new entity.
        """
        entity = self._next_entity_id
        self._next_entity_id += 1
        self._alive_entities.add(entity)
        return entity

    def destroy_entity(self, entity: int) -> None:
        """
        Completely removes an entity and all of its attached components from memory.
        Usually called when a monster dies, an item is destroyed, or a particle fades.
        """
        if entity not in self._alive_entities:
            return

        # Remove the entity's components from all component pools
        for component_pool in self._components.values():
            if entity in component_pool:
                del component_pool[entity]

        # Remove the entity from the active roster
        self._alive_entities.remove(entity)

    def add_component(self, entity: int, component: Any) -> None:
        """
        Attaches a data component (like Health or Position) to an entity.
        """
        component_type = type(component)

        # If this is the first time we've seen this type of component,
        # create a new dictionary pool for it.
        if component_type not in self._components:
            self._components[component_type] = {}

        self._components[component_type][entity] = component

    def remove_component(self, entity: int, component_type: Type[C]) -> None:
        """
        Rips a component off an entity.
        Example: Removing a 'PoisonedComponent' when a cure is taken.
        """
        if component_type in self._components and entity in self._components[component_type]:
            del self._components[component_type][entity]

    def get_component(self, entity: int, component_type: Type[C]) -> Optional[C]:
        """
        Retrieves a specific component from an entity so a System can read/modify it.
        Returns None if the entity doesn't have that component.
        """
        if component_type in self._components:
            return self._components[component_type].get(entity)
        return None

    def has_component(self, entity: int, component_type: Type[C]) -> bool:
        """
        Checks if an entity possesses a specific component.
        """
        return component_type in self._components and entity in self._components[component_type]

    def view(self, *component_types: Type[Any]) -> Iterator[tuple[int, tuple[Any, ...]]]:
        """
        The most important method in the engine. Systems use this to query the database.

        Example: registry.view(Position, Health)
        Returns: An iterator of (Entity ID, (Position Instance, Health Instance))
                 for ONLY the entities that have BOTH Position and Health.
        """
        # If no components are requested, return nothing to prevent errors.
        if not component_types:
            return

        # Find the smallest component pool to optimize the search (Data-Oriented trick)
        # It's faster to check if 5 entities with 'BossComponent' also have 'Position',
        # rather than checking if 10,000 entities with 'Position' also have 'BossComponent'.
        pools = []
        for c_type in component_types:
            if c_type not in self._components:
                return # If any requested component type doesn't exist yet, no entity can match.
            pools.append(self._components[c_type])

        # Sort pools by size (smallest first)
        pools.sort(key=len)
        smallest_pool = pools[0]

        # Check every entity in the smallest pool to see if it's in ALL the other pools
        for entity in smallest_pool.keys():
            has_all = True
            for pool in pools[1:]:
                if entity not in pool:
                    has_all = False
                    break

            # If the entity has every component requested, yield it and its data back to the System
            if has_all:
                components = tuple(self._components[c_type][entity] for c_type in component_types)
                yield entity, components

    def get_entities_at_position(self, x: int, y: int, z: int = 0) -> list[int]:
        """
        Get all entities at a specific 3D position.

        Args:
            x, y, z: 3D coordinates

        Returns:
            List of entity IDs at this position
        """
        from pyrogue_engine.systems.spatial.components import Position

        entities_at_pos = []

        if Position not in self._components:
            return entities_at_pos

        for entity, pos in self._components[Position].items():
            if pos.x == x and pos.y == y and pos.z == z:
                entities_at_pos.append(entity)

        return entities_at_pos

    def get_entities_with_tag(self, tag: str) -> list[int]:
        """
        Get all entities with a specific tag.

        Args:
            tag: Tag string to search for (e.g., "NPC.WorkerBee")

        Returns:
            List of entity IDs with this tag
        """
        from pyrogue_engine.core.tags import Tags

        entities_with_tag = []

        if Tags not in self._components:
            return entities_with_tag

        for entity, tags_component in self._components[Tags].items():
            if tag in tags_component.tags:
                entities_with_tag.append(entity)

        return entities_with_tag


# ---------------------------------------------------------------------------
# The System Base Class
# ---------------------------------------------------------------------------
class System:
    """
    The base class for all logic processors in the game.
    Systems contain NO data themselves. They only read/write data to the Registry,
    and post/listen to events via the EventBus.
    """
    def __init__(self, registry: Registry, event_bus: 'EventBus') -> None:
        self.registry = registry
        self.event_bus = event_bus

    def update(self, delta_time: float) -> None:
        """
        The main execution block for the system. Called every game tick.
        Must be overridden by child classes (e.g., MovementSystem, CombatSystem).
        """
        pass
