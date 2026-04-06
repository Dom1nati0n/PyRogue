"""
PygameRenderer - Pygame-CE implementation of BaseRenderer

Renders the game using Pygame Community Edition (pygame-ce).
Provides desktop GUI rendering with sprites, text, and input handling.
"""

from typing import Tuple, List, Dict, Any, Optional
import pygame
from pyrogue_client.renderers.base_renderer import BaseRenderer, InputPayload, InputEvent


class PygameRenderer(BaseRenderer):
    """
    Pygame-based display renderer.

    Handles all rendering through pygame-ce library.
    Manages sprite assets, fonts, and input events.
    """

    def __init__(self, asset_manager=None):
        """
        Initialize Pygame renderer.

        Args:
            asset_manager: Optional asset manager for loading sprites/fonts
        """
        self.asset_manager = asset_manager
        self.screen = None
        self.width = 0
        self.height = 0
        self.is_running = False
        self.clock = pygame.time.Clock()
        self.fps = 60

        # Font cache
        self.fonts = {}
        self.default_font = None

        # Sprite cache
        self.sprites = {}

    # =========================================================================
    # WINDOW MANAGEMENT
    # =========================================================================

    def init_window(self, width: int, height: int, title: str) -> None:
        """Initialize Pygame window."""
        if not pygame.get_init():
            pygame.init()

        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(title)

        # Initialize font
        self.default_font = pygame.font.Font(None, 24)

        self.is_running = True

    def clear(self) -> None:
        """Clear the screen with black."""
        if self.screen:
            self.screen.fill((0, 0, 0))

    def present(self) -> None:
        """Update the display."""
        if self.screen:
            pygame.display.flip()
            self.clock.tick(self.fps)

    def is_open(self) -> bool:
        """Check if window is still open."""
        return self.is_running

    # =========================================================================
    # DRAWING OPERATIONS
    # =========================================================================

    def draw_sprite(
        self,
        x: int,
        y: int,
        asset_id: str,
        fg_color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """Draw a sprite at the given position."""
        if not self.screen:
            return

        # Try to load from asset manager
        if self.asset_manager:
            try:
                sprite_surface = self.asset_manager.get_sprite(asset_id)
                self.screen.blit(sprite_surface, (x, y))
                return
            except:
                pass

        # Fallback: Draw a colored rectangle with asset_id text
        # (when no asset manager is available)
        pygame.draw.rect(self.screen, fg_color, (x, y, 32, 32))
        self._draw_asset_label(x, y, asset_id, fg_color, bg_color)

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        fg_color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """Draw text at the given position."""
        if not self.screen or not self.default_font:
            return

        # Render text surface
        if bg_color != (0, 0, 0):
            text_surface = self.default_font.render(text, True, fg_color, bg_color)
        else:
            text_surface = self.default_font.render(text, True, fg_color)

        # Blit to screen
        self.screen.blit(text_surface, (x, y))

    def _draw_asset_label(
        self,
        x: int,
        y: int,
        text: str,
        fg_color: Tuple[int, int, int],
        bg_color: Tuple[int, int, int],
    ) -> None:
        """Helper: Draw text label on top of a sprite."""
        if not self.screen or not self.default_font:
            return

        # Create small font for label
        small_font = pygame.font.Font(None, 12)
        label_surface = small_font.render(text[:3], True, fg_color)
        self.screen.blit(label_surface, (x + 2, y + 2))

    # =========================================================================
    # INPUT HANDLING
    # =========================================================================

    def poll_input(self) -> List[InputPayload]:
        """Poll Pygame events and convert to engine-agnostic input."""
        events = []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
                events.append(InputPayload(InputEvent.QUIT))

            elif event.type == pygame.KEYDOWN:
                input_event = self._map_key_event(event.key)
                if input_event:
                    events.append(input_event)

        return events

    def _map_key_event(self, key: int) -> Optional[InputPayload]:
        """Map Pygame key code to engine input event."""
        key_map = {
            # Movement
            pygame.K_UP: InputEvent.MOVE_UP,
            pygame.K_w: InputEvent.MOVE_UP,
            pygame.K_DOWN: InputEvent.MOVE_DOWN,
            pygame.K_s: InputEvent.MOVE_DOWN,
            pygame.K_LEFT: InputEvent.MOVE_LEFT,
            pygame.K_a: InputEvent.MOVE_LEFT,
            pygame.K_RIGHT: InputEvent.MOVE_RIGHT,
            pygame.K_d: InputEvent.MOVE_RIGHT,

            # Actions
            pygame.K_SPACE: InputEvent.WAIT,
            pygame.K_e: InputEvent.INTERACT,
            pygame.K_RETURN: InputEvent.INTERACT,
            pygame.K_f: InputEvent.ATTACK,
            pygame.K_g: InputEvent.PICK_UP,
            pygame.K_x: InputEvent.DROP,

            # UI
            pygame.K_i: InputEvent.INVENTORY,
            pygame.K_c: InputEvent.CHARACTER_SHEET,

            # System
            pygame.K_ESCAPE: InputEvent.QUIT,
            pygame.K_q: InputEvent.QUIT,
            pygame.K_F12: InputEvent.SCREENSHOT,
        }

        event_type = key_map.get(key)
        if event_type:
            return InputPayload(event_type)
        return None

    # =========================================================================
    # UTILITY
    # =========================================================================

    def get_window_size(self) -> Tuple[int, int]:
        """Get window dimensions."""
        return (self.width, self.height)

    def set_title(self, title: str) -> None:
        """Set window title."""
        pygame.display.set_caption(title)

    def screenshot(self, filename: str) -> None:
        """Save a screenshot."""
        if self.screen:
            pygame.image.save(self.screen, filename)

    def shutdown(self) -> None:
        """Clean up Pygame."""
        pygame.quit()
