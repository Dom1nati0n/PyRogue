"""
TagManager - Load and Query the Tag Ontology

The tag system is a Directed Acyclic Graph (DAG) where properties flow DOWN
the hierarchy. Tags inherit properties from their parents, with child properties
overriding parents.

Example hierarchy:
    Material
    ├─ Metal (Conductive: true, Opaque: true)
    │  ├─ Iron (Magnetic: true, ThermalLimit: 1538)
    │  └─ Copper (ThermalLimit: 1085)
    └─ Stone (Opaque: true)

TagManager loads the JSON, flattens it for O(1) lookup, and provides methods
to query properties with inheritance.

Usage:
    manager = TagManager("tags.json")
    properties = manager.get_all_properties("Material.Metal.Iron")
    # Returns: {Conductive: true, Opaque: true, Magnetic: true, ThermalLimit: 1538}
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .tag import Tag


class TagManager:
    """
    Manages the tag ontology hierarchy and property inheritance.

    Loads tags.json, flattens the tree for O(1) lookup, and provides methods
    to query properties with automatic inheritance from parent tags.
    """

    def __init__(self, tags_json_path: str | Path = "tags.json"):
        """
        Initialize the tag manager by loading and flattening tags.

        Args:
            tags_json_path: Path to tags.json file

        Raises:
            FileNotFoundError: If tags.json doesn't exist
            json.JSONDecodeError: If tags.json is malformed
        """
        self.tags_json_path = Path(tags_json_path)
        self.tags_data: Dict[str, Any] = {}  # Raw nested hierarchy
        self.flat_tags: Dict[str, Dict[str, Any]] = {}  # Flattened lookup
        self.tag_classes: Dict[str, Set[str]] = {}  # Classification cache

        # Network dictionary: tag string <-> integer ID for bandwidth optimization
        self.tag_to_id: Dict[str, int] = {}  # "Material.Metal.Iron" → 42
        self.id_to_tag: Dict[int, str] = {}  # 42 → "Material.Metal.Iron"
        self.network_dict_built = False

        self._load_tags()
        self._build_network_dictionary()

    def _load_tags(self) -> None:
        """Load tags.json and flatten the hierarchy."""
        if not self.tags_json_path.exists():
            raise FileNotFoundError(f"Tags file not found: {self.tags_json_path}")

        with open(self.tags_json_path) as f:
            data = json.load(f)

        # Extract main tag hierarchy
        self.tags_data = data.get("tags", {})

        # Extract tag classes (for classification system)
        classes_data = data.get("tag_classes", {})
        for class_name, tag_list in classes_data.items():
            self.tag_classes[class_name] = set(tag_list)

        # Flatten the tree for O(1) lookup
        self._flatten_tags(self.tags_data)

    def _flatten_tags(self, tags: Dict[str, Any], parent_path: str = "") -> None:
        """
        Recursively flatten the tag hierarchy into a flat lookup table.

        Args:
            tags: Nested tag dictionary
            parent_path: Current path in hierarchy (e.g., "Material.Metal")
        """
        for tag_name, tag_data in tags.items():
            # Build full path (e.g., "Material.Metal.Iron")
            full_name = f"{parent_path}.{tag_name}" if parent_path else tag_name

            # Store in flat table
            self.flat_tags[full_name] = tag_data

            # Recurse into children
            if "children" in tag_data:
                self._flatten_tags(tag_data["children"], full_name)

    def _build_network_dictionary(self) -> None:
        """
        Build the network dictionary: assign a unique integer ID to every tag.

        This runs at server startup and enables bandwidth-efficient tag transmission.
        Instead of sending "Material.Metal.Iron" (25+ bytes), we send just 42 (1-2 bytes).

        The dictionary is sent to clients in the handshake packet.
        """
        tag_id = 1  # Start at 1 (0 is reserved for "no tag")

        # Sort tags alphabetically for deterministic IDs across restarts
        for tag_name in sorted(self.flat_tags.keys()):
            self.tag_to_id[tag_name] = tag_id
            self.id_to_tag[tag_id] = tag_name
            tag_id += 1

        self.network_dict_built = True

    def tag_exists(self, tag_name: str) -> bool:
        """
        Check if a tag is defined in the ontology.

        Args:
            tag_name: Tag path (e.g., "Material.Metal.Iron")

        Returns:
            True if tag exists
        """
        return tag_name in self.flat_tags

    def create_tag(self, tag_name: str) -> Tag:
        """
        Create a Tag object with all inherited properties.

        This merges properties from the entire hierarchy chain.

        Args:
            tag_name: Tag path to create

        Returns:
            Tag object with merged properties

        Raises:
            ValueError: If tag doesn't exist
        """
        if not self.tag_exists(tag_name):
            raise ValueError(f"Tag not found: {tag_name}")

        properties = self.get_all_properties(tag_name)
        transition_result = self.get_property(tag_name, "TransitionResult")

        return Tag(
            name=tag_name,
            properties=properties,
            transition_result=transition_result,
            transition_duration=5  # default
        )

    def get_property(
        self,
        tag_name: str,
        property_key: str,
        default: Any = None
    ) -> Any:
        """
        Get a single property from a tag, checking inheritance chain.

        Walks UP the hierarchy from most specific to least specific,
        returning the FIRST matching property found.

        Example: get_property("Material.Metal.Iron", "Conductive")
        1. Check Material.Metal.Iron → not found
        2. Check Material.Metal → found Conductive: true → return true

        Args:
            tag_name: Tag path to query
            property_key: Property name
            default: Value to return if not found

        Returns:
            Property value, or default if not found
        """
        path_parts = tag_name.split(".")

        # Walk from most specific to least specific
        for i in range(len(path_parts), 0, -1):
            current_path = ".".join(path_parts[:i])
            tag_data = self.flat_tags.get(current_path)

            if tag_data and "properties" in tag_data:
                props = tag_data["properties"]
                if property_key in props:
                    return props[property_key]

        return default

    def get_all_properties(self, tag_name: str) -> Dict[str, Any]:
        """
        Get ALL properties for a tag, merged from the entire hierarchy.

        Properties are accumulated from parent to child, with child values
        overriding parent values (child wins).

        Example: get_all_properties("Material.Metal.Iron")
        1. Get Material.properties → {}
        2. Get Material.Metal.properties → {Conductive: true, Opaque: true, AcousticDampening: 5}
        3. Get Material.Metal.Iron.properties → {Magnetic: true, ThermalLimit: 1538, Integrity: 100}
        4. Merge (most specific wins) →
           {Conductive: true, Opaque: true, AcousticDampening: 5, Magnetic: true, ThermalLimit: 1538, Integrity: 100}

        Args:
            tag_name: Tag path to query

        Returns:
            Dictionary of all inherited properties (most specific values)
        """
        result: Dict[str, Any] = {}
        path_parts = tag_name.split(".")

        # Walk from LEAST specific to MOST specific
        for i in range(1, len(path_parts) + 1):
            current_path = ".".join(path_parts[:i])
            tag_data = self.flat_tags.get(current_path)

            if tag_data and "properties" in tag_data:
                result.update(tag_data["properties"])  # Merge/override

        return result

    def get_transition_result(self, tag_name: str) -> Optional[str]:
        """
        Get what a tag transitions to (if applicable).

        Used for state transitions like melting, burning, etc.

        Example: Iron at ThermalLimit transitions to Material.Liquid.Magma

        Args:
            tag_name: Tag path

        Returns:
            Target tag path, or None if no transition defined
        """
        return self.get_property(tag_name, "TransitionResult")

    def get_tag_class(self, tag_name: str) -> Optional[str]:
        """
        Get the classification of a tag (Intrinsic, Utility, Hazard).

        Used to determine tag behavior:
        - Intrinsic: Always active
        - Utility: Disabled by "Unidentified" status
        - Hazard: Always active (even when Unidentified)

        Checks exact match first, then prefix match against parent tags.

        Args:
            tag_name: Tag path to classify

        Returns:
            Class name ("Intrinsic", "Utility", "Hazard"), or None if unclassified
        """
        # Check for exact match
        for class_name, tags in self.tag_classes.items():
            if tag_name in tags:
                return class_name

        # Check if tag is a child of any classified tag (prefix match)
        for class_name, tags in self.tag_classes.items():
            for parent in tags:
                if tag_name.startswith(parent + "."):
                    return class_name

        # Default classification
        return "Intrinsic"

    def is_tag_active(self, tag_name: str, has_unidentified: bool) -> bool:
        """
        Check if a tag is functionally active on an entity.

        Utility tags are disabled if entity has "Unidentified" status.
        Hazard tags always fire (reveal hidden triggers even when unidentified).
        Intrinsic tags are always active.

        Args:
            tag_name: Tag to check
            has_unidentified: True if entity has Unidentified status

        Returns:
            True if tag is active and should be processed
        """
        if not has_unidentified:
            return True

        tag_class = self.get_tag_class(tag_name)

        if tag_class == "Utility":
            return False  # Disabled by Unidentified
        elif tag_class == "Hazard":
            return True  # Always fire
        else:  # Intrinsic or None
            return True  # Always active

    def get_all_tags_with_prefix(self, prefix: str) -> List[str]:
        """
        Get all tags matching a prefix.

        Useful for finding all "Material.*" tags, all "Logic.*" tags, etc.

        Args:
            prefix: Tag prefix to match (e.g., "Material")

        Returns:
            List of matching tag paths
        """
        return [name for name in self.flat_tags.keys() if name.startswith(prefix)]

    def tags_to_ids(self, tags: List[str]) -> List[int]:
        """
        Convert a list of tag strings to their network integer IDs.

        Used when replicating entity tags over the network.
        Example: ["Material.Metal.Iron", "Status.Hot"] → [42, 128]

        Args:
            tags: List of tag strings (e.g., ["Material.Metal.Iron"])

        Returns:
            List of integer IDs (e.g., [42])

        Raises:
            ValueError: If any tag is not found in the dictionary
        """
        result = []
        for tag_str in tags:
            if tag_str not in self.tag_to_id:
                raise ValueError(f"Tag not found in network dictionary: {tag_str}")
            result.append(self.tag_to_id[tag_str])
        return result

    def ids_to_tags(self, tag_ids: List[int]) -> List[str]:
        """
        Convert a list of network integer IDs back to tag strings.

        Used on the client side to reconstruct tag names from network packets.
        Example: [42, 128] → ["Material.Metal.Iron", "Status.Hot"]

        Args:
            tag_ids: List of integer IDs (e.g., [42])

        Returns:
            List of tag strings (e.g., ["Material.Metal.Iron"])

        Raises:
            ValueError: If any ID is not found in the dictionary
        """
        result = []
        for tag_id in tag_ids:
            if tag_id not in self.id_to_tag:
                raise ValueError(f"Tag ID not found in network dictionary: {tag_id}")
            result.append(self.id_to_tag[tag_id])
        return result

    def export_network_dictionary(self) -> Dict[int, str]:
        """
        Export the network dictionary for the handshake packet.

        Clients receive this once at connection time and cache it in memory.
        Format: {1: "Material.Metal.Iron", 2: "Material.Metal.Copper", ...}

        Returns:
            Dictionary mapping integer IDs to tag strings
        """
        return self.id_to_tag.copy()

    def debug_dump(self) -> str:
        """Return formatted string of entire ontology for debugging."""
        lines = ["=== Tag Ontology ===\n"]

        # Group tags by top-level category
        categories: Dict[str, List[str]] = {}
        for tag_name in sorted(self.flat_tags.keys()):
            top_level = tag_name.split(".")[0]
            if top_level not in categories:
                categories[top_level] = []
            categories[top_level].append(tag_name)

        for category in sorted(categories.keys()):
            lines.append(f"\n{category}:")
            for tag_name in categories[category]:
                tag_data = self.flat_tags[tag_name]
                props = tag_data.get("properties", {})
                if props:
                    props_str = ", ".join(f"{k}={v}" for k, v in list(props.items())[:3])
                    lines.append(f"  {tag_name} → {props_str}...")
                else:
                    lines.append(f"  {tag_name}")

        return "\n".join(lines)
