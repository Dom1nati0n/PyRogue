"""
Sequence Tracking System - Predictive Mode Confirmation

For predictive mode (client-side prediction), clients send inputs with sequence IDs.
The server processes these inputs and must confirm back to the client which predictions
were actually validated (to let them know if they predicted correctly or need to correct).

Architecture:
    1. Client sends: {"action": "move_up", "sequence_id": 42}
    2. NetworkInputValidator validates and emits: MovementIntentEvent(direction="up", sequence_id=42)
    3. MovementSystem moves the entity
    4. SequenceTrackingSystem listens for intent events with sequence_id
    5. Updates PlayerController.last_processed_sequence_id = 42
    6. ReplicationSystem includes last_processed_sequence_id in next FOV packet
    7. Client receives confirmation that prediction #42 was validated

THE CONSTITUTION Compliance:
    ✓ Reactive: Listens to intent events (movement.intent, combat.attack.intent, etc)
    ✓ Intent-Driven: Tracks sequence_id from the intent metadata
    ✓ Pure: Only updates PlayerController, no mutations of other state
    ✓ Predictive-Mode-Only: Only active when config.gameplay.sync_model == "predictive"
"""

from typing import Any, Optional

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import Event, EventBus
from pyrogue_engine.systems.rpg.components import PlayerController


class SequenceTrackingSystem:
    """
    Confirms client input sequence IDs after they are processed by the server.

    Only used in predictive mode. Listens for intent events that include sequence_id
    in their metadata, then updates PlayerController.last_processed_sequence_id so that
    the ReplicationSystem can include confirmation in the next FOV packet.

    Usage:
        sequence_tracker = SequenceTrackingSystem(registry, event_bus, config)
        # SequenceTrackingSystem will automatically listen and confirm sequence IDs
    """

    def __init__(self, registry: Registry, event_bus: EventBus, config: Any):
        """
        Initialize sequence tracking system.

        Args:
            registry: ECS registry (for entity queries and component updates)
            event_bus: Event bus (subscribe to intent events)
            config: Server config (to check if predictive mode is enabled)
        """
        self.registry = registry
        self.event_bus = event_bus
        self.config = config

        # Only subscribe if predictive mode is enabled
        if self.config.gameplay.sync_model == "predictive":
            # Listen to all intent events
            self.event_bus.subscribe("movement.intent", self._on_movement_intent)
            self.event_bus.subscribe("combat.attack.intent", self._on_combat_intent)
            self.event_bus.subscribe("inventory.pickup.intent", self._on_inventory_intent)
            self.event_bus.subscribe("inventory.drop.intent", self._on_inventory_intent)
            self.event_bus.subscribe("interaction.intent", self._on_interaction_intent)
            self.event_bus.subscribe("turn.wait", self._on_wait_intent)

            print("[SequenceTrackingSystem] Initialized (predictive mode enabled)")
        else:
            print(f"[SequenceTrackingSystem] Disabled (sync_model={config.gameplay.sync_model})")

    # =========================================================================
    # Intent Event Handlers
    # =========================================================================

    def _on_movement_intent(self, event: Event) -> None:
        """Track sequence_id for movement intent."""
        self._track_sequence_id(event, "entity_id")

    def _on_combat_intent(self, event: Event) -> None:
        """Track sequence_id for combat intent."""
        self._track_sequence_id(event, "attacker_id")

    def _on_inventory_intent(self, event: Event) -> None:
        """Track sequence_id for inventory intent."""
        self._track_sequence_id(event, "actor_id")

    def _on_interaction_intent(self, event: Event) -> None:
        """Track sequence_id for interaction intent."""
        self._track_sequence_id(event, "actor_id")

    def _on_wait_intent(self, event: Event) -> None:
        """Track sequence_id for wait intent."""
        self._track_sequence_id(event, "entity_id")

    # =========================================================================
    # Core Logic
    # =========================================================================

    def _track_sequence_id(self, event: Event, entity_id_key: str) -> None:
        """
        Generic handler to track sequence_id from any intent event.

        Extracts sequence_id from event metadata, finds the PlayerController
        for the actor entity, and confirms the sequence_id.

        Args:
            event: Intent event (MovementIntentEvent, etc.)
            entity_id_key: Key name in event.metadata for the actor entity_id
                          (e.g., "entity_id", "attacker_id", "actor_id")
        """
        metadata = event.metadata or {}
        entity_id = metadata.get(entity_id_key)
        sequence_id = metadata.get("sequence_id")

        # Only track if sequence_id was provided (predictive mode)
        if sequence_id is None:
            return

        if entity_id is None:
            print(f"[SequenceTrackingSystem] WARNING: {event.event_type} missing {entity_id_key}")
            return

        # Get PlayerController for this entity
        controller = self.registry.get_component(entity_id, PlayerController)
        if not controller:
            # Not a player entity, ignore
            return

        # Confirm the sequence_id
        controller.last_processed_sequence_id = sequence_id

        # Telemetry
        if sequence_id % 10 == 0:  # Log every 10th
            print(
                f"[SequenceTrackingSystem] Confirmed sequence {sequence_id} "
                f"for session {controller.session_id[:8]}..."
            )
