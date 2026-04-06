"""
Replication System - Network State Synchronization

Captures replicated game events and builds per-client state packets.
Implements FOV-aware culling to scale to 100+ players without bandwidth collapse.

Architecture:
    1. Systems emit events marked with replicate=True
    2. ReplicationSystem subscribes to all events (via wildcard)
    3. For replicated events, compute which clients need them (FOV-based)
    4. Build per-client state packet
    5. Emit ReplicationPacket event for network layer to broadcast

THE CONSTITUTION Compliance:
    ✓ Reactive: Listens to replicated events
    ✓ Intent-Driven: Emits ReplicationPacket (what was replicated), not mutations
    ✓ Decoupled: Systems have zero awareness of replication
    ✓ Configurable: FOV radius, delta compression in config.json

Example Flow:
    GameSystem: emit(DamageTakenEvent(target=42, damage=10), replicate=True)
                    ↓
    ReplicationSystem hears it
                    ↓
    Checks: event.replicate=True? YES
    Computes: Which players can see entity 42? (FOV check)
    Finds: session_id="player_7b9a" has avatar nearby
                    ↓
    Emits: ReplicationPacket for that session
                    ↓
    Network layer sends to that client only
"""

import time
from typing import Dict, Set, Optional, Any

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import Event, EventBus, EventPriority
from pyrogue_engine.core.config import ServerConfig
from pyrogue_engine.core.tags import Tags
from pyrogue_engine.systems.spatial.components import Position
from pyrogue_engine.systems.rpg.components import PlayerController


