"""
Spell System - Event-driven ability casting with AP (Action Points) cost.

Follows THE CONSTITUTION:
  ✓ Reactive: Listens to spell.cast intent events
  ✓ Pure: No mutations except component state updates
  ✓ Intent-driven: Emits spell.executed events with results
  ✓ Decoupled: JSON-based spell definitions, no hardcoding
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pyrogue_engine.core.events import Event, EventBus
from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.systems.spatial.components import Position
from pyrogue_engine.systems.rpg.components import ActionPoints, Health


@dataclass
class SpellProperties:
    """Spell ability properties."""
    spell_id: str  # Unique identifier
    spell_name: str
    tags: List[str] = field(default_factory=list)  # ["damage", "teleport", "heal", etc.]
    ap_cost: int = 5  # Action point cost
    cooldown: int = 0  # Frames until usable again
    range: int = 0  # For targeted spells (0 = self)
    effects: List[Dict[str, Any]] = field(default_factory=list)  # Effect definitions


@dataclass
class SpellCastable:
    """Component: Tracks spells entity can cast."""
    spells: Dict[str, SpellProperties] = field(default_factory=dict)  # spell_id → SpellProperties
    current_cooldowns: Dict[str, int] = field(default_factory=dict)  # spell_id → frames_remaining
    frame_count: int = 0


class SpellSystem:
    """
    Handles spell casting with AP cost validation and cooldown management.

    Subscribes to "spell.cast" intents, validates AP, checks cooldowns,
    and emits "spell.executed" events with results.
    """

    def __init__(self, registry: Registry, event_bus: EventBus, config: Any):
        """Initialize spell system."""
        self.registry = registry
        self.event_bus = event_bus
        self.config = config

        # Subscribe to spell intents
        self.event_bus.subscribe("spell.cast", self._on_spell_cast)
        self.event_bus.subscribe("world.tick", self._on_world_tick)

        print("[SpellSystem] Initialized - ready to handle spell casting")

    def _on_world_tick(self, event: Event) -> None:
        """Update cooldowns on each world tick."""
        # Decrement cooldowns for all entities with spells
        for entity_id, (spellcaster,) in self.registry.view(SpellCastable):
            spellcaster.frame_count += 1

            # Decrement cooldowns
            expired = []
            for spell_id, remaining in list(spellcaster.current_cooldowns.items()):
                spellcaster.current_cooldowns[spell_id] = remaining - 1
                if spellcaster.current_cooldowns[spell_id] <= 0:
                    expired.append(spell_id)

            # Remove expired cooldowns
            for spell_id in expired:
                del spellcaster.current_cooldowns[spell_id]

    def _on_spell_cast(self, event: Event) -> None:
        """
        Called when entity attempts to cast a spell.

        Event metadata should contain:
        - caster_id: Entity attempting to cast
        - spell_id: Which spell to cast
        - target_id (optional): Target entity
        - target_pos (optional): Target position
        """
        metadata = event.metadata or {}
        caster_id = metadata.get("caster_id")
        spell_id = metadata.get("spell_id")
        target_id = metadata.get("target_id")
        target_pos = metadata.get("target_pos")

        if not all([caster_id, spell_id]):
            return

        # Get caster components
        spellcaster = self.registry.get_component(caster_id, SpellCastable)
        ap = self.registry.get_component(caster_id, ActionPoints)
        pos = self.registry.get_component(caster_id, Position)

        if not (spellcaster and ap and pos):
            return

        # Get spell definition
        if spell_id not in spellcaster.spells:
            print(f"[SpellSystem] Unknown spell {spell_id}")
            return

        spell = spellcaster.spells[spell_id]

        # Check cooldown
        if spell_id in spellcaster.current_cooldowns:
            remaining = spellcaster.current_cooldowns[spell_id]
            print(f"[SpellSystem] Spell {spell_id} on cooldown ({remaining} frames remaining)")
            return

        # Check AP cost
        if ap.current < spell.ap_cost:
            print(f"[SpellSystem] {caster_id} insufficient AP for {spell_id} (need {spell.ap_cost}, have {ap.current})")
            return

        # Execute spell
        self._execute_spell(caster_id, spell, pos, target_id, target_pos, spellcaster, ap)

    def _execute_spell(
        self,
        caster_id: int,
        spell: SpellProperties,
        caster_pos: Position,
        target_id: Optional[int],
        target_pos: Optional[Dict],
        spellcaster: SpellCastable,
        ap: ActionPoints,
    ) -> None:
        """Execute spell logic based on spell tags."""
        # Deduct AP
        ap.current = max(0, ap.current - spell.ap_cost)

        # Set cooldown
        if spell.cooldown > 0:
            spellcaster.current_cooldowns[spell.spell_id] = spell.cooldown

        print(f"[SpellSystem] {caster_id} cast {spell.spell_name} (AP: {ap.current})")

        # Execute based on spell tags
        results = {}

        if "teleport" in spell.tags:
            results.update(self._execute_teleport(caster_id, caster_pos, target_pos))

        if "heal" in spell.tags:
            results.update(self._execute_heal(caster_id, target_id, spell))

        if "damage" in spell.tags:
            results.update(self._execute_damage(caster_id, target_id, spell))

        if "summon" in spell.tags:
            results.update(self._execute_summon(caster_id, caster_pos, spell))

        # Emit spell execution event
        self.event_bus.emit(
            Event(
                event_type="spell.executed",
                metadata={
                    "caster_id": caster_id,
                    "spell_id": spell.spell_id,
                    "ap_remaining": ap.current,
                    "results": results,
                },
            )
        )

    def _execute_teleport(self, caster_id: int, caster_pos: Position, target_pos: Optional[Dict]) -> Dict:
        """Teleport spell: move caster to target position."""
        if not target_pos:
            return {"teleport": False, "reason": "No target position"}

        old_x, old_y = caster_pos.x, caster_pos.y
        caster_pos.x = target_pos.get("x", old_x)
        caster_pos.y = target_pos.get("y", old_y)

        print(f"[SpellSystem] {caster_id} teleported from ({old_x}, {old_y}) to ({caster_pos.x}, {caster_pos.y})")

        return {
            "teleport": True,
            "from": (old_x, old_y),
            "to": (caster_pos.x, caster_pos.y),
        }

    def _execute_heal(self, caster_id: int, target_id: Optional[int], spell: SpellProperties) -> Dict:
        """Heal spell: restore HP to target."""
        heal_amount = 0
        for effect in spell.effects:
            if effect.get("type") == "heal":
                heal_amount = effect.get("amount", 10)
                break

        if not heal_amount or not target_id:
            return {"heal": False, "reason": "Invalid heal target"}

        target_health = self.registry.get_component(target_id, Health)
        if not target_health:
            return {"heal": False, "reason": "Target has no health"}

        old_hp = target_health.current
        target_health.current = min(target_health.maximum, target_health.current + heal_amount)
        actual_heal = target_health.current - old_hp

        print(f"[SpellSystem] {target_id} healed for {actual_heal} HP ({old_hp}→{target_health.current})")

        return {"heal": True, "target": target_id, "amount": actual_heal}

    def _execute_damage(self, caster_id: int, target_id: Optional[int], spell: SpellProperties) -> Dict:
        """Damage spell: deal damage to target."""
        damage = 0
        for effect in spell.effects:
            if effect.get("type") == "damage":
                damage = effect.get("amount", 5)
                break

        if not damage or not target_id:
            return {"damage": False, "reason": "Invalid damage target"}

        target_health = self.registry.get_component(target_id, Health)
        if not target_health:
            return {"damage": False, "reason": "Target has no health"}

        target_health.current = max(0, target_health.current - damage)

        print(f"[SpellSystem] {target_id} took {damage} damage ({target_health.current} HP remaining)")

        return {"damage": True, "target": target_id, "amount": damage}

    def _execute_summon(self, caster_id: int, caster_pos: Position, spell: SpellProperties) -> Dict:
        """
        Summon spell: spawn entities via the spell system.
        Respects world max_bees constraint.

        Expected effect structure:
        {
            "type": "summon_entity",
            "template": "worker_bee",
            "count": 5
        }
        """
        summon_count = 0
        summon_template = None

        for effect in spell.effects:
            if effect.get("type") == "summon_entity":
                summon_template = effect.get("template", "worker_bee")
                summon_count = effect.get("count", 1)
                break

        if not summon_template or summon_count == 0:
            return {"summon": False, "reason": "No summon effect in spell"}

        # Check world max_bees constraint
        current_bees = len(self.registry.get_entities_with_tag("NPC.WorkerBee"))
        max_bees = self.config.world_gen.max_bees if hasattr(self.config, 'world_gen') else 50

        if current_bees >= max_bees:
            return {"summon": False, "reason": f"Max bees reached ({current_bees}/{max_bees})"}

        # Emit summon intent (the actual spawning is handled by the entity factory)
        self.event_bus.emit(
            Event(
                event_type="spell.summon.intent",
                metadata={
                    "caster_id": caster_id,
                    "template": summon_template,
                    "count": min(summon_count, max_bees - current_bees),
                    "position": {"x": caster_pos.x, "y": caster_pos.y, "z": caster_pos.z},
                }
            )
        )

        print(f"[SpellSystem] {caster_id} summoned {summon_template} (current bees: {current_bees}/{max_bees})")

        return {
            "summon": True,
            "template": summon_template,
            "count": min(summon_count, max_bees - current_bees),
            "caster": caster_id,
        }

    def add_spell_to_entity(self, entity_id: int, spell: SpellProperties) -> None:
        """Add a spell to an entity's spellcaster component."""
        spellcaster = self.registry.get_component(entity_id, SpellCastable)
        if not spellcaster:
            # Create new spellcaster component
            spellcaster = SpellCastable(spells={spell.spell_id: spell})
            self.registry.add_component(entity_id, spellcaster)
        else:
            spellcaster.spells[spell.spell_id] = spell
