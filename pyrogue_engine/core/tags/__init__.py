"""
Tag System - Hierarchical Property Inheritance

Tags represent INTRINSIC properties of entities. They form a directed acyclic graph (DAG)
where properties flow down the hierarchy and child properties override parent properties.

Components:
- Tag: A single tag with hierarchical properties
- Tags: ECS component holding all tags for an entity
- TagManager: Loads and manages the tag ontology

Example Usage:
    manager = TagManager("tags.json")

    # Get a tag object with all inherited properties
    iron_tag = manager.create_tag("Material.Metal.Iron")

    # Or query properties directly
    is_conductive = manager.get_property("Material.Metal.Iron", "Conductive")
    all_properties = manager.get_all_properties("Material.Metal.Iron")

    # Create entity
    entity = registry.create_entity()
    registry.add_component(entity, Tags(tags=[iron_tag]))
"""

from .tag import Tag, Tags
from .tag_manager import TagManager

__all__ = [
    "Tag",
    "Tags",
    "TagManager",
]
