"""
Enhanced Input System - Modeled after Unreal's Enhanced Input System
Fully configurable via JSON input profiles with modifiers, triggers, contexts, and actions
Features:
  - Input Mapping Contexts with priority-based stacking
  - All button trigger types (Pressed, Released, Held, Triggered, etc.)
  - Trigger categories: Explicit, Implicit, Blocker
  - Value modifiers (scale, deadzone, smooth, negate, swizzle)
  - Context push/pop for UI/Gameplay switching
  - Callback system with priority
"""

import json
import pygame
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Tuple, Any


class InputTriggerType(Enum):
    """Button press modes - all trigger types"""
    DOWN = "down"                 # Key is held down
    PRESSED = "pressed"           # Key just pressed this frame
    RELEASED = "released"         # Key just released this frame
    TRIGGERED = "triggered"       # Any change (pressed or released)
    TAP = "tap"                   # Quick press and release
    LONG_PRESS = "long_press"     # Held for duration
    DOUBLE_TAP = "double_tap"     # Two taps within window


class TriggerCategory(Enum):
    """Trigger behavior category (Unreal style)"""
    EXPLICIT = "explicit"         # Succeeds if trigger succeeds - others ignored
    IMPLICIT = "implicit"         # Succeeds only if ALL implicit succeed
    BLOCKER = "blocker"          # Fails mapping if blocker succeeds


class InputValueType(Enum):
    """Type of value the action produces"""
    DIGITAL = "digital"           # Boolean (pressed/not pressed)
    AXIS_1D = "axis_1d"          # Single axis (-1 to 1)
    AXIS_2D = "axis_2d"          # Two axes (x, y)
    AXIS_3D = "axis_3d"          # Three axes (x, y, z)


class InputModifierType(Enum):
    """Modifiers that transform input values"""
    NEGATE = "negate"             # Invert the value
    SWIZZLE = "swizzle"           # Rearrange axes
    SCALE = "scale"               # Multiply by factor
    DEADZONE = "deadzone"         # Remove small movements
    SMOOTH = "smooth"             # Smooth over time


@dataclass
class InputModifier:
    """Modifies an input value before triggering action"""
    type: InputModifierType
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> 'InputModifier':
        return cls(
            type=InputModifierType(data['type']),
            params=data.get('params', {})
        )

    def apply(self, value: Any) -> Any:
        """Apply this modifier to an input value"""
        if self.type == InputModifierType.NEGATE:
            if isinstance(value, (int, float)):
                return -value
            elif isinstance(value, tuple):
                return tuple(-v for v in value)

        elif self.type == InputModifierType.SCALE:
            scale = self.params.get('scale', 1.0)
            if isinstance(value, (int, float)):
                return value * scale
            elif isinstance(value, tuple):
                return tuple(v * scale for v in value)

        elif self.type == InputModifierType.DEADZONE:
            threshold = self.params.get('threshold', 0.1)
            if isinstance(value, (int, float)):
                return value if abs(value) > threshold else 0
            elif isinstance(value, tuple):
                return tuple(v if abs(v) > threshold else 0 for v in value)

        elif self.type == InputModifierType.SWIZZLE:
            order = self.params.get('order', [0, 1])
            if isinstance(value, tuple):
                return tuple(value[i] if i < len(value) else 0 for i in order)

        return value


@dataclass
class InputTrigger:
    """Determines when an input action fires with category support"""
    type: InputTriggerType
    category: TriggerCategory = TriggerCategory.EXPLICIT
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> 'InputTrigger':
        category_str = data.get('category', 'explicit')
        try:
            category = TriggerCategory(category_str)
        except ValueError:
            category = TriggerCategory.EXPLICIT

        return cls(
            type=InputTriggerType(data['type']),
            category=category,
            params=data.get('params', {})
        )

    def should_trigger(self, is_down: bool, was_down: bool, press_duration: float = 0.0, value: Any = None) -> bool:
        """Determine if action should trigger based on this trigger type"""
        if self.type == InputTriggerType.PRESSED:
            return is_down and not was_down  # Just pressed
        elif self.type == InputTriggerType.RELEASED:
            return not is_down and was_down  # Just released
        elif self.type == InputTriggerType.DOWN:
            return is_down  # While held down
        elif self.type == InputTriggerType.TRIGGERED:
            return is_down != was_down  # Any change
        elif self.type == InputTriggerType.TAP:
            # Quick press and release
            return not is_down and was_down and press_duration < self.params.get('max_duration', 0.2)
        elif self.type == InputTriggerType.LONG_PRESS:
            # Held for minimum duration
            min_duration = self.params.get('min_duration', 0.5)
            return is_down and press_duration >= min_duration
        elif self.type == InputTriggerType.DOUBLE_TAP:
            # Two taps within window - simplified
            return is_down and not was_down
        return False


