"""
Construction System - 3D-Aware Physics Arbiter

The Agent-Based Generation system (Bee Agents) is purely intent-driven.
This system acts as the Physics Arbiter—it listens to map manipulation intents
and validates them against the World Fabric rules:

1. Spawn Safety: No builds within safe_radius of spawn point
2. Surface Height: No floating tiles (more than 5 units above natural surface)
3. Ocean Height: Destroyed tiles below sea_level become water
4. Blueprint Grid: Updates 3D grid for pathfinding and AI awareness

Event Flow:
    Bee emits map.build.intent or map.destroy.intent
    ConstructionSystem validates against world rules
    ConstructionSystem mutates ECS and emits map.build.resolved or map.destroy.resolved
    NetworkSystem picks up the .resolved events and sends Delta Syncs to clients
"""

from pyrogue_engine.core.ecs import System
from pyrogue_engine.core.events import Event
from pyrogue_engine.systems.spatial.components import Position, Tags


class ConstructionSystem(System):
    """
    3D-Aware construction validator and executor.

    Subscribes to:
    - map.build.intent: Create a new tile at a 3D position
    - map.destroy.intent: Destroy a tile at a 3D position
    - map.pheromone.intent: Create an invisible pheromone marker

    Validates against:
    - Spawn safety radius
    - Natural surface height (no floating blocks in sky)
    - Sea level (voids below sea level become water)

    Emits:
    - map.build.resolved: Confirmation that a tile was built (replicate=True)
    - map.destroy.resolved: Confirmation that a tile was destroyed (replicate=True)
    - map.pheromone.resolved: Confirmation that a pheromone was placed (no replicate)
    """

    def __init__(self, registry, event_bus, config=None, blueprint=None):
        """
        Initialize construction system with world rules.

        Args:
            registry: ECS Registry for entity management
            event_bus: EventBus for subscribing to intents
            config: ServerConfig (for spawn safety, sea level, etc.)
            blueprint: LevelBlueprint (for surface height map and grid)
        """
        super().__init__(registry, event_bus)
        self.config = config
        self.blueprint = blueprint

        # Subscribe to bee intents
        self.event_bus.subscribe("map.build.intent", self._on_build_intent)
        self.event_bus.subscribe("map.destroy.intent", self._on_destroy_intent)
        self.event_bus.subscribe("map.pheromone.intent", self._on_pheromone_intent)

    def _validate_build_position(self, x: int, y: int, z: int) -> bool:
        """
        Validate that a build position respects world rules.

        Returns:
            True if build is allowed, False otherwise
        """
        if not self.config or not self.blueprint:
            return True  # No validation if config/blueprint not set

        # 1. Spawn Safety: Protect area around spawn point
        spawn_x, spawn_y, spawn_z = self.config.world_gen.spawn_point
        safe_radius = self.config.world_gen.spawn_safety_radius

        # Use Chebyshev distance (max of absolute differences)
        dist = max(abs(x - spawn_x), abs(y - spawn_y))
        if dist < safe_radius and z == spawn_z:
            # This position is in the spawn safety zone
            return False

        # 2. Surface Height: No floating tiles (more than 5 units above ground)
        surface_z = self.blueprint.get_surface_z(x, y)
        if z > surface_z + 5:
            # Floating too high in the sky
            return False

        # 3. World Bounds
        if not (0 <= x < self.blueprint.width and 0 <= y < self.blueprint.height and 0 <= z < self.blueprint.depth):
            return False

        return True

    def _on_build_intent(self, event: Event):
        """
        Handle map.build.intent: Create a new tile with the specified tag.

        Expected metadata:
        - x, y, z: 3D Tile coordinates
        - build_tag: Tag to apply (e.g., "Terrain.Wall.Stone")
        - builder_id: Entity that requested the build
        - ap_cost: Action Points consumed
        """
        meta = event.metadata
        x, y, z = meta["x"], meta["y"], meta.get("z", 0)

        # Validate position against world rules
        if not self._validate_build_position(x, y, z):
            # Build rejected: silent failure (bees will try elsewhere)
            return

        # 1. Create the ECS tile entity
        tile_id = self.registry.create_entity()

        # 2. Add components
        self.registry.add_component(tile_id, Position(x, y, z))
        self.registry.add_component(tile_id, Tags([meta["build_tag"]]))

        # 3. Update blueprint grid (mark as solid)
        if self.blueprint:
            self.blueprint.set_tile(x, y, z, 1)

        # 4. Emit resolved event for Delta Sync (clients need to know a tile was built)
        self.event_bus.emit(
            Event(
                "map.build.resolved",
                replicate=True,  # Send to all connected clients
                metadata={
                    "type": "spawn",
                    "id": tile_id,
                    "x": x,
                    "y": y,
                    "z": z,
                    "tag": meta["build_tag"],
                    "builder_id": meta.get("builder_id"),
                }
            )
        )

    def _on_destroy_intent(self, event: Event):
        """
        Handle map.destroy.intent: Destroy a tile at the specified 3D position.

        Graceful Ocean Height: If tile is below sea level, it becomes water instead of air.

        Expected metadata:
        - x, y, z: 3D Tile coordinates
        - builder_id: Entity that requested the destruction
        - ap_cost: Action Points consumed
        """
        meta = event.metadata
        x, y, z = meta["x"], meta["y"], meta.get("z", 0)

        # 1. Find the wall/tile at this 3D coordinate and destroy it
        entities = self.registry.get_entities_at_position(x, y, z)

        for entity_id in entities:
            tags = self.registry.get_component(entity_id, Tags)
            # Destroy terrain walls (not creatures or other entities)
            if tags and any(tag.startswith("Terrain.Wall") for tag in tags.tags):
                self.registry.destroy_entity(entity_id)

                # Update blueprint grid
                if self.blueprint:
                    self.blueprint.set_tile(x, y, z, 0)

                # 2. Graceful Ocean Height: If below sea level, spawn water
                sea_level = self.config.world_gen.sea_level if self.config else 12
                if z <= sea_level:
                    self._spawn_water_tile(x, y, z)

                # 3. Emit resolved event
                self.event_bus.emit(
                    Event(
                        "map.destroy.resolved",
                        replicate=True,  # Send to all connected clients
                        metadata={
                            "type": "despawn",
                            "id": entity_id,
                            "x": x,
                            "y": y,
                            "z": z,
                            "builder_id": meta.get("builder_id"),
                        }
                    )
                )

                # Only destroy one wall per intent (first match wins)
                break

    def _spawn_water_tile(self, x: int, y: int, z: int) -> None:
        """Spawn a water tile at the given position."""
        water_id = self.registry.create_entity()
        self.registry.add_component(water_id, Position(x, y, z))
        self.registry.add_component(water_id, Tags(["Terrain.Water"]))

        # Emit event for clients to render water
        self.event_bus.emit(
            Event(
                "map.build.resolved",
                replicate=True,
                metadata={
                    "type": "spawn",
                    "id": water_id,
                    "x": x,
                    "y": y,
                    "z": z,
                    "tag": "Terrain.Water",
                }
            )
        )

    def _on_pheromone_intent(self, event: Event):
        """
        Handle map.pheromone.intent: Create an invisible pheromone marker.

        Pheromones are invisible entities that track distance from start.
        Used by Scout bees to map the maze. Other systems read pheromones
        to determine pathing, spawn points, etc.

        Expected metadata:
        - x, y, z: 3D Pheromone coordinates
        - distance_value: Distance from origin (usually steps taken)
        """
        meta = event.metadata
        x, y, z = meta["x"], meta["y"], meta.get("z", 0)

        # 1. Create invisible pheromone entity
        pheromone_id = self.registry.create_entity()

        # 2. Add components
        self.registry.add_component(pheromone_id, Position(x, y, z))
        # Tag as pheromone so other systems can identify it
        self.registry.add_component(pheromone_id, Tags(["Pheromone", f"Pheromone.Distance.{meta['distance_value']}"]))

        # 3. Store the distance value in a custom component or memory
        if not hasattr(self.registry, "pheromone_map"):
            self.registry.pheromone_map = {}
        key = (x, y, z)
        self.registry.pheromone_map[key] = meta["distance_value"]

        # 4. No replicate needed for pheromones (they're invisible, internal to server)
        self.event_bus.emit(
            Event(
                "map.pheromone.resolved",
                replicate=False,  # Keep pheromones server-side only
                metadata={
                    "id": pheromone_id,
                    "x": x,
                    "y": y,
                    "z": z,
                    "distance_value": meta["distance_value"],
                }
            )
        )

    def update(self, delta_time: float) -> None:
        """
        Update phase (not used, all work is event-driven).

        Args:
            delta_time: Frame delta time in seconds
        """
        pass
