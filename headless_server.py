#!/usr/bin/env python
"""
Headless Game Server - Separation of Identity + Replication

Runs the pure game engine and connects web clients via WebSocket.
Implements three-layer ID mapping + FOV-aware replication.

Architecture:
  Input Pipeline:  session_id → entity_id → intent events → game systems
  Output Pipeline: game events → replication filter → per-client packets → network

Flow:
  1. Client connects with session_id (persistent, localStorage)
  2. SessionManagementSystem maps session_id → entity_id
  3. Client sends actions (validated anti-cheat before intent)
  4. Game systems process intents reactively
  5. Events marked replicate=True flow through ReplicationSystem
  6. ReplicationSystem applies FOV culling (only nearby players see)
  7. Per-client packets emitted for network layer to broadcast

Replication modes (config.json):
  - full_state: Broadcast all entities (< 10 players)
  - fov_culled: FOV-aware visibility (100+ players)
  - delta_compressed: Only changed fields (advanced optimization)

Engine is completely decoupled from networking.
"""

import asyncio
import queue
import sys
import threading
import time
import uuid
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import websockets
except ImportError:
    print("ERROR: websockets library not found. Install with: pip install websockets")
    sys.exit(1)


class SimulationThread(threading.Thread):
    """
    Dedicated simulation thread running the engine at a fixed tick rate.

    Implements the Accumulator Pattern with support for three network sync modes:
    - authoritative: Process all available inputs, tick immediately
    - lockstep: Wait for inputs from all connected players before ticking
    - predictive: Process inputs with sequence IDs for client-side prediction validation

    Architecture:
        Input Queue (thread-safe) → _drain_inputs() → _process_frame() → engine.update(tick_rate)
        Accumulator grows as: accumulator += delta_time * config.gameplay.simulation_speed
        Ticks when: accumulator >= config.gameplay.tick_rate
        GIL yielded: time.sleep(0.001) at loop end
    """

    # Lockstep timeout: if a player hasn't sent input after this long, force tick anyway
    MAX_LOCKSTEP_DELAY = 0.5

    def __init__(
        self,
        registry: Any,
        event_bus: Any,
        config: Any,
        validator: Any,
        session_mgmt: Any,
        input_queue: queue.Queue,
        event_class: Any,
    ):
        super().__init__(daemon=True)
        self.registry = registry
        self.event_bus = event_bus
        self.config = config
        self.validator = validator
        self.session_mgmt = session_mgmt
        self.input_queue = input_queue
        self.Event = event_class

        # Accumulator state
        self.accumulator = 0.0
        self.last_time = time.perf_counter()
        self.current_frame = 0

        # Lockstep tracking: frame_number → {session_id: has_input}
        self.lockstep_frame_inputs: Dict[int, Dict[str, bool]] = {}
        self.lockstep_frame_times: Dict[int, float] = {}

        # Telemetry
        self.tick_count = 0
        self.inputs_processed = 0
        self.last_telemetry_time = time.perf_counter()

        print(
            f"[SimulationThread] Initialized: "
            f"tick_rate={config.gameplay.tick_rate}s, "
            f"sync_model={config.gameplay.sync_model}, "
            f"speed={config.gameplay.simulation_speed}x"
        )

    def run(self) -> None:
        """
        Main simulation loop using accumulator pattern.

        Maintains a fixed tick rate regardless of network latency or hardware variance.
        Strictly enforces: accumulator += delta * simulation_speed, then while accumulator >= tick_rate.
        """
        try:
            print("[SimulationThread] Starting main loop")

            self.last_time = time.perf_counter()

            while True:
                # Measure elapsed time since last iteration
                now = time.perf_counter()
                delta = now - self.last_time
                self.last_time = now

                # Apply simulation speed multiplier
                accumulator_delta = delta * self.config.gameplay.simulation_speed
                self.accumulator += accumulator_delta

                # Process all accumulated ticks
                while self.accumulator >= self.config.gameplay.tick_rate:
                    self._process_frame()
                    self.accumulator -= self.config.gameplay.tick_rate
                    self.current_frame += 1
                    self.tick_count += 1

                # Telemetry every 60 ticks
                if self.tick_count % 60 == 0:
                    self._log_telemetry()

                # Yield GIL to allow asyncio WebSocket thread to run
                time.sleep(0.001)

        except KeyboardInterrupt:
            print("[SimulationThread] Interrupted")
        except Exception as e:
            print(f"[SimulationThread] ERROR: {e}")
            import traceback
            traceback.print_exc()

    def _process_frame(self) -> None:
        """
        Process a single engine tick.

        Flow:
        1. Check lockstep readiness (if lockstep mode enabled)
        2. Drain inputs from queue (validates and emits intent events)
        3. Emit world.tick event (triggers all system.update() methods)
        4. Telemetry tracking

        Sync modes:
        - authoritative: Always proceed, tick immediately with available inputs
        - lockstep: Wait for all connected players or timeout, then tick
        - predictive: Tick with inputs, pass sequence_id through intent event metadata
        """
        # Step 1: Lockstep validation (if enabled)
        if self.config.gameplay.sync_model == "lockstep":
            if not self._check_lockstep_ready():
                # Not ready yet (continue main loop without ticking)
                return

        # Step 2: Drain and validate inputs from queue
        # This automatically emits MovementIntentEvent, AttackIntentEvent, etc. to event_bus
        inputs = self._drain_inputs()

        # Step 3: Emit world tick event for all per-frame systems
        # Systems like MovementSystem, AISystem, APRegenerationSystem listen for this
        self.event_bus.emit(
            self.Event(
                event_type="world.tick",
                metadata={
                    "delta_time": self.config.gameplay.tick_rate,
                    "frame": self.current_frame,
                    "inputs_count": len(inputs),
                },
            )
        )

        # Step 4: Telemetry tracking
        if inputs:
            self.inputs_processed += len(inputs)

    def _drain_inputs(self) -> list:
        """
        Pull all available inputs from the queue and deduplicate per session.

        Returns list of validated input packets ready for engine processing.
        Implements Gotcha #2 fix: deduplicates inputs per session_id (keeps most recent).
        """
        # Group inputs by session_id, keep only the most recent per session
        latest_per_session: Dict[str, Dict[str, Any]] = {}

        while True:
            try:
                input_packet = self.input_queue.get_nowait()
                session_id = input_packet.get("session_id")

                if session_id:
                    # Keep only the most recent input for this session (discard older duplicates)
                    latest_per_session[session_id] = input_packet

            except queue.Empty:
                break  # No more inputs

        # Validate and return deduplicated inputs
        validated_inputs = []
        for session_id, input_data in latest_per_session.items():
            result = self.validator.receive_client_input(
                session_id=session_id,
                action_data=input_data,
                registry=self.registry,
                event_bus=self.event_bus,
                session_management=self.session_mgmt,
            )

            if result.get("type") == "ok":
                validated_inputs.append((session_id, input_data))

        return validated_inputs

    def _check_lockstep_ready(self) -> bool:
        """
        Check if all connected players have submitted inputs for the current frame.

        Implements Gotcha #1 fix: enforces MAX_LOCKSTEP_DELAY timeout to prevent
        one lagging player from holding the entire server hostage.

        Returns:
            True if ready to tick (either all inputs present or timeout exceeded)
            False if still waiting for inputs (continue loop without ticking)
        """
        from pyrogue_engine.systems.rpg.components import PlayerController

        # Get list of currently connected players
        connected_sessions = set()
        for entity_id, controller in self.registry.view(PlayerController):
            if controller.is_connected:
                connected_sessions.add(controller.session_id)

        if not connected_sessions:
            # No players, tick anyway
            return True

        # Initialize frame tracking if needed
        if self.current_frame not in self.lockstep_frame_inputs:
            self.lockstep_frame_inputs[self.current_frame] = {
                sid: False for sid in connected_sessions
            }
            self.lockstep_frame_times[self.current_frame] = time.perf_counter()

        # Check if we have inputs from all connected players
        frame_inputs = self.lockstep_frame_inputs[self.current_frame]
        frame_start_time = self.lockstep_frame_times[self.current_frame]
        time_waiting = time.perf_counter() - frame_start_time

        # Check for timeouts (Gotcha #1 mitigation)
        if time_waiting > self.MAX_LOCKSTEP_DELAY:
            missing = [sid for sid, has_input in frame_inputs.items() if not has_input]
            print(
                f"[SimulationThread] Lockstep timeout (frame {self.current_frame}): "
                f"missing inputs from {len(missing)} player(s). Forcing tick anyway."
            )
            return True

        # Check if all players have submitted
        all_ready = all(frame_inputs.values())
        return all_ready

    def _log_telemetry(self) -> None:
        """Log tick rate and queue statistics."""
        now = time.perf_counter()
        elapsed = now - self.last_telemetry_time
        ticks_per_sec = 60 / elapsed if elapsed > 0 else 0
        queue_size = self.input_queue.qsize()

        print(
            f"[SimulationThread] Tick {self.tick_count:6d} | "
            f"Rate {ticks_per_sec:6.1f} Hz | "
            f"Accumulator {self.accumulator:.3f} | "
            f"Queue {queue_size:3d} | "
            f"Inputs/frame {self.inputs_processed // 60 if self.inputs_processed > 0 else 0:3d}"
        )

        self.last_telemetry_time = now


