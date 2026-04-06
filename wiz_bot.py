#!/usr/bin/env python3
"""
WizBot Spawner - Factory for creating autonomous testing bots.

Usage:
    python wiz_bot.py spawn 10 10  # Spawn at (10, 10)
    python wiz_bot.py teleport <entity_id> 20 20  # Teleport an existing bot
    python wiz_bot.py load-config  # Load wiz_bot.json

Can also be imported as a module:
    from wiz_bot import spawn_wiz_bot, WizBotFactory
    entity_id = spawn_wiz_bot(registry, event_bus, x=10, y=10)
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.systems.spatial.components import Position
from pyrogue_engine.systems.rpg.components import Health, PlayerController
from pyrogue_engine.systems.rpg.debug_component import DebugComponent
from pyrogue_engine.core.events import EventBus


class WizBotFactory:
    """Factory for creating WizBot entities with configured components."""

    def __init__(self, config_path: str = "wiz_bot.json"):
        """
        Initialize the factory.

        Args:
            config_path: Path to wiz_bot.json configuration
        """
        self.config_path = Path(config_path)
        self.template = self._load_template()

    def _load_template(self) -> Dict[str, Any]:
        """Load wiz_bot.json template."""
        if not self.config_path.exists():
            print(f"[WizBotFactory] Config not found at {self.config_path}")
            return self._default_template()

        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WizBotFactory] Error loading config: {e}")
            return self._default_template()

    def _default_template(self) -> Dict[str, Any]:
        """Fallback template if config not found."""
        return {
            "entity_type": "wiz_bot",
            "name": "WizBot",
            "spawn_position": [10, 10],
            "components": {
                "PositionComponent": {"x": 10, "y": 10},
                "TileSprite": {"char": "W", "fg_color": [0, 255, 255]},
                "Health": {"current": 100, "maximum": 100},
                "PlayerController": {
                    "session_id": "wiz_bot_debug",
                    "is_connected": True,
                    "reconnect_timer": 0.0,
                },
                "DebugComponent": {
                    "enabled": True,
                    "test_mode": "exploration",
                    "log_interval": 60,
                },
            },
        }

    def spawn(self, registry: Registry, x: int, y: int, test_mode: str = None) -> int:
        """
        Spawn a WizBot entity at the given coordinates.

        Args:
            registry: ECS Registry
            x: Spawn X coordinate
            y: Spawn Y coordinate
            test_mode: Optional override for test mode ("exploration", "cheese_multiply_test", "cheese_replicate_test")

        Returns:
            entity_id of the created WizBot
        """
        # Create entity first (returns just an ID)
        entity_id = registry.create_entity()

        # Apply components from template
        components = self.template.get("components", {})

        # Position (override with spawn coordinates)
        if "PositionComponent" in components:
            pos_data = components["PositionComponent"].copy()
            pos_data["x"] = x
            pos_data["y"] = y
            registry.add_component(entity_id, Position(**pos_data))

        # Health
        if "Health" in components:
            health_data = components["Health"]
            registry.add_component(entity_id, Health(**health_data))

        # PlayerController
        if "PlayerController" in components:
            ctrl_data = components["PlayerController"].copy()
            ctrl_data["session_id"] = f"wiz_bot_{x}_{y}_{entity_id}"
            registry.add_component(entity_id, PlayerController(**ctrl_data))

        # DebugComponent
        if "DebugComponent" in components:
            debug_data = components["DebugComponent"].copy()
            debug_data["stats"] = {"spawn_x": x, "spawn_y": y}
            if test_mode:
                debug_data["test_mode"] = test_mode
            registry.add_component(entity_id, DebugComponent(**debug_data))

        # Sprite (stored as dict component)
        if "TileSprite" in components:
            sprite_data = components["TileSprite"]
            registry.add_component(entity_id, sprite_data)

        print(f"[WizBotFactory] Spawned WizBot at ({x}, {y}) with entity_id {entity_id}")
        return entity_id


def spawn_wiz_bot(
    registry: Registry, event_bus: EventBus, x: int = 10, y: int = 10, test_mode: str = None
) -> int:
    """
    Convenience function to spawn a WizBot.

    Args:
        registry: ECS Registry
        event_bus: Event bus
        x: Spawn X
        y: Spawn Y
        test_mode: Optional test mode ("exploration", "cheese_multiply_test", "cheese_replicate_test")

    Returns:
        entity_id
    """
    factory = WizBotFactory()
    entity_id = factory.spawn(registry, x, y, test_mode=test_mode)

    # Register with AI system if it exists
    # (This would be done in headless_server.py during initialization)

    return entity_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python wiz_bot.py [spawn|config]")
        print("  spawn <x> <y>  - Spawn WizBot at coordinates")
        print("  config         - Print loaded config")
        sys.exit(1)

    command = sys.argv[1]

    if command == "config":
        factory = WizBotFactory()
        print(json.dumps(factory.template, indent=2))

    elif command == "spawn":
        if len(sys.argv) < 4:
            print("Usage: python wiz_bot.py spawn <x> <y>")
            sys.exit(1)

        x, y = int(sys.argv[2]), int(sys.argv[3])
        print(f"[WizBot] Would spawn at ({x}, {y})")
        print("[WizBot] (Requires Registry + EventBus context to actually spawn)")
