"""Renderers - Display adapters for different platforms"""

from pyrogue_client.renderers.base_renderer import (
    BaseRenderer,
    InputEvent,
    InputPayload,
    RendererFactory,
)
from pyrogue_client.renderers.pygame_renderer import PygameRenderer
from pyrogue_client.renderers.terminal_renderer import TerminalRenderer
from pyrogue_client.renderers.web_renderer import WebRenderer

# Register all renderers
RendererFactory.register_renderer("pygame", PygameRenderer)
RendererFactory.register_renderer("terminal", TerminalRenderer)
RendererFactory.register_renderer("web", WebRenderer)

__all__ = [
    "BaseRenderer",
    "InputEvent",
    "InputPayload",
    "RendererFactory",
    "PygameRenderer",
    "TerminalRenderer",
    "WebRenderer",
]
