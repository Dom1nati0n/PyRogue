"""
AudioManager - Sound effects and music management

Listens to pyrogue_engine events and plays appropriate sounds.
Handles background music and sound effect caching.
"""

import pygame
from pyrogue_engine.core.events import EventBus, Event


class AudioManager:
    """
    Manages sound effects and music.

    Subscribes to engine events and plays sounds in response.
    Caches sound samples to avoid repeated file I/O.
    """

    def __init__(self, event_bus: EventBus):
        """
        Initialize the audio manager.

        Args:
            event_bus: pyrogue_engine EventBus to subscribe to
        """
        self.bus = event_bus
        self.sounds = {}  # Sound cache: {sound_id: pygame.mixer.Sound}
        self.music = None  # Current background music

        # Initialize pygame mixer if not already done
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        # Subscribe to events
        # TODO: Connect to engine events as they're defined
        # Examples:
        # self.bus.on(DamageTakenEvent, self._on_damage)
        # self.bus.on(MovementIntentEvent, self._on_footstep)
        # self.bus.on(DeathEvent, self._on_death)

    def load_sound(self, sound_id: str, filepath: str) -> None:
        """
        Load a sound effect.

        Args:
            sound_id: Identifier for the sound (e.g., "hit_metal")
            filepath: Path to audio file (WAV, MP3, OGG, etc.)
        """
        try:
            self.sounds[sound_id] = pygame.mixer.Sound(filepath)
        except pygame.error as e:
            print(f"Failed to load sound '{sound_id}' from {filepath}: {e}")

    def play_sound(self, sound_id: str, loops: int = 0, max_time: int = 0) -> None:
        """
        Play a sound effect.

        Args:
            sound_id: ID of the sound to play
            loops: Number of times to loop (0 = play once)
            max_time: Maximum time to play in milliseconds (0 = full duration)
        """
        if sound_id in self.sounds:
            try:
                self.sounds[sound_id].play(loops=loops, maxtime=max_time)
            except pygame.error as e:
                print(f"Failed to play sound '{sound_id}': {e}")

    def set_music(self, filepath: str) -> None:
        """
        Load and play background music.

        Args:
            filepath: Path to music file
        """
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play(loops=-1)  # Loop indefinitely
            self.music = filepath
        except pygame.error as e:
            print(f"Failed to load music from {filepath}: {e}")

    def stop_music(self) -> None:
        """Stop background music."""
        pygame.mixer.music.stop()
        self.music = None

    def set_volume(self, volume: float) -> None:
        """
        Set master volume.

        Args:
            volume: Volume level (0.0 = silent, 1.0 = max)
        """
        volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(volume)

    # Event handlers (stubs for when events are connected)

    def _on_damage(self, event: Event) -> None:
        """Play damage sound when entity takes damage."""
        self.play_sound("damage_hit")

    def _on_footstep(self, event: Event) -> None:
        """Play footstep sound when entity moves."""
        self.play_sound("footstep", loops=0)

    def _on_death(self, event: Event) -> None:
        """Play death sound when entity dies."""
        self.play_sound("death", loops=0)

    def shutdown(self) -> None:
        """Cleanup audio system."""
        pygame.mixer.stop()
        pygame.mixer.quit()
