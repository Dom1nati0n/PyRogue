"""
Pyrogue Client - Presentation Layer

The client is the thin shell that wraps pyrogue_engine.
It handles all hardware I/O and presentation:
- Input translation (keyboard → engine events)
- Rendering (engine state → display)
- UI (menus, HUD, dialogs)
- Audio (sound effects, music)

The client imports pyrogue_engine but pyrogue_engine never imports the client.
This enforces the Hexagonal Architecture boundary.
"""

from pyrogue_client.client_app import ClientApp, create_client
from pyrogue_client.input import ClientInputAdapter, EnhancedInputSystem
from pyrogue_client.renderers import (
    BaseRenderer,
    RendererFactory,
    PygameRenderer,
    TerminalRenderer,
    WebRenderer,
)

__all__ = [
    "ClientApp",
    "create_client",
    "ClientInputAdapter",
    "EnhancedInputSystem",
    "BaseRenderer",
    "RendererFactory",
    "PygameRenderer",
    "TerminalRenderer",
    "WebRenderer",
]
