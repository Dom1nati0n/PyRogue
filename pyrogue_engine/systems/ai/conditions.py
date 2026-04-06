"""
Condition Nodes - Decision Tree Logic

Condition nodes read entity state and return SUCCESS/FAILURE.
They never mutate state or emit events.

Use conditions in Routine nodes to guard actions:
    {
        "type": "Routine",
        "children": [
            {"type": "ConditionHasTarget"},
            {"type": "ConditionTargetAdjacent"},
            {"type": "ActionMeleeAttack"}
        ]
    }

This ensures ActionMeleeAttack only runs if both conditions pass.
"""

from .decision_tree import DecisionNode, NodeState, TreeContext
from pyrogue_engine.systems.spatial.components import Position
from pyrogue_engine.systems.rpg.components import Health


class ConditionHasTarget(DecisionNode):
    """Check if entity has a target in memory."""

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        if memory.has("target_id"):
            return NodeState.SUCCESS
        return NodeState.FAILURE


class ConditionTargetAdjacent(DecisionNode):
    """Check if target is in an adjacent tile (8-directional, distance <= 1)."""

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        target_id = memory.get("target_id")
        if not target_id:
            return NodeState.FAILURE

        my_pos = context.registry.get_component(entity_id, Position)
        target_pos = context.registry.get_component(target_id, Position)

        if not my_pos or not target_pos:
            return NodeState.FAILURE

        # 8-directional: adjacent if dx and dy are both <= 1
        dx = abs(my_pos.x - target_pos.x)
        dy = abs(my_pos.y - target_pos.y)

        if dx <= 1 and dy <= 1 and not (dx == 0 and dy == 0):
            return NodeState.SUCCESS

        return NodeState.FAILURE


class ConditionTargetInRange(DecisionNode):
    """Check if target is within a distance range."""

    def __init__(self, max_distance: int = 5):
        self.max_distance = max_distance

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        target_id = memory.get("target_id")
        if not target_id:
            return NodeState.FAILURE

        my_pos = context.registry.get_component(entity_id, Position)
        target_pos = context.registry.get_component(target_id, Position)

        if not my_pos or not target_pos:
            return NodeState.FAILURE

        # Chebyshev distance (max of dx, dy) for diagonals
        distance = max(abs(my_pos.x - target_pos.x), abs(my_pos.y - target_pos.y))

        if distance <= self.max_distance:
            return NodeState.SUCCESS

        return NodeState.FAILURE


class ConditionTargetAlive(DecisionNode):
    """Check if target entity is still alive."""

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        target_id = memory.get("target_id")
        if not target_id:
            return NodeState.FAILURE

        health = context.registry.get_component(target_id, Health)
        if not health:
            return NodeState.FAILURE

        if health.is_alive():
            return NodeState.SUCCESS

        return NodeState.FAILURE


class ConditionSelfAlive(DecisionNode):
    """Check if this entity is still alive."""

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        health = context.registry.get_component(entity_id, Health)
        if not health:
            return NodeState.FAILURE

        if health.is_alive():
            return NodeState.SUCCESS

        return NodeState.FAILURE


class ConditionSelfHealthLow(DecisionNode):
    """Check if this entity's health is below a threshold (percentage)."""

    def __init__(self, threshold: float = 0.3):
        """threshold: 0.0 to 1.0 (0.3 = 30%)"""
        self.threshold = threshold

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        health = context.registry.get_component(entity_id, Health)
        if not health:
            return NodeState.FAILURE

        health_percentage = health.current / health.maximum if health.maximum > 0 else 0
        if health_percentage < self.threshold:
            return NodeState.SUCCESS

        return NodeState.FAILURE


class ConditionMemoryKey(DecisionNode):
    """Check if a key exists in memory."""

    def __init__(self, key: str):
        self.key = key

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        if memory.has(self.key):
            return NodeState.SUCCESS
        return NodeState.FAILURE


class IsPhaseCondition(DecisionNode):
    """
    Gates bee behaviors based on the global Generation Phase.

    The server cycles through phases:
    - Phase 1: Excavation (Drunkard + Architect bees carve tunnels)
    - Phase 2: Decoration (optional cosmetic pass)
    - Phase 3: Topology (Scout bees map the maze with pheromones)
    - Phase 4: Placement (Quartermaster spawns points of interest)

    Parameters:
    - target_phase (int): The phase this node should allow (1, 2, 3, 4)

    Reads:
    - Global state: context.custom["generation_phase"] or registry global state

    Returns:
    - SUCCESS if current phase matches target_phase
    - FAILURE otherwise
    """

    def __init__(self, target_phase: int = 1, **kwargs):
        self.target_phase = target_phase

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        # Check current generation phase from context
        current_phase = context.custom.get("generation_phase", 1) if context.custom else 1

        if current_phase == self.target_phase:
            return NodeState.SUCCESS

        return NodeState.FAILURE
