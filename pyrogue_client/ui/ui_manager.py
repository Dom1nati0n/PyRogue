"""
UIManager - Manages menus, dialogs, and HUD elements

Reads engine state (Registry components) and renders UI elements via the renderer.
Manages input context stacking for menu navigation.
"""

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import EventBus
from pyrogue_client.renderers import BaseRenderer
from pyrogue_client.input import ClientInputAdapter


class UIManager:
    """
    Manages all UI elements.

    Coordinates between engine state (components), renderer (drawing),
    and input adapter (context stacking).
    """

    def __init__(
        self,
        registry: Registry,
        event_bus: EventBus,
        renderer: BaseRenderer,
        input_adapter: ClientInputAdapter,
    ):
        """
        Initialize the UI manager.

        Args:
            registry: pyrogue_engine Registry
            event_bus: pyrogue_engine EventBus
            renderer: BaseRenderer implementation
            input_adapter: ClientInputAdapter for context switching
        """
        self.registry = registry
        self.bus = event_bus
        self.renderer = renderer
        self.input = input_adapter

        # Active menus/dialogs
        self.active_menus = []

    def open_inventory_menu(self, player_entity_id: int) -> None:
        """Open the inventory menu for the player."""
        self.input.push_ui_context("inventory_menu")
        self.active_menus.append("inventory")

    def open_character_sheet(self, player_entity_id: int) -> None:
        """Open the character sheet menu."""
        self.input.push_ui_context("character_menu")
        self.active_menus.append("character")

    def open_abilities_menu(self, player_entity_id: int) -> None:
        """Open the abilities menu."""
        self.input.push_ui_context("abilities_menu")
        self.active_menus.append("abilities")

    def close_top_menu(self) -> None:
        """Close the top-most menu."""
        if self.active_menus:
            self.active_menus.pop()
            self.input.pop_ui_context()

    def close_all_menus(self) -> None:
        """Close all open menus."""
        while self.active_menus:
            self.close_top_menu()

    def render(self) -> None:
        """
        Render UI elements.

        Called after the game world is rendered but before presentation.
        """
        # TODO: Implement UI rendering
        # - Draw HUD (player stats, messages)
        # - Draw active menus (inventory, character sheet, etc.)
        # - Draw dialogs (quest updates, loot notifications, etc.)
        pass

    def update(self, dt: float) -> None:
        """
        Update UI state.

        Args:
            dt: Delta time since last frame
        """
        # TODO: Implement UI updates
        # - Animate menu transitions
        # - Update animated elements (health bars, etc.)
        pass
