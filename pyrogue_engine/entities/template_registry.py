"""
TemplateRegistry - Load and cache entity templates

Loads JSON template files at startup and caches them in memory.
Provides O(1) template lookup for entity spawning.

Usage:
    registry = TemplateRegistry()
    registry.load_creatures("creatures.json")
    registry.load_items("items.json")

    creature_template = registry.get_creature("wolf")
    item_template = registry.get_item("iron_longsword")
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from .template import (
    CreatureTemplate,
    ItemTemplate,
    TileTemplate,
    GroupTemplate,
    MindTemplate,
    BondTemplate,
    LootTable,
    LootEntry,
    DurabilityTemplate,
    StackableTemplate,
)


class TemplateRegistry:
    """
    Central registry for all entity templates.

    Loads from JSON files and caches for fast O(1) lookup.
    """

    def __init__(self):
        """Initialize empty registry."""
        self.creatures: Dict[str, CreatureTemplate] = {}
        self.items: Dict[str, ItemTemplate] = {}
        self.tiles: Dict[str, TileTemplate] = {}
        self.groups: Dict[str, GroupTemplate] = {}

    def load_creatures(self, json_path: str | Path) -> None:
        """
        Load creature templates from JSON file.

        JSON format:
        {
            "creatures": {
                "wolf": {
                    "display_name": "Wolf",
                    "tags": ["Living.Animal"],
                    ...
                }
            },
            "groups": {
                "wolfpack": {
                    "leader_template": "wolf_alpha",
                    ...
                }
            }
        }

        Args:
            json_path: Path to creatures.json

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON is malformed
            ValueError: If template is missing required fields
        """
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Creatures file not found: {json_path}")

        with open(path) as f:
            data = json.load(f)

        # Load creatures
        creatures_data = data.get("creatures", {})
        for template_id, config in creatures_data.items():
            creature = self._parse_creature_template(template_id, config)
            self.creatures[template_id] = creature

        # Load groups
        groups_data = data.get("groups", {})
        for template_id, config in groups_data.items():
            group = self._parse_group_template(template_id, config)
            self.groups[template_id] = group

    def load_items(self, json_path: str | Path) -> None:
        """
        Load item templates from JSON file.

        JSON format:
        {
            "items": {
                "iron_longsword": {
                    "display_name": "Iron Longsword",
                    "tags": ["Material.Metal.Iron"],
                    ...
                }
            }
        }

        Args:
            json_path: Path to items.json

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON is malformed
        """
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Items file not found: {json_path}")

        with open(path) as f:
            data = json.load(f)

        items_data = data.get("items", {})
        for template_id, config in items_data.items():
            item = self._parse_item_template(template_id, config)
            self.items[template_id] = item

    def load_tiles(self, json_path: str | Path) -> None:
        """
        Load tile templates from JSON file.

        Args:
            json_path: Path to tiles.json
        """
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Tiles file not found: {json_path}")

        with open(path) as f:
            data = json.load(f)

        tiles_data = data.get("tiles", {})
        for template_id, config in tiles_data.items():
            tile = self._parse_tile_template(template_id, config)
            self.tiles[template_id] = tile

    def get_creature(self, template_id: str) -> Optional[CreatureTemplate]:
        """Get a creature template by ID."""
        return self.creatures.get(template_id)

    def get_item(self, template_id: str) -> Optional[ItemTemplate]:
        """Get an item template by ID."""
        return self.items.get(template_id)

    def get_tile(self, template_id: str) -> Optional[TileTemplate]:
        """Get a tile template by ID."""
        return self.tiles.get(template_id)

    def get_group(self, template_id: str) -> Optional[GroupTemplate]:
        """Get a group template by ID."""
        return self.groups.get(template_id)

    def has_creature(self, template_id: str) -> bool:
        """Check if creature template exists."""
        return template_id in self.creatures

    def has_item(self, template_id: str) -> bool:
        """Check if item template exists."""
        return template_id in self.items

    def has_tile(self, template_id: str) -> bool:
        """Check if tile template exists."""
        return template_id in self.tiles

    def has_group(self, template_id: str) -> bool:
        """Check if group template exists."""
        return template_id in self.groups

    def list_creatures(self) -> List[str]:
        """Get all creature template IDs."""
        return sorted(self.creatures.keys())

    def list_items(self) -> List[str]:
        """Get all item template IDs."""
        return sorted(self.items.keys())

    def list_tiles(self) -> List[str]:
        """Get all tile template IDs."""
        return sorted(self.tiles.keys())

    def list_groups(self) -> List[str]:
        """Get all group template IDs."""
        return sorted(self.groups.keys())

    # =========================================================================
    # Private: Template Parsing
    # =========================================================================

    def _parse_creature_template(
        self,
        template_id: str,
        config: Dict
    ) -> CreatureTemplate:
        """Parse creature template from JSON config."""
        # Required fields
        display_name = config.get("display_name", "Unknown")
        description = config.get("description", "")
        sprite = config.get("sprite", "@")
        sprite_color = config.get("sprite_color", "white")

        # Tags
        tags = config.get("tags", ["Living.Animal"])

        # Mind (optional)
        mind_config = config.get("mind")
        mind = None
        if mind_config:
            mind = MindTemplate(
                trait=mind_config.get("trait"),
                starting_mood=mind_config.get("starting_mood"),
                starting_urge=mind_config.get("starting_urge"),
            )

        # Bond (optional)
        bond_config = config.get("bond")
        bond = None
        if bond_config:
            bond = BondTemplate(
                allegiance=bond_config.get("allegiance"),
                role=bond_config.get("role"),
                group_loyalty=bond_config.get("group_loyalty", 50),
            )

        # Properties
        properties = config.get("properties", {})

        # Initiative
        initiative_speed = config.get("initiative_speed", 10.0)

        # Loot (optional)
        loot = None
        loot_config = config.get("loot")
        if loot_config:
            entries = []
            for entry_config in loot_config.get("entries", []):
                entry = LootEntry(
                    item_template=entry_config.get("item_template"),
                    weight=entry_config.get("weight", 1.0),
                    min_quantity=entry_config.get("min_quantity", 1),
                    max_quantity=entry_config.get("max_quantity", 1),
                )
                entries.append(entry)

            loot = LootTable(
                drop_chance=loot_config.get("drop_chance", 1.0),
                entries=entries,
            )

        return CreatureTemplate(
            template_id=template_id,
            display_name=display_name,
            description=description,
            sprite=sprite,
            sprite_color=sprite_color,
            tags=tags,
            mind=mind,
            bond=bond,
            properties=properties,
            initiative_speed=initiative_speed,
            loot=loot,
        )

    def _parse_item_template(
        self,
        template_id: str,
        config: Dict
    ) -> ItemTemplate:
        """Parse item template from JSON config."""
        # Required fields
        display_name = config.get("display_name", "Unknown Item")
        description = config.get("description", "")
        sprite = config.get("sprite", "?")
        sprite_color = config.get("sprite_color", "white")

        # Tags
        tags = config.get("tags", [])

        # Properties
        properties = config.get("properties", {})

        # Durability (optional)
        durability = None
        durability_config = config.get("durability")
        if durability_config:
            maximum = durability_config.get("maximum", 100.0)
            durability = DurabilityTemplate(
                maximum=maximum,
                current=durability_config.get("current", maximum),
            )

        # Stackable (optional)
        stackable = None
        stackable_config = config.get("stackable")
        if stackable_config:
            stackable = StackableTemplate(
                max_stack=stackable_config.get("max_stack", 1)
            )

        return ItemTemplate(
            template_id=template_id,
            display_name=display_name,
            description=description,
            sprite=sprite,
            sprite_color=sprite_color,
            tags=tags,
            properties=properties,
            durability=durability,
            stackable=stackable,
        )

    def _parse_tile_template(
        self,
        template_id: str,
        config: Dict
    ) -> TileTemplate:
        """Parse tile template from JSON config."""
        sprite = config.get("sprite", ".")
        sprite_color = config.get("sprite_color", "white")
        tags = config.get("tags", [])
        properties = config.get("properties", {})

        return TileTemplate(
            template_id=template_id,
            sprite=sprite,
            sprite_color=sprite_color,
            tags=tags,
            properties=properties,
        )

    def _parse_group_template(
        self,
        template_id: str,
        config: Dict
    ) -> GroupTemplate:
        """Parse group template from JSON config."""
        leader_template = config.get("leader_template")
        member_templates = config.get("member_templates", [])
        allegiance = config.get("allegiance")
        description = config.get("description")

        if not leader_template or not member_templates:
            raise ValueError(
                f"Group template '{template_id}' missing "
                "leader_template or member_templates"
            )

        return GroupTemplate(
            template_id=template_id,
            leader_template=leader_template,
            member_templates=member_templates,
            allegiance=allegiance,
            description=description,
        )