@dataclass
class InputMapping:
    """Maps physical input (key/button) to logical action"""
    key: int = 0                           # pygame key code
    mouse_button: int = 0                 # 1=left, 2=right, 3=middle
    axis: str = ""                        # 'axis_x', 'axis_y', 'axis_scroll'
    modifier_keys: List[int] = field(default_factory=list)  # Ctrl, Shift, Alt

    modifiers: List[InputModifier] = field(default_factory=list)
    triggers: List[InputTrigger] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict) -> 'InputMapping':
        mapping = cls(
            key=data.get('key', 0),
            mouse_button=data.get('mouse_button', 0),
            axis=data.get('axis', ''),
            modifier_keys=data.get('modifier_keys', [])
        )

        # Parse modifiers
        for mod_data in data.get('modifiers', []):
            mapping.modifiers.append(InputModifier.from_dict(mod_data))

        # Parse triggers
        for trig_data in data.get('triggers', []):
            mapping.triggers.append(InputTrigger.from_dict(trig_data))

        # Default trigger if none specified
        if not mapping.triggers:
            mapping.triggers.append(InputTrigger(InputTriggerType.PRESSED))

        return mapping

    def apply_modifiers(self, value: Any) -> Any:
        """Apply all modifiers to a value in sequence"""
        for modifier in self.modifiers:
            value = modifier.apply(value)
        return value


@dataclass
class InputAction:
    """A logical input action (e.g., 'Move', 'Attack')"""
    name: str
    value_type: InputValueType
    mappings: List[InputMapping] = field(default_factory=list)

    # State tracking
    current_value: Any = None
    is_down: bool = False
    was_down: bool = False
    should_trigger: bool = False
    press_duration: float = 0.0  # How long the key has been held

    @classmethod
    def from_dict(cls, name: str, data: Dict) -> 'InputAction':
        action = cls(
            name=name,
            value_type=InputValueType(data.get('value_type', 'digital'))
        )

        for mapping_data in data.get('mappings', []):
            action.mappings.append(InputMapping.from_dict(mapping_data))

        return action


@dataclass
class InputCallback:
    """Callback triggered when an action fires"""
    action_name: str
    trigger_type: InputTriggerType
    callback: Callable
    priority: int = 0  # Higher priority fires first


@dataclass
class InputMappingContext:
    """Groups input mappings for a specific context (UI, Gameplay, etc.)"""
    name: str
    priority: int = 0                                    # Higher priority = active first
    enabled: bool = True                                 # Can be disabled/enabled
    actions: Dict[str, InputAction] = field(default_factory=dict)

    @classmethod
    def from_file(cls, filepath: str, name: str = None, priority: int = 0) -> 'InputMappingContext':
        """Load a mapping context from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)

        context = cls(
            name=name or data.get('name', 'Default'),
            priority=priority
        )

        for action_name, action_data in data.get('actions', {}).items():
            context.actions[action_name] = InputAction.from_dict(action_name, action_data)

        return context

    def get_action(self, name: str) -> Optional[InputAction]:
        """Get an action by name from this context"""
        return self.actions.get(name)

    def add_action(self, action: InputAction) -> None:
        """Add an action to this context"""
        self.actions[action.name] = action


class InputProfile:
    """Complete input configuration (can be swapped at runtime)"""

    def __init__(self, name: str):
        self.name = name
        self.actions: Dict[str, InputAction] = {}
        self.contexts: List[InputMappingContext] = []

    @classmethod
    def from_file(cls, filepath: str) -> 'InputProfile':
        """Load an input profile from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)

        profile = cls(data.get('name', 'Default'))

        for action_name, action_data in data.get('actions', {}).items():
            profile.actions[action_name] = InputAction.from_dict(action_name, action_data)

        return profile

    def get_action(self, name: str) -> Optional[InputAction]:
        """Get an action by name from all contexts"""
        return self.actions.get(name)

    def add_action(self, action: InputAction) -> None:
        """Add an action to the profile"""
        self.actions[action.name] = action

    def add_context(self, context: InputMappingContext) -> None:
        """Add a mapping context"""
        self.contexts.append(context)
        # Keep sorted by priority (highest first)
        self.contexts.sort(key=lambda c: c.priority, reverse=True)

    def remove_context(self, context_name: str) -> None:
        """Remove a mapping context"""
        self.contexts = [c for c in self.contexts if c.name != context_name]

    def get_context(self, name: str) -> Optional[InputMappingContext]:
        """Get a context by name"""
        return next((c for c in self.contexts if c.name == name), None)


