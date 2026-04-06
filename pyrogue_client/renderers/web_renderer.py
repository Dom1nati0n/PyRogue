"""
WebRenderer - Web/Browser implementation of BaseRenderer

Instead of rendering immediately, accumulates draw calls into a JSON frame buffer.
The frame buffer is broadcast to a web client for rendering via WebGL or Canvas.

Allows the same game engine to power both desktop (Pygame) and web (Browser) versions.
"""

from typing import Tuple, List, Optional, Dict, Any
import json
from pyrogue_client.renderers.base_renderer import BaseRenderer, InputPayload, InputEvent


class WebRenderer(BaseRenderer):
    """
    Web-based display renderer.

    Accumulates draw calls into JSON frames instead of immediate rendering.
    Frames are JSON-serializable for transmission to web clients.

    Frame format:
    {
        "type": "frame",
        "sprites": [
            {"x": 10, "y": 10, "asset": "goblin", "fg": [255,0,0], "bg": [0,0,0]},
            ...
        ],
        "text": [
            {"x": 5, "y": 2, "text": "Health: 50/100", "fg": [0,255,0], "bg": [0,0,0]},
            ...
        ]
    }
    """

    def __init__(self, output_file: Optional[str] = None, broadcast_fn=None):
        """
        Initialize Web renderer.

        Args:
            output_file: Optional file to write frames to (for development/testing)
            broadcast_fn: Optional function to call with each frame (for websocket/etc)
        """
        self.output_file = output_file
        self.broadcast_fn = broadcast_fn
        self.width = 80
        self.height = 24
        self.frame_buffer = {"sprites": [], "text": []}
        self.is_running = True
        self.frame_count = 0

    # =========================================================================
    # WINDOW MANAGEMENT
    # =========================================================================

    def init_window(self, width: int, height: int, title: str) -> None:
        """Initialize web window (stores dimensions)."""
        self.width = width
        self.height = height
        self.frame_buffer = {"sprites": [], "text": []}

        # Send initial frame with window info
        init_frame = {
            "type": "init",
            "width": width,
            "height": height,
            "title": title,
        }
        self._broadcast_frame(init_frame)

    def clear(self) -> None:
        """Clear the frame buffer."""
        self.frame_buffer = {"sprites": [], "text": []}

    def present(self) -> None:
        """
        Send the accumulated frame to the web client.

        This is where all the draw calls are bundled and transmitted.
        """
        frame = {
            "type": "frame",
            "frame_number": self.frame_count,
            "sprites": self.frame_buffer["sprites"],
            "text": self.frame_buffer["text"],
        }

        self._broadcast_frame(frame)
        self.frame_count += 1
        self.clear()

    def is_open(self) -> bool:
        """Check if web session is still active."""
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
        """Add a sprite draw call to the frame buffer."""
        sprite_data = {
            "x": x,
            "y": y,
            "asset": asset_id,
            "fg": list(fg_color),
            "bg": list(bg_color),
        }
        self.frame_buffer["sprites"].append(sprite_data)

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        fg_color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """Add a text draw call to the frame buffer."""
        text_data = {
            "x": x,
            "y": y,
            "text": text,
            "fg": list(fg_color),
            "bg": list(bg_color),
        }
        self.frame_buffer["text"].append(text_data)

    # =========================================================================
    # INPUT HANDLING
    # =========================================================================

    def poll_input(self) -> List[InputPayload]:
        """
        Poll for input from the web client.

        In a real implementation, this would read from a websocket queue
        or HTTP polling mechanism.

        For now, returns empty (input would come via websocket/HTTP).
        """
        # In a real web implementation, this would:
        # 1. Check a queue of inputs from the web client
        # 2. Parse them and convert to InputPayload
        # 3. Return the list
        return []

    def receive_input(self, input_data: Dict[str, Any]) -> InputPayload:
        """
        Receive an input event from the web client.

        Args:
            input_data: Dict like {"type": "move", "direction": "up"}

        Returns:
            InputPayload representing the input
        """
        input_type = input_data.get("type", "").lower()

        key_map = {
            "move_up": InputEvent.MOVE_UP,
            "move_down": InputEvent.MOVE_DOWN,
            "move_left": InputEvent.MOVE_LEFT,
            "move_right": InputEvent.MOVE_RIGHT,
            "interact": InputEvent.INTERACT,
            "attack": InputEvent.ATTACK,
            "wait": InputEvent.WAIT,
            "inventory": InputEvent.INVENTORY,
            "character_sheet": InputEvent.CHARACTER_SHEET,
            "quit": InputEvent.QUIT,
        }

        event_type = key_map.get(input_type)
        if event_type:
            return InputPayload(event_type, **input_data)

        return None

    # =========================================================================
    # BROADCASTING
    # =========================================================================

    def _broadcast_frame(self, frame: Dict[str, Any]) -> None:
        """
        Broadcast a frame to the web client.

        Implementation options:
        1. Write to file (for testing)
        2. Call broadcast function (for websocket/HTTP)
        3. Both
        """
        # Write to file if specified (useful for debugging/testing)
        if self.output_file:
            try:
                with open(self.output_file, "a") as f:
                    f.write(json.dumps(frame) + "\n")
            except:
                pass

        # Call broadcast function if provided (for real websocket/HTTP)
        if self.broadcast_fn:
            try:
                self.broadcast_fn(frame)
            except:
                pass

    def get_frame_json(self) -> str:
        """Get the current frame as JSON string (for testing)."""
        frame = {
            "type": "frame",
            "frame_number": self.frame_count,
            "sprites": self.frame_buffer["sprites"],
            "text": self.frame_buffer["text"],
        }
        return json.dumps(frame, indent=2)

    # =========================================================================
    # UTILITY
    # =========================================================================

    def get_window_size(self) -> Tuple[int, int]:
        """Get window dimensions."""
        return (self.width, self.height)

    def set_title(self, title: str) -> None:
        """Set window title (send to client)."""
        title_frame = {
            "type": "set_title",
            "title": title,
        }
        self._broadcast_frame(title_frame)

    def shutdown(self) -> None:
        """Send shutdown signal to client."""
        shutdown_frame = {
            "type": "shutdown",
            "message": "Game engine shutting down",
        }
        self._broadcast_frame(shutdown_frame)
