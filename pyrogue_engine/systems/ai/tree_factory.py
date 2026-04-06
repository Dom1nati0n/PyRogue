"""
TreeFactory & NodeRegistry - JSON to Decision Tree Parser

NodeRegistry: Maps node type strings to node classes.
TreeFactory: Parses JSON and builds Decision Tree instances.

Architecture:
1. Register all node types with GLOBAL_REGISTRY at startup
2. TreeFactory uses registry to instantiate nodes from JSON
3. Built trees are cached to avoid re-parsing
4. Game loads JSON files (smart_assassin.json, horde_zombie.json, etc.)
5. TreeFactory builds the tree, stores it in Brain.root_node
6. AISystem ticks the tree every turn
"""

import json
from typing import Dict, Type, Optional, Any

from .decision_tree import DecisionNode, Fallback, Routine
from .modifiers import InvertModifier, ForceSuccessModifier, CooldownGuard


class NodeRegistry:
    """
    Registry of available node types.

    Maps node type strings (from JSON) to Python node classes.

    Example:
        registry = NodeRegistry()
        registry.register("Fallback", Fallback)
        registry.register("ConditionHasTarget", ConditionHasTarget)

        node_class = registry.get("Fallback")  # Returns Fallback class
    """

    def __init__(self):
        self.nodes: Dict[str, Type[DecisionNode]] = {}

    def register(self, node_type: str, node_class: Type[DecisionNode]) -> None:
        """
        Register a node type.

        Args:
            node_type: String identifier (e.g., "Fallback", "ConditionHasTarget")
            node_class: Python class that implements DecisionNode
        """
        if not issubclass(node_class, DecisionNode):
            raise TypeError(f"{node_class} must inherit from DecisionNode")
        self.nodes[node_type] = node_class

    def get(self, node_type: str) -> Type[DecisionNode]:
        """
        Retrieve a registered node class.

        Args:
            node_type: String identifier

        Returns:
            Node class

        Raises:
            ValueError if node type not registered
        """
        if node_type not in self.nodes:
            raise ValueError(
                f"Unknown node type: {node_type}. "
                f"Registered types: {sorted(self.nodes.keys())}"
            )
        return self.nodes[node_type]

    def has(self, node_type: str) -> bool:
        """Check if a node type is registered."""
        return node_type in self.nodes


class TreeFactory:
    """
    Builds Decision Trees from JSON configuration.

    Usage:
        factory = TreeFactory(GLOBAL_REGISTRY)

        # Load from file
        tree = factory.load_from_file("content/ai/smart_assassin.json")

        # Or from dict
        json_data = {"type": "Fallback", "children": [...]}
        tree = factory.build_tree(json_data)

    Caching:
        # Load once, cache it
        tree = factory.load_from_file("content/ai/horde_zombie.json", cache_key="horde_zombie")

        # Load again (instant from cache)
        tree = factory.load_from_file("content/ai/horde_zombie.json", cache_key="horde_zombie")
    """

    def __init__(self, registry: NodeRegistry):
        """
        Initialize factory.

        Args:
            registry: NodeRegistry with all registered node types
        """
        self.registry = registry
        self.tree_cache: Dict[str, DecisionNode] = {}

    def build_tree(
        self,
        json_data: Dict[str, Any],
        cache_key: Optional[str] = None
    ) -> DecisionNode:
        """
        Build a tree from JSON dictionary.

        Args:
            json_data: Dict with 'type' and optional 'children' and 'comment'
            cache_key: If provided, cache the built tree under this key

        Returns:
            Instantiated DecisionNode tree

        Raises:
            ValueError if JSON is malformed
            KeyError if node type not in registry
        """
        if cache_key and cache_key in self.tree_cache:
            return self.tree_cache[cache_key]

        node = self._parse_node(json_data)

        if cache_key:
            self.tree_cache[cache_key] = node

        return node

    def _parse_node(self, json_data: Dict[str, Any]) -> DecisionNode:
        """
        Recursively parse a node and its children from JSON.

        Args:
            json_data: Node definition with 'type' and optional 'children' and 'params'

        Returns:
            Instantiated DecisionNode

        Raises:
            ValueError if 'type' missing
            KeyError if node type not registered
        """
        node_type = json_data.get("type")
        if not node_type:
            raise ValueError(f"Node missing 'type' field: {json_data}")

        # Get the node class from registry
        node_class = self.registry.get(node_type)

        # Extract custom parameters (default to empty dict)
        params = json_data.get("params", {})

        # Parse children recursively
        children_data = json_data.get("children", [])
        children = [self._parse_node(child) for child in children_data]

        # Instantiate the node
        if children:
            return node_class(children=children, **params)
        else:
            # Leaf nodes (conditions, actions) have no children
            return node_class(**params)

    def load_from_file(
        self,
        json_path: str,
        cache_key: Optional[str] = None
    ) -> DecisionNode:
        """
        Load and build tree from JSON file.

        Args:
            json_path: Path to JSON file
            cache_key: If provided, cache the tree

        Returns:
            Instantiated DecisionNode tree

        Raises:
            FileNotFoundError if file doesn't exist
            json.JSONDecodeError if JSON is malformed
        """
        with open(json_path) as f:
            json_data = json.load(f)
        return self.build_tree(json_data, cache_key)

    def clear_cache(self) -> None:
        """Clear the tree cache. Use for testing or hot-reload."""
        self.tree_cache.clear()


# Global registry populated at module import
# Games can add their own custom nodes by importing this and calling .register()
GLOBAL_REGISTRY = NodeRegistry()

# Register built-in control flow nodes
GLOBAL_REGISTRY.register("Fallback", Fallback)
GLOBAL_REGISTRY.register("Routine", Routine)

# Register modifier (guard) nodes
GLOBAL_REGISTRY.register("InvertModifier", InvertModifier)
GLOBAL_REGISTRY.register("ForceSuccessModifier", ForceSuccessModifier)
GLOBAL_REGISTRY.register("CooldownGuard", CooldownGuard)

# Condition and action nodes are registered by their modules after import
# Example: from pyrogue_engine.systems.ai.conditions import * (in __init__.py or main)
