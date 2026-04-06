"""
Game Mode System - Event-driven rule systems for game sessions

Modes handle:
- Player session tracking (join/leave)
- Score and leaderboards
- Global event triggers at specific times/conditions
- Mode transitions (round end, objective complete, etc.)
- Message broadcasting to all players
- Host assignment and reassignment
- Player spawning (resolved from PLAYER_SPAWN_INTENT)

Modes subscribe to events and emit in response. No procedural ticking from main loop.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from pyrogue_engine.core.events import Event, EventBus, SessionEvents
from pyrogue_engine.core.ecs import Registry


@dataclass
class PlayerSession:
    """Per-player session state within a game mode"""
    entity_id: int
    join_time_ms: int
    score: int = 0
    is_active: bool = True


@dataclass
class Scoreboard:
    """Tracks scores for all players"""
    scores: Dict[int, int] = field(default_factory=dict)

    def add_score(self, entity_id: int, points: int):
        self.scores[entity_id] = self.scores.get(entity_id, 0) + points

    def get_leaderboard(self) -> List[tuple]:
        """Returns [(entity_id, score), ...] sorted descending by score"""
        return sorted(self.scores.items(), key=lambda x: x[1], reverse=True)


class GameMode(ABC):
    """
    Abstract base class for game rule systems.

    Subclasses implement specific rulesets (survival, round-based, cooperative, etc.)
    All timing and progression is event-driven.
    """

    def __init__(self, registry: Registry, event_bus: EventBus, entity_factory=None):
        self.registry = registry
        self.event_bus = event_bus
        self.entity_factory = entity_factory  # Optional: for spawning player avatars

        self.players: Dict[int, PlayerSession] = {}
        self.scoreboard = Scoreboard()
        self.message_log: List[str] = []
        self.host_id: Optional[int] = None
        self.elapsed_ms: int = 0

        # Subscribe to game events
        self.event_bus.subscribe("timer.tick", self._on_timer_tick)
        self.event_bus.subscribe("game.turn", self._on_turn)
        self.event_bus.subscribe("player.joined", self._on_player_joined)
        self.event_bus.subscribe("player.left", self._on_player_left)
        self.event_bus.subscribe("combat.kill", self._on_kill)

        # Subscribe to session/spawn events (Separation of Identity)
        self.event_bus.subscribe(SessionEvents.PLAYER_SPAWN_INTENT, self._on_spawn_intent)
        self.event_bus.subscribe(SessionEvents.PLAYER_RECONNECTED, self._on_player_reconnected)

    # =========================================================================
    # Event Handlers - Subclasses can override to extend behavior
    # =========================================================================

    def _on_timer_tick(self, event: Event):
        """Called by TimerSystem each frame. Track elapsed time and check transitions."""
        self.elapsed_ms += event.delta_ms

        # Check for mode-specific transitions
        next_mode = self._check_transition()
        if next_mode:
            self.event_bus.emit(Event("mode.transition", next_mode=next_mode))

    def _on_turn(self, event: Event):
        """Called each game turn. Override for turn-based events."""
        pass

    def _on_player_joined(self, event: Event):
        """Called when a player joins the session."""
        metadata = event.metadata or {}
        entity_id = metadata.get("entity_id")

        if not entity_id:
            return

        session = PlayerSession(entity_id, self.elapsed_ms)
        self.players[entity_id] = session
        self.scoreboard.scores[entity_id] = 0

        # Assign host if none exists
        if not self.host_id:
            self.host_id = entity_id

        self.broadcast_message(f"Player {entity_id} joined")

        # Emit replicated event so all clients see updated player count
        self.event_bus.emit(Event(
            event_type="mode.player_count_changed",
            replicate=True,
            scope="global",
            metadata={"count": len(self.players)}
        ))

    def _on_player_left(self, event: Event):
        """Called when a player leaves the session."""
        metadata = event.metadata or {}
        entity_id = metadata.get("entity_id")

        if not entity_id:
            return

        self.players.pop(entity_id, None)
        self.scoreboard.scores.pop(entity_id, None)

        # Reassign host if the host left
        if self.host_id == entity_id:
            remaining = list(self.players.keys())
            if remaining:
                self.host_id = remaining[0]
                self.broadcast_message(f"New host assigned: Player {self.host_id}")
            else:
                self.host_id = None
                self.broadcast_message("No players remaining")
                self.event_bus.emit(Event("mode.end", replicate=True, scope="global"))

        self.broadcast_message(f"Player {entity_id} left")

        # Emit replicated event
        self.event_bus.emit(Event(
            event_type="mode.player_count_changed",
            replicate=True,
            scope="global",
            metadata={"count": len(self.players)}
        ))

    def _on_kill(self, event: Event):
        """Called when a kill occurs. Award points to attacker."""
        attacker_id = event.attacker_id
        if attacker_id in self.players:
            self.scoreboard.add_score(attacker_id, 100)
            self.broadcast_message(f"Player {attacker_id} +100 points")

    def _on_spawn_intent(self, event: Event):
        """
        Called when a new player needs to spawn (Separation of Identity).

        The SessionManagementSystem emitted this because a new session connected.
        This mode now resolves where/how to spawn.
        """
        metadata = event.metadata or {}
        session_id = metadata.get("session_id")

        if not session_id:
            return

        # Delegate to subclass spawn resolver
        spawn_result = self._resolve_spawn(session_id)
        if spawn_result:
            entity_id, x, y = spawn_result
            # Attach PlayerController to bridge session → entity
            from pyrogue_engine.systems.rpg.components import PlayerController
            self.registry.add_component(entity_id, PlayerController(session_id=session_id))

            # Announce the join
            self.event_bus.emit(SessionEvents.player_joined(session_id, entity_id))

    def _on_player_reconnected(self, event: Event):
        """Called when a reconnecting player reclaims their entity."""
        metadata = event.metadata or {}
        session_id = metadata.get("session_id")
        entity_id = metadata.get("entity_id")

        if not session_id or not entity_id:
            return

        # Subclass can override for reconnect-specific logic
        self._handle_reconnect(session_id, entity_id)

    # =========================================================================
    # Public Interface
    # =========================================================================

    def broadcast_message(self, message: str):
        """Send message to all players"""
        self.message_log.append(message)
        # Mark as replicated so all connected clients receive it (global scope)
        self.event_bus.emit(Event(
            event_type="ui.message",
            replicate=True,
            scope="global",
            metadata={"text": message, "source": "game_mode"}
        ))

    def get_game_state(self) -> dict:
        """Return current game state for UI/rendering"""
        return {
            "mode_name": self.__class__.__name__,
            "elapsed_time_ms": self.elapsed_ms,
            "active_players": len(self.players),
            "host_id": self.host_id,
            "leaderboard": self.scoreboard.get_leaderboard(),
            "message_log": self.message_log[-20:],  # Last 20 messages
        }

    # =========================================================================
    # Abstract Methods - Subclasses must implement
    # =========================================================================

    @abstractmethod
    def _check_transition(self) -> Optional[str]:
        """
        Return the next mode name if transition should occur, None otherwise.
        Called every timer tick.
        """
        pass

    @abstractmethod
    def _resolve_spawn(self, session_id: str) -> Optional[Tuple[int, int, int]]:
        """
        Resolve spawn for a new player (Separation of Identity).

        Called when PLAYER_SPAWN_INTENT is emitted (new session connecting).
        Subclass determines valid spawn point and creates entity.

        Args:
            session_id: The session that needs to spawn

        Returns:
            (entity_id, x, y) if spawn successful
            None if spawn failed (e.g., map full, no valid spawn point)

        Implementation guide:
            1. Check player count (enforce max players if needed)
            2. Find a valid spawn point (from tags config or hardcoded list)
            3. Use entity factory to create avatar: factory.create_from_template(...)
            4. Position entity at spawn point
            5. Return (entity_id, x, y)

        The caller will:
            - Attach PlayerController(session_id=session_id) to the entity
            - Emit PLAYER_JOINED event
        """
        pass

    def _handle_reconnect(self, session_id: str, entity_id: int):
        """
        Optional: Handle reconnection-specific logic.

        Called when PLAYER_RECONNECTED is emitted (returning player reclaims entity).
        Override to reset status effects, restore health, etc.

        Args:
            session_id: The session reconnecting
            entity_id: The entity they reclaimed

        Default: Do nothing (entity remains as-is)
        """
        pass


class SurvivalMode(GameMode):
    """
    Survival mode - accumulate score until time limit or all players leave.
    Infinite duration if time_limit_ms is 0.

    Spawn behavior: Players spawn at predefined spawn points (configurable in JSON).
    """

    # Default spawn points (override in JSON config)
    DEFAULT_SPAWN_POINTS = [
        (10, 10), (15, 10), (20, 10),
        (10, 15), (15, 15), (20, 15),
    ]

    def __init__(
        self,
        registry: Registry,
        event_bus: EventBus,
        time_limit_ms: int = 0,
        entity_factory=None,
        spawn_points: List[Tuple[int, int]] = None,
    ):
        super().__init__(registry, event_bus, entity_factory)
        self.time_limit_ms = time_limit_ms
        self.spawn_points = spawn_points or self.DEFAULT_SPAWN_POINTS
        self.next_spawn_index = 0
        self.broadcast_message("Survival Mode started")

    def _check_transition(self) -> Optional[str]:
        if self.time_limit_ms > 0 and self.elapsed_ms >= self.time_limit_ms:
            self.broadcast_message("Time limit reached")
            return "endgame"
        return None

    def _resolve_spawn(self, session_id: str) -> Optional[Tuple[int, int, int]]:
        """
        Spawn a new player at the next available spawn point.

        Returns:
            (entity_id, x, y) if spawn successful, None otherwise
        """
        if not self.entity_factory:
            print(f"[SurvivalMode] Cannot spawn: no entity_factory configured")
            return None

        # Check max players (optional - comment out to allow unlimited)
        max_players = 100
        if len(self.players) >= max_players:
            self.broadcast_message(f"Server full ({max_players} players)")
            return None

        # Find next spawn point (round-robin)
        if not self.spawn_points:
            self.broadcast_message("No spawn points configured")
            return None

        x, y = self.spawn_points[self.next_spawn_index % len(self.spawn_points)]
        self.next_spawn_index += 1

        try:
            # Use factory to spawn player avatar
            entity_id = self.entity_factory.spawn_creature("player_avatar", x, y)
            return (entity_id, x, y)
        except Exception as e:
            print(f"[SurvivalMode] Spawn failed for {session_id}: {e}")
            return None


class RoundBasedMode(GameMode):
    """
    Round-based mode - fixed number of rounds with duration per round.
    Automatically transitions after final round.

    Spawn behavior: Players can join between rounds or in the first round.
    """

    DEFAULT_SPAWN_POINTS = [
        (10, 10), (15, 10), (20, 10),
        (10, 15), (15, 15), (20, 15),
    ]

    def __init__(
        self,
        registry: Registry,
        event_bus: EventBus,
        max_rounds: int = 3,
        round_duration_ms: int = 60000,
        entity_factory=None,
        spawn_points: List[Tuple[int, int]] = None,
    ):
        super().__init__(registry, event_bus, entity_factory)
        self.max_rounds = max_rounds
        self.current_round = 1
        self.round_duration_ms = round_duration_ms
        self.round_start_time_ms = 0
        self.spawn_points = spawn_points or self.DEFAULT_SPAWN_POINTS
        self.next_spawn_index = 0

        self.broadcast_message(f"Round {self.current_round}/{self.max_rounds} started")

    def _on_timer_tick(self, event: Event):
        """Override to track round progression"""
        super()._on_timer_tick(event)

        elapsed_this_round = self.elapsed_ms - self.round_start_time_ms
        if elapsed_this_round >= self.round_duration_ms and self.current_round < self.max_rounds:
            self.current_round += 1
            self.round_start_time_ms = self.elapsed_ms
            self.broadcast_message(f"Round {self.current_round}/{self.max_rounds} started")

    def _check_transition(self) -> Optional[str]:
        if self.current_round >= self.max_rounds:
            elapsed_this_round = self.elapsed_ms - self.round_start_time_ms
            if elapsed_this_round >= self.round_duration_ms:
                self.broadcast_message("All rounds complete")
                return "endgame"
        return None

    def _resolve_spawn(self, session_id: str) -> Optional[Tuple[int, int, int]]:
        """Spawn player at next available spawn point"""
        if not self.entity_factory:
            return None

        if len(self.players) >= 100:
            self.broadcast_message("Server full")
            return None

        if not self.spawn_points:
            return None

        x, y = self.spawn_points[self.next_spawn_index % len(self.spawn_points)]
        self.next_spawn_index += 1

        try:
            entity_id = self.entity_factory.spawn_creature("player_avatar", x, y)
            return (entity_id, x, y)
        except Exception as e:
            print(f"[RoundBasedMode] Spawn failed: {e}")
            return None


class CooperativeMode(GameMode):
    """
    Cooperative mode - shared party objective and score.
    Players work together toward a common goal.

    Spawn behavior: All players spawn at a central meeting point.
    """

    DEFAULT_SPAWN_POINTS = [
        (15, 15), (16, 15), (14, 15),
        (15, 16), (15, 14), (16, 16),
    ]

    def __init__(
        self,
        registry: Registry,
        event_bus: EventBus,
        objective_count: int = 5,
        entity_factory=None,
        spawn_points: List[Tuple[int, int]] = None,
    ):
        super().__init__(registry, event_bus, entity_factory)
        self.party_score = 0
        self.objectives_complete = 0
        self.objective_count = objective_count
        self.spawn_points = spawn_points or self.DEFAULT_SPAWN_POINTS
        self.next_spawn_index = 0

        self.broadcast_message(f"Cooperative Mode: Complete {objective_count} objectives")

    def _on_kill(self, event: Event):
        """In coop, kills contribute to party score"""
        self.party_score += 50
        self.broadcast_message(f"Party +50 points (Total: {self.party_score})")

    def _check_transition(self) -> Optional[str]:
        if self.objectives_complete >= self.objective_count:
            self.broadcast_message("All objectives complete")
            return "endgame"
        return None

    def _resolve_spawn(self, session_id: str) -> Optional[Tuple[int, int, int]]:
        """Spawn player at central meeting point"""
        if not self.entity_factory:
            return None

        if len(self.players) >= 100:
            return None

        if not self.spawn_points:
            return None

        x, y = self.spawn_points[self.next_spawn_index % len(self.spawn_points)]
        self.next_spawn_index += 1

        try:
            entity_id = self.entity_factory.spawn_creature("player_avatar", x, y)
            return (entity_id, x, y)
        except Exception as e:
            print(f"[CooperativeMode] Spawn failed: {e}")
            return None


class GameModeManager:
    """
    Manages game mode lifecycle and transitions.
    Handles loading, unloading, and switching between mode implementations.
    """

    def __init__(self, registry: Registry, event_bus: EventBus, entity_factory=None):
        self.registry = registry
        self.event_bus = event_bus
        self.entity_factory = entity_factory  # Optional: for player spawning
        self.current_mode: Optional[GameMode] = None

        # Register available modes
        self.modes = {
            "survival": SurvivalMode,
            "rounds": RoundBasedMode,
            "cooperative": CooperativeMode,
        }

        # Listen for transition requests
        self.event_bus.subscribe("mode.transition", self._on_transition_request)

    def load_mode(self, mode_name: str, **kwargs) -> bool:
        """
        Load a new game mode.

        Args:
            mode_name: Name of mode to load
            **kwargs: Arguments to pass to mode constructor

        Returns:
            True if successful, False if mode not found
        """
        if mode_name not in self.modes:
            return False

        # Cleanup old mode
        if self.current_mode:
            self.current_mode.broadcast_message("Mode ending")

        # Load new mode (pass entity_factory if available)
        mode_class = self.modes[mode_name]
        if self.entity_factory and "entity_factory" not in kwargs:
            kwargs["entity_factory"] = self.entity_factory

        self.current_mode = mode_class(self.registry, self.event_bus, **kwargs)

        # Notify systems to load world state
        self.event_bus.emit(Event("world.load", mode=mode_name))

        return True

    def _on_transition_request(self, event: Event):
        """Handle mode transition requests from current mode"""
        next_mode = event.next_mode
        self.load_mode(next_mode)

    def add_player(self, entity_id: int) -> bool:
        """Add player to current mode"""
        if not self.current_mode:
            return False

        # Check player limit (optional - implement as needed)
        self.event_bus.emit(Event("player.joined", entity_id=entity_id))
        return True

    def remove_player(self, entity_id: int):
        """Remove player from current mode"""
        self.event_bus.emit(Event("player.left", entity_id=entity_id))

    def get_game_state(self) -> dict:
        """Get current game state for rendering"""
        if self.current_mode:
            return self.current_mode.get_game_state()
        return {}
