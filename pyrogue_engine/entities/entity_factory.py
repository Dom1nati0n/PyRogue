"""
EntityFactory - Dynamically instantiate entities from templates

The factory takes a template and coordinates, and builds a complete ECS entity
with all necessary components.

Pattern: For each template field, attach the corresponding component.
Optional fields = optional components.

Usage:
    factory = EntityFactory(registry, event_bus, tag_manager)

    entity_id = factory.spawn_creature("wolf", x=10, y=20)
    entity_id = factory.spawn_item("iron_longsword", x=15, y=25)
    leader_id, member_ids = factory.spawn_group("wolfpack", x=30, y=40)
"""

from typing import List, Optional, Tuple

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import EventBus
from pyrogue_engine.core.tags import TagManager, Tag, Tags
from pyrogue_engine.systems.spatial.components import Position
from pyrogue_engine.systems.rpg.components import Health, Attributes, ActionPoints

from .template import (
    CreatureTemplate,
    ItemTemplate,
    TileTemplate,
    GroupTemplate,
)
from .template_registry import TemplateRegistry


class EntityFactory:
    """
    Dynamically instantiates ECS entities from templates.

    The factory is the bridge between data (JSON templates) and logic (ECS components).
    It reads template definitions and attaches the correct components to entities.
    """

    def __init__(
        self,
        registry: Registry,
        event_bus: EventBus,
        tag_manager: TagManager,
        template_registry: TemplateRegistry,
    ):
        """
        Initialize the factory.

        Args:
            registry: ECS Registry
            event_bus: EventBus for publishing events
            tag_manager: TagManager for tag inheritance
            template_registry: TemplateRegistry with loaded templates
        """
        self.registry = registry
        self.event_bus = event_bus
        self.tag_manager = tag_manager
        self.template_registry = template_registry

    # =========================================================================
    # Creature Spawning
    # =========================================================================

    def spawn_creature(
        self,
        template_id: str,
        x: int,
        y: int,
        z: int = 0,
    ) -> int:
        """
        Spawn a creature entity from template.

        Args:
            template_id: Creature template ID
            x, y, z: World position

        Returns:
            Entity ID

        Raises:
            ValueError: If template doesn't exist
        """
        template = self.template_registry.get_creature(template_id)
        if not template:
            raise ValueError(f"Creature template not found: {template_id}")

        # Create entity
        entity_id = self.registry.create_entity()

        # Attach Position
        self.registry.add_component(entity_id, Position(x=x, y=y, z=z))

        # Attach Tags with inherited properties
        tags_list = []
        for tag_name in template.tags:
            tag = self.tag_manager.create_tag(tag_name)
            tags_list.append(tag)
        self.registry.add_component(entity_id, Tags(tags=tags_list))

        # Attach display components (custom - your game defines these)
        # Example: self.registry.add_component(entity_id, Sprite(template.sprite, template.sprite_color))
        # Example: self.registry.add_component(entity_id, Examinable(template.display_name, template.description))

        # Attach combat components
        # Example: self.registry.add_component(entity_id, Health(current=100, maximum=100))
        # Example: self.registry.add_component(entity_id, Attributes(stats={"strength": 12}))

        # Attach action points (for turns)
        # Example: self.registry.add_component(entity_id, ActionPoints(current=100, maximum=100))

        # Attach AI components (if your game has them)
        # Example: self.registry.add_component(entity_id, Brain(mindset_id="aggressive_melee"))
        # Example: self.registry.add_component(entity_id, Memory())
        # Example: self.registry.add_component(entity_id, Faction(name="goblin"))

        # Attach optional behavioral components
        if template.mind:
            # Example: self.registry.add_component(entity_id, Mind(template.mind.trait, template.mind.starting_mood, template.mind.starting_urge))
            pass

        if template.bond:
            # Example: self.registry.add_component(entity_id, Bond(template.bond.allegiance, template.bond.role))
            pass

        # Attach loot (if any)
        if template.loot:
            # Example: self.registry.add_component(entity_id, LootTable(template.loot))
            pass

        return entity_id

    # =========================================================================
    # Item Spawning
    # =========================================================================

    def spawn_item(
        self,
        template_id: str,
        x: int,
        y: int,
        z: int = 0,
    ) -> int:
        """
        Spawn an item entity from template.

        Properties are merged: tag inheritance + template overrides.

        Args:
            template_id: Item template ID
            x, y, z: World position

        Returns:
            Entity ID

        Raises:
            ValueError: If template doesn't exist
        """
        template = self.template_registry.get_item(template_id)
        if not template:
            raise ValueError(f"Item template not found: {template_id}")

        # Create entity
        entity_id = self.registry.create_entity()

        # Attach Position
        self.registry.add_component(entity_id, Position(x=x, y=y, z=z))

        # Attach Tags with inherited properties
        tags_list = []
        merged_properties = {}

        for tag_name in template.tags:
            tag = self.tag_manager.create_tag(tag_name)
            tags_list.append(tag)
            # Merge properties from tag
            merged_properties.update(tag.properties)

        # Apply template property overrides
        merged_properties.update(template.properties)

        self.registry.add_component(entity_id, Tags(tags=tags_list))

        # Attach display components (custom)
        # Example: self.registry.add_component(entity_id, Sprite(template.sprite, template.sprite_color))
        # Example: self.registry.add_component(entity_id, Examinable(template.display_name, template.description))

        # Attach properties component
        # Example: self.registry.add_component(entity_id, Properties(data=merged_properties))

        # Attach optional mechanics
        if template.durability:
            # Example: self.registry.add_component(entity_id, Durability(template.durability.maximum, template.durability.current))
            pass

        if template.stackable:
            # Example: self.registry.add_component(entity_id, Stackable(quantity=1, max_stack=template.stackable.max_stack))
            pass

        return entity_id

    # =========================================================================
    # Tile Spawning
    # =========================================================================

    def spawn_tile(
        self,
        template_id: str,
        x: int,
        y: int,
        z: int = 0,
    ) -> int:
        """
        Spawn a tile entity from template.

        Args:
            template_id: Tile template ID
            x, y, z: World position

        Returns:
            Entity ID

        Raises:
            ValueError: If template doesn't exist
        """
        template = self.template_registry.get_tile(template_id)
        if not template:
            raise ValueError(f"Tile template not found: {template_id}")

        # Create entity
        entity_id = self.registry.create_entity()

        # Attach Position
        self.registry.add_component(entity_id, Position(x=x, y=y, z=z))

        # Attach Tags
        tags_list = []
        for tag_name in template.tags:
            tag = self.tag_manager.create_tag(tag_name)
            tags_list.append(tag)
        self.registry.add_component(entity_id, Tags(tags=tags_list))

        # Attach display components
        # Example: self.registry.add_component(entity_id, Sprite(template.sprite, template.sprite_color))

        # Attach properties
        # Example: self.registry.add_component(entity_id, Properties(data=template.properties))

        return entity_id

    # =========================================================================
    # Group Spawning
    # =========================================================================

    def spawn_group(
        self,
        template_id: str,
        x: int,
        y: int,
        z: int = 0,
    ) -> Tuple[int, List[int]]:
        """
        Spawn a group (leader + members) with established bonds.

        This is useful for spawning packs, squads, etc. The leader is spawned
        at the given position, and members are spawned nearby.

        Args:
            template_id: Group template ID
            x, y, z: Leader spawn position

        Returns:
            Tuple of (leader_entity_id, [member_entity_ids])

        Raises:
            ValueError: If template doesn't exist or referenced creatures don't exist
        """
        template = self.template_registry.get_group(template_id)
        if not template:
            raise ValueError(f"Group template not found: {template_id}")

        # Spawn leader
        leader_id = self.spawn_creature(template.leader_template, x, y, z)

        # Spawn members in a grid around leader
        member_ids = []
        for i, member_template in enumerate(template.member_templates):
            # Grid spacing: roughly 3 tiles apart
            offset_x = (i % 2) * 3 - 1
            offset_y = (i // 2) * 3 - 1

            member_id = self.spawn_creature(
                member_template,
                x + offset_x,
                y + offset_y,
                z,
            )
            member_ids.append(member_id)

        # Establish bonds between entities (game code would do this)
        # Example: self._bond_group(leader_id, member_ids, template)

        return leader_id, member_ids

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _bond_group(
        self,
        leader_id: int,
        member_ids: List[int],
        template: GroupTemplate,
    ) -> None:
        """
        Establish bonds between group members.

        This is game-specific code that would update Bond components.

        Args:
            leader_id: Leader entity ID
            member_ids: List of member entity IDs
            template: Group template with bonding strength
        """
        # Example implementation (game-specific):
        # leader_bonds = registry.get_component(leader_id, Bond)
        # for member_id in member_ids:
        #     leader_bonds.bonded_with.append((member_id, template.leader_to_member_strength))
        #
        # for member_id in member_ids:
        #     member_bonds = registry.get_component(member_id, Bond)
        #     member_bonds.leader_id = leader_id
        #     for other_member_id in member_ids:
        #         if other_member_id != member_id:
        #             member_bonds.bonded_with.append((other_member_id, template.member_to_member_strength))
        pass

    def debug_dump(self) -> str:
        """Return formatted string of all loaded templates."""
        lines = ["=== Entity Templates ===\n"]

        lines.append(f"Creatures: {len(self.template_registry.creatures)}")
        for template_id in self.template_registry.list_creatures()[:5]:
            lines.append(f"  - {template_id}")
        if len(self.template_registry.creatures) > 5:
            lines.append(f"  ... and {len(self.template_registry.creatures) - 5} more")

        lines.append(f"\nItems: {len(self.template_registry.items)}")
        for template_id in self.template_registry.list_items()[:5]:
            lines.append(f"  - {template_id}")
        if len(self.template_registry.items) > 5:
            lines.append(f"  ... and {len(self.template_registry.items) - 5} more")

        lines.append(f"\nGroups: {len(self.template_registry.groups)}")
        for template_id in self.template_registry.list_groups():
            lines.append(f"  - {template_id}")

        return "\n".join(lines)
