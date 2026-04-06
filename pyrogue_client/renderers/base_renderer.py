"""
BaseRenderer - Universal Display Contract (The Glass Wall)

This abstract base class defines the complete contract that any rendering
engine must fulfill to work with the roguelike engine.

By depending ONLY on this interface, the engine becomes completely
platform-agnostic. Swap renderers, swap platforms. Same game logic everywhere.

The Glass Wall separates:
  - ECS/Simulation logic (platform-agnostic)
  - RenderSystem/UISystem (depend only on BaseRenderer)
  - Actual rendering (Pygame, Terminal, Web, etc.)
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum


class InputEvent(Enum):
    """Standard input events mapped from platform-specific events."""
    # Movement
    MOVE_UP = "up"
    MOVE_DOWN = "down"
    MOVE_LEFT = "left"
    MOVE_RIGHT = "right"

    # Actions
    INTERACT = "interact"
    ATTACK = "attack"
    WAIT = "wait"
    PICK_UP = "pickup"
    DROP = "drop"

    # UI
    MENU_UP = "menu_up"
    MENU_DOWN = "menu_down"
    MENU_SELECT = "menu_select"
    MENU_CANCEL = "menu_cancel"
    INVENTORY = "inventory"
    CHARACTER_SHEET = "character_sheet"

    # System
    QUIT = "quit"
    SAVE = "save"
    LOAD = "load"
    SCREENSHOT = "screenshot"


class InputPayload:
    """Container for input event data."""

    def __init__(self, event_type: InputEvent, **kwargs):
        """
        Create an input payload.

        Args:
            event_type: The type of input event
            **kwargs: Additional data (e.g., position for mouse events)
        """
        self.event_type = event_type
        self.data = kwargs

    def __repr__(self):
        return f"<Input {self.event_type.value} {self.data}>"


class BaseRenderer(ABC):
    """
    Abstract base class for all display/rendering adapters.

    Any class implementing this interface can be used to render the game.
    The engine has no knowledge of whether it's Pygame, Terminal, Web, etc.

    This is the "Glass Wall" - the complete boundary between logic and presentation.
    """

    # =========================================================================
    # WINDOW/SCREEN MANAGEMENT
    # =========================================================================

    @abstractmethod
    def init_window(self, width: int, height: int, title: str) -> None:
        """
        Initialize the display window.

        Args:
            width: Window width in pixels (or character columns for terminal)
            height: Window height in pixels (or character rows for terminal)
            title: Window title (ignored by terminal adapters)
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear the display buffer."""
        pass

    @abstractmethod
    def present(self) -> None:
        """
        Display the buffer to the screen.

        For Pygame: calls pygame.display.flip()
        For Terminal: refreshes the screen
        For Web: sends JSON frame to client
        """
        pass

    @abstractmethod
    def is_open(self) -> bool:
        """Check if the window is still open (user hasn't closed it)."""
        pass

    # =========================================================================
    # DRAWING OPERATIONS
    # =========================================================================

    @abstractmethod
    def draw_sprite(
        self,
        x: int,
        y: int,
        asset_id: str,
        fg_color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """
        Draw a sprite at the given position.

        Args:
            x: X coordinate (pixel or column)
            y: Y coordinate (pixel or row)
            asset_id: Identifier for the sprite/tile to draw
                     (e.g., "goblin", "wall", "health_potion")
            fg_color: Foreground color (R, G, B) tuple
            bg_color: Background color (R, G, B) tuple

        Implementation notes:
        - Pygame: Loads sprite from asset cache, blits to surface
        - Terminal: Maps asset_id to ASCII character, applies color
        - Web: Appends {"type": "sprite", "x": x, "y": y, "asset": asset_id, ...} to frame
        """
        pass

    @abstractmethod
    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        fg_color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """
        Draw text at the given position.

        Args:
            x: X coordinate
            y: Y coordinate
            text: Text string to draw
            fg_color: Text color (R, G, B)
            bg_color: Background color (R, G, B)

        Implementation notes:
        - Pygame: Renders using font, blits to surface
        - Terminal: Writes directly to terminal buffer
        - Web: Appends {"type": "text", "x": x, "y": y, "text": text, ...} to frame
        """
        pass

    # =========================================================================
    # INPUT HANDLING
    # =========================================================================

    @abstractmethod
    def poll_input(self) -> List[InputPayload]:
        """
        Poll for input events and return them in engine-agnostic format.

        Returns:
            List of InputPayload objects representing input events

        Implementation notes:
        - Pygame: Reads pygame.event.get(), maps to InputEvent
        - Terminal: Reads curses input, maps to InputEvent
        - Web: Reads from websocket/HTTP, maps to InputEvent

        Must handle:
        - Movement keys (arrow keys, WASD)
        - Action keys (space, enter)
        - UI navigation keys (numbers, vim keys)
        - System keys (ESC, Q, etc.)
        """
        pass

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_window_size(self) -> Tuple[int, int]:
        """Get the window dimensions. Override if needed."""
        raise NotImplementedError("get_window_size() not implemented by adapter")

    def set_title(self, title: str) -> None:
        """Set the window title. Override if needed."""
        pass

    def screenshot(self, filename: str) -> None:
        """Save a screenshot. Override if implemented."""
        pass

    def shutdown(self) -> None:
        """Cleanup and shutdown the adapter."""
        pass


class RendererFactory:
    """Factory for creating renderers by name."""

    _renderers = {}

    @classmethod
    def register_renderer(cls, name: str, renderer_class: type) -> None:
        """Register a renderer class."""
        cls._renderers[name] = renderer_class

    @classmethod
    def create(cls, renderer_name: str, *args, **kwargs) -> BaseRenderer:
        """
        Create a renderer instance.

        Args:
            renderer_name: Name of the renderer ('pygame', 'terminal', 'web')
            *args, **kwargs: Arguments to pass to the renderer constructor

        Returns:
            BaseRenderer instance

        Example:
            renderer = RendererFactory.create('pygame', width=1280, height=720)
        """
        if renderer_name not in cls._renderers:
            available = ", ".join(cls._renderers.keys())
            raise ValueError(
                f"Unknown renderer '{renderer_name}'. Available: {available}"
            )

        renderer_class = cls._renderers[renderer_name]
        return renderer_class(*args, **kwargs)

    @classmethod
    def list_renderers(cls) -> List[str]:
        """Get list of registered renderer names."""
        return list(cls._renderers.keys())