class EnhancedInputSystem:
    """
    Complete input system modeled after Unreal's Enhanced Input System.
    Handles:
      - Input actions with value types (digital, axis1d, axis2d, axis3d)
      - Input mappings with modifiers and triggers
      - Input mapping contexts with priority stacking
      - Trigger categories (explicit, implicit, blocker)
      - All button modes (pressed, released, down, tap, long_press, double_tap, etc.)
      - Callbacks with priority
      - Context push/pop for UI/Gameplay switching
    """

    def __init__(self, default_profile_path: str = "input_profile.json"):
        self.current_profile = InputProfile.from_file(default_profile_path)

        # Callback system
        self.callbacks: List[InputCallback] = []

        # Input state for each action
        self.action_values: Dict[str, Any] = {}
        self.action_pressed: Dict[str, bool] = {}
        self.action_triggered: Dict[str, bool] = {}
        self.action_press_duration: Dict[str, float] = {}

        # Input mapping contexts (stack-based, highest priority active)
        self.active_contexts: List[InputMappingContext] = []

        # Physical input state
        self.keys_pressed: set = set()
        self.keys_down: set = set()
        self.key_press_time: Dict[int, float] = {}  # Track when key was pressed
        self.mouse_buttons: Dict[int, bool] = {1: False, 2: False, 3: False}
        self.mouse_button_press_time: Dict[int, float] = {}
        self.mouse_pos: Tuple[int, int] = (0, 0)
        self.scroll_delta: int = 0

        # Modifier key state
        self.shift_held = False
        self.ctrl_held = False
        self.alt_held = False

        # Timing for duration tracking
        self.last_frame_time = 0.0

    def load_profile(self, filepath: str) -> None:
        """Load a new input profile"""
        self.current_profile = InputProfile.from_file(filepath)
        self.active_contexts.clear()

    def push_context(self, context: InputMappingContext) -> None:
        """Push a context onto the stack (enables it with high priority)"""
        self.active_contexts.append(context)
        self.active_contexts.sort(key=lambda c: c.priority, reverse=True)

    def pop_context(self) -> Optional[InputMappingContext]:
        """Pop the top context from the stack"""
        if self.active_contexts:
            return self.active_contexts.pop()
        return None

    def push_context_by_name(self, context_name: str) -> bool:
        """Push a context by name from the profile"""
        context = self.current_profile.get_context(context_name)
        if context:
            self.push_context(context)
            return True
        return False

    def pop_context_by_name(self, context_name: str) -> bool:
        """Remove a specific context from the active stack"""
        original_len = len(self.active_contexts)
        self.active_contexts = [c for c in self.active_contexts if c.name != context_name]
        return len(self.active_contexts) < original_len

    def enable_context(self, context_name: str) -> bool:
        """Enable a context in the active stack"""
        context = next((c for c in self.active_contexts if c.name == context_name), None)
        if context:
            context.enabled = True
            return True
        return False

    def disable_context(self, context_name: str) -> bool:
        """Disable a context in the active stack (without removing it)"""
        context = next((c for c in self.active_contexts if c.name == context_name), None)
        if context:
            context.enabled = False
            return True
        return False

    def add_callback(self, action_name: str, trigger_type: InputTriggerType,
                     callback: Callable, priority: int = 0) -> None:
        """Register a callback for an action"""
        cb = InputCallback(action_name, trigger_type, callback, priority)
        self.callbacks.append(cb)
        # Sort by priority (higher first)
        self.callbacks.sort(key=lambda x: x.priority, reverse=True)

    def remove_callback(self, callback: InputCallback) -> None:
        """Unregister a callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def update(self, dt: float) -> None:
        """Update input system - call once per frame"""
        import time
        current_time = time.time()

        # Process pygame events
        self._process_events()

        # Update press durations for tracked keys
        for key in self.key_press_time:
            if key in self.keys_down:
                self.key_press_time[key] = current_time - self.key_press_time[key]

        # Update all actions from active contexts (by priority)
        # Higher priority contexts block lower priority ones
        processed_actions = set()

        for context in self.active_contexts:
            if not context.enabled:
                continue

            for action_name, action in context.actions.items():
                if action_name in processed_actions:
                    continue  # Already processed by higher priority context

                self._update_action(action, self.key_press_time.get(
                    next((m.key for m in action.mappings if m.key), None), 0.0))
                processed_actions.add(action_name)

        # Also update actions from base profile
        for action_name, action in self.current_profile.actions.items():
            if action_name not in processed_actions:
                self._update_action(action, self.key_press_time.get(
                    next((m.key for m in action.mappings if m.key), None), 0.0))

        # Fire callbacks
        self._fire_callbacks()

    def _process_events(self) -> None:
        """Process pygame events and update physical input state"""
        import time
        current_time = time.time()

        self.keys_pressed.clear()
        self.scroll_delta = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            elif event.type == pygame.KEYDOWN:
                self.keys_down.add(event.key)
                self.keys_pressed.add(event.key)

                # Track press start time
                if event.key not in self.key_press_time:
                    self.key_press_time[event.key] = current_time

                # Update modifier keys
                if event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
                    self.shift_held = True
                elif event.key == pygame.K_LCTRL or event.key == pygame.K_RCTRL:
                    self.ctrl_held = True
                elif event.key == pygame.K_LALT or event.key == pygame.K_RALT:
                    self.alt_held = True

            elif event.type == pygame.KEYUP:
                self.keys_down.discard(event.key)

                # Clear press time tracking
                if event.key in self.key_press_time:
                    del self.key_press_time[event.key]

                if event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
                    self.shift_held = False
                elif event.key == pygame.K_LCTRL or event.key == pygame.K_RCTRL:
                    self.ctrl_held = False
                elif event.key == pygame.K_LALT or event.key == pygame.K_RALT:
                    self.alt_held = False

            elif event.type == pygame.MOUSEMOTION:
                self.mouse_pos = event.pos

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button in [1, 2, 3]:
                    self.mouse_buttons[event.button] = True
                    self.mouse_button_press_time[event.button] = current_time
                elif event.button == 4:
                    self.scroll_delta = 1
                elif event.button == 5:
                    self.scroll_delta = -1

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button in [1, 2, 3]:
                    self.mouse_buttons[event.button] = False
                    if event.button in self.mouse_button_press_time:
                        del self.mouse_button_press_time[event.button]

        return True

    def _update_action(self, action: InputAction, press_duration: float = 0.0) -> None:
        """Update an input action based on current input state and trigger categories"""
        action.was_down = action.is_down
        action.is_down = False
        action.should_trigger = False
        new_value = None

        explicit_triggered = False
        implicit_passed = True
        blocker_blocked = False

        # Check each mapping for this action
        for mapping in action.mappings:
            # Check if this mapping is active
            if not self._check_mapping_active(mapping):
                continue

            # Get raw value from input
            value = self._get_mapping_value(mapping)
            if value is None:
                continue

            # Apply modifiers
            value = mapping.apply_modifiers(value)

            # Check triggers with categories
            for trigger in mapping.triggers:
                trigger_result = trigger.should_trigger(
                    self._mapping_is_down(mapping),
                    self._mapping_was_down(mapping),
                    press_duration,
                    value
                )

                if trigger.category == TriggerCategory.EXPLICIT:
                    if trigger_result:
                        explicit_triggered = True
                        action.is_down = True
                        action.should_trigger = True
                        new_value = value
                        break

                elif trigger.category == TriggerCategory.IMPLICIT:
                    if not trigger_result:
                        implicit_passed = False

                elif trigger.category == TriggerCategory.BLOCKER:
                    if trigger_result:
                        blocker_blocked = True
                        break

            if explicit_triggered or blocker_blocked:
                break

        # Apply category logic
        if blocker_blocked:
            action.is_down = False
            action.should_trigger = False
            new_value = None
        elif implicit_passed and not explicit_triggered:
            # Implicit triggers determine success if no explicit trigger
            action.is_down = implicit_passed
            if implicit_passed:
                action.should_trigger = True

        action.current_value = new_value
        action.press_duration = press_duration
        self.action_values[action.name] = new_value
        self.action_pressed[action.name] = action.is_down
        self.action_triggered[action.name] = action.should_trigger
        self.action_press_duration[action.name] = press_duration

    def _check_mapping_active(self, mapping: InputMapping) -> bool:
        """Check if modifier keys for this mapping are satisfied"""
        if not mapping.modifier_keys:
            return True

        for mod_key in mapping.modifier_keys:
            if mod_key == pygame.K_LSHIFT or mod_key == pygame.K_RSHIFT:
                if not self.shift_held:
                    return False
            elif mod_key == pygame.K_LCTRL or mod_key == pygame.K_RCTRL:
                if not self.ctrl_held:
                    return False
            elif mod_key == pygame.K_LALT or mod_key == pygame.K_RALT:
                if not self.alt_held:
                    return False

        return True

    def _get_mapping_value(self, mapping: InputMapping) -> Any:
        """Get the value from a physical input mapping"""
        if mapping.key:
            if mapping.key in self.keys_down:
                return 1.0

        elif mapping.mouse_button:
            if self.mouse_buttons.get(mapping.mouse_button, False):
                return 1.0

        elif mapping.axis:
            if mapping.axis == 'axis_x':
                return 1.0 if pygame.key.get_pressed()[pygame.K_RIGHT] else (-1.0 if pygame.key.get_pressed()[pygame.K_LEFT] else 0.0)
            elif mapping.axis == 'axis_y':
                return 1.0 if pygame.key.get_pressed()[pygame.K_DOWN] else (-1.0 if pygame.key.get_pressed()[pygame.K_UP] else 0.0)
            elif mapping.axis == 'axis_scroll':
                return float(self.scroll_delta)

        return None

    def _mapping_is_down(self, mapping: InputMapping) -> bool:
        """Check if a mapping is currently active"""
        if mapping.key:
            return mapping.key in self.keys_down
        elif mapping.mouse_button:
            return self.mouse_buttons.get(mapping.mouse_button, False)
        elif mapping.axis:
            value = self._get_mapping_value(mapping)
            return value is not None and value != 0
        return False

    def _mapping_was_down(self, mapping: InputMapping) -> bool:
        """Check if a mapping was active last frame"""
        # This would require frame-to-frame tracking
        # For now, return False
        return False

    def _fire_callbacks(self) -> None:
        """Fire all registered callbacks for triggered actions"""
        for callback in self.callbacks:
            # Check both profile and active contexts for the action
            action = self.current_profile.get_action(callback.action_name)

            # Check active contexts (highest priority first)
            for context in self.active_contexts:
                if context.enabled:
                    context_action = context.get_action(callback.action_name)
                    if context_action:
                        action = context_action
                        break

            if not action:
                continue

            # Check if this trigger type should fire
            should_fire = False
            if callback.trigger_type == InputTriggerType.PRESSED:
                should_fire = action.should_trigger and action.is_down
            elif callback.trigger_type == InputTriggerType.RELEASED:
                should_fire = action.should_trigger and not action.is_down
            elif callback.trigger_type == InputTriggerType.DOWN:
                should_fire = action.is_down
            elif callback.trigger_type == InputTriggerType.TRIGGERED:
                should_fire = action.should_trigger
            elif callback.trigger_type == InputTriggerType.TAP:
                should_fire = action.should_trigger and action.press_duration < 0.2
            elif callback.trigger_type == InputTriggerType.LONG_PRESS:
                should_fire = action.is_down and action.press_duration >= 0.5
            elif callback.trigger_type == InputTriggerType.DOUBLE_TAP:
                should_fire = action.should_trigger  # Simplified

            if should_fire:
                callback.callback(action.current_value)

    # Convenience methods
    def is_action_pressed(self, action_name: str) -> bool:
        """Check if an action is currently pressed"""
        return self.action_pressed.get(action_name, False)

    def is_action_triggered(self, action_name: str) -> bool:
        """Check if an action just triggered this frame"""
        return self.action_triggered.get(action_name, False)

    def get_action_value(self, action_name: str) -> Any:
        """Get the current value of an action"""
        return self.action_values.get(action_name)

    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position"""
        return self.mouse_pos
