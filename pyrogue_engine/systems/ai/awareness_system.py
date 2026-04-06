"""
AwarenessSystem - The Sensory & Threat Pipeline

Runs BEFORE the AISystem each turn. Bridges the gap between:
- Phase 1 (FOV): What can this entity see?
- Phase 6 (Perception): What threats are visible?
- Phase 5 (Cognition): What should this entity do about it?

Pipeline:
1. For each entity with Vision, Memory, Faction, Position
2. Get visible tiles from Vision component (from FOV system, Phase 1)
3. Query spatial map for entities in visible tiles
4. Evaluate each visible entity using FactionRegistry and threat math
5. Write target_id to Memory (picked up by Decision Tree)
6. Update ScentMemory with last known position

Result: Decision Tree has target_id in Memory, can execute attack/chase logic.
"""

from pyrogue_engine.core.ecs import Registry, System
from pyrogue_engine.core.events import EventBus

from pyrogue_engine.systems.spatial.components import Position, Vision
from pyrogue_engine.systems.rpg.components import Health

from .components import Memory, Faction, ScentMemory
from .factions import FactionRegistry
from .threat_math import (
    calculate_distance,
    calculate_threat_score,
    select_highest_threat,
    ThreatScore,
)


class AwarenessSystem(System):
    """
    Evaluates visible entities and updates Memory with threat information.

    This system acts as the NPC's sensory input. It:
    1. Reads what the entity can see (Vision.visible_tiles from Phase 1)
    2. Finds entities on visible tiles (via spatial query)
    3. Evaluates threat using FactionRegistry
    4. Writes results to Memory (input to Phase 5 Decision Tree)

    Usage:
        registry = Registry()
        event_bus = EventBus()

        faction_registry = FactionRegistry()
        faction_registry.set_hostile("goblin", "player")
        faction_registry.set_hostile("undead", ["human", "elf", "goblin"])

        # Spatial query function: returns entity IDs on specific tiles
        def get_entities_on_tiles(visible_tiles):
            results = []
            for x, y in visible_tiles:
                entities = spatial_map.get_entities_at(x, y)
                results.extend(entities)
            return results

        awareness_system = AwarenessSystem(
            registry,
            event_bus,
            faction_registry,
            spatial_query_fn=get_entities_on_tiles
        )

        # In main game loop, call BEFORE AISystem
        awareness_system.update(delta_time)
        ai_system.update(delta_time)
    """

    def __init__(
        self,
        registry: Registry,
        event_bus: EventBus,
        faction_registry: FactionRegistry,
        spatial_query_fn=None
    ):
        """
        Initialize Awareness System.

        Args:
            registry: ECS Registry
            event_bus: EventBus for publishing events (optional)
            faction_registry: FactionRegistry defining hostilities
            spatial_query_fn: Function(visible_tiles) -> List[entity_ids]
                             If None, uses O(N) fallback of checking all entities
        """
        super().__init__(registry, event_bus)
        self.faction_registry = faction_registry
        self.spatial_query_fn = spatial_query_fn

    def update(self, delta_time: float) -> None:
        """
        Process awareness for all entities with Vision and Memory.

        Call this BEFORE AISystem each turn.

        Args:
            delta_time: Time since last frame (unused, but required by System interface)
        """
        # Find entities with Vision, Memory, Faction
        for entity_id, (vision, memory, my_faction, my_pos) in self.registry.view(
            Vision, Memory, Faction, Position
        ):
            self._evaluate_threats(entity_id, vision, memory, my_faction, my_pos)
            self._update_scent_memory(entity_id, memory)

    def _evaluate_threats(
        self,
        entity_id: int,
        vision: Vision,
        memory: Memory,
        my_faction: Faction,
        my_pos: Position
    ) -> None:
        """
        Scan visible tiles, evaluate threats, update Memory.

        Args:
            entity_id: This entity
            vision: Vision component (contains visible_tiles)
            memory: Memory component (to be updated)
            my_faction: This entity's faction
            my_pos: This entity's position
        """
        # Step 1: Get entities on visible tiles
        visible_entities = self._get_visible_entities(vision.visible_tiles if hasattr(vision, 'visible_tiles') else set())

        # Step 2: Evaluate each visible entity
        threats: list[ThreatScore] = []

        for other_id in visible_entities:
            if other_id == entity_id:
                continue

            threat = self._evaluate_single_entity(
                entity_id=other_id,
                my_faction=my_faction,
                my_pos=my_pos,
                memory=memory
            )

            if threat and threat.score > 0:
                threats.append(threat)

        # Step 3: Pick highest threat
        if threats:
            best_threat = select_highest_threat(threats)
            if best_threat:
                memory.set("target_id", best_threat.entity_id)
                # Store position so Decision Tree can access it
                other_pos = self.registry.get_component(best_threat.entity_id, Position)
                if other_pos:
                    memory.set("target_position", (other_pos.x, other_pos.y))
                memory.set("threat_score", best_threat.score)
                memory.set("target_distance", best_threat.distance)
        else:
            # No threats visible
            memory.data.pop("target_id", None)
            memory.data.pop("threat_score", None)

    def _evaluate_single_entity(
        self,
        entity_id: int,
        my_faction: Faction,
        my_pos: Position,
        memory: Memory
    ) -> ThreatScore | None:
        """
        Evaluate a single visible entity for threat.

        Returns None if not a threat, or ThreatScore if hostile.

        Args:
            entity_id: Entity to evaluate
            my_faction: My faction (for hostility check)
            my_pos: My position (for distance calc)
            memory: My memory (for aggro status)

        Returns:
            ThreatScore or None
        """
        # Get their faction
        their_faction = self.registry.get_component(entity_id, Faction)
        if not their_faction:
            return None  # No faction = not a threat

        # Check hostility
        if not self.faction_registry.should_attack(my_faction.name, their_faction.name):
            return None  # Not hostile

        # Get their position
        their_pos = self.registry.get_component(entity_id, Position)
        if not their_pos:
            return None

        # Calculate distance
        distance = calculate_distance(my_pos.x, my_pos.y, their_pos.x, their_pos.y)

        # Get their health
        health = self.registry.get_component(entity_id, Health)
        health_percent = (health.current / health.maximum) if health and health.maximum > 0 else 1.0

        # Check if already in combat with this target
        current_target = memory.get("target_id")
        is_aggroed = (current_target == entity_id)

        # Calculate threat score
        threat = calculate_threat_score(
            entity_id=entity_id,
            distance=distance,
            base_threat=10.0,  # Could read from entity's CombatStats
            health_percent=health_percent,
            is_aggroed=is_aggroed
        )

        return threat

    def _get_visible_entities(self, visible_tiles: set) -> list[int]:
        """
        Get entity IDs standing on visible tiles.

        Uses spatial_query_fn if provided (O(visible_tiles)),
        otherwise falls back to O(N) scan of all entities.

        Args:
            visible_tiles: Set of (x, y) tuples from Vision component

        Returns:
            List of entity IDs on visible tiles
        """
        if self.spatial_query_fn:
            # Fast path: O(visible_tiles) if spatial indexing available
            return self.spatial_query_fn(visible_tiles)

        # Fallback: O(N) scan
        # Check all entities, see if any are on visible tiles
        visible_entities = []
        for entity_id, pos in self.registry.view(Position):
            if (pos.x, pos.y) in visible_tiles:
                visible_entities.append(entity_id)
        return visible_entities

    def _update_scent_memory(self, entity_id: int, memory: Memory) -> None:
        """
        Update ScentMemory: age it, clear if stale, update if target spotted.

        This enables out-of-sight pursuit: even if we lose sight of the target,
        we remember where they went and can search there.

        Args:
            entity_id: This entity
            memory: This entity's memory
        """
        scent = self.registry.get_component(entity_id, ScentMemory)
        if not scent:
            return

        # Age the scent
        scent.age(tick_delta=1)

        # If scent is too old, forget it
        if not scent.is_fresh():
            scent.clear()

        # If we have a target, update the scent
        target_pos = memory.get("target_position")
        if target_pos:
            scent.update_position(target_pos[0], target_pos[1])
