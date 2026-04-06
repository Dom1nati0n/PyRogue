"""
TerminalRenderer - Terminal/Console implementation of BaseRenderer

Renders the game to the terminal using ASCII characters and colors.
Supports both curses (Linux/Mac) and standard terminal output (Windows/fallback).

Allows the same game to run in a retro terminal mode or headless server environment.
"""

from typing import Tuple, List, Optional, Dict
import sys
import os
from pyrogue_client.renderers.base_renderer import BaseRenderer, InputPayload, InputEvent


class TerminalRenderer(BaseRenderer):
    """
    Terminal-based display renderer.

    Renders the game to the terminal using ASCII art.
    Supports keyboard input via standard input.
    """

    # ASCII art mappings for common entities
    ASSET_MAP = {
        # Creatures
        "goblin": "g",
        "orc": "O",
        "troll": "T",
        "dragon": "D",
        "skeleton": "s",
        "zombie": "Z",
        "bat": "b",
        "spider": "8",

        # Items
        "sword": "/",
        "dagger": "\\",
        "bow": ")",
        "shield": "[",
        "potion": "!",
        "scroll": "?",
        "gold": "*",
        "health_potion": "!",
        "mana_potion": "!",

        # Environment
        "wall": "#",
        "floor": ".",
        "door": "+",
        "stairs": ">",
        "water": "~",
        "lava": "^",
        "altar": "_",

        # Traps
        "trap": "^",
        "pit": "v",

        # UI
        "player": "@",
        "npc": "N",
    }

    # Color codes (ANSI)
    COLORS = {
        "black": 30,
        "red": 31,
        "green": 32,
        "yellow": 33,
        "blue": 34,
        "magenta": 35,
        "cyan": 36,
        "white": 37,
    }

    def __init__(self, use_curses: bool = False):
        """
        Initialize Terminal renderer.

        Args:
            use_curses: If True, use curses library (Linux/Mac)
                       If False, use standard ANSI sequences
        """
        self.use_curses = use_curses and self._is_curses_available()
        self.width = 80
        self.height = 24
        self.buffer = []
        self.is_running = True
        self.input_buffer = []

        if self.use_curses:
            import curses
            self.curses = curses
            self.stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(True)
        else:
            self.stdscr = None

    # =========================================================================
    # WINDOW MANAGEMENT
    # =========================================================================

    def init_window(self, width: int, height: int, title: str) -> None:
        """Initialize terminal window."""
        self.width = width
        self.height = height
        self._clear_buffer()

        if not self.use_curses:
            # Clear screen using ANSI
            print("\033[2J\033[H", end="")

    def clear(self) -> None:
        """Clear the buffer."""
        self._clear_buffer()

    def present(self) -> None:
        """Display the buffer to terminal."""
        if self.use_curses:
            self._present_curses()
        else:
            self._present_ansi()

    def is_open(self) -> bool:
        """Check if terminal is still running."""
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
        # Get ASCII character for this asset
        char = self.ASSET_MAP.get(asset_id, "?")

        # Add to buffer
        self._add_to_buffer(x, y, char, fg_color, bg_color)

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        fg_color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """Draw text at the given position."""
        for i, char in enumerate(text):
            if x + i < self.width:
                self._add_to_buffer(x + i, y, char, fg_color, bg_color)

    # =========================================================================
    # INPUT HANDLING
    # =========================================================================

    def poll_input(self) -> List[InputPayload]:
        """Poll for input events from terminal."""
        events = []

        if self.use_curses:
            events = self._poll_input_curses()
        else:
            events = self._poll_input_ansi()

        # Check for quit
        if len(events) > 0 and events[0].event_type == InputEvent.QUIT:
            self.is_running = False

        return events

    def _poll_input_curses(self) -> List[InputPayload]:
        """Poll input using curses."""
        events = []

        try:
            self.stdscr.nodelay(True)
            ch = self.stdscr.getch()

            if ch == -1:
                return events

            # Map curses key codes to input events
            key_map = {
                self.curses.KEY_UP: InputEvent.MOVE_UP,
                self.curses.KEY_DOWN: InputEvent.MOVE_DOWN,
                self.curses.KEY_LEFT: InputEvent.MOVE_LEFT,
                self.curses.KEY_RIGHT: InputEvent.MOVE_RIGHT,
                ord(' '): InputEvent.WAIT,
                ord('q'): InputEvent.QUIT,
                27: InputEvent.QUIT,  # ESC
            }

            event_type = key_map.get(ch)
            if event_type:
                events.append(InputPayload(event_type))

        except:
            pass

        return events

    def _poll_input_ansi(self) -> List[InputPayload]:
        """Poll input using standard input (simplified)."""
        # Note: This is a simplified version that doesn't handle non-blocking input well
        # In production, would use tty/termios or similar
        events = []
        return events

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _clear_buffer(self) -> None:
        """Clear the display buffer."""
        self.buffer = [[(".", (255, 255, 255), (0, 0, 0)) for _ in range(self.width)] for _ in range(self.height)]

    def _add_to_buffer(
        self,
        x: int,
        y: int,
        char: str,
        fg_color: Tuple[int, int, int],
        bg_color: Tuple[int, int, int],
    ) -> None:
        """Add a character to the display buffer."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.buffer[y][x] = (char, fg_color, bg_color)

    def _is_curses_available(self) -> bool:
        """Check if curses is available."""
        try:
            import curses
            return True
        except ImportError:
            return False

    def _present_curses(self) -> None:
        """Display buffer using curses."""
        if not self.stdscr:
            return

        try:
            self.stdscr.clear()
            for y, row in enumerate(self.buffer):
                for x, (char, fg, bg) in enumerate(row):
                    if y < self.height and x < self.width:
                        self.stdscr.addch(y, x, ord(char))
            self.stdscr.refresh()
        except:
            pass

    def _present_ansi(self) -> None:
        """Display buffer using ANSI sequences."""
        output = "\033[H"  # Move cursor to home

        for y, row in enumerate(self.buffer):
            for x, (char, fg, bg) in enumerate(row):
                # Simple color: just use character
                output += char

            output += "\n"

        print(output, end="", flush=True)

    def _rgb_to_ansi(self, rgb: Tuple[int, int, int]) -> int:
        """Convert RGB to nearest ANSI color code."""
        r, g, b = rgb
        if r > 128:
            return 37  # white
        elif g > 128:
            return 32  # green
        elif b > 128:
            return 34  # blue
        else:
            return 30  # black

    # =========================================================================
    # CLEANUP
    # =========================================================================

    def shutdown(self) -> None:
        """Clean up terminal."""
        if self.use_curses and self.stdscr:
            import curses
            curses.echo()
            curses.nocbreak()
            curses.endwin()