class ReplicationSystem:
    """
    Captures replicated game events and builds per-client state packets.

    Subscribes to all events, filters for replicate=True, applies FOV culling,
    and emits per-client ReplicationPacket events for the network layer.
    """

    def __init__(self, registry: Registry, event_bus: EventBus, config: ServerConfig):
        """
        Initialize replication system.

        Args:
            registry: ECS registry (for entity queries)
            event_bus: Event bus (subscribe to all events)
            config: Server config (FOV radius, compression settings)
        """
        self.registry = registry
        self.event_bus = event_bus
        self.config = config

        # Per-client state snapshots (for delta compression in future)
        self.client_snapshots: Dict[str, Dict[int, Dict[str, Any]]] = {}
        # session_id → {entity_id: {component_data}}

        # Track which entities each client knows about (Delta Sync protocol)
        # session_id → Set[entity_id]
        # Used to determine Spawn/Update/Despawn packets
        self.client_known_entities: Dict[str, Set[int]] = {}

        # Subscribe to ALL events (capture replicated ones)
        # Use wildcard to hear everything
        self.event_bus.subscribe("*", self._on_event)

        print(
            f"[ReplicationSystem] Initialized: "
            f"mode={config.replication.mode}, "
            f"radius={config.replication.player_view_radius}, "
            f"delta_compression={config.replication.use_delta_compression}"
        )

    def _on_event(self, event: Event):
        """
        Called for EVERY event on the bus (subscribed via wildcard).

        Filter by event.replicate flag and process replicated events.

        Delta Sync Strategy:
        - If entity is in client's known_entities, send a tiny "update" packet (just position)
        - If entity is NOT known, skip it (client will get full data via FOV sync when it enters view)
        - If a PLAYER moves, trigger FOV recalculation (spawn/despawn check)
        """
        # Skip if replication disabled or event not marked for replication
        if not self.config.replication.enabled or not event.replicate:
            return

        # Only send deltas for events with a source entity (movement, damage, etc.)
        if event.source_entity_id is None:
            return

        entity_id = event.source_entity_id

        # Special case: if a player moved, recalculate their FOV (spawn/despawn entities)
        # Check if this entity is a player
        controller = self.registry.get_component(entity_id, PlayerController)
        if controller and controller.is_connected:
            # Player moved! Recalculate their FOV
            self._sync_player_fov(controller.session_id, entity_id)
            return  # FOV sync handles all the packets

        # Determine which clients need this event
        affected_sessions = self._get_affected_sessions(event)

        if not affected_sessions:
            return

        # Build per-client delta packets
        for session_id in affected_sessions:
            known = self.client_known_entities.get(session_id, set())

            # Only send update if client already knows about this entity
            # (If not known, they'll get full spawn data when it enters their FOV)
            if entity_id in known:
                pos = self.registry.get_component(entity_id, Position)

                # Send minimal update packet (just position)
                packet = {
                    "type": "update",
                    "id": entity_id,
                    "p": [pos.x, pos.y] if pos else None
                }
                self._emit_replication_packet(session_id, packet)

    def _get_affected_sessions(self, event: Event) -> Set[str]:
        """
        Determine which player sessions should receive this event.

        Rules:
        - scope="global" → all connected players
        - scope="local" or None + source_entity_id → only players in FOV of that entity
        - No source_entity_id → all connected players (safe default)

        Returns:
            Set of session_id strings
        """
        # Global scope: send to all connected players
        if event.scope == "global":
            return self._all_connected_sessions()

        # Local scope: only players who can see source_entity_id
        if event.source_entity_id is not None:
            return self._compute_visible_to(event.source_entity_id)

        # Default: no scope specified, but replicate=True → all players
        return self._all_connected_sessions()

    def _compute_visible_to(self, entity_id: int) -> Set[str]:
        """
        Compute which player sessions can see entity_id based on FOV.

        Uses simple rectangle distance check (Chebyshev distance / max(dx, dy)).
        Could be upgraded to shadowcasting for true FOV.

        Args:
            entity_id: Entity to check visibility for

        Returns:
            Set of session_ids that can see this entity
        """
        visible_sessions = set()

        # Get entity position
        entity_pos = self.registry.get_component(entity_id, Position)
        if not entity_pos:
            return visible_sessions

        # Check each connected player
        for player_entity, controller in self.registry.view(PlayerController):
            # Skip disconnected players
            if not controller.is_connected:
                continue

            # Get player position
            player_pos = self.registry.get_component(player_entity, Position)
            if not player_pos:
                continue

            # Compute 3D distance (Chebyshev: max(dx, dy, dz) = cubic distance)
            dx = abs(entity_pos.x - player_pos.x)
            dy = abs(entity_pos.y - player_pos.y)
            dz = abs(entity_pos.z - player_pos.z)
            distance = max(dx, dy, dz)

            # Is entity within player's view radius?
            radius = self.config.replication.player_view_radius
            if self.config.replication.include_adjacent_tiles:
                # FOV + 1-tile border for smooth visibility edges
                radius += 1

            if distance <= radius:
                visible_sessions.add(controller.session_id)

        return visible_sessions

    def _all_connected_sessions(self) -> Set[str]:
        """Get all connected player sessions."""
        sessions = set()
        for entity_id, controller in self.registry.view(PlayerController):
            if controller.is_connected:
                sessions.add(controller.session_id)
        return sessions

    def _sync_player_fov(self, session_id: str, player_entity_id: int) -> None:
        """
        Delta Sync: Compare player's old FOV to new FOV and emit Spawn/Despawn packets.

        Called when a player moves. Computes what entered/left their view and sends
        minimal packets:
        - "spawn": Full entity data (position + tags) for newly visible entities
        - "despawn": Just entity ID for entities that left view
        - Updates are handled separately via _on_event

        Args:
            session_id: Player's session ID
            player_entity_id: Player's entity ID
        """
        if session_id not in self.client_known_entities:
            self.client_known_entities[session_id] = set()

        known = self.client_known_entities[session_id]

        # Compute which entities are currently visible to this player
        player_pos = self.registry.get_component(player_entity_id, Position)
        if not player_pos:
            return

        currently_visible = set()

        # Check all entities in the world (simple iteration; could optimize with spatial hash)
        for entity_id in self.registry._alive_entities:
            if entity_id == player_entity_id:
                continue  # Don't replicate player to themselves

            entity_pos = self.registry.get_component(entity_id, Position)
            if not entity_pos:
                continue

            # Compute 3D distance (Chebyshev distance with Z)
            dx = abs(entity_pos.x - player_pos.x)
            dy = abs(entity_pos.y - player_pos.y)
            dz = abs(entity_pos.z - player_pos.z)
            distance = max(dx, dy, dz)

            # Is entity within FOV?
            radius = self.config.replication.player_view_radius
            if self.config.replication.include_adjacent_tiles:
                radius += 1

            if distance <= radius:
                currently_visible.add(entity_id)

        # 1. SPAWN: Entities that just entered FOV
        new_entities = currently_visible - known
        for entity_id in new_entities:
            pos = self.registry.get_component(entity_id, Position)
            tags_comp = self.registry.get_component(entity_id, Tags)

            # Build spawn packet with full data (position + tags)
            packet = {
                "type": "spawn",
                "id": entity_id,
                "p": [pos.x, pos.y] if pos else None,
                "t": tags_comp.tag_names() if tags_comp else []
            }
            self._emit_replication_packet(session_id, packet)
            known.add(entity_id)

        # 2. DESPAWN: Entities that left FOV
        lost_entities = known - currently_visible
        for entity_id in lost_entities:
            packet = {"type": "despawn", "id": entity_id}
            self._emit_replication_packet(session_id, packet)
            known.remove(entity_id)

    def _build_replication_packet(self, session_id: str, event: Event) -> Dict[str, Any]:
        """
        Build client-specific replication packet from event.

        Args:
            session_id: Target client session
            event: Event to replicate

        Returns:
            Packet dict to send to client
        """
        # Simple mode: send entire event data
        # Could add delta compression here in future

        packet = {
            "type": event.event_type,
            "metadata": event.metadata or {},
            "timestamp_ns": time.time_ns(),
        }

        # Optional: Add delta compression info (future enhancement)
        if self.config.replication.use_delta_compression:
            packet["is_delta"] = False  # TODO: compute actual deltas

        return packet

    def _emit_replication_packet(self, session_id: str, packet: Dict[str, Any]) -> None:
        """
        Emit a replication packet event for network layer to send to client.

        Args:
            session_id: Target client session
            packet: State packet to send
        """
        self.event_bus.emit(Event(
            event_type="replication.packet",
            priority=EventPriority.NORMAL,
            replicate=False,  # Don't re-replicate this
            metadata={
                "session_id": session_id,
                "packet": packet,
            }
        ))

    def get_player_view_radius(self) -> int:
        """Get configured player view radius."""
        return self.config.replication.player_view_radius

    def is_delta_compression_enabled(self) -> bool:
        """Check if delta compression is enabled."""
        return self.config.replication.use_delta_compression
