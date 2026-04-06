"""
Debug Component - Telemetry and testing data for WizBot.

Stores performance metrics, entity counts, and test statistics
that the WizBot AI system updates each frame.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class DebugComponent:
    """
    Debug telemetry component for testing bots.

    Attributes:
        enabled: Whether debug collection is active
        frame_count: Frames since bot spawn
        last_log_time: When last telemetry was printed
        test_mode: Current test mode ("exploration", "stress", "fov_test", etc.)
        log_interval: Print telemetry every N frames
        stats: Dict of arbitrary test metrics (entity_count, fps, etc.)
    """

    enabled: bool = True
    frame_count: int = 0
    last_log_time: float = 0.0
    test_mode: str = "exploration"  # "exploration", "stress_test", "fov_validation", etc.
    log_interval: int = 60  # Print stats every 60 frames at 20 Hz = 3 seconds
    stats: Dict[str, Any] = field(default_factory=dict)
    teleport_dest: Optional[tuple] = None  # (x, y) if teleport pending

    def update_stat(self, key: str, value: Any) -> None:
        """Update a stat in the stats dict."""
        self.stats[key] = value

    def get_stat(self, key: str) -> Any:
        """Retrieve a stat value."""
        return self.stats.get(key)

    def should_log(self) -> bool:
        """Check if it's time to log telemetry."""
        return (self.frame_count % self.log_interval == 0) and self.enabled

    def mark_teleport(self, x: int, y: int) -> None:
        """Queue a teleport to the given coordinates."""
        self.teleport_dest = (x, y)

    def clear_teleport(self) -> None:
        """Clear the teleport destination after executing."""
        self.teleport_dest = None
