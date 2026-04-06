"""
Tag Component - Represents what something IS.

A tag is a hierarchical label with inherited properties.
Example: "Material.Metal.Iron" inherits properties from Material, Material.Metal, and Material.Metal.Iron.

This is different from Status Effects or Buffs—tags are permanent intrinsic properties.
An item IS made of iron. It's not temporarily "made of iron" from a status effect.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Tag:
    """
    A single tag attached to an entity.

    Properties are merged from the entire inheritance chain in the tag hierarchy.
    Example: Tag("Material.Metal.Iron") automatically gets properties from:
    - Material (if defined)
    - Material.Metal (if defined)
    - Material.Metal.Iron (if defined)

    Attributes:
        name: Full hierarchical path (e.g., "Material.Metal.Iron")
        properties: All inherited properties merged from the hierarchy
                   Read-only; populated by TagManager when created
        transition_result: Optional tag path this transitions to on timeout
                          (e.g., "Material.Liquid.Magma" for melting iron)
        transition_duration: How many ticks before automatic transition
    """

    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    transition_result: Optional[str] = None
    transition_duration: int = 5  # default ticks before transition


@dataclass
class Tags:
    """
    ECS Component: All tags attached to an entity.

    An entity can have multiple tags (e.g., "Material.Metal.Iron" + "Logic.Trigger" for an iron trap).
    Tags represent INTRINSIC properties. Systems query them to determine behavior.

    Example:
        entity has tags: ["Material.Metal.Iron", "Logic.Trigger"]
        - Material.Metal.Iron tells fire system "conductive, melts at 1538°C"
        - Logic.Trigger tells electronics system "can trigger signals"

    Methods allow finding tags by hierarchy prefix or checking for properties.

    Attributes:
        tags: List of Tag objects attached to this entity
    """

    tags: list[Tag] = field(default_factory=list)

    def add_tag(self, tag: Tag) -> None:
        """Add a tag to this entity."""
        self.tags.append(tag)

    def has_tag(self, tag_name: str) -> bool:
        """Check if entity has a specific tag."""
        return any(t.name == tag_name for t in self.tags)

    def has_tag_hierarchy(self, base_tag_name: str) -> bool:
        """Check if entity has any tag starting with a base (e.g., has any Material tag)."""
        return any(t.name.startswith(base_tag_name) for t in self.tags)

    def get_tag(self, tag_name: str) -> Optional[Tag]:
        """Get a specific tag by exact name."""
        for tag in self.tags:
            if tag.name == tag_name:
                return tag
        return None

    def get_tag_with_hierarchy(self, base_tag_name: str) -> Optional[Tag]:
        """
        Get the MOST SPECIFIC tag that matches a base (e.g., Material).

        If entity has tags ["Material.Metal.Iron", "Material.Stone.Granite"],
        calling get_tag_with_hierarchy("Material") returns Material.Metal.Iron
        (the most specific, longest path).

        Args:
            base_tag_name: Base tag path (e.g., "Material", "Living", "Logic")

        Returns:
            Most specific matching Tag, or None if no match
        """
        matching = [t for t in self.tags if t.name.startswith(base_tag_name)]
        if not matching:
            return None
        # Return tag with longest name (most specific)
        return max(matching, key=lambda t: len(t.name))

    def get_property(self, property_key: str) -> Optional[Any]:
        """
        Get the first property matching the key from any tag.

        Returns the property value if found in any tag, None otherwise.

        Args:
            property_key: Property name (e.g., "Conductive", "ThermalLimit")

        Returns:
            Property value or None
        """
        for tag in self.tags:
            if property_key in tag.properties:
                return tag.properties[property_key]
        return None

    def get_property_from_tag(self, tag_name: str, property_key: str) -> Optional[Any]:
        """
        Get a property from a specific tag.

        Args:
            tag_name: Exact tag name to query
            property_key: Property name

        Returns:
            Property value from that tag, or None
        """
        tag = self.get_tag(tag_name)
        if tag:
            return tag.properties.get(property_key)
        return None

    def remove_tag(self, tag_name: str) -> bool:
        """Remove a tag from this entity."""
        self.tags = [t for t in self.tags if t.name != tag_name]
        return True

    def replace_tag(self, old_tag_name: str, new_tag: Tag) -> bool:
        """Replace one tag with another (for transitions)."""
        for i, tag in enumerate(self.tags):
            if tag.name == old_tag_name:
                self.tags[i] = new_tag
                return True
        return False

    def clear_tags(self) -> None:
        """Remove all tags."""
        self.tags.clear()

    def tag_names(self) -> list[str]:
        """Get list of all tag names on this entity."""
        return [t.name for t in self.tags]

    def __repr__(self) -> str:
        return f"Tags({', '.join(t.name for t in self.tags)})"
