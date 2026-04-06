"""
ClientApp - Main application loop

Orchestrates the client-side systems:
- Input (EnhancedInputSystem → ClientInputAdapter)
- Rendering (BaseRenderer implementations)
- UI (UIManager, Menus)
- Audio (AudioManager)

The client reads Engine state and translates it to presentation.
The Engine processes intents from the client without knowing about Pygame/display.
"""

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import EventBus

from pyrogue_client.input import ClientInputAdapter
from pyrogue_client.renderers import RendererFactory, BaseRenderer


class ClientApp:
    """
    Main client application.

    Owns the main loop and coordinates input, rendering, UI, and audio.
    """

    def __init__(
        self,
        engine_registry: Registry,
        engine_event_bus: EventBus,
        renderer_type: str = "pygame",
        window_width: int = 1280,
        window_height: int = 720,
        title: str = "Pyrogue",
    ):
        """
        Initialize the client application.

        Args:
            engine_registry: pyrogue_engine ECS Registry (shared with engine systems)
            engine_event_bus: pyrogue_engine EventBus (shared with engine systems)
            renderer_type: Which renderer to use ('pygame', 'terminal', 'web')
            window_width: Initial window width
            window_height: Initial window height
            title: Window title
        """
        self.registry = engine_registry
        self.bus = engine_event_bus

        self.window_width = window_width
        self.window_height = window_height
        self.title = title

        # Initialize client systems
        self.renderer = RendererFactory.create(renderer_type)
        self.input = ClientInputAdapter(engine_event_bus)

        # These will be initialized when game starts
        self.player_entity_id = None
        self.is_running = False

    def initialize_game(self, player_entity_id: int) -> None:
        """
        Initialize the game with a player entity.

        Called after the game has spawned the player and is ready to run.

        Args:
            player_entity_id: The ECS entity ID of the player
        """
        self.player_entity_id = player_entity_id
        self.input.set_player_entity(player_entity_id)

        # Initialize renderer
        self.renderer.init_window(self.window_width, self.window_height, self.title)

        self.is_running = True

    def update(self, dt: float) -> None:
        """
        Update the client each frame.

        This is called by the main game loop AFTER the engine systems have ticked.

        Args:
            dt: Delta time since last frame (seconds)
        """
        # 1. Process input and emit intents to engine
        self.input.update(dt)

        # 2. Read engine state and render
        self.renderer.clear()
        self._render_game_state()
        self.renderer.present()

        # 3. Check if window was closed
        if not self.renderer.is_open():
            self.is_running = False

    def _render_game_state(self) -> None:
        """
        Render the current engine state.

        Reads components from registry and draws them via renderer.
        """
        from pyrogue_engine.systems.spatial.components import Position
        from pyrogue_engine.systems.rpg.components import Health
        from pyrogue_engine.core.tags import Tags

        # Iterate over all entities with Position and Tags
        for entity_id, (position, tags) in self.registry.view(Position, Tags):
            # Get sprite info from tags or entity
            # For now, draw a placeholder
            self.renderer.draw_sprite(
                position.x * 16,
                position.y * 16,
                asset_id="entity",
                fg_color=(255, 255, 255),
            )

        # Draw UI panel (placeholder)
        if self.player_entity_id is not None:
            health = self.registry.get_component(self.player_entity_id, Health)
            if health:
                self.renderer.draw_text(
                    10,
                    10,
                    f"HP: {health.current}/{health.maximum}",
                    fg_color=(255, 100, 100),
                )

    def shutdown(self) -> None:
        """Cleanup and shutdown the client."""
        self.renderer.shutdown()


# Example: Create and run a client
def create_client(engine_registry, engine_event_bus, renderer_type="pygame"):
    """
    Factory function to create a properly initialized client.

    Args:
        engine_registry: pyrogue_engine Registry
        engine_event_bus: pyrogue_engine EventBus
        renderer_type: Renderer type ('pygame', 'terminal', 'web')

    Returns:
        ClientApp instance
    """
    return ClientApp(
        engine_registry=engine_registry,
        engine_event_bus=engine_event_bus,
        renderer_type=renderer_type,
        window_width=1280,
        window_height=720,
        title="Pyrogue - Roguelike Engine",
    )
