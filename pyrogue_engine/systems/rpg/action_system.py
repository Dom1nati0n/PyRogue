"""
Action System - Request → Validate → Dispatch pipeline.

Following your action_system_advanced.py pattern:
1. Parse ActionRequest
2. Validate preconditions (actor, target, resources)
3. Resolve targets (single, AOE, etc.)
4. Execute (fire dispatcher events)
5. Return ActionResult

Completely decoupled from ECS state. Systems listen to emitted events.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

from pyrogue_engine.core.events import EventBus
from pyrogue_engine.core.ecs import Registry
from .components import ActionPoints, Health
from .combat_system import AttackIntentEvent


class ActionTargetType(Enum):
    """How an action targets entities"""
    SINGLE = "single"
    AOE_BURST = "aoe_burst"
    AOE_CONE = "aoe_cone"
    SELF = "self"


class ActionValidationError(Exception):
    """Raised when action validation fails"""
    pass


@dataclass
class ActionRequest:
    """
    A request to perform a combat action.

    Attributes:
        actor_id: Entity performing the action
        action_key: Action identifier (e.g., "HEAVY_SLASH")
        target_id: Primary target entity ID
        payload: Action data (base_damage, damage_type, etc.)
    """
    actor_id: int
    action_key: str
    target_id: int
    payload: dict = field(default_factory=dict)


@dataclass
class ActionResult:
    """Outcome of executing an action"""
    success: bool = False
    message: str = ""
    error: str = ""
    targets_hit: List[int] = field(default_factory=list)
    damage_dealt: int = 0

    def __repr__(self) -> str:
        if self.success:
            return f"<ActionResult: {self.damage_dealt} dmg to {len(self.targets_hit)} targets>"
        return f"<ActionResult: FAILED - {self.error}>"


# ---------------------------------------------------------------------------
# Action Definitions (Game-Specific)
# ---------------------------------------------------------------------------
# This would be populated by your game. Each action defines:
#   - ap_cost: Action Point cost
#   - base_damage: Damage value
#   - damage_type: Type of damage
#   - stat_key: Which stat to use for modifier
# ---------------------------------------------------------------------------

ACTIONS = {
    "LIGHT_SLASH": {
        "ap_cost": 1,
        "base_damage": 5,
        "damage_type": "Slashing",
        "stat_key": "agility",  # or "ORANGE" or "dexterity"
    },
    "HEAVY_SLASH": {
        "ap_cost": 3,
        "base_damage": 14,
        "damage_type": "Slashing",
        "stat_key": "strength",
    },
    "PUNCH": {
        "ap_cost": 1,
        "base_damage": 5,
        "damage_type": "Bludgeoning",
        "stat_key": "strength",
    },
}


# ---------------------------------------------------------------------------
# Action Resolver
# ---------------------------------------------------------------------------

class ActionResolver:
    """
    Validates and executes combat actions.

    Pipeline:
    1. Validate actor exists and can act
    2. Validate action is legal
    3. Validate target exists and is valid
    4. Validate actor has resources (AP)
    5. Execute: emit AttackIntentEvent
    6. Deduct costs
    7. Return ActionResult
    """

    def __init__(self, registry: Registry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus

    def resolve_action(self, request: ActionRequest) -> ActionResult:
        """
        Process an action request through the validation and execution pipeline.

        Args:
            request: ActionRequest

        Returns:
            ActionResult with success/failure and details
        """
        try:
            # Step 1: Validate actor
            actor_ap = self._validate_actor(request.actor_id)

            # Step 2: Validate action
            action_data = self._validate_action(request.action_key)

            # Step 3: Validate target
            self._validate_target(request.target_id)

            # Step 4: Check resources (AP)
            if not actor_ap.can_afford(action_data["ap_cost"]):
                raise ActionValidationError(
                    f"Not enough AP: need {action_data['ap_cost']}, have {actor_ap.current}"
                )

            # Step 5: Execute action
            result = self._execute_action(request, action_data)

            # Step 6: Deduct costs
            actor_ap.spend(action_data["ap_cost"])

            return result

        except ActionValidationError as e:
            return ActionResult(success=False, error=str(e))
        except Exception as e:
            return ActionResult(success=False, error=f"Unexpected error: {str(e)}")

    def _validate_actor(self, actor_id: int) -> ActionPoints:
        """Ensure actor exists and has AP component"""
        ap = self.registry.get_component(actor_id, ActionPoints)
        if ap is None:
            raise ActionValidationError(f"Actor {actor_id} not found or has no AP")
        return ap

    def _validate_action(self, action_key: str) -> dict:
        """Ensure action exists in database"""
        action = ACTIONS.get(action_key)
        if action is None:
            raise ActionValidationError(f"Unknown action: {action_key}")
        return action

    def _validate_target(self, target_id: int) -> None:
        """Ensure target exists and is alive"""
        health = self.registry.get_component(target_id, Health)
        if health is None:
            raise ActionValidationError(f"Target {target_id} not found")
        if health.is_dead():
            raise ActionValidationError(f"Target {target_id} is dead")

    def _execute_action(self, request: ActionRequest, action_data: dict) -> ActionResult:
        """
        Execute the action: emit event(s) for resolution.

        The actual damage calculation and application happens in CombatResolverSystem
        which listens to AttackIntentEvent.
        """
        # Create attack intent event
        attack_event = AttackIntentEvent(
            attacker_id=request.actor_id,
            target_id=request.target_id,
            base_damage=action_data["base_damage"],
            damage_type=action_data["damage_type"],
            stat_key=action_data["stat_key"],
        )

        # Emit to event bus (CombatResolverSystem will handle it)
        self.event_bus.emit(attack_event)

        # Return success result
        return ActionResult(
            success=True,
            message=f"Action {request.action_key} executed",
            targets_hit=[request.target_id],
        )
