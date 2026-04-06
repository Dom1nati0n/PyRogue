"""Event Bus - Central event dispatcher with topic-based routing"""

from typing import Callable, Dict, List, Optional, Any
import asyncio

from .event import Event, EventPriority


class EventBus:
    """Central event dispatcher with topic-based routing and async support

    Features:
    - Topic-based routing (fine-grained subscription)
    - Sync and async callbacks
    - Priority-based event queuing
    - Wildcard subscriptions (e.g., "damage.*")

    Subscribers register callbacks for specific topics. When an event
    is emitted, only relevant subscribers are invoked (O(1) lookup).

    Thread-safety: This implementation is NOT thread-safe for subscriptions.
    For multithreaded games, add locks around subscriber modifications.
    """

    def __init__(self):
        """Initialize an empty subscriber registry and event queue"""
        # Topic -> List of (callback, is_async)
        self.subscribers: Dict[str, List[tuple]] = {}
        # Wildcard subscribers: topic_prefix -> List of (callback, is_async)
        self.wildcard_subscribers: Dict[str, List[tuple]] = {}
        # Priority-based event queue
        self.event_queue: List[tuple] = []  # (priority_value, event)
        self.processing = False

    def subscribe(
        self,
        topic: str,
        callback: Callable[[Event], None],
    ) -> None:
        """Register a callback for events of a specific topic

        Topics use dot notation for hierarchical routing:
        - "damage" — all damage events
        - "damage.melee" — only melee damage
        - "damage.*" — damage and all subtopics (wildcard)

        Args:
            topic (str): Topic to listen for (e.g., "damage", "buff.haste")
            callback (Callable): Function to invoke when event fires.
                                 Can be sync or async (automatically detected).

        Example:
            def on_damage(event: Event) -> None:
                print(f"Event: {event.event_type}")

            event_bus.subscribe("damage", on_damage)
        """
        # Determine if callback is async
        is_async = asyncio.iscoroutinefunction(callback)

        if topic not in self.subscribers:
            self.subscribers[topic] = []

        self.subscribers[topic].append((callback, is_async))

    def subscribe_wildcard(
        self,
        topic_prefix: str,
        callback: Callable[[Event], None],
    ) -> None:
        """Register a callback that matches any topic starting with prefix

        Args:
            topic_prefix (str): Topic prefix (e.g., "damage." matches "damage.*")
            callback (Callable): Callback function
        """
        is_async = asyncio.iscoroutinefunction(callback)

        if topic_prefix not in self.wildcard_subscribers:
            self.wildcard_subscribers[topic_prefix] = []

        self.wildcard_subscribers[topic_prefix].append((callback, is_async))

    def unsubscribe(
        self,
        topic: str,
        callback: Callable[[Event], None],
    ) -> None:
        """Unregister a callback from a topic

        Args:
            topic (str): Topic to stop listening to
            callback (Callable): Callback to remove
        """
        if topic in self.subscribers:
            self.subscribers[topic] = [
                (cb, is_async) for cb, is_async in self.subscribers[topic]
                if cb != callback
            ]

    def emit(self, event: Event) -> None:
        """Broadcast an event to all relevant subscribers (synchronously)

        Events are dispatched immediately using topic-based routing.
        Async subscribers are NOT awaited (use emit_async for that).

        Args:
            event (Event): The event to broadcast
        """
        topic = event.get_full_topic()

        # Get exact subscribers
        callbacks = self.subscribers.get(topic, [])

        # Get wildcard subscribers
        for prefix, wildcard_cbs in self.wildcard_subscribers.items():
            if topic.startswith(prefix.rstrip("*")):
                callbacks.extend(wildcard_cbs)

        # Execute callbacks with graceful error handling
        for callback, is_async in callbacks:
            try:
                if is_async:
                    # For sync emit, schedule async callbacks (don't await)
                    asyncio.create_task(callback(event))
                else:
                    callback(event)
            except Exception as e:
                print(f"[ERROR] Event callback failed: {type(e).__name__}: {e}")

    async def emit_async(self, event: Event) -> None:
        """Broadcast an event asynchronously (awaits async subscribers)

        Use this for network events or long-running handlers.

        Args:
            event (Event): The event to broadcast
        """
        topic = event.get_full_topic()

        # Get exact subscribers
        callbacks = self.subscribers.get(topic, [])

        # Get wildcard subscribers
        for prefix, wildcard_cbs in self.wildcard_subscribers.items():
            if topic.startswith(prefix.rstrip("*")):
                callbacks.extend(wildcard_cbs)

        # Execute callbacks asynchronously
        tasks = []
        for callback, is_async in callbacks:
            try:
                if is_async:
                    tasks.append(callback(event))
                else:
                    # Wrap sync callbacks in async
                    tasks.append(asyncio.get_event_loop().run_in_executor(None, callback, event))
            except Exception as e:
                print(f"[ERROR] Event callback failed: {type(e).__name__}: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def queue_event(self, event: Event) -> None:
        """Queue an event for later processing (used for deferred/async events)

        Args:
            event (Event): Event to queue
        """
        priority_value = event.priority.value
        self.event_queue.append((priority_value, event))
        # Sort queue by priority
        self.event_queue.sort(key=lambda x: x[0])

    async def process_queue(self) -> None:
        """Process all queued events in priority order

        Use this in the main game loop to handle deferred events.
        """
        while self.event_queue:
            _, event = self.event_queue.pop(0)
            await self.emit_async(event)

    def clear(self) -> None:
        """Remove all subscribers and clear queue. Useful for testing."""
        self.subscribers.clear()
        self.wildcard_subscribers.clear()
        self.event_queue.clear()
