"""
AI Systems - Data-Driven Decision Trees for entity behavior.

This module provides a clean, extensible system for defining AI behavior as JSON.
Each entity can have a Brain that executes a Decision Tree every turn.

The tree is composed of:
- Fallback nodes (try children until one succeeds)
- Routine nodes (execute children in sequence, fail on first failure)
- Condition nodes (check entity state)
- Action nodes (emit events for systems to handle)

No game-specific logic lives here. AI doesn't know about combat, movement, or rendering.
It just reads Memory/Registry, makes decisions, and emits events.

Example:
    # At startup, register custom nodes
    from pyrogue_engine.systems.ai import GLOBAL_REGISTRY, Memory, Brain, AISystem
    from my_game.ai import ActionSpellCast  # Custom action
    GLOBAL_REGISTRY.register("ActionSpellCast", ActionSpellCast)

    # Create an AI entity
    entity_id = registry.create_entity()
    registry.add_component(entity_id, Brain(mindset_id="smart_mage"))
    registry.add_component(entity_id, Memory())

    # Load JSON tree, system will handle it
    ai_system.update(delta_time)
"""

from .components import Memory, Brain, Faction, ScentMemory
from .decision_tree import DecisionNode, NodeState, TreeContext, Fallback, Routine
from .tree_factory import TreeFactory, NodeRegistry, GLOBAL_REGISTRY
from .system import AISystem
from .factions import FactionRegistry, Faction as FactionAlignment
from .threat_math import (
    calculate_distance,
    calculate_threat_score,
    select_highest_threat,
    rank_threats,
    ThreatScore,
    adjusted_vision_range,
    calculate_alarm_radius,
)
from .awareness_system import AwarenessSystem

# Import and register built-in condition nodes
from .conditions import (
    ConditionHasTarget,
    ConditionTargetAdjacent,
    ConditionTargetInRange,
    ConditionTargetAlive,
    ConditionSelfAlive,
    ConditionSelfHealthLow,
    ConditionMemoryKey,
    IsPhaseCondition,
)

# Import and register built-in action nodes
from .actions import (
    ActionMeleeAttack,
    ActionJPSMove,
    ActionFlowFieldMove,
    ActionWander,
    Wander3DAction,
    ActionWait,
    ActionUpdateMemory,
    DigAction,
    AutomataStepAction,
    DropPheromoneAction,
    CastSpellAction,
    BroadcastMessageAction,
)

# Register condition nodes
GLOBAL_REGISTRY.register("ConditionHasTarget", ConditionHasTarget)
GLOBAL_REGISTRY.register("ConditionTargetAdjacent", ConditionTargetAdjacent)
GLOBAL_REGISTRY.register("ConditionTargetInRange", ConditionTargetInRange)
GLOBAL_REGISTRY.register("ConditionTargetAlive", ConditionTargetAlive)
GLOBAL_REGISTRY.register("ConditionSelfAlive", ConditionSelfAlive)
GLOBAL_REGISTRY.register("ConditionSelfHealthLow", ConditionSelfHealthLow)
GLOBAL_REGISTRY.register("ConditionMemoryKey", ConditionMemoryKey)
GLOBAL_REGISTRY.register("IsPhaseCondition", IsPhaseCondition)

# Register action nodes
GLOBAL_REGISTRY.register("ActionMeleeAttack", ActionMeleeAttack)
GLOBAL_REGISTRY.register("ActionJPSMove", ActionJPSMove)
GLOBAL_REGISTRY.register("ActionFlowFieldMove", ActionFlowFieldMove)
GLOBAL_REGISTRY.register("ActionWander", ActionWander)
GLOBAL_REGISTRY.register("Wander3DAction", Wander3DAction)
GLOBAL_REGISTRY.register("ActionWait", ActionWait)
GLOBAL_REGISTRY.register("ActionUpdateMemory", ActionUpdateMemory)
GLOBAL_REGISTRY.register("DigAction", DigAction)
GLOBAL_REGISTRY.register("AutomataStepAction", AutomataStepAction)
GLOBAL_REGISTRY.register("DropPheromoneAction", DropPheromoneAction)
GLOBAL_REGISTRY.register("CastSpellAction", CastSpellAction)
GLOBAL_REGISTRY.register("BroadcastMessageAction", BroadcastMessageAction)

__all__ = [
    # Components
    "Memory",
    "Brain",
    "Faction",
    "ScentMemory",
    "FactionAlignment",
    # Decision Tree
    "DecisionNode",
    "NodeState",
    "TreeContext",
    "Fallback",
    "Routine",
    # Conditions
    "ConditionHasTarget",
    "ConditionTargetAdjacent",
    "ConditionTargetInRange",
    "ConditionTargetAlive",
    "ConditionSelfAlive",
    "ConditionSelfHealthLow",
    "ConditionMemoryKey",
    "IsPhaseCondition",
    # Actions
    "ActionMeleeAttack",
    "ActionJPSMove",
    "ActionFlowFieldMove",
    "ActionWander",
    "Wander3DAction",
    "ActionWait",
    "ActionUpdateMemory",
    "DigAction",
    "AutomataStepAction",
    "DropPheromoneAction",
    "CastSpellAction",
    "BroadcastMessageAction",
    # Factory
    "TreeFactory",
    "NodeRegistry",
    "GLOBAL_REGISTRY",
    # Factions & Threat
    "FactionRegistry",
    "FactionAlignment",
    "calculate_distance",
    "calculate_threat_score",
    "select_highest_threat",
    "rank_threats",
    "ThreatScore",
    "adjusted_vision_range",
    "calculate_alarm_radius",
    # Systems
    "AISystem",
    "AwarenessSystem",
]
