"""
Session and Connection Events

These events form the core lifecycle of player connection, session management,
and spawning. They follow the Separation of Identity pattern:
  - Network Client ID: WebSocket connection (ephemeral, implementation detail)
  - Session ID: Persistent UUID (stored in client localStorage)
  - Entity ID: Physical avatar in ECS (integer)
"""

from pyrogue_engine.core.events.event import Event, EventPriority


class SessionEvents:
    """
    Session lifecycle event definitions.

    Usage:
        event_bus.emit(Event(
            SessionEvents.CLIENT_CONNECTED,
            metadata={"session_id": "player_7b9a..."}
        ))
    """

    # =========================================================================
    # Network Handshake (Headless Server)
    # =========================================================================

    CLIENT_CONNECTED = "session.client_connected"
    """
    Emitted when a WebSocket client connects.

    Metadata:
        session_id (str): Persistent session UUID (from client or newly generated)
        client_id (str, optional): Network connection ID (ws_001, etc.)

    Flow:
        1. Client connects to WebSocket
        2. Server checks for session token in message
        3. If no token: generate UUID, send back to client
        4. Server emits this event
        5. SessionManagementSystem handles it
    """

    CLIENT_DISCONNECTED = "session.client_disconnected"
    """
    Emitted when WebSocket connection drops or closes gracefully.

    Metadata:
        session_id (str): The session being disconnected
        reason (str, optional): "timeout", "client_closed", "error", etc.

    Result:
        SessionManagementSystem sets PlayerController.is_connected = False
        Entity remains in world (no deletion)
    """

    # =========================================================================
    # Player Spawning (SessionManagementSystem → GameMode)
    # =========================================================================

    PLAYER_SPAWN_INTENT = "session.player_spawn_intent"
    """
    Emitted by SessionManagementSystem when a new player needs to spawn.

    Metadata:
        session_id (str): The session that needs a spawn

    Listener:
        GameMode or spawn resolver system
        Determines valid spawn point and creates avatar entity
        Attaches PlayerController component with this session_id
    """

    PLAYER_RECONNECTED = "session.player_reconnected"
    """
    Emitted by SessionManagementSystem when a reconnecting player reclaims their entity.

    Metadata:
        session_id (str): The reconnecting session
        entity_id (int): The entity they're reclaiming

    Listener:
        Systems that need to reset state (reset status effects, etc.)
        Client receives full state update
    """

    # =========================================================================
    # Player Lifecycle (GameMode / Systems)
    # =========================================================================

    PLAYER_JOINED = "player.joined"
    """
    Emitted by GameMode when a new player has spawned and joined the world.

    Metadata:
        session_id (str): The session
        entity_id (int): The spawned avatar

    Listener:
        UI systems, leaderboard, game state
        Used for broadcasts ("Player X joined the game")
    """

    PLAYER_LEFT = "player.left"
    """
    Emitted by GameMode when a player's entity is destroyed or mode ends.

    Metadata:
        session_id (str): The session that left
        entity_id (int): The avatar being removed
        reason (str, optional): "disconnected", "died", "mode_ended", etc.

    Listener:
        GameMode updates player tracking
        Leaderboard updates
    """

    # =========================================================================
    # Helpers for Creating Events
    # =========================================================================

    @staticmethod
    def client_connected(session_id: str, client_id: str = None) -> Event:
        """Create a CLIENT_CONNECTED event"""
        return Event(
            SessionEvents.CLIENT_CONNECTED,
            priority=EventPriority.HIGH,
            metadata={"session_id": session_id, "client_id": client_id}
        )

    @staticmethod
    def client_disconnected(session_id: str, reason: str = None) -> Event:
        """Create a CLIENT_DISCONNECTED event"""
        return Event(
            SessionEvents.CLIENT_DISCONNECTED,
            priority=EventPriority.HIGH,
            metadata={"session_id": session_id, "reason": reason}
        )

    @staticmethod
    def player_spawn_intent(session_id: str) -> Event:
        """Create a PLAYER_SPAWN_INTENT event"""
        return Event(
            SessionEvents.PLAYER_SPAWN_INTENT,
            priority=EventPriority.HIGH,
            metadata={"session_id": session_id}
        )

    @staticmethod
    def player_reconnected(session_id: str, entity_id: int) -> Event:
        """Create a PLAYER_RECONNECTED event"""
        return Event(
            SessionEvents.PLAYER_RECONNECTED,
            priority=EventPriority.HIGH,
            metadata={"session_id": session_id, "entity_id": entity_id}
        )

    @staticmethod
    def player_joined(session_id: str, entity_id: int) -> Event:
        """Create a PLAYER_JOINED event"""
        return Event(
            SessionEvents.PLAYER_JOINED,
            priority=EventPriority.NORMAL,
            metadata={"session_id": session_id, "entity_id": entity_id}
        )

    @staticmethod
    def player_left(session_id: str, entity_id: int, reason: str = None) -> Event:
        """Create a PLAYER_LEFT event"""
        return Event(
            SessionEvents.PLAYER_LEFT,
            priority=EventPriority.NORMAL,
            metadata={"session_id": session_id, "entity_id": entity_id, "reason": reason}
        )
