"""
Modifier Nodes (Guards) - The Gatekeepers of Behavior Tree Execution

Modifiers wrap exactly ONE child and alter its execution or result.
They are the "decorators" that make decision trees state-aware and intelligent.

Philosophy: In Behavior Tree theory, these are called Guards or Modifiers.
(Confusing name in Python where @decorator means something different!)

They intercept the tick() going down, modify execution, and modify the NodeState
coming back up. Perfect for implementing cooldowns, inversions, and conditional guards.

Example use cases:
- CooldownGuard: "Only execute this action once per second"
- InvertModifier: "Execute action ONLY if this condition fails"
- ForceSuccessModifier: "Always report success, even if the action fails"

When composed, you can build incredibly intelligent behaviors:
  CooldownGuard(InvertModifier(Sequence([condition, action])))
  -> "Only try this sequence once per second, and only if condition fails"
"""

import time
from typing import List
from pyrogue_engine.systems.ai.decision_tree import DecisionNode, NodeState, TreeContext
from pyrogue_engine.systems.ai.components import Memory


class ModifierNode(DecisionNode):
    """
    Base class for Guard/Modifier nodes.

    These nodes wrap exactly ONE child and alter its execution or result.

    Enforces the "one child" contract that all modifiers require.
    """

    def __init__(self, children: List[DecisionNode] = None, **kwargs):
        """
        Initialize a modifier with exactly one child.

        Args:
            children: Must be a list with exactly one DecisionNode

        Raises:
            ValueError if children is None, empty, or has more than one element
        """
        super().__init__()
        if not children or len(children) != 1:
            raise ValueError(
                f"{self.__class__.__name__} must have exactly ONE child. "
                f"Got {len(children) if children else 0} children."
            )
        self.child = children[0]


class InvertModifier(ModifierNode):
    """
    Inverts the result of its child.

    Maps:
        SUCCESS -> FAILURE
        FAILURE -> SUCCESS
        RUNNING -> RUNNING (stays running)

    Use case:
        "Try this action ONLY if the condition fails"
        {
            "type": "InvertModifier",
            "children": [
                {"type": "ConditionPlayerVisible"}
            ]
        }

    This modifier will return SUCCESS when the player is NOT visible.
    """

    def __init__(self, children: List[DecisionNode] = None, **kwargs):
        super().__init__(children, **kwargs)

    def tick(self, entity_id: int, memory: Memory, context: TreeContext) -> NodeState:
        result = self.child.tick(entity_id, memory, context)

        if result == NodeState.SUCCESS:
            return NodeState.FAILURE
        if result == NodeState.FAILURE:
            return NodeState.SUCCESS

        # If RUNNING, stay RUNNING (don't invert mid-execution)
        return result


class ForceSuccessModifier(ModifierNode):
    """
    Always returns SUCCESS, regardless of what the child does.

    Maps:
        SUCCESS -> SUCCESS
        FAILURE -> SUCCESS
        RUNNING -> RUNNING (waits for child to finish)

    Use case:
        "Always treat this action as successful, even if it fails"
        {
            "type": "ForceSuccessModifier",
            "children": [
                {"type": "ActionAttemptSpecialMove"}
            ]
        }

    Useful for "best effort" actions that shouldn't block the tree.
    """

    def __init__(self, children: List[DecisionNode] = None, **kwargs):
        super().__init__(children, **kwargs)

    def tick(self, entity_id: int, memory: Memory, context: TreeContext) -> NodeState:
        result = self.child.tick(entity_id, memory, context)

        # If still running, wait for child to finish
        if result == NodeState.RUNNING:
            return NodeState.RUNNING

        # All other states (success or failure) return SUCCESS
        return NodeState.SUCCESS


class CooldownGuard(ModifierNode):
    """
    Prevents the child from executing more than once every X seconds.

    Uses the entity's Memory (Blackboard) to track the last execution time.

    Parameters:
        cooldown (float): Cooldown duration in seconds (default: 1.0)
        memory_key (str): Blackboard key to store last execution time
                          (default: "last_run")

    Returns:
        FAILURE if still on cooldown
        Otherwise, returns the child's result
        Resets cooldown timer only if child returns SUCCESS

    Use case:
        "Only evaluate this action once per second"
        {
            "type": "CooldownGuard",
            "params": {
                "cooldown": 1.0,
                "memory_key": "last_automata_build"
            },
            "children": [
                {"type": "Sequence", "children": [
                    {"type": "HasAPCondition", "params": {"required_ap": 20}},
                    {"type": "AutomataStepAction"}
                ]}
            ]
        }

    This allows the tree to evaluate preconditions while respecting the cooldown.
    If the sequence succeeds, the cooldown resets. If it fails, cooldown is unchanged.
    """

    def __init__(
        self,
        children: List[DecisionNode] = None,
        cooldown: float = 1.0,
        memory_key: str = "last_run",
        **kwargs
    ):
        """
        Initialize cooldown guard.

        Args:
            children: Exactly one child node
            cooldown: Duration in seconds before child can execute again
            memory_key: Key in Memory (blackboard) to track last execution
        """
        super().__init__(children, **kwargs)
        self.cooldown = cooldown
        self.memory_key = memory_key

    def tick(self, entity_id: int, memory: Memory, context: TreeContext) -> NodeState:
        current_time = time.time()
        last_run = memory.get(self.memory_key, 0.0)

        # GUARD CHECK: Is it still on cooldown?
        if current_time - last_run < self.cooldown:
            return NodeState.FAILURE  # Block execution

        # Pass execution to child
        result = self.child.tick(entity_id, memory, context)

        # If the child actually succeeded, reset the cooldown timer
        if result == NodeState.SUCCESS:
            memory.set(self.memory_key, current_time)

        return result
