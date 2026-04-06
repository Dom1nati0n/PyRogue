"""
Server Configuration Management

Loads config.json and provides access to server-wide settings:
- Multiplayer configuration (max players, tick rate)
- Replication modes (FOV culling, delta compression)
- GameMode settings

All values are data-driven (no hardcoding), following THE CONSTITUTION principle 2.

Usage:
    config = ServerConfig.load("config.json")
    if config.replication.enabled:
        replication_system = ReplicationSystem(registry, event_bus, config)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple


@dataclass
class GameplayConfig:
    """Gameplay and simulation settings"""
    simulation_speed: float = 1.0  # Time multiplier (1.0 = normal, 2.0 = 2x speed)
    tick_rate: float = 0.1  # Fixed time step in seconds (0.1 = 100ms, 10 Hz)
    sync_model: str = "authoritative"  # "authoritative", "lockstep", "predictive"


@dataclass
class ReplicationConfig:
    """Replication system settings"""
    enabled: bool = True
    mode: str = "fov_culled"  # "full_state", "fov_culled", "delta_compressed"
    player_view_radius: int = 8
    include_adjacent_tiles: bool = True
    use_delta_compression: bool = True
    max_entities_per_client: Optional[int] = None  # None = unlimited


@dataclass
class MultiplayerConfig:
    """Multiplayer session settings"""
    enabled: bool = True
    max_players: int = 100
    tick_rate_hz: int = 60
    reconnect_timeout_seconds: int = 30
    max_disconnected_ai_takeover: bool = True


@dataclass
class GameModeConfig:
    """GameMode-specific settings"""
    type: str = "survival"  # "survival", "rounds", "cooperative"
    spawn_points: List[Tuple[int, int, int]] = field(default_factory=list)  # Now 3D with Z
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldGenConfig:
    """World generation and 3D structure settings"""
    width: int = 200
    height: int = 200
    max_depth: int = 36  # Z-axis range (0 to max_depth)
    sea_level: int = 12  # Baseline water level (Z-coordinate)
    max_bees: int = 50  # Max concurrent worker bee entities
    spawn_point: Tuple[int, int, int] = (10, 10, 12)  # Default spawn (x, y, z)
    spawn_safety_radius: int = 5  # Radius of empty tiles guaranteed around spawn


@dataclass
class ServerConfig:
    """Complete server configuration"""
    server_name: str = "PyRogue"
    server_port: int = 8000
    multiplayer: MultiplayerConfig = field(default_factory=MultiplayerConfig)
    replication: ReplicationConfig = field(default_factory=ReplicationConfig)
    gameplay: GameplayConfig = field(default_factory=GameplayConfig)
    gamemode: GameModeConfig = field(default_factory=GameModeConfig)
    world_gen: WorldGenConfig = field(default_factory=WorldGenConfig)

    @staticmethod
    def load(config_path: str = "config.json") -> "ServerConfig":
        """
        Load server configuration from JSON file.

        Args:
            config_path: Path to config.json (relative or absolute)

        Returns:
            ServerConfig with loaded values, or defaults if file not found
        """
        path = Path(config_path)

        if not path.exists():
            print(f"[Config] File not found: {config_path}, using defaults")
            return ServerConfig()

        try:
            with open(path, "r") as f:
                data = json.load(f)

            # Parse nested configs
            multiplayer_data = data.get("multiplayer", {})
            replication_data = data.get("replication", {})
            gameplay_data = data.get("gameplay", {})
            gamemode_data = data.get("gamemode", {})
            world_gen_data = data.get("world_gen", {})

            return ServerConfig(
                server_name=data.get("server", {}).get("name", "PyRogue"),
                server_port=data.get("server", {}).get("port", 8000),
                multiplayer=MultiplayerConfig(**multiplayer_data),
                replication=ReplicationConfig(**replication_data),
                gameplay=GameplayConfig(**gameplay_data),
                gamemode=GameModeConfig(
                    type=gamemode_data.get("type", "survival"),
                    spawn_points=[tuple(p) for p in gamemode_data.get("spawn_points", [])],
                    properties=gamemode_data.get("properties", {}),
                ),
                world_gen=WorldGenConfig(
                    width=world_gen_data.get("width", 200),
                    height=world_gen_data.get("height", 200),
                    max_depth=world_gen_data.get("max_depth", 36),
                    sea_level=world_gen_data.get("sea_level", 12),
                    max_bees=world_gen_data.get("max_bees", 50),
                    spawn_point=tuple(world_gen_data.get("spawn_point", [10, 10, 12])),
                    spawn_safety_radius=world_gen_data.get("spawn_safety_radius", 5),
                ),
            )

        except json.JSONDecodeError as e:
            print(f"[Config] JSON parse error: {e}, using defaults")
            return ServerConfig()
        except Exception as e:
            print(f"[Config] Load error: {e}, using defaults")
            return ServerConfig()

    def __str__(self) -> str:
        """Human-readable config summary"""
        return f"""
[Server Config]
  Server: {self.server_name}:{self.server_port}
  Multiplayer: {self.multiplayer.max_players} players, {self.multiplayer.tick_rate_hz} Hz
  Replication: {self.replication.mode} (enabled={self.replication.enabled})
  Player View Radius: {self.replication.player_view_radius}
  Gameplay: tick_rate={self.gameplay.tick_rate}s, speed={self.gameplay.simulation_speed}x, sync={self.gameplay.sync_model}
  GameMode: {self.gamemode.type}
  World Gen: {self.world_gen.width}x{self.world_gen.height}x{self.world_gen.max_depth}, sea_level={self.world_gen.sea_level}, max_bees={self.world_gen.max_bees}
  Spawn Point: {self.world_gen.spawn_point}
""".strip()
