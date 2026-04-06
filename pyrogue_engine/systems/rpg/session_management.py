"""
Session Management System

Handles the complete lifecycle of player sessions:
- Connection/disconnection
- Spawn intent for new players
- Reconnection for returning players
- Graceful handling of network volatility

This is the bridge between the network layer and the game engine.
All session state lives in PlayerController components in the ECS.

THE CONSTITUTION compliance:
  ✓ Reactive: Listens to CLIENT_CONNECTED / CLIENT_DISCONNECTED events
  ✓ Intent-Driven: Emits PLAYER_SPAWN_INTENT, PLAYER_RECONNECTED
  ✓ Tag-Driven: Spawn config lives in JSON, not code (handled by GameMode)
  ✓ No Client Logic: This is pure game state
"""

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import Event, EventBus, SessionEvents
from pyrogue_engine.systems.rpg.components import PlayerController


class SessionManagementSystem:
    """
    Manages player sessions and their mapping to entities.

    One-way responsibility flow:
      Network → CLIENT_CONNECTED event → This system checks registry
                      ↓
              Does session exist?
                ↙           ↘
            YES             NO
            ↓               ↓
        PLAYER_RECONNECTED  PLAYER_SPAWN_INTENT
        (flag entity ready) (GameMode resolves spawn)
    """

    def __init__(self, registry: Registry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus

        # Subscribe to network events
        self.event_bus.subscribe(SessionEvents.CLIENT_CONNECTED, self._on_client_connected)
        self.event_bus.subscribe(SessionEvents.CLIENT_DISCONNECTED, self._on_client_disconnected)

    def _on_client_connected(self, event: Event):
        """
        Handle client connection.

        If this session already owns an entity (reconnect), flag it as connected.
        If this is a brand new session (new player), emit spawn intent.
        """
        metadata = event.metadata or {}
        session_id = metadata.get("session_id")

        if not session_id:
            print("[SessionManagementSystem] ERROR: CLIENT_CONNECTED missing session_id")
            return

        # Query: does this session already own an entity?
        existing_entity = self._find_entity_by_session(session_id)

        if existing_entity:
            # Welcome back
            controller = self.registry.get_component(existing_entity, PlayerController)
            if controller:
                controller.is_connected = True
                controller.reconnect_timer = 0.0

                # Notify game systems
                self.event_bus.emit(SessionEvents.player_reconnected(session_id, existing_entity))
                print(f"[SessionManagementSystem] Player {session_id} reconnected as entity {existing_entity}")
        else:
            # Brand new player
            self.event_bus.emit(SessionEvents.player_spawn_intent(session_id))
            print(f"[SessionManagementSystem] New player {session_id} needs spawn")

    def _on_client_disconnected(self, event: Event):
        """
        Handle client disconnection.

        Find the entity owned by this session and flag it as disconnected.
        The entity remains in the world and can be targeted, damaged, or
        controlled by AI if the mode supports it.
        """
        metadata = event.metadata or {}
        session_id = metadata.get("session_id")
        reason = metadata.get("reason", "unknown")

        if not session_id:
            print("[SessionManagementSystem] ERROR: CLIENT_DISCONNECTED missing session_id")
            return

        # Find entity
        entity_id = self._find_entity_by_session(session_id)
        if entity_id:
            controller = self.registry.get_component(entity_id, PlayerController)
            if controller:
                controller.is_connected = False
                print(f"[SessionManagementSystem] Player {session_id} (entity {entity_id}) disconnected ({reason})")
        else:
            print(f"[SessionManagementSystem] Disconnect event for unknown session {session_id}")

    def _find_entity_by_session(self, session_id: str) -> int | None:
        """
        Query the registry to find the entity owned by a session.

        Returns:
            Entity ID (int) if found, None otherwise.
        """
        for entity_id, controller in self.registry.view(PlayerController):
            if controller.session_id == session_id:
                return entity_id
        return None

    def is_player_connected(self, entity_id: int) -> bool:
        """Check if a player entity is currently connected."""
        controller = self.registry.get_component(entity_id, PlayerController)
        return controller.is_connected if controller else False

    def get_session_for_entity(self, entity_id: int) -> str | None:
        """Get the session_id that owns an entity."""
        controller = self.registry.get_component(entity_id, PlayerController)
        return controller.session_id if controller else None

    def get_entity_for_session(self, session_id: str) -> int | None:
        """Get the entity_id owned by a session (if any)."""
        return self._find_entity_by_session(session_id)
