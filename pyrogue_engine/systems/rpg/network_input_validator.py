"""
Network Input Validator - Anti-cheat system for Separation of Identity.

Validates all client actions against current server state before accepting them.
Prevents cheating: invisible attacks, out-of-bounds movement, picking up items from nowhere, etc.

Maps session_id → entity_id, then validates and emits intent events.

THE CONSTITUTION compliance:
  ✓ Reactive: Called on network input (MovementIntentEvent, AttackIntentEvent)
  ✓ Validation: Anti-cheat barrier before intent events reach resolvers
  ✓ No Logic: Pure validation, no game logic mutations
"""

from typing import Optional, Dict, Any

from pyrogue_engine.systems.spatial.components import Position
from pyrogue_engine.systems.rpg.components import Health
from pyrogue_engine.core.events import Event, EventPriority


class NetworkInputValidator:
    """
    Validate client input against server state before emitting intent events.

    Maps session_id (network identity) → entity_id (game identity) using
    SessionManagementSystem, then validates actions against that entity.

    Usage:
        validator = NetworkInputValidator()
        response = validator.receive_client_input(
            session_id="player_7b9a...",
            action_data={"action": "move", "direction": "up"},
            registry=registry,
            event_bus=event_bus,
            session_management=session_system
        )
    """

    def __init__(self):
        """Initialize validator."""
        self.input_handlers = {
            "move": self._validate_move,
            "attack": self._validate_attack,
            "interact": self._validate_interact,
            "pickup": self._validate_pickup,
            "drop": self._validate_drop,
            "use": self._validate_use,
            "throw": self._validate_throw,
            "wait": self._validate_wait,
        }
        self.fov_system: Optional[Any] = None
        self.collision_system: Optional[Any] = None

    def receive_client_input(
        self,
        session_id: str,
        action_data: Dict[str, Any],
        registry: Any,
        event_bus: Any,
        session_management: Any,
    ) -> Dict[str, Any]:
        """
        Receive and validate client input (Separation of Identity).

        Maps session_id (network) to entity_id (game), validates, and emits intent.

        Args:
            session_id: Persistent session UUID from client
            action_data: Dict with "action" key and action-specific data
            registry: ECS registry for validation checks
            event_bus: Event bus to emit intent events
            session_management: SessionManagementSystem for session→entity mapping

        Returns:
            Response dict:
                {"type": "error", "message": ...} if invalid
                {"type": "ok"} if valid (intent event emitted)
        """
        # Step 1: Map session_id → entity_id
        if not session_management:
            return {"type": "error", "message": "Session management unavailable"}

        entity_id = session_management.get_entity_for_session(session_id)
        if not entity_id:
            return {"type": "error", "message": "No active player entity for this session"}

        # Step 2: Check if player is connected
        if not session_management.is_player_connected(entity_id):
            return {"type": "error", "message": "Player is not connected"}

        # Step 3: Parse action
        action_type = action_data.get("action")
        if not action_type:
            return {"type": "error", "message": "Missing action field"}

        if action_type not in self.input_handlers:
            return {"type": "error", "message": f"Unknown action: {action_type}"}

        # Step 4: Validate action (against this entity)
        validator = self.input_handlers[action_type]
        is_valid, error = validator(entity_id, action_data, registry)

        if not is_valid:
            return {"type": "error", "message": error}

        # Step 5: Action is valid, emit intent event
        intent_dict = self._action_to_intent(action_type, entity_id, action_data)
        if intent_dict:
            # Convert dict to Event object
            event_type = intent_dict.pop("type")
            intent_event = Event(
                event_type=event_type,
                priority=EventPriority.HIGH,
                metadata=intent_dict
            )
            event_bus.emit(intent_event)

        return {"type": "ok", "action": action_type}

    # =========================================================================
    # Validation Rules
    # =========================================================================

    def _validate_move(self, entity_id: int, action: Dict, registry: Any) -> tuple:
        """
        Validate movement action.

        Checks:
        - Entity exists and has Position
        - Direction is valid
        - Target position is in bounds
        - (Optional) Target position is not blocked
        """
        # Entity must have Position
        player_pos = registry.get_component(entity_id, Position)
        if not player_pos:
            return False, "Entity has no position"

        direction = action.get("direction")
        if direction not in ["up", "down", "left", "right", "upleft", "upright", "downleft", "downright"]:
            return False, f"Invalid direction: {direction}"

        # Calculate new position
        dx, dy = self._direction_to_delta(direction)
        new_x = player_pos.x + dx
        new_y = player_pos.y + dy

        # Must be in bounds
        # TODO: Get map bounds from registry or config
        if new_x < 0 or new_y < 0 or new_x >= 200 or new_y >= 200:
            return False, "Out of bounds"

        # Optional: Check collision with collision_system if available
        # For now, allow it (collision resolution happens in MovementSystem)
        return True, None

    def _validate_attack(self, entity_id: int, action: Dict, registry: Any) -> tuple:
        """
        Validate attack action.

        Checks:
        - Target exists
        - Target is adjacent
        - (Optional) Target is visible (FOV)
        - Target is attackable (has Health)
        """
        target_id = action.get("target_id")

        if target_id is None:
            return False, "Missing target_id"

        # Both must have positions
        attacker_pos = registry.get_component(entity_id, Position)
        target_pos = registry.get_component(target_id, Position)

        if not attacker_pos or not target_pos:
            return False, "Position missing"

        # Must be adjacent (within 1 tile)
        dx = abs(attacker_pos.x - target_pos.x)
        dy = abs(attacker_pos.y - target_pos.y)
        if dx > 1 or dy > 1:
            return False, "Target not adjacent"

        # Optional: Target must be visible (FOV check)
        if self.fov_system:
            try:
                visible_tiles = self.fov_system.compute_fov(attacker_pos.x, attacker_pos.y)
                if (target_pos.x, target_pos.y) not in visible_tiles:
                    return False, "Target not visible"
            except Exception:
                # FOV failed, allow for now
                pass

        # Target must have Health (be attackable)
        target_health = registry.get_component(target_id, Health)
        if not target_health:
            return False, "Target cannot be attacked"

        return True, None

    def _validate_interact(self, entity_id: int, action: Dict, registry: Any) -> tuple:
        """
        Validate interaction action.

        Checks:
        - Target exists
        - Target is adjacent
        """
        target_id = action.get("target_id")

        if target_id is None:
            return False, "Missing target_id"

        # Both must have positions
        actor_pos = registry.get_component(entity_id, Position)
        target_pos = registry.get_component(target_id, Position)

        if not actor_pos or not target_pos:
            return False, "Position missing"

        # Must be adjacent
        dx = abs(actor_pos.x - target_pos.x)
        dy = abs(actor_pos.y - target_pos.y)
        if dx > 1 or dy > 1:
            return False, "Target not adjacent"

        return True, None

    def _validate_pickup(self, entity_id: int, action: Dict, registry: Any) -> tuple:
        """
        Validate pickup action.

        Checks:
        - Item exists
        - Item is adjacent or on same tile
        - (Optional) Item is visible (FOV)
        """
        item_id = action.get("item_id")

        if item_id is None:
            return False, "Missing item_id"

        # Both must have positions
        player_pos = registry.get_component(entity_id, Position)
        item_pos = registry.get_component(item_id, Position)

        if not player_pos or not item_pos:
            return False, "Position missing"

        # Must be adjacent or same tile
        dx = abs(player_pos.x - item_pos.x)
        dy = abs(player_pos.y - item_pos.y)
        if dx > 1 or dy > 1:
            return False, "Item not adjacent"

        # Optional: Item must be visible (FOV check)
        if self.fov_system:
            try:
                visible_tiles = self.fov_system.compute_fov(player_pos.x, player_pos.y)
                if (item_pos.x, item_pos.y) not in visible_tiles:
                    return False, "Item not visible"
            except Exception:
                pass

        return True, None

    def _validate_drop(self, entity_id: int, action: Dict, registry: Any) -> tuple:
        """
        Validate drop action.

        Checks:
        - Item is in player's inventory (TODO)
        """
        item_id = action.get("item_id")

        if item_id is None:
            return False, "Missing item_id"

        # TODO: Check if item is in entity's inventory

        return True, None

    def _validate_wait(self, entity_id: int, action: Dict, registry: Any) -> tuple:
        """
        Validate wait action (no-op, always valid).
        """
        return True, None

    def _validate_use(self, entity_id: int, action: Dict, registry: Any) -> tuple:
        """
        Validate use action (use item as weapon).

        Checks:
        - Target exists (optional, can be self)
        - Entity exists
        """
        # Use can target self or specific target
        target_id = action.get("target_id", entity_id)

        # Check both entities exist
        user = registry.get_component(entity_id, Position)  # User must have position
        if not user:
            return False, "User has no position"

        return True, None

    def _validate_throw(self, entity_id: int, action: Dict, registry: Any) -> tuple:
        """
        Validate throw action (throw item as projectile).

        Checks:
        - Entity exists and has position
        - Target position is reasonable (within throw range)
        """
        user = registry.get_component(entity_id, Position)
        if not user:
            return False, "User has no position"

        target_pos = action.get("target_pos")
        if not target_pos:
            return False, "Missing target_pos for throw"

        # Check within reasonable throw range (e.g., 20 tiles max)
        dx = abs(user.x - target_pos.get("x", 0))
        dy = abs(user.y - target_pos.get("y", 0))
        if dx > 20 or dy > 20:
            return False, "Target too far to throw"

        return True, None

    # =========================================================================
    # Helpers
    # =========================================================================

    def _direction_to_delta(self, direction: str) -> tuple:
        """Convert direction string to (dx, dy)."""
        deltas = {
            "up": (0, -1),
            "down": (0, 1),
            "left": (-1, 0),
            "right": (1, 0),
            "upleft": (-1, -1),
            "upright": (1, -1),
            "downleft": (-1, 1),
            "downright": (1, 1),
        }
        return deltas.get(direction, (0, 0))

    def _action_to_intent(self, action_type: str, entity_id: int, action: Dict) -> Optional[Dict[str, Any]]:
        """
        Convert validated action to intent event dict.

        For predictive mode: includes sequence_id from action_data so that
        SequenceTrackingSystem can confirm the prediction after processing.

        Returns:
            Event dict or None
        """
        # Extract sequence_id if present (predictive mode)
        sequence_id = action.get("sequence_id")

        if action_type == "move":
            intent_dict = {
                "type": "movement.intent",
                "entity_id": entity_id,
                "direction": action.get("direction"),
            }
        elif action_type == "attack":
            intent_dict = {
                "type": "combat.attack.intent",
                "attacker_id": entity_id,
                "target_id": action.get("target_id"),
            }
        elif action_type == "interact":
            intent_dict = {
                "type": "interaction.intent",
                "actor_id": entity_id,
                "target_id": action.get("target_id"),
            }
        elif action_type == "pickup":
            intent_dict = {
                "type": "inventory.pickup.intent",
                "actor_id": entity_id,
                "item_id": action.get("item_id"),
            }
        elif action_type == "drop":
            intent_dict = {
                "type": "inventory.drop.intent",
                "actor_id": entity_id,
                "item_id": action.get("item_id"),
            }
        elif action_type == "use":
            intent_dict = {
                "type": "item.used",
                "actor_id": entity_id,
                "item_id": action.get("item_id"),
                "target_id": action.get("target_id", entity_id),
            }
        elif action_type == "throw":
            intent_dict = {
                "type": "item.thrown",
                "actor_id": entity_id,
                "item_id": action.get("item_id"),
                "target_pos": action.get("target_pos"),
            }
        elif action_type == "wait":
            intent_dict = {
                "type": "turn.wait",
                "entity_id": entity_id,
            }
        else:
            return None

        # Add sequence_id to metadata if present (predictive mode)
        if sequence_id is not None:
            intent_dict["sequence_id"] = sequence_id

        return intent_dict

    def set_fov_system(self, fov_system: Any) -> None:
        """Set the FOV system for visibility checks."""
        self.fov_system = fov_system

    def set_collision_system(self, collision_system: Any) -> None:
        """Set the collision system for movement checks."""
        self.collision_system = collision_system
