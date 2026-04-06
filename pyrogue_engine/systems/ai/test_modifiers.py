"""
Test suite for Modifier Nodes (Guards).

Tests the three core modifiers:
- InvertModifier
- ForceSuccessModifier
- CooldownGuard

Usage:
    python -m pyrogue_engine.systems.ai.test_modifiers
"""

import time
from decision_tree import DecisionNode, NodeState, TreeContext
from tree_factory import TreeFactory, GLOBAL_REGISTRY
from components import Memory, Brain
from modifiers import InvertModifier, ForceSuccessModifier, CooldownGuard
from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import EventBus


# Dummy test nodes for assertions
class SuccessNode(DecisionNode):
    """Always returns SUCCESS."""
    def tick(self, entity_id: int, memory: Memory, context: TreeContext) -> NodeState:
        return NodeState.SUCCESS


class FailureNode(DecisionNode):
    """Always returns FAILURE."""
    def tick(self, entity_id: int, memory: Memory, context: TreeContext) -> NodeState:
        return NodeState.FAILURE


class RunningNode(DecisionNode):
    """Always returns RUNNING."""
    def tick(self, entity_id: int, memory: Memory, context: TreeContext) -> NodeState:
        return NodeState.RUNNING


# Test Setup
def setup_test_context():
    """Create a minimal test context."""
    registry = Registry()
    event_bus = EventBus()
    return TreeContext(registry=registry, event_bus=event_bus)


def test_invert_modifier():
    """Test InvertModifier correctly inverts results."""
    context = setup_test_context()
    memory = Memory()

    # Test 1: SUCCESS -> FAILURE
    invert_success = InvertModifier(children=[SuccessNode()])
    result = invert_success.tick(1, memory, context)
    assert result == NodeState.FAILURE, "SUCCESS should invert to FAILURE"
    print("✓ Test 1: InvertModifier inverts SUCCESS to FAILURE")

    # Test 2: FAILURE -> SUCCESS
    invert_failure = InvertModifier(children=[FailureNode()])
    result = invert_failure.tick(1, memory, context)
    assert result == NodeState.SUCCESS, "FAILURE should invert to SUCCESS"
    print("✓ Test 2: InvertModifier inverts FAILURE to SUCCESS")

    # Test 3: RUNNING -> RUNNING (no inversion)
    invert_running = InvertModifier(children=[RunningNode()])
    result = invert_running.tick(1, memory, context)
    assert result == NodeState.RUNNING, "RUNNING should stay RUNNING"
    print("✓ Test 3: InvertModifier preserves RUNNING state")

    # Test 4: Must have exactly one child
    try:
        InvertModifier(children=[SuccessNode(), FailureNode()])
        assert False, "Should raise ValueError with multiple children"
    except ValueError as e:
        assert "exactly ONE child" in str(e)
        print("✓ Test 4: InvertModifier enforces single-child rule")


def test_force_success_modifier():
    """Test ForceSuccessModifier always returns SUCCESS."""
    context = setup_test_context()
    memory = Memory()

    # Test 1: SUCCESS -> SUCCESS
    force_success = ForceSuccessModifier(children=[SuccessNode()])
    result = force_success.tick(1, memory, context)
    assert result == NodeState.SUCCESS, "Should return SUCCESS"
    print("✓ Test 1: ForceSuccessModifier returns SUCCESS when child succeeds")

    # Test 2: FAILURE -> SUCCESS
    force_failure = ForceSuccessModifier(children=[FailureNode()])
    result = force_failure.tick(1, memory, context)
    assert result == NodeState.SUCCESS, "Should force SUCCESS on failure"
    print("✓ Test 2: ForceSuccessModifier returns SUCCESS when child fails")

    # Test 3: RUNNING -> RUNNING (waits for child)
    force_running = ForceSuccessModifier(children=[RunningNode()])
    result = force_running.tick(1, memory, context)
    assert result == NodeState.RUNNING, "Should stay RUNNING while child runs"
    print("✓ Test 3: ForceSuccessModifier preserves RUNNING state")


