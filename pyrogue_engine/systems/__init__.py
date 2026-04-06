"""
Systems - Reactive game systems organized by domain

This module contains reusable, battle-tested game systems for pyrogue_engine.
All systems follow the reactive pattern: listen to events and respond.

Subsystems:
- spatial: Movement, FOV, collision detection, direction management
- rpg: Combat, damage calculation, status effects, action handling
- ai: Decision trees, NPC behavior, threat assessment, awareness

All systems are completely decoupled from each other and communicate only
through the event bus. See THE_CONSTITUTION.md for design principles.

Example:
    from pyrogue_engine.systems.spatial import PerceptionSystem, Position
    from pyrogue_engine.systems.rpg import CombatResolverSystem, Health
    from pyrogue_engine.systems.ai import AISystem, Brain
"""

# Import spatial systems and components
from .spatial import (
    # Components
    Position,
    Velocity,
    SubpixelAccumulator,
    Movement,
    Facing,
    Vision,
    VisibleTiles,
    # Systems
    PerceptionSystem,
    KinematicMovementSystem,
    DirectionalFacingSystem,
    CollisionSystem,
    # Functions
    compute_shadowcast_fov,
    can_move_to,
    can_move_diagonal,
    CollisionEvent,
)

# Import RPG systems and components
from .rpg import (
    # Components
    Health,
    Attributes,
    Defense,
    Equipment,
    CombatStats,
    ActionPoints,
    # Systems
    CombatResolverSystem,
    InitiativeSystem,
    StatusEffectSystem,
    ActionResolver,
    # Events
    AttackIntentEvent,
    DamageTakenEvent,
    HealingAppliedEvent,
    DeathEvent,
    ApplyEffectEvent,
    EffectExpiredEvent,
    TurnTickEvent,
    # Combat Math
    DamageRoll,
    calculate_damage,
    apply_damage_type_resistance,
    calculate_critical_hit,
    calculate_dodge,
    calculate_healing,
    # Action System
    ActionRequest,
    ActionResult,
    ActionTargetType,
    ActionValidationError,
    EffectTemplate,
    ActiveEffects,
    ACTIONS,
)

# Import AI systems and components
from .ai import (
    # Components
    Memory,
    Brain,
    Faction,
    ScentMemory,
    # Decision Trees
    DecisionNode,
    NodeState,
    TreeContext,
    Fallback,
    Routine,
    # Factories
    TreeFactory,
    NodeRegistry,
    GLOBAL_REGISTRY,
    # Systems
    AISystem,
    AwarenessSystem,
    # Threat Calculation
    calculate_distance,
    calculate_threat_score,
    select_highest_threat,
    rank_threats,
    ThreatScore,
    adjusted_vision_range,
    calculate_alarm_radius,
    # Factions
    FactionRegistry,
    FactionAlignment,
    # Built-in Conditions
    ConditionHasTarget,
    ConditionTargetAdjacent,
    ConditionTargetInRange,
    ConditionTargetAlive,
    ConditionSelfAlive,
    ConditionSelfHealthLow,
    ConditionMemoryKey,
    # Built-in Actions
    ActionMeleeAttack,
    ActionJPSMove,
    ActionFlowFieldMove,
    ActionWander,
    ActionWait,
    ActionUpdateMemory,
)

__all__ = [
    # Spatial
    "Position",
    "Velocity",
    "SubpixelAccumulator",
    "Movement",
    "Facing",
    "Vision",
    "VisibleTiles",
    "PerceptionSystem",
    "KinematicMovementSystem",
    "DirectionalFacingSystem",
    "CollisionSystem",
    "compute_shadowcast_fov",
    "can_move_to",
    "can_move_diagonal",
    "CollisionEvent",
    # RPG
    "Health",
    "Attributes",
    "Defense",
    "Equipment",
    "CombatStats",
    "ActionPoints",
    "CombatResolverSystem",
    "InitiativeSystem",
    "StatusEffectSystem",
    "ActionResolver",
    "AttackIntentEvent",
    "DamageTakenEvent",
    "HealingAppliedEvent",
    "DeathEvent",
    "ApplyEffectEvent",
    "EffectExpiredEvent",
    "TurnTickEvent",
    "DamageRoll",
    "calculate_damage",
    "apply_damage_type_resistance",
    "calculate_critical_hit",
    "calculate_dodge",
    "calculate_healing",
    "ActionRequest",
    "ActionResult",
    "ActionTargetType",
    "ActionValidationError",
    "EffectTemplate",
    "ActiveEffects",
    "ACTIONS",
    # AI
    "Memory",
    "Brain",
    "Faction",
    "ScentMemory",
    "DecisionNode",
    "NodeState",
    "TreeContext",
    "Fallback",
    "Routine",
    "TreeFactory",
    "NodeRegistry",
    "GLOBAL_REGISTRY",
    "AISystem",
    "AwarenessSystem",
    "calculate_distance",
    "calculate_threat_score",
    "select_highest_threat",
    "rank_threats",
    "ThreatScore",
    "adjusted_vision_range",
    "calculate_alarm_radius",
    "FactionRegistry",
    "FactionAlignment",
    "ConditionHasTarget",
    "ConditionTargetAdjacent",
    "ConditionTargetInRange",
    "ConditionTargetAlive",
    "ConditionSelfAlive",
    "ConditionSelfHealthLow",
    "ConditionMemoryKey",
    "ActionMeleeAttack",
    "ActionJPSMove",
    "ActionFlowFieldMove",
    "ActionWander",
    "ActionWait",
    "ActionUpdateMemory",
]
