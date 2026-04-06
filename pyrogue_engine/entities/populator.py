"""
LevelPopulator - Transform Mathematical Blueprints into Living Worlds

The populator is the final piece of the pipeline. It takes a LevelBlueprint
(from Phase 3 MapGen) and uses the EntityFactory (from Phase 7.2) to spawn
creatures, items, and structures.

The populator is agnostic to map generation algorithm. It works with any
generator (BSP, Cellular Automata, Noise, etc.) because it only reads the
standardized LevelBlueprint format.

Workflow:
1. Generate blueprint (Phase 3)
2. Analyze blueprint (flood fill, etc.)
3. Populate with creatures & items (this module)
4. Game loop processes simulation (Phases 1-6)
"""

import random
from typing import Dict, List, Optional, Tuple

from pyrogue_engine.generation.level_blueprint import LevelBlueprint
from .entity_factory import EntityFactory


class LevelPopulator:
    """
    Populates a LevelBlueprint with actors (creatures) and objects (items).

    Uses weighted encounter and loot tables to spawn entities at random
    valid locations in the blueprint.

    The populator doesn't care HOW the blueprint was generated (BSP, automata, noise).
    It only reads the standardized format and spawns accordingly.
    """

    def __init__(self, entity_factory: EntityFactory):
        """
        Initialize populator with entity factory.

        Args:
            entity_factory: EntityFactory for spawning creatures/items
        """
        self.factory = entity_factory

    def populate(
        self,
        blueprint: LevelBlueprint,
        encounter_table: Optional[Dict[str, int]] = None,
        loot_table: Optional[Dict[str, int]] = None,
        min_spawn_distance: int = 5,
    ) -> Tuple[List[int], List[int]]:
        """
        Populate a level blueprint with creatures and items.

        Handles both structured maps (with room_centers) and organic maps
        (with flood-filled walkable_regions).

        Args:
            blueprint: LevelBlueprint from map generator
            encounter_table: Dict of {creature_template_id: weight}
                           Higher weight = more likely to spawn
            loot_table: Dict of {item_template_id: weight}
            min_spawn_distance: Minimum distance from entrance (tiles)

        Returns:
            Tuple of (creature_entity_ids, item_entity_ids)

        Raises:
            ValueError: If blueprint is invalid or no spawn points found
        """
        if not blueprint:
            raise ValueError("Blueprint cannot be None")

        if not blueprint.is_walkable:
            raise ValueError("Blueprint has no walkable tiles")

        creature_ids = []
        item_ids = []

        # 1. Place map transitions (entrance/exit)
        self._place_transitions(blueprint)

        # 2. Get valid spawn points (excluding entrance/exit)
        spawn_points = self._get_spawn_points(
            blueprint,
            min_spawn_distance=min_spawn_distance
        )

        if not spawn_points:
            raise ValueError("No valid spawn points found in blueprint")

        # 3. Populate with creatures and items
        for x, y in spawn_points:
            creature_id = self._spawn_encounter(x, y, encounter_table)
            if creature_id:
                creature_ids.append(creature_id)

            item_id = self._spawn_loot(x, y, loot_table)
            if item_id:
                item_ids.append(item_id)

        return creature_ids, item_ids

    def populate_rooms(
        self,
        blueprint: LevelBlueprint,
        encounter_table: Optional[Dict[str, int]] = None,
        loot_table: Optional[Dict[str, int]] = None,
        spawns_per_room: int = 1,
    ) -> Tuple[List[int], List[int]]:
        """
        Populate structured rooms (BSP, recursive division, etc.).

        This variant assumes the blueprint has room_centers from a structured
        generator like BSP. Places entities in room centers rather than
        random walkable points.

        Args:
            blueprint: LevelBlueprint with room_centers
            encounter_table: Dict of {creature_template_id: weight}
            loot_table: Dict of {item_template_id: weight}
            spawns_per_room: How many entities per room center

        Returns:
            Tuple of (creature_entity_ids, item_entity_ids)

        Raises:
            ValueError: If blueprint has no room_centers
        """
        if not hasattr(blueprint, 'room_centers') or not blueprint.room_centers:
            raise ValueError("Blueprint has no room_centers (not a structured map?)")

        creature_ids = []
        item_ids = []

        # Place map transitions
        self._place_transitions(blueprint)

        # Populate each room
        for center_x, center_y in blueprint.room_centers:
            # Skip entrance and exit
            if (center_x, center_y) == blueprint.entrance or (center_x, center_y) == blueprint.exit:
                continue

            # Spawn multiple entities per room
            for _ in range(spawns_per_room):
                # Add small random offset from center
                x = center_x + random.randint(-2, 2)
                y = center_y + random.randint(-2, 2)

                # Ensure we're still on walkable tile
                if blueprint.is_walkable(x, y):
                    creature_id = self._spawn_encounter(x, y, encounter_table)
                    if creature_id:
                        creature_ids.append(creature_id)

                    item_id = self._spawn_loot(x, y, loot_table)
                    if item_id:
                        item_ids.append(item_id)

        return creature_ids, item_ids

    def populate_regions(
        self,
        blueprint: LevelBlueprint,
        encounter_table: Optional[Dict[str, int]] = None,
        loot_table: Optional[Dict[str, int]] = None,
        spawns_per_region: int = 1,
        use_density: bool = True,
    ) -> Tuple[List[int], List[int]]:
        """
        Populate organic regions (Cellular Automata, Noise, Voronoi, etc.).

        This variant uses flood-filled walkable_regions from the analyzer.
        Spawns creatures/items throughout the regions, respecting density.

        Args:
            blueprint: LevelBlueprint with walkable_regions
            encounter_table: Dict of {creature_template_id: weight}
            loot_table: Dict of {item_template_id: weight}
            spawns_per_region: Base number of spawns per region
            use_density: If True, scale spawns by region size

        Returns:
            Tuple of (creature_entity_ids, item_entity_ids)

        Raises:
            ValueError: If blueprint has no walkable_regions
        """
        if not hasattr(blueprint, 'walkable_regions') or not blueprint.walkable_regions:
            raise ValueError("Blueprint has no walkable_regions")

        creature_ids = []
        item_ids = []

        # Place map transitions
        self._place_transitions(blueprint)

        # Populate each region
        for region in blueprint.walkable_regions:
            if not region:
                continue

            # Calculate how many spawns for this region
            if use_density:
                # Density: 1 spawn per N tiles
                num_spawns = max(spawns_per_region, len(region) // 40)
            else:
                num_spawns = spawns_per_region

            # Get valid spawn points (exclude entrance/exit)
            valid_points = [
                pt for pt in region
                if pt != blueprint.entrance and pt != blueprint.exit
            ]

            if not valid_points:
                continue

            # Randomly select spawn points
            spawn_points = random.sample(
                valid_points,
                k=min(num_spawns, len(valid_points))
            )

            # Spawn creatures and loot
            for x, y in spawn_points:
                creature_id = self._spawn_encounter(x, y, encounter_table)
                if creature_id:
                    creature_ids.append(creature_id)

                item_id = self._spawn_loot(x, y, loot_table)
                if item_id:
                    item_ids.append(item_id)

        return creature_ids, item_ids

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _place_transitions(self, blueprint: LevelBlueprint) -> None:
        """
        Place entrance and exit tiles on the blueprint.

        Args:
            blueprint: LevelBlueprint with entrance/exit coordinates
        """
        if blueprint.entrance:
            x, y = blueprint.entrance
            if blueprint.is_walkable(x, y):
                self.factory.spawn_tile("stairs_up", x, y)

        if blueprint.exit:
            x, y = blueprint.exit
            if blueprint.is_walkable(x, y):
                self.factory.spawn_tile("stairs_down", x, y)

    def _get_spawn_points(
        self,
        blueprint: LevelBlueprint,
        min_spawn_distance: int = 5,
    ) -> List[Tuple[int, int]]:
        """
        Get valid spawn points from blueprint.

        Uses walkable_regions if available, otherwise scans for walkable tiles.
        Filters out entrance/exit and respects minimum distance.

        Args:
            blueprint: LevelBlueprint
            min_spawn_distance: Minimum distance from entrance (for difficulty scaling)

        Returns:
            List of (x, y) valid spawn points
        """
        # Prefer walkable_regions if available (more efficient)
        if hasattr(blueprint, 'walkable_regions') and blueprint.walkable_regions:
            # Use largest region (usually the main area)
            region = max(blueprint.walkable_regions, key=len)
            valid = [
                pt for pt in region
                if pt != blueprint.entrance and pt != blueprint.exit
            ]
            return valid

        # Fallback: scan entire grid for walkable tiles
        valid = []
        for x in range(blueprint.width):
            for y in range(blueprint.height):
                if blueprint.is_walkable(x, y):
                    if (x, y) != blueprint.entrance and (x, y) != blueprint.exit:
                        # Optional: respect distance from entrance
                        if self._distance_from_point(x, y, blueprint.entrance) >= min_spawn_distance:
                            valid.append((x, y))

        return valid

    def _spawn_encounter(
        self,
        x: int,
        y: int,
        encounter_table: Optional[Dict[str, int]],
    ) -> Optional[int]:
        """
        Roll for and spawn a creature at (x, y).

        Uses weighted random selection from encounter_table.

        Args:
            x, y: Spawn coordinates
            encounter_table: Dict of {template_id: weight}

        Returns:
            Creature entity ID, or None if nothing spawned
        """
        if not encounter_table:
            return None

        # 60% chance to spawn something
        if random.random() > 0.60:
            return None

        # Weighted random selection
        templates = list(encounter_table.keys())
        weights = list(encounter_table.values())

        try:
            creature_template = random.choices(templates, weights=weights, k=1)[0]
            return self.factory.spawn_creature(creature_template, x, y)
        except (ValueError, IndexError):
            return None

    def _spawn_loot(
        self,
        x: int,
        y: int,
        loot_table: Optional[Dict[str, int]],
    ) -> Optional[int]:
        """
        Roll for and spawn an item at (x, y).

        Uses weighted random selection from loot_table.

        Args:
            x, y: Spawn coordinates
            loot_table: Dict of {template_id: weight}

        Returns:
            Item entity ID, or None if nothing spawned
        """
        if not loot_table:
            return None

        # 30% chance to spawn loot
        if random.random() > 0.30:
            return None

        # Weighted random selection
        templates = list(loot_table.keys())
        weights = list(loot_table.values())

        try:
            item_template = random.choices(templates, weights=weights, k=1)[0]
            return self.factory.spawn_item(item_template, x, y)
        except (ValueError, IndexError):
            return None

    def _distance_from_point(
        self,
        x1: int,
        y1: int,
        point: Optional[Tuple[int, int]],
    ) -> int:
        """
        Calculate Chebyshev distance (max of dx, dy).

        Used for spawning difficulty scaling.
        """
        if not point:
            return 0

        x2, y2 = point
        return max(abs(x1 - x2), abs(y1 - y2))