async def run_server():
    """Main server loop with Separation of Identity + Replication."""
    try:
        # Import pyrogue_engine systems
        from pyrogue_engine.core.ecs import Registry
        from pyrogue_engine.core.events import EventBus, SessionEvents, Event
        from pyrogue_engine.core.config import ServerConfig
        from pyrogue_engine.systems.rpg.network_input_validator import NetworkInputValidator
        from pyrogue_engine.systems.rpg.session_management import SessionManagementSystem
        from pyrogue_engine.systems.rpg.sequence_tracking import SequenceTrackingSystem
        from pyrogue_engine.systems.replication import ReplicationSystem

        print("=" * 70)
        print("PyRogue Headless Server (Separation of Identity + Replication)")
        print("=" * 70)

        # Load server config
        config = ServerConfig.load("config.json")
        print(f"[*] {config}")

        # Setup engine core
        event_bus = EventBus()
        registry = Registry()
        print("[*] ECS initialized")

        # Setup session management (input bridge: network → entity)
        session_mgmt = SessionManagementSystem(registry, event_bus)
        print("[*] Session management initialized")

        # Setup input validator (maps session_id → entity_id, anti-cheat)
        validator = NetworkInputValidator()
        print("[*] Network input validator initialized")

        # Setup replication system (output pipeline: events → clients)
        replication = None
        if config.replication.enabled:
            replication = ReplicationSystem(registry, event_bus, config)
            print("[*] Replication system initialized")

        # Setup sequence tracking system (predictive mode confirmation)
        sequence_tracker = SequenceTrackingSystem(registry, event_bus, config)
        print("[*] Sequence tracking system initialized")

        # Load templates and setup entity factory (universal spawner)
        from pyrogue_engine.core.tags import TagManager
        from pyrogue_engine.entities.template_registry import TemplateRegistry
        from pyrogue_engine.entities.entity_factory import EntityFactory
        from pyrogue_engine.systems.game.mode import GameModeManager

        tag_manager = TagManager("pyrogue_engine/core/tags/tags.json")
        print("[*] Tag system loaded")

        template_registry = TemplateRegistry()
        template_registry.load_creatures("templates/entities/creatures.json")
        template_registry.load_items("templates/items/items.json")
        template_registry.load_tiles("templates/entities/tiles.json")
        print("[*] Entity templates loaded")

        entity_factory = EntityFactory(registry, event_bus, tag_manager, template_registry)
        print("[*] Entity factory created (universal spawner)")

        mode_manager = GameModeManager(registry, event_bus, entity_factory=entity_factory)
        mode_manager.load_mode("survival")  # Start in survival mode
        print("[*] Game mode manager initialized (survival mode loaded)")

        # Create input queue (thread-safe bridge between network and simulation)
        input_queue: queue.Queue = queue.Queue()
        print("[*] Input queue created")

        # Create outbound queue (thread-safe bridge from simulation back to network)
        outbound_queue: queue.Queue = queue.Queue()
        print("[*] Outbound queue created")

        # Start simulation thread (accumulator pattern, fixed tick rate)
        sim_thread = SimulationThread(
            registry=registry,
            event_bus=event_bus,
            config=config,
            validator=validator,
            session_mgmt=session_mgmt,
            input_queue=input_queue,
            event_class=Event,
        )
        sim_thread.start()
        print("[*] Simulation thread started")

        # Network layer
        connected_sessions = {}      # client_id → session_id
        websocket_connections = {}   # client_id → websocket object

        async def handle_client_connected(client_id: str, websocket: Any):
            """Called when WebSocket client connects"""
            session_id = str(uuid.uuid4())
            connected_sessions[client_id] = session_id
            websocket_connections[client_id] = websocket

            # Emit to engine
            event_bus.emit(SessionEvents.client_connected(session_id, client_id))
            print(f"[Network] Client {client_id} connected → session {session_id[:8]}...")
            return session_id

        async def handle_client_disconnected(client_id: str):
            """Called when WebSocket client disconnects"""
            session_id = connected_sessions.pop(client_id, None)
            websocket_connections.pop(client_id, None)
            if session_id:
                event_bus.emit(SessionEvents.client_disconnected(session_id, reason="client_closed"))
                print(f"[Network] Client {client_id} disconnected")

        def handle_client_input(client_id: str, action_data: dict) -> dict:
            """
            Called when client sends input action.

            Pushes input to queue for SimulationThread to process.
            Returns immediately without validation (validation happens in SimulationThread).
            """
            session_id = connected_sessions.get(client_id)
            if not session_id:
                return {"type": "error", "message": "Not connected"}

            # Push to input queue (SimulationThread will validate and process)
            input_packet = {
                "session_id": session_id,
                "client_id": client_id,
                **action_data,
            }
            input_queue.put(input_packet)

            # Return immediately (actual validation happens in SimulationThread)
            return {"type": "queued", "message": "Input queued for processing"}

        # Handler for replication packets (from ReplicationSystem)
        def on_replication_packet(event):
            """
            Route replication packets to outbound queue for network broadcast.

            Called by ReplicationSystem whenever it generates FOV-culled state updates
            for a client. This decouples the ECS from the async network layer.
            """
            metadata = event.metadata or {}
            session_id = metadata.get("session_id")
            packet = metadata.get("packet")

            if session_id and packet:
                # Push to outbound queue (asyncio loop will broadcast to clients)
                outbound_queue.put((session_id, packet))

        if replication:
            event_bus.subscribe("replication.packet", on_replication_packet)

        print("[*] Network handlers registered")

        # WebSocket Server Handler
        async def websocket_handler(websocket, path):
            """
            Handle incoming WebSocket connections.

            Manages the full lifecycle:
            1. Client connects → assign session_id
            2. Client sends inputs → validate and queue
            3. Client disconnects → clean up
            """
            client_id = str(uuid.uuid4())

            try:
                # Client connected
                await handle_client_connected(client_id, websocket)

                # Listen for incoming messages
                async for message in websocket:
                    try:
                        action_data = json.loads(message)
                        result = handle_client_input(client_id, action_data)
                        # Send acknowledgement back to client
                        await websocket.send_json({
                            "type": "ack",
                            "message": result.get("message", "Input received"),
                            "status": result.get("type", "ok")
                        })
                    except json.JSONDecodeError:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Invalid JSON format"
                        })
                    except Exception as e:
                        print(f"[WebSocket] Error processing message from {client_id}: {e}")

            except websockets.exceptions.ConnectionClosed:
                pass  # Client disconnected normally
            except Exception as e:
                print(f"[WebSocket] Unexpected error for {client_id}: {e}")
            finally:
                # Client disconnected
                await handle_client_disconnected(client_id)

        print("[*] WebSocket handler registered")

        # Initialize game world
        from pyrogue_engine.systems.rpg.wiz_bot_ai import WizBotAI
        from pyrogue_engine.systems.rpg.spell_system import SpellSystem, SpellProperties, SpellCastable
        from pyrogue_engine.systems.rpg.components import ActionPoints
        from wiz_bot import WizBotFactory
        from pyrogue_engine.systems.item.cheese_system import CheeseSystem

        wiz_bot_ai = WizBotAI(registry, event_bus, config)
        wiz_bot_factory = WizBotFactory()
        cheese_system = CheeseSystem(registry, event_bus, config)
        spell_system = SpellSystem(registry, event_bus, config)

        # Initialize 3D world structure
        from pyrogue_engine.generation.level_blueprint import LevelBlueprint
        from pyrogue_engine.generation.height_map import HeightMapGenerator
        from pyrogue_engine.systems.gameplay.construction_system import ConstructionSystem

        # Create 3D blueprint with height map
        blueprint = LevelBlueprint(
            width=config.world_gen.width,
            height=config.world_gen.height,
            depth=config.world_gen.max_depth,
        )

        # Generate natural height map
        height_gen = HeightMapGenerator(
            width=config.world_gen.width,
            height=config.world_gen.height,
            max_elevation=20,
            sea_level=config.world_gen.sea_level,
        )
        height_gen.populate_blueprint(blueprint, seed=42)

        # Initialize Construction System (3D-aware physics arbiter)
        construction_system = ConstructionSystem(registry, event_bus, config, blueprint)

        print(f"[*] 3D World initialized: {config.world_gen.width}x{config.world_gen.height}x{config.world_gen.max_depth}")
        print(f"[*] Height map generated (sea_level={config.world_gen.sea_level}, elevation_range=0-{blueprint.surface_map.max()})")
        print(f"[*] Construction System ready (spawn safety radius={config.world_gen.spawn_safety_radius})")

        # Spawn testing WizBot
        wiz_bot_id = wiz_bot_factory.spawn(registry, x=10, y=10, test_mode="exploration")
        wiz_bot_ai.register_wiz_bot(wiz_bot_id)

        # Add AP component to WizBot (for spell casting)
        registry.add_component(wiz_bot_id, ActionPoints(current=100, maximum=100))

        # Load and add teleport spell
        with open("templates/spells/teleport.json") as f:
            teleport_spell_data = json.load(f)

        teleport_spell = SpellProperties(
            spell_id=teleport_spell_data["spell_id"],
            spell_name=teleport_spell_data["spell_name"],
            tags=teleport_spell_data.get("tags", []),
            ap_cost=teleport_spell_data.get("ap_cost", 10),
            cooldown=teleport_spell_data.get("cooldown", 0),
            range=teleport_spell_data.get("range", 0),
            effects=teleport_spell_data.get("effects", []),
        )
        spell_system.add_spell_to_entity(wiz_bot_id, teleport_spell)

        print(f"[*] WizBot spawned at (10, 10) with ID {wiz_bot_id}")
        print(f"[*] WizBot learned teleport spell (10 AP cost, 20 frame cooldown)")

        # Spawn some test cheese items for WizBot to interact with
        from pyrogue_engine.systems.item.cheese_item import create_debug_cheese
        for i in range(3):
            cheese_data = create_debug_cheese(10 + i*5, 10, size="normal")
            cheese_id = registry.create_entity()
            for component_name, component_data in cheese_data["components"].items():
                if component_name == "PositionComponent":
                    from pyrogue_engine.systems.spatial.components import Position as PosComp
                    registry.add_component(cheese_id, PosComp(**component_data))
                elif component_name == "ItemComponent":
                    from pyrogue_engine.systems.item.cheese_item import ItemComponent
                    registry.add_component(cheese_id, ItemComponent(**component_data))
                elif component_name == "CheeseProperties":
                    from pyrogue_engine.systems.item.cheese_item import CheeseProperties
                    registry.add_component(cheese_id, CheeseProperties(**component_data))
                else:
                    registry.add_component(cheese_id, component_data)
        print(f"[*] Spawned 3 test cheese items")

        # Spawn the Architect (Resident God of world generation)
        from pyrogue_engine.systems.ai import Memory, Brain, GLOBAL_REGISTRY
        from pyrogue_engine.systems.ai.tree_factory import TreeFactory

        architect_id = registry.create_entity()

        # Position (at world spawn point)
        spawn_x, spawn_y, spawn_z = config.world_gen.spawn_point
        registry.add_component(architect_id, Position(spawn_x, spawn_y, spawn_z))

        # Health (immortal)
        registry.add_component(architect_id, Health(current=999999, maximum=999999))

        # Memory (for tracking world state)
        registry.add_component(architect_id, Memory())

        # Action Points (for spell casting)
        registry.add_component(architect_id, ActionPoints(current=999999, maximum=999999))

        # Behavior Tree (load architect_god.json)
        tree_factory = TreeFactory(GLOBAL_REGISTRY)
        architect_tree = tree_factory.load_from_file(
            "pyrogue_engine/systems/ai/examples/architect_god.json",
            cache_key="architect_god"
        )
        registry.add_component(architect_id, Brain(root_node=architect_tree))

        # Tags (for identification and max_bees counting)
        from pyrogue_engine.core.tags import Tags
        registry.add_component(architect_id, Tags(["NPC", "NPC.Architect", "Immortal"]))

        # Add summon_worker_bee spell to Architect
        with open("templates/spells/summon_worker_bee.json") as f:
            summon_spell_data = json.load(f)

        summon_spell = SpellProperties(
            spell_id=summon_spell_data["spell_id"],
            spell_name=summon_spell_data["spell_name"],
            tags=summon_spell_data.get("tags", []),
            ap_cost=summon_spell_data.get("ap_cost", 25),
            cooldown=summon_spell_data.get("cooldown", 0),
            range=summon_spell_data.get("range", 0),
            effects=summon_spell_data.get("effects", []),
        )
        spell_system.add_spell_to_entity(architect_id, summon_spell)

        print(f"[*] Architect spawned at {config.world_gen.spawn_point} with ID {architect_id}")
        print(f"[*] Architect learned: Summon Worker Bee Swarm (25 AP cost)")

        # Event handler for worker bee summoning
        def on_spell_summon_intent(event: Event):
            """Spawn worker bees when spell.summon.intent is emitted."""
            meta = event.metadata or {}
            template = meta.get("template", "worker_bee")
            count = meta.get("count", 1)
            pos = meta.get("position", {"x": 10, "y": 10, "z": 12})

            summoned_ids = []
            for i in range(count):
                # Spawn worker bee at summoner's location + small offset
                x = pos.get("x", 10) + (i % 3)
                y = pos.get("y", 10) + (i // 3)
                z = pos.get("z", 12)

                bee_id = registry.create_entity()
                registry.add_component(bee_id, Position(x, y, z))
                registry.add_component(bee_id, Health(current=10, maximum=10))
                registry.add_component(bee_id, ActionPoints(current=100, maximum=100))
                registry.add_component(bee_id, Memory())
                registry.add_component(bee_id, Tags(["NPC", "NPC.WorkerBee", "Builder", "Living"]))

                # Assign behavior tree (randomly choose drunkard, architect, or scout based on phase)
                tree_to_load = "bee_drunkard"  # Default to excavator
                tree_factory_local = TreeFactory(GLOBAL_REGISTRY)
                try:
                    bee_tree = tree_factory_local.load_from_file(
                        f"pyrogue_engine/systems/ai/examples/{tree_to_load}.json",
                        cache_key=tree_to_load
                    )
                    registry.add_component(bee_id, Brain(root_node=bee_tree))
                except Exception as e:
                    print(f"[WARNING] Failed to load bee tree {tree_to_load}: {e}")

                summoned_ids.append(bee_id)

            print(f"[*] Summoned {len(summoned_ids)} worker bees at ({pos.get('x')}, {pos.get('y')}, {pos.get('z')})")

        event_bus.subscribe("spell.summon.intent", on_spell_summon_intent)
        print("[*] Game world initialized")

        # Start WebSocket server
        # Try network config first, fall back to server.port from config.json
        ws_host = "0.0.0.0"
        ws_port = 8000

        if hasattr(config, 'network') and hasattr(config.network, 'port'):
            ws_port = config.network.port
        elif hasattr(config, 'server') and hasattr(config.server, 'port'):
            ws_port = config.server.port

        async with websockets.serve(websocket_handler, ws_host, ws_port):
            print("=" * 70)
            print("Server ready!")
            print(f"  WebSocket: ws://{ws_host}:{ws_port}")
            print(f"  Replication: {config.replication.mode if config.replication.enabled else 'DISABLED'}")
            print(f"  Max players: {config.multiplayer.max_players}")
            print(f"  Player view radius: {config.replication.player_view_radius} tiles")
            print("=" * 70 + "\n")

            # Game loop (asyncio, ~60 FPS)
            frame_count = 0
            start_time = time.time()
            packets_sent = 0

            while True:
                # Drain outbound queue and broadcast packets to clients
                # This is the output pipeline: SimulationThread → ReplicationSystem → outbound_queue → WebSocket
                packets_to_broadcast = []
                while True:
                    try:
                        session_id, packet = outbound_queue.get_nowait()
                        # Look up which client_id is connected to this session
                        client_id = next(
                            (cid for cid, sid in connected_sessions.items() if sid == session_id),
                            None,
                        )

                        if client_id:
                            packets_to_broadcast.append((client_id, packet))
                            packets_sent += 1

                    except queue.Empty:
                        break

                # Broadcast packets to clients via WebSocket
                for client_id, packet in packets_to_broadcast:
                    websocket = websocket_connections.get(client_id)
                    if websocket:
                        try:
                            await websocket.send_json(packet)
                        except Exception as e:
                            print(f"[Network] Send error for {client_id}: {e}")
                            await handle_client_disconnected(client_id)

                frame_count += 1

                # Telemetry every 60 frames
                if frame_count % 60 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed
                    connected = len(connected_sessions)
                    queue_depth = outbound_queue.qsize()
                    print(
                        f"Frame {frame_count:5d} | FPS {fps:5.1f} | "
                        f"Sessions {connected} | Packets/sec {packets_sent} | "
                        f"Outbound Q {queue_depth}"
                    )
                    packets_sent = 0

                await asyncio.sleep(0.016)  # ~60 FPS

    except ImportError as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n✓ Shutdown")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_server())
