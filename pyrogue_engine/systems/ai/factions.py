"""
Factions - NPC Allegiance System

Defines who attacks who. Completely decoupled from player reputation.

This extracts the ternary alignment system from my_lib and uses a registry-based
hostility lookup for efficient, composable faction checks.

Pattern: Build a FactionRegistry at game startup, query it in AwarenessSystem.
"""

from enum import Enum
from typing import Set, Dict


class Faction(Enum):
    """
    NPC alignment/allegiance.

    Used to determine if one entity should attack another.

    NEUTRAL: No strong allegiance. May be ignored or negotiated with.
    ALLY: Friendly faction. Attacks HOSTILE entities.
    HOSTILE: Aggressive faction. Attacks everything except HOSTILE.
    PLAYER: The player. Attacked by HOSTILE entities.
    """

    NEUTRAL = "neutral"
    ALLY = "ally"
    HOSTILE = "hostile"
    PLAYER = "player"


class FactionRegistry:
    """
    Global registry defining who attacks who.

    Use this to define all faction relationships in one place at startup.
    Then query it in AwarenessSystem to determine hostility.

    Example:
        factions = FactionRegistry()

        # Goblins hate everyone except other goblins
        factions.set_hostile("goblin", "player", mutual=False)
        factions.set_hostile("goblin", "human", mutual=False)
        factions.set_hostile("goblin", "elf", mutual=False)

        # Humans and elves are allies
        factions.set_allied("human", "elf", mutual=True)

        # Zombies only attack the living (everyone)
        factions.set_hostile("undead", ["human", "elf", "goblin"], mutual=False)
    """

    def __init__(self):
        """Initialize empty registry."""
        # faction_name -> set of hostile faction names
        self.hostilities: Dict[str, Set[str]] = {}

        # faction_name -> set of allied faction names
        self.alliances: Dict[str, Set[str]] = {}

    def set_hostile(
        self,
        faction_a: str,
        faction_b: str | list[str],
        mutual: bool = True
    ) -> None:
        """
        Mark factions as hostile (will attack on sight).

        Args:
            faction_a: Faction that will attack
            faction_b: Faction(s) to attack. Can be single string or list.
            mutual: If True, both sides become hostile to each other.
                   If False, only faction_a attacks faction_b.

        Example:
            factions.set_hostile("goblin", "player")
            # Goblins attack players, and players attack goblins (mutual=True)

            factions.set_hostile("zombie", ["human", "elf"], mutual=False)
            # Zombies attack humans and elves, but humans/elves don't specifically target zombies
        """
        # Handle list of targets
        if isinstance(faction_b, list):
            for target in faction_b:
                self.set_hostile(faction_a, target, mutual)
            return

        # Initialize sets if needed
        if faction_a not in self.hostilities:
            self.hostilities[faction_a] = set()
        if faction_b not in self.hostilities:
            self.hostilities[faction_b] = set()

        # Add hostility
        self.hostilities[faction_a].add(faction_b)

        if mutual:
            self.hostilities[faction_b].add(faction_a)

    def set_allied(
        self,
        faction_a: str,
        faction_b: str | list[str],
        mutual: bool = True
    ) -> None:
        """
        Mark factions as allied (won't attack, may coordinate).

        Args:
            faction_a: First faction
            faction_b: Second faction(s). Can be single string or list.
            mutual: If True, both sides are allied. If False, one-way.

        Example:
            factions.set_allied("human", "elf", mutual=True)
            # Humans and elves are buddies
        """
        # Handle list of targets
        if isinstance(faction_b, list):
            for target in faction_b:
                self.set_allied(faction_a, target, mutual)
            return

        # Initialize sets if needed
        if faction_a not in self.alliances:
            self.alliances[faction_a] = set()
        if faction_b not in self.alliances:
            self.alliances[faction_b] = set()

        # Add alliance
        self.alliances[faction_a].add(faction_b)

        if mutual:
            self.alliances[faction_b].add(faction_a)

    def is_hostile(self, faction_a: str, faction_b: str) -> bool:
        """
        Check if faction_a should attack faction_b.

        Args:
            faction_a: Attacker faction
            faction_b: Defender faction

        Returns:
            True if faction_a is hostile to faction_b
        """
        if faction_a not in self.hostilities:
            return False
        return faction_b in self.hostilities[faction_a]

    def are_allied(self, faction_a: str, faction_b: str) -> bool:
        """
        Check if faction_a is allied with faction_b.

        Args:
            faction_a: First faction
            faction_b: Second faction

        Returns:
            True if factions are allied
        """
        if faction_a not in self.alliances:
            return False
        return faction_b in self.alliances[faction_a]

    def should_attack(self, attacker_faction: str, defender_faction: str) -> bool:
        """
        Comprehensive check: should attacker_faction attack defender_faction?

        Logic:
        - If hostile: YES
        - If allied: NO
        - If neutral: NO

        Args:
            attacker_faction: Faction of potential attacker
            defender_faction: Faction of potential defender

        Returns:
            True if attack should happen
        """
        # Check explicit alliance first (don't attack allies)
        if self.are_allied(attacker_faction, defender_faction):
            return False

        # Check explicit hostility
        return self.is_hostile(attacker_faction, defender_faction)

    def debug_dump(self) -> str:
        """Return formatted string of all relationships for debugging."""
        lines = ["=== Faction Registry ==="]
        lines.append("\nHostilities:")
        for faction, targets in sorted(self.hostilities.items()):
            if targets:
                lines.append(f"  {faction} attacks: {', '.join(sorted(targets))}")
        lines.append("\nAlliances:")
        for faction, allies in sorted(self.alliances.items()):
            if allies:
                lines.append(f"  {faction} allied with: {', '.join(sorted(allies))}")
        return "\n".join(lines)
