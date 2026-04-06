"""
ClientInputAdapter - Bridges hardware input to pyrogue_engine events

Wraps the EnhancedInputSystem and translates action callbacks into
pyrogue_engine EventBus events. Manages input context stacking for
UI/Gameplay mode switching.
"""

from pyrogue_client.input.enhanced_input_system import (
    EnhancedInputSystem,
    InputTriggerType,
)
from pyrogue_engine.systems.spatial.movement import MovementIntentEvent
from pyrogue_engine.systems.rpg.combat_system import AttackIntentEvent
from pyrogue_engine.core.events import EventBus


class ClientInputAdapter:
    """
    Bridges the hardware-level EnhancedInputSystem to the pure-math pyrogue_engine EventBus.

    Manages:
    - Loading input profiles
    - Translating EIS actions to Engine events
    - Input context stacking (UI vs Gameplay)
    - Player entity binding
    """

    def __init__(self, engine_event_bus: EventBus, profile_path: str = "pyrogue_client/input/profiles/default.json"):
        """
        Initialize the input adapter.

        Args:
            engine_event_bus: pyrogue_engine EventBus for emitting intents
            profile_path: Path to JSON input profile
        """
        self.bus = engine_event_bus
        self.eis = EnhancedInputSystem(profile_path)

        # Current player entity (set before gameplay)
        self.player_entity_id = None

        self._register_bindings()

    def set_player_entity(self, entity_id: int) -> None:
        """Set the entity that input intents are directed at."""
        self.player_entity_id = entity_id

    def push_ui_context(self, context_name: str) -> bool:
        """
        Push a UI context (e.g., 'inventory_menu').
        Higher priority contexts block lower priority ones.
        """
        return self.eis.push_context_by_name(context_name)

    def pop_ui_context(self) -> bool:
        """Pop the current context stack."""
        popped = self.eis.pop_context()
        return popped is not None

    def update(self, dt: float) -> None:
        """
        Update input system.

        Call once per frame from the main client loop.
        Processes pygame events and fires registered callbacks.
        """
        self.eis.update(dt)

    # =========================================================================
    # Private: Callback Registration
    # =========================================================================

    def _register_bindings(self) -> None:
        """Register all action callbacks that bridge to engine events."""

        # --- MOVEMENT BINDINGS ---
        self.eis.add_callback("move_north", InputTriggerType.TRIGGERED, lambda val: self._on_move(0, -1))
        self.eis.add_callback("move_south", InputTriggerType.TRIGGERED, lambda val: self._on_move(0, 1))
        self.eis.add_callback("move_east", InputTriggerType.TRIGGERED, lambda val: self._on_move(1, 0))
        self.eis.add_callback("move_west", InputTriggerType.TRIGGERED, lambda val: self._on_move(-1, 0))

        # Diagonals
        self.eis.add_callback("move_northwest", InputTriggerType.TRIGGERED, lambda val: self._on_move(-1, -1))
        self.eis.add_callback("move_northeast", InputTriggerType.TRIGGERED, lambda val: self._on_move(1, -1))
        self.eis.add_callback("move_southwest", InputTriggerType.TRIGGERED, lambda val: self._on_move(-1, 1))
        self.eis.add_callback("move_southeast", InputTriggerType.TRIGGERED, lambda val: self._on_move(1, 1))

        # --- ACTION BINDINGS ---
        self.eis.add_callback("wait", InputTriggerType.TRIGGERED, self._on_wait)
        self.eis.add_callback("interact", InputTriggerType.TRIGGERED, self._on_interact)

        # --- UI BINDINGS ---
        self.eis.add_callback("inventory", InputTriggerType.TRIGGERED, self._on_inventory)
        self.eis.add_callback("character", InputTriggerType.TRIGGERED, self._on_character)
        self.eis.add_callback("abilities", InputTriggerType.TRIGGERED, self._on_abilities)
        self.eis.add_callback("messages", InputTriggerType.TRIGGERED, self._on_messages)
        self.eis.add_callback("look", InputTriggerType.TRIGGERED, self._on_look)
        self.eis.add_callback("menu", InputTriggerType.TRIGGERED, self._on_menu)

    # =========================================================================
    # Private: Event Emission
    # =========================================================================

    def _on_move(self, dx: int, dy: int) -> None:
        """Emit movement intent to engine."""
        if self.player_entity_id is not None:
            self.bus.emit(MovementIntentEvent(
                entity_id=self.player_entity_id,
                dx=dx,
                dy=dy
            ))

    def _on_wait(self, value) -> None:
        """Emit wait/skip turn intent."""
        if self.player_entity_id is not None:
            # Wait is a no-op intent; game logic handles it
            from pyrogue_engine.core.events import Event

            class WaitIntentEvent(Event):
                def __init__(self, entity_id: int):
                    self.entity_id = entity_id

            self.bus.emit(WaitIntentEvent(self.player_entity_id))

    def _on_interact(self, value) -> None:
        """Emit interaction intent."""
        if self.player_entity_id is not None:
            from pyrogue_engine.core.events import Event

            class InteractionIntentEvent(Event):
                def __init__(self, entity_id: int):
                    self.entity_id = entity_id

            self.bus.emit(InteractionIntentEvent(self.player_entity_id))

    def _on_inventory(self, value) -> None:
        """Open inventory menu."""
        self.push_ui_context("inventory_menu")

    def _on_character(self, value) -> None:
        """Open character sheet menu."""
        self.push_ui_context("character_menu")

    def _on_abilities(self, value) -> None:
        """Open abilities menu."""
        self.push_ui_context("abilities_menu")

    def _on_messages(self, value) -> None:
        """Open message log menu."""
        self.push_ui_context("messages_menu")

    def _on_look(self, value) -> None:
        """Enter look mode."""
        self.push_ui_context("look_mode")

    def _on_menu(self, value) -> None:
        """Open pause/escape menu."""
        self.push_ui_context("pause_menu")
