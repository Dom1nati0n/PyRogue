"""
Decision Tree Core - The Node System

Defines the fundamental building blocks for Decision Trees:
- NodeState (SUCCESS, FAILURE, RUNNING)
- TreeContext (dependencies shared across all nodes)
- DecisionNode (base class for all node types)
- Fallback (try children until one succeeds)
- Routine (execute children in sequence)

Philosophy: Nodes never mutate entity state directly. They read from
Memory/Registry and emit events. The corresponding systems handle state changes.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import EventBus


class NodeState(Enum):
    """Return state of a Decision Tree node."""

    SUCCESS = "success"  # Node completed successfully
    FAILURE = "failure"  # Node failed (preconditions not met, action blocked, etc.)
    RUNNING = "running"  # Node is still executing (for multi-turn actions)


@dataclass
class TreeContext:
    """
    Holds all dependencies nodes might need.

    This avoids passing dozens of parameters to each tick() call.
    Nodes that don't need a dependency simply ignore it.

    Attributes:
        registry: ECS Registry for component queries
        event_bus: EventBus for emitting intent events
        map_system: Optional game map system (for pathfinding)
        flow_fields: Optional dict of FlowField instances by name
        custom: Optional dict for game-specific state (walkable_callback, etc.)
    """

    registry: Registry
    event_bus: EventBus
    map_system: Optional[Any] = None
    flow_fields: Optional[Dict[str, Any]] = field(default_factory=dict)
    custom: Optional[Dict[str, Any]] = field(default_factory=dict)


class DecisionNode:
    """
    Base class for all Decision Tree nodes.

    Each node has a single responsibility: read state and return SUCCESS/FAILURE/RUNNING.

    Do NOT mutate entity components directly in tick(). Instead, emit events:
    - Emit AttackIntentEvent for combat
    - Emit MovementIntentEvent for movement
    - Update Memory if tracking state

    Example:
        class ActionMeleeAttack(DecisionNode):
            def tick(self, entity_id, memory, context):
                target_id = memory.get("target_id")
                if not target_id:
                    return NodeState.FAILURE

                # Emit attack intent (CombatSystem handles the rest)
                attack = AttackIntentEvent(entity_id, target_id, 10, "Melee", "strength")
                context.event_bus.emit(attack)

                return NodeState.SUCCESS
    """

    def tick(
        self,
        entity_id: int,
        memory: "Memory",
        context: TreeContext
    ) -> NodeState:
        """
        Execute this node.

        Args:
            entity_id: The entity running this tree
            memory: The entity's Memory component (shared state)
            context: Shared dependencies (registry, event_bus, etc.)

        Returns:
            NodeState.SUCCESS, FAILURE, or RUNNING
        """
        raise NotImplementedError(f"{self.__class__.__name__}.tick() not implemented")


class Fallback(DecisionNode):
    """
    Selector: Try children in order until one succeeds.

    Returns SUCCESS on first child that doesn't return FAILURE.
    Returns FAILURE if all children fail.

    Use case:
    - "Try to attack, fallback to chase, fallback to wander"
    - "Try to see target, fallback to search, fallback to patrol"

    Example JSON:
        {
            "type": "Fallback",
            "children": [
                {"type": "ConditionTargetAdjacent"},
                {"type": "ActionMeleeAttack"},
                {"type": "ActionMoveTowardsTarget"},
                {"type": "ActionWander"}
            ]
        }
    """

    def __init__(self, children: List[DecisionNode]):
        self.children = children

    def tick(
        self,
        entity_id: int,
        memory: "Memory",
        context: TreeContext
    ) -> NodeState:
        for child in self.children:
            state = child.tick(entity_id, memory, context)
            if state != NodeState.FAILURE:
                return state
        return NodeState.FAILURE


class Routine(DecisionNode):
    """
    Sequence: Execute children in order. Stop on first failure.

    Returns SUCCESS if all children succeed.
    Returns FAILURE on first child that doesn't return SUCCESS.

    Use case:
    - "Check preconditions, then execute action"
    - "Load state, check validity, commit action"

    Example JSON:
        {
            "type": "Routine",
            "children": [
                {"type": "ConditionHasTarget"},
                {"type": "ConditionTargetAdjacent"},
                {"type": "ActionMeleeAttack"}
            ]
        }

    This will only attempt the attack if target exists AND is adjacent.
    """

    def __init__(self, children: List[DecisionNode]):
        self.children = children

    def tick(
        self,
        entity_id: int,
        memory: "Memory",
        context: TreeContext
    ) -> NodeState:
        for child in self.children:
            state = child.tick(entity_id, memory, context)
            if state != NodeState.SUCCESS:
                return state
        return NodeState.SUCCESS
