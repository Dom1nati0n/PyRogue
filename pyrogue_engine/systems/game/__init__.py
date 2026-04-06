"""
Game Mode System - Event-driven rule systems and session management.

Provides pluggable game mode implementations:
- SurvivalMode: Score-based survival until time limit
- RoundBasedMode: Fixed rounds with per-round duration
- CooperativeMode: Shared party objective system

All modes are event-driven and support multiplayer with drop-in/drop-out.
"""

from .mode import (
    GameMode,
    GameModeManager,
    PlayerSession,
    Scoreboard,
    SurvivalMode,
    RoundBasedMode,
    CooperativeMode,
)

__all__ = [
    "GameMode",
    "GameModeManager",
    "PlayerSession",
    "Scoreboard",
    "SurvivalMode",
    "RoundBasedMode",
    "CooperativeMode",
]
