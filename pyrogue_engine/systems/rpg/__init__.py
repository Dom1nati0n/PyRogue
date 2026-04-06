"""
RPG Systems - Generic, reusable combat and character systems.

This module provides:
- Flexible stat components that work with any naming scheme
- Pure combat math (unit-testable damage calculation)
- Event-driven combat system (no tight coupling)
- Request→Validate→Dispatch action pipeline

All systems are completely decoupled from game lore:
- "RED/ORANGE/YELLOW" stats or "STR/DEX/INT" stats → engine doesn't care
- Equipment system is generic (main_hand_id, armor_id)
- Damage types are strings (Slashing, Fire, etc.)
- Action definitions are just data dictionaries
"""

# Components
from .components import (
    Health,
    Attributes,
    Defense,
    Equipment,
    CombatStats,
    ActionPoints,
)

# Pure Math
from .combat_math import (
    DamageRoll,
    calculate_damage,
    apply_damage_type_resistance,
    calculate_critical_hit,
    calculate_dodge,
    calculate_healing,
)

# Systems
from .combat_system import (
    CombatResolverSystem,
    InitiativeSystem,
    AttackIntentEvent,
    DamageTakenEvent,
    HealingAppliedEvent,
    DeathEvent,
    AttackHitEvent,
    AttackMissedEvent,
    CriticalHitEvent,
    ActionResolvedEvent,
    CombatStartedEvent,
    CombatEndedEvent,
    TurnStartedEvent,
    TurnEndedEvent,
)

# Action System
from .action_system import (
    ActionResolver,
    ActionRequest,
    ActionResult,
    ActionTargetType,
    ActionValidationError,
    ACTIONS,
)

# Effects System
from .effects import (
    EffectTemplate,
    ActiveEffects,
    ApplyEffectEvent,
    EffectExpiredEvent,
    TurnTickEvent,
    StatusEffectSystem,
)

# AP Regeneration System (Live Stepping mode only)
from .ap_regeneration import (
    APRegenerationSystem,
)

# Projectile System
from .projectile import (
    Projectile,
    Deflector,
    ProjectileSystem,
    ProjectileDestroyEvent,
)

__all__ = [
    # Components
    "Health",
    "Attributes",
    "Defense",
    "Equipment",
    "CombatStats",
    "ActionPoints",
    # Combat Math
    "DamageRoll",
    "calculate_damage",
    "apply_damage_type_resistance",
    "calculate_critical_hit",
    "calculate_dodge",
    "calculate_healing",
    # Combat System
    "CombatResolverSystem",
    "InitiativeSystem",
    "AttackIntentEvent",
    "DamageTakenEvent",
    "HealingAppliedEvent",
    "DeathEvent",
    "AttackHitEvent",
    "AttackMissedEvent",
    "CriticalHitEvent",
    "ActionResolvedEvent",
    "CombatStartedEvent",
    "CombatEndedEvent",
    "TurnStartedEvent",
    "TurnEndedEvent",
    # Action System
    "ActionResolver",
    "ActionRequest",
    "ActionResult",
    "ActionTargetType",
    "ActionValidationError",
    "ACTIONS",
    # Effects System
    "EffectTemplate",
    "ActiveEffects",
    "ApplyEffectEvent",
    "EffectExpiredEvent",
    "TurnTickEvent",
    "StatusEffectSystem",
    # AP Regeneration (Live Stepping mode)
    "APRegenerationSystem",
    # Projectile System
    "Projectile",
    "Deflector",
    "ProjectileSystem",
    "ProjectileDestroyEvent",
]
