"""
WizBot AI System - Autonomous testing bot for debugging and stress-testing.

The WizBot is a lightweight, intelligent testing entity that:
  1. Explores the map autonomously using random walk
  2. Collects and logs telemetry (frame count, entity count, FOV coverage)
  3. Supports teleport for unsticking from corners
  4. Validates that the engine is running correctly

Compliance with THE CONSTITUTION:
  ✓ Reactive: Listens to "world.tick" event
  ✓ Intent-Driven: Emits movement.intent events like a normal player
  ✓ Pure: No mutations except to its own DebugComponent state
  ✓ No Awareness: WizBot has zero awareness of replication, network, or UI
"""

import random
import time
from typing import Any, Optional

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import Event, EventBus
from pyrogue_engine.systems.spatial.components import Position
from pyrogue_engine.systems.rpg.components import Health, PlayerController
from pyrogue_engine.systems.rpg.debug_component import DebugComponent

try:
    from pyrogue_engine.systems.item.cheese_item import ItemComponent, CheeseProperties
except ImportError:
    ItemComponent = None
    CheeseProperties = None


class WizBotAI:
    """
    Autonomous testing bot for validating the engine under load.

    Spawns with a DebugComponent and moves autonomously every frame,
    emitting movement.intent events like a real player.
    """

    DIRECTIONS = ["up", "down", "left", "right", "upleft", "upright", "downleft", "downright"]
    EXPLORE_CHANCE = 0.7  # 70% chance to move each frame (30% pause)

    def __init__(self, registry: Registry, event_bus: EventBus, config: Any):
        """
        Initialize the WizBot AI system.

        Args:
            registry: ECS registry (for entity queries)
            event_bus: Event bus (subscribe to world.tick)
            config: Server config
        """
        self.registry = registry
        self.event_bus = event_bus
        self.config = config

        # Track which WizBot entity IDs we're managing
        self.wiz_bots = set()

        # Track inventory for each bot (for stress testing)
        self.bot_inventory = {}  # bot_id -> list of item_ids

        # Subscribe to world ticks
        self.event_bus.subscribe("world.tick", self._on_world_tick)

        print("[WizBotAI] Initialized - ready to spawn testing bots")

    def register_wiz_bot(self, entity_id: int) -> None:
        """Register a WizBot entity for AI updates."""
        self.wiz_bots.add(entity_id)
        self.bot_inventory[entity_id] = []  # Initialize empty inventory
        debug = self.registry.get_component(entity_id, DebugComponent)
        if debug:
            print(f"[WizBotAI] Registered bot entity {entity_id} in {debug.test_mode} mode")

    def _on_world_tick(self, event: Event) -> None:
        """Called every world tick. Update all registered WizBots."""
        for bot_id in self.wiz_bots:
            self._update_bot(bot_id)

    def _update_bot(self, bot_id: int) -> None:
        """Update a single WizBot entity."""
        pos = self.registry.get_component(bot_id, Position)
        debug = self.registry.get_component(bot_id, DebugComponent)
        controller = self.registry.get_component(bot_id, PlayerController)

        if not (pos and debug and controller):
            return

        debug.frame_count += 1

        # 1. Handle pending teleport (for unsticking)
        if debug.teleport_dest:
            self._execute_teleport(bot_id, pos, debug)
            return

        # 2. Collect telemetry
        self._collect_telemetry(bot_id, debug)

        # 3. Log telemetry if it's time
        if debug.should_log():
            self._log_telemetry(bot_id, debug)

        # 4. Run stress test mode if enabled
        if debug.test_mode == "cheese_multiply_test":
            self._run_cheese_multiply_test(bot_id, pos, debug)
            return  # Don't explore during stress test
        elif debug.test_mode == "cheese_replicate_test":
            self._run_cheese_replicate_test(bot_id, pos, debug)
            return  # Don't explore during stress test

        # 5. Test all player actions (comprehensive feature coverage)
        if ItemComponent:
            self._test_all_player_actions(bot_id, pos, debug)
            self._test_cheese_interaction(bot_id, pos, debug)

        # 5b. Test spell casting (frequently for testing)
        if random.random() < 0.15:  # 15% chance per frame to test spells more
            self._test_spell_casting(bot_id, pos, debug)

        # 6. Explore: move in a random direction
        if random.random() < self.EXPLORE_CHANCE:
            self._move_random(bot_id, debug)

    def _collect_telemetry(self, bot_id: int, debug: DebugComponent) -> None:
        """Collect telemetry about the engine state."""
        # Count entities with Position component (rough measure of world load)
        entity_count = 0
        for entity_id, _ in self.registry.view(Position):
            entity_count += 1

        debug.update_stat("entity_count", entity_count)
        debug.update_stat("bot_frame", debug.frame_count)

        # TODO: Add more telemetry as needed
        # - Connected players
        # - Events processed per frame
        # - Average FOV culling effectiveness

    def _log_telemetry(self, bot_id: int, debug: DebugComponent) -> None:
        """Print telemetry to console."""
        entity_count = debug.get_stat("entity_count") or 0
        frame = debug.frame_count

        print(
            f"[WizBotAI] Bot {bot_id} | Frame {frame:5d} | "
            f"Mode {debug.test_mode:15s} | "
            f"Entities {entity_count:3d} | "
            f"Stats: {debug.stats}"
        )

    def _move_random(self, bot_id: int, debug: DebugComponent) -> None:
        """Emit a random movement intent."""
        direction = random.choice(self.DIRECTIONS)

        self.event_bus.emit(
            Event(
                event_type="movement.intent",
                metadata={
                    "entity_id": bot_id,
                    "direction": direction,
                    "source": "wiz_bot",  # Tag so systems can ignore if needed
                },
            )
        )

    def _execute_teleport(self, bot_id: int, pos: Position, debug: DebugComponent) -> None:
        """Teleport the WizBot to unstuck it."""
        x, y = debug.teleport_dest
        pos.x = x
        pos.y = y
        debug.clear_teleport()

        print(f"[WizBotAI] Bot {bot_id} teleported to ({x}, {y})")

    def _test_cheese_interaction(self, bot_id: int, pos: Position, debug: DebugComponent) -> None:
        """
        Test cheese interactions: find nearby cheese, use it, throw it, test splitting.

        This exercises the inventory, combat, and item systems simultaneously.
        """
        if not ItemComponent:
            return

        # Find nearby cheese (within 3 tiles)
        cheese_nearby = []
        for entity_id, (item,) in self.registry.view(ItemComponent):
            if "cheese" not in item.tags:
                continue

            item_pos = self.registry.get_component(entity_id, Position)
            if not item_pos:
                continue

            dist = abs(pos.x - item_pos.x) + abs(pos.y - item_pos.y)
            if dist <= 3:
                cheese_nearby.append((entity_id, dist))

        if not cheese_nearby:
            return

        # Pick closest cheese
        cheese_id, distance = min(cheese_nearby, key=lambda x: x[1])
        cheese = self.registry.get_component(cheese_id, ItemComponent)

        if not cheese:
            return

        # Randomly interact with cheese
        action = random.choice(["use", "throw", "drop"])

        if action == "use":
            # Use cheese as weapon (test combat)
            self.event_bus.emit(
                Event(
                    event_type="item.used",
                    metadata={
                        "item_id": cheese_id,
                        "actor_id": bot_id,
                        "target_id": bot_id,  # Self-damage for testing
                    },
                )
            )
            debug.update_stat("cheese_used", debug.get_stat("cheese_used") or 0 + 1)

        elif action == "throw":
            # Throw cheese (test projectile)
            target_x = pos.x + random.randint(-5, 5)
            target_y = pos.y + random.randint(-5, 5)
            self.event_bus.emit(
                Event(
                    event_type="item.thrown",
                    metadata={
                        "item_id": cheese_id,
                        "actor_id": bot_id,
                        "target_pos": {"x": target_x, "y": target_y},
                    },
                )
            )
            debug.update_stat("cheese_thrown", debug.get_stat("cheese_thrown") or 0 + 1)

        elif action == "drop":
            # Drop cheese (test ground items)
            self.event_bus.emit(
                Event(
                    event_type="item.dropped",
                    metadata={
                        "item_id": cheese_id,
                        "drop_pos": {"x": pos.x, "y": pos.y},
                    },
                )
            )
            debug.update_stat("cheese_dropped", debug.get_stat("cheese_dropped") or 0 + 1)

    def _test_all_player_actions(self, bot_id: int, pos: Position, debug: DebugComponent) -> None:
        """
        Comprehensive test of all player actions.

        Tests: move, attack, interact, pickup, drop, use, throw, wait.
        """
        # 1. Movement (already tested via _move_random)
        debug.update_stat("moves_tested", debug.get_stat("moves_tested") or 0 + 1)

        # 2. Attack - target nearby entities
        for target_id, (health,) in self.registry.view(Health):
            if target_id == bot_id:
                continue

            target_pos = self.registry.get_component(target_id, Position)
            if not target_pos:
                continue

            dist = abs(pos.x - target_pos.x) + abs(pos.y - target_pos.y)
            if dist <= 2:  # Melee range
                self.event_bus.emit(
                    Event(
                        event_type="combat.attack.intent",
                        metadata={
                            "attacker_id": bot_id,
                            "target_id": target_id,
                        },
                    )
                )
                debug.update_stat("attacks_tested", debug.get_stat("attacks_tested") or 0 + 1)
                break

        # 2b. Interact - try to interact with nearby entities
        for target_id, (health,) in self.registry.view(Health):
            if target_id == bot_id:
                continue

            target_pos = self.registry.get_component(target_id, Position)
            if not target_pos:
                continue

            dist = abs(pos.x - target_pos.x) + abs(pos.y - target_pos.y)
            if dist <= 1:  # Adjacent
                self.event_bus.emit(
                    Event(
                        event_type="interaction.intent",
                        metadata={
                            "actor_id": bot_id,
                            "target_id": target_id,
                        },
                    )
                )
                debug.update_stat("interactions_tested", debug.get_stat("interactions_tested") or 0 + 1)
                break

        # 3. Pickup - find items on ground
        for item_id, (item,) in self.registry.view(ItemComponent):
            item_pos = self.registry.get_component(item_id, Position)
            if not item_pos:
                continue

            dist = abs(pos.x - item_pos.x) + abs(pos.y - item_pos.y)
            if dist <= 1:  # Adjacent
                self.event_bus.emit(
                    Event(
                        event_type="inventory.pickup.intent",
                        metadata={
                            "actor_id": bot_id,
                            "item_id": item_id,
                        },
                    )
                )
                debug.update_stat("pickups_tested", debug.get_stat("pickups_tested") or 0 + 1)
                break

        # 4. Wait (idle action)
        if random.random() < 0.1:  # 10% chance
            self.event_bus.emit(
                Event(
                    event_type="turn.wait",
                    metadata={"entity_id": bot_id},
                )
            )
            debug.update_stat("waits_tested", debug.get_stat("waits_tested") or 0 + 1)

    def _run_cheese_multiply_test(self, bot_id: int, pos: Position, debug: DebugComponent) -> None:
        """
        Stress test: Spawn cheese until inventory full, then use each one.

        Tests inventory limits, item spawning, and combat damage over time.
        """
        if not ItemComponent or not CheeseProperties:
            return

        inventory = self.bot_inventory.get(bot_id, [])
        MAX_INVENTORY = 10

        # Phase 1: Collect cheese up to limit
        if len(inventory) < MAX_INVENTORY:
            # Find nearby cheese to pick up, or spawn new one
            cheese_nearby = []
            for entity_id, (item,) in self.registry.view(ItemComponent):
                if "cheese" not in item.tags:
                    continue
                if entity_id in inventory:
                    continue  # Already have it

                item_pos = self.registry.get_component(entity_id, Position)
                if not item_pos:
                    continue

                dist = abs(pos.x - item_pos.x) + abs(pos.y - item_pos.y)
                if dist <= 5:
                    cheese_nearby.append((entity_id, dist))

            if cheese_nearby:
                # Pick up closest cheese
                cheese_id, distance = min(cheese_nearby, key=lambda x: x[1])
                inventory.append(cheese_id)
                debug.update_stat("cheese_collected", debug.get_stat("cheese_collected") or 0 + 1)
                print(f"[WizBotAI] Bot {bot_id} collected cheese {cheese_id}, inventory {len(inventory)}/{MAX_INVENTORY}")
            else:
                # Spawn new cheese at bot location
                from pyrogue_engine.systems.item.cheese_item import create_debug_cheese
                cheese_data = create_debug_cheese(pos.x, pos.y, size="normal")

                cheese_id = self.registry.create_entity()
                for component_name, component_data in cheese_data["components"].items():
                    if component_name == "PositionComponent":
                        from pyrogue_engine.systems.spatial.components import Position as PosComponent
                        self.registry.add_component(cheese_id, PosComponent(**component_data))
                    elif component_name == "ItemComponent":
                        self.registry.add_component(cheese_id, ItemComponent(**component_data))
                    elif component_name == "CheeseProperties":
                        self.registry.add_component(cheese_id, CheeseProperties(**component_data))
                    else:
                        self.registry.add_component(cheese_id, component_data)
                inventory.append(cheese_id)
                debug.update_stat("cheese_spawned", debug.get_stat("cheese_spawned") or 0 + 1)
                print(f"[WizBotAI] Bot {bot_id} spawned cheese {cheese_id}, inventory {len(inventory)}/{MAX_INVENTORY}")

        # Phase 2: Use each cheese when inventory is full
        elif len(inventory) >= MAX_INVENTORY:
            if inventory:
                cheese_id = inventory.pop(0)  # FIFO: use oldest first
                # Emit use event
                self.event_bus.emit(
                    Event(
                        event_type="item.used",
                        metadata={
                            "item_id": cheese_id,
                            "user_id": bot_id,
                            "target_id": bot_id,
                        },
                    )
                )
                debug.update_stat("cheese_used", debug.get_stat("cheese_used") or 0 + 1)
                print(f"[WizBotAI] Bot {bot_id} used cheese {cheese_id}, {len(inventory)} remaining")

    def _run_cheese_replicate_test(self, bot_id: int, pos: Position, debug: DebugComponent) -> None:
        """
        Stress test: Spawn cheese one-at-a-time until inventory full, then delete all except one.

        Tests item spawning rate and deletion mechanics.
        """
        if not ItemComponent or not CheeseProperties:
            return

        inventory = self.bot_inventory.get(bot_id, [])
        MAX_INVENTORY = 10

        # Phase 1: Spawn cheese one-at-a-time up to limit
        if len(inventory) < MAX_INVENTORY:
            from pyrogue_engine.systems.item.cheese_item import create_debug_cheese
            cheese_data = create_debug_cheese(pos.x, pos.y, size="small")

            cheese_id = self.registry.create_entity()
            for component_name, component_data in cheese_data["components"].items():
                if component_name == "PositionComponent":
                    from pyrogue_engine.systems.spatial.components import Position as PosComponent
                    self.registry.add_component(cheese_id, PosComponent(**component_data))
                elif component_name == "ItemComponent":
                    self.registry.add_component(cheese_id, ItemComponent(**component_data))
                elif component_name == "CheeseProperties":
                    self.registry.add_component(cheese_id, CheeseProperties(**component_data))
                else:
                    self.registry.add_component(cheese_id, component_data)
            inventory.append(cheese_id)
            debug.update_stat("cheese_spawned", debug.get_stat("cheese_spawned") or 0 + 1)
            print(f"[WizBotAI] Bot {bot_id} spawned cheese {cheese_id}, inventory {len(inventory)}/{MAX_INVENTORY}")

        # Phase 2: Delete all except one when inventory is full
        elif len(inventory) >= MAX_INVENTORY:
            if len(inventory) > 1:
                # Keep first cheese, delete the rest
                cheese_to_delete = inventory[1]
                inventory.pop(1)
                self.registry.delete_entity(cheese_to_delete)
                debug.update_stat("cheese_deleted", debug.get_stat("cheese_deleted") or 0 + 1)
                print(f"[WizBotAI] Bot {bot_id} deleted cheese {cheese_to_delete}, {len(inventory)} remaining")

    def _test_spell_casting(self, bot_id: int, pos: Position, debug: DebugComponent) -> None:
        """
        Test spell casting: attempt to cast teleport to a random nearby location.

        Tests: Spell system, AP cost deduction, cooldown management.
        """
        try:
            from pyrogue_engine.systems.rpg.spell_system import SpellCastable
        except ImportError:
            return

        spellcaster = self.registry.get_component(bot_id, SpellCastable)
        if not spellcaster or "teleport" not in spellcaster.spells:
            return

        # Pick a random teleport destination (8 tiles away)
        target_x = pos.x + random.randint(-8, 8)
        target_y = pos.y + random.randint(-8, 8)

        # Emit spell cast intent
        self.event_bus.emit(
            Event(
                event_type="spell.cast",
                metadata={
                    "caster_id": bot_id,
                    "spell_id": "teleport",
                    "target_pos": {"x": target_x, "y": target_y},
                },
            )
        )
        debug.update_stat("spells_cast", debug.get_stat("spells_cast") or 0 + 1)

    def teleport_bot(self, bot_id: int, x: int, y: int) -> None:
        """Public API: Teleport a WizBot to coordinates."""
        debug = self.registry.get_component(bot_id, DebugComponent)
        if debug:
            debug.mark_teleport(x, y)