def test_cooldown_guard():
    """Test CooldownGuard respects cooldown timing."""
    context = setup_test_context()
    memory = Memory()

    # Test 1: First execution succeeds and sets cooldown
    cooldown = CooldownGuard(children=[SuccessNode()], cooldown=0.1, memory_key="test_cd")
    result = cooldown.tick(1, memory, context)
    assert result == NodeState.SUCCESS, "First execution should succeed"
    assert memory.has("test_cd"), "Should set cooldown timer"
    print("✓ Test 1: CooldownGuard allows first execution and sets timer")

    # Test 2: Immediate second execution fails (still on cooldown)
    result = cooldown.tick(1, memory, context)
    assert result == NodeState.FAILURE, "Should block execution on cooldown"
    print("✓ Test 2: CooldownGuard blocks execution during cooldown")

    # Test 3: After cooldown expires, execution succeeds
    time.sleep(0.15)  # Wait for cooldown to expire
    result = cooldown.tick(1, memory, context)
    assert result == NodeState.SUCCESS, "Should allow execution after cooldown"
    print("✓ Test 3: CooldownGuard allows execution after cooldown expires")

    # Test 4: FAILURE doesn't reset cooldown
    memory.clear()
    cooldown_fail = CooldownGuard(children=[FailureNode()], cooldown=0.1, memory_key="test_cd_fail")
    result = cooldown_fail.tick(1, memory, context)
    assert result == NodeState.FAILURE, "Should return FAILURE"
    assert not memory.has("test_cd_fail"), "Should NOT set timer on failure"
    print("✓ Test 4: CooldownGuard doesn't reset timer on failure")


def test_tree_factory_parsing_modifiers():
    """Test TreeFactory can parse modifiers from JSON."""
    factory = TreeFactory(GLOBAL_REGISTRY)

    # Test 1: Simple InvertModifier
    json_invert = {
        "type": "InvertModifier",
        "children": [{"type": "SuccessNode"}]
    }
    tree = factory.build_tree(json_invert)
    assert isinstance(tree, InvertModifier)
    print("✓ Test 1: TreeFactory parses InvertModifier")

    # Test 2: CooldownGuard with params
    json_cooldown = {
        "type": "CooldownGuard",
        "params": {
            "cooldown": 2.0,
            "memory_key": "my_cooldown"
        },
        "children": [{"type": "SuccessNode"}]
    }
    tree = factory.build_tree(json_cooldown)
    assert isinstance(tree, CooldownGuard)
    assert tree.cooldown == 2.0
    assert tree.memory_key == "my_cooldown"
    print("✓ Test 2: TreeFactory parses CooldownGuard with custom params")

    # Test 3: Nested modifiers
    json_nested = {
        "type": "InvertModifier",
        "children": [
            {
                "type": "CooldownGuard",
                "params": {"cooldown": 1.0},
                "children": [{"type": "SuccessNode"}]
            }
        ]
    }
    tree = factory.build_tree(json_nested)
    assert isinstance(tree, InvertModifier)
    assert isinstance(tree.child, CooldownGuard)
    print("✓ Test 3: TreeFactory parses nested modifiers")


def run_all_tests():
    """Run all modifier tests."""
    print("\n" + "="*60)
    print("MODIFIER SYSTEM TEST SUITE")
    print("="*60)

    # Register dummy nodes for testing
    GLOBAL_REGISTRY.register("SuccessNode", SuccessNode)
    GLOBAL_REGISTRY.register("FailureNode", FailureNode)
    GLOBAL_REGISTRY.register("RunningNode", RunningNode)

    print("\n[InvertModifier Tests]")
    test_invert_modifier()

    print("\n[ForceSuccessModifier Tests]")
    test_force_success_modifier()

    print("\n[CooldownGuard Tests]")
    test_cooldown_guard()

    print("\n[TreeFactory Integration Tests]")
    test_tree_factory_parsing_modifiers()

    print("\n" + "="*60)
    print("✓ ALL TESTS PASSED")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()
