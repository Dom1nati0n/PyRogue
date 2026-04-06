"""
Game Initialization - Separate from server logic.

Creates initial game state (entities, map, etc).
Engine stays pure - this is just setup.
"""

from my_lib.core.components.game_components import PositionComponent
from my_lib.core.components.tile_sprite import TileSprite


def initialize_game(ecs_manager):
    """
    Initialize game world with starting entities.

    Args:
        ecs_manager: ECSManager instance

    Returns:
        player_id (int)
    """
    # Create player
    player_id = ecs_manager.create_entity(
        PositionComponent(x=40, y=12),
        TileSprite(char="@", color_index=15)  # White
    )

    # Create some enemies
    for i in range(3):
        ecs_manager.create_entity(
            PositionComponent(x=40 + i * 5, y=12 + i),
            TileSprite(char="g", color_index=1)  # Red
        )

    return player_id
