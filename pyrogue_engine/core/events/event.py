"""Base event class for the event system"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Dict


class EventPriority(Enum):
    """Event processing priority levels"""
    CRITICAL = 0  # Immediate execution
    HIGH = 1      # Standard events
    NORMAL = 2    # State updates
    LOW = 3       # UI updates, logging
    DEFERRED = 4  # Async/deferred events


@dataclass(frozen=True)
class Event:
    """Base event class for all game events

    Immutable event record with optional priority and topic routing.

    Attributes:
        event_type (str): Category of event
        priority (EventPriority): Processing priority
        topic (Optional[str]): Fine-grained routing topic (e.g., "combat.melee")
        metadata (Optional[Dict[str, Any]]): Additional event-specific data
        replicate (bool): Should ReplicationSystem capture this event? (default: False)
        scope (Optional[str]): Replication scope: "global" (all clients) or "local" (FOV-based)
        source_entity_id (Optional[int]): Entity that originated this event (for FOV culling)
    """
    event_type: str
    priority: EventPriority = EventPriority.HIGH
    topic: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    replicate: bool = False
    scope: Optional[str] = None
    source_entity_id: Optional[int] = None

    def __str__(self) -> str:
        """Human-readable event representation"""
        return f"[{self.event_type.upper()}] {self.get_full_topic()}"

    def get_full_topic(self) -> str:
        """Get full routing topic (event_type if topic not specified)"""
        return self.topic or self.event_type
