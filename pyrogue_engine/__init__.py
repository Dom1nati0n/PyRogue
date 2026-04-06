"""
pyrogue_engine - A clean, extraction-based roguelike game engine

Built using the "Clean Shell" strategy: transplanting proven organs from
the original rogue library into a pristine architecture.
"""

from .core import Registry, System, Event, EventPriority, EventBus

__all__ = ["Registry", "System", "Event", "EventPriority", "EventBus"]
