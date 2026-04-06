"""
Quick validation test for TreeFactory.

Run this to verify the TreeFactory can parse JSON and build trees.

Usage:
    python -m pyrogue_engine.systems.ai.test_tree_factory
"""

from decision_tree import DecisionNode, NodeState, Fallback, Routine
from tree_factory import TreeFactory, GLOBAL_REGISTRY


def test_basic_tree_parsing():
    """Test that TreeFactory can parse simple trees."""
    factory = TreeFactory(GLOBAL_REGISTRY)

    # Test 1: Simple Fallback
    json_fallback = {
        "type": "Fallback",
        "children": [
            {"type": "ActionWait"},
            {"type": "ActionWander"}
        ]
    }
    tree = factory.build_tree(json_fallback, cache_key="test_fallback")
    assert isinstance(tree, Fallback)
    assert len(tree.children) == 2
    print("✓ Test 1: Fallback parsing works")

    # Test 2: Routine with conditions
    json_routine = {
        "type": "Routine",
        "children": [
            {"type": "ConditionHasTarget"},
            {"type": "ActionWait"}
        ]
    }
    tree = factory.build_tree(json_routine)
    assert isinstance(tree, Routine)
    assert len(tree.children) == 2
    print("✓ Test 2: Routine parsing works")

    # Test 3: Nested tree
    json_nested = {
        "type": "Fallback",
        "children": [
            {
                "type": "Routine",
                "children": [
                    {"type": "ConditionHasTarget"},
                    {"type": "ActionMeleeAttack"}
                ]
            },
            {"type": "ActionWander"}
        ]
    }
    tree = factory.build_tree(json_nested, cache_key="smart_assassin_simple")
    assert isinstance(tree, Fallback)
    assert len(tree.children) == 2
    assert isinstance(tree.children[0], Routine)
    print("✓ Test 3: Nested tree parsing works")

    # Test 4: Cache retrieval
    tree_cached = factory.build_tree(json_nested, cache_key="smart_assassin_simple")
    assert tree is tree_cached
    print("✓ Test 4: Tree caching works")

    # Test 5: Load from file
    try:
        tree = factory.load_from_file("examples/smart_assassin.json", cache_key="smart_assassin_file")
        assert isinstance(tree, Fallback)
        print("✓ Test 5: File loading works")
    except FileNotFoundError:
        print("⚠ Test 5: Skipped (examples/smart_assassin.json not found in test context)")

    print("\n✅ All TreeFactory tests passed!")


def test_node_registry():
    """Test that all built-in nodes are registered."""
    expected_nodes = [
        # Control flow
        "Fallback", "Routine",
        # Conditions
        "ConditionHasTarget", "ConditionTargetAdjacent", "ConditionTargetInRange",
        "ConditionTargetAlive", "ConditionSelfAlive", "ConditionSelfHealthLow",
        "ConditionMemoryKey",
        # Actions
        "ActionMeleeAttack", "ActionJPSMove", "ActionFlowFieldMove",
        "ActionWander", "ActionWait", "ActionUpdateMemory"
    ]

    for node_type in expected_nodes:
        assert GLOBAL_REGISTRY.has(node_type), f"Missing: {node_type}"
        print(f"✓ {node_type} registered")

    print(f"\n✅ All {len(expected_nodes)} nodes registered!")


if __name__ == "__main__":
    print("Testing TreeFactory...\n")
    test_node_registry()
    print()
    test_basic_tree_parsing()
