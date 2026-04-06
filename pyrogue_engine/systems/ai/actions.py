"""
Action Nodes - Decision Tree Executors

Action nodes emit events for systems to process.
They never mutate entity components directly.

Examples:
- ActionMeleeAttack emits AttackIntentEvent
- ActionJPSMove emits MovementIntentEvent (after pathfinding)
- ActionFlowFieldMove reads flow field and emits MovementIntentEvent
- ActionWander emits random MovementIntentEvent

Events emitted here are picked up by:
- CombatResolverSystem (handles AttackIntentEvent)
- KinematicMovementSystem (handles MovementIntentEvent)
- StatusEffectSystem (handles ApplyEffectEvent)
"""

from .decision_tree import DecisionNode, NodeState, TreeContext
from pyrogue_engine.systems.spatial.components import Position
from pyrogue_engine.systems.rpg.components import Attributes, Health


class ActionMeleeAttack(DecisionNode):
    """
    Melee attack the target in memory.

    Reads:
    - memory["target_id"]: Entity ID to attack
    - entity's Attributes component for stat modifiers

    Emits:
    - AttackIntentEvent (CombatSystem handles damage)

    Returns:
    - SUCCESS if attack emitted
    - FAILURE if no target or missing components
    """

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        target_id = memory.get("target_id")
        if not target_id:
            return NodeState.FAILURE

        # Get attacker's stats
        attrs = context.registry.get_component(entity_id, Attributes)
        if not attrs:
            return NodeState.FAILURE

        # Import here to avoid circular imports
        from pyrogue_engine.systems.rpg.combat_system import AttackIntentEvent

        attack_event = AttackIntentEvent(
            attacker_id=entity_id,
            target_id=target_id,
            base_damage=5,  # Could read from entity's equipment or memory
            damage_type="Melee",
            stat_key="strength"
        )
        context.event_bus.emit(attack_event)

        return NodeState.SUCCESS


class ActionJPSMove(DecisionNode):
    """
    Move towards target using Jump Point Search (fast pathfinding).

    Reads:
    - memory["target_id"]: Entity to chase
    - entity Position
    - walkable_callback from context.custom

    Emits:
    - MovementIntentEvent with next step

    Returns:
    - SUCCESS if movement emitted
    - FAILURE if no path or missing components

    Note:
    - Requires walkable_callback in context.custom["walkable_callback"]
    - JPS instance is cached in context.custom["jps"]
    """

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        target_id = memory.get("target_id")
        if not target_id:
            return NodeState.FAILURE

        my_pos = context.registry.get_component(entity_id, Position)
        target_pos = context.registry.get_component(target_id, Position)

        if not my_pos or not target_pos:
            return NodeState.FAILURE

        # Get or create JPS instance
        jps = context.custom.get("jps")
        if not jps:
            walkable_cb = context.custom.get("walkable_callback")
            if not walkable_cb:
                return NodeState.FAILURE

            from my_lib.core.ai.pathfinding import JPS
            jps = JPS(walkable_cb)
            context.custom["jps"] = jps

        # Find path
        path = jps.find_path((my_pos.x, my_pos.y), (target_pos.x, target_pos.y))

        if not path or len(path) < 2:
            return NodeState.FAILURE

        # Take next step
        next_pos = path[1]
        dx = next_pos[0] - my_pos.x
        dy = next_pos[1] - my_pos.y

        from pyrogue_engine.systems.spatial.movement import MovementIntentEvent

        move_event = MovementIntentEvent(
            entity_id=entity_id,
            dx=dx,
            dy=dy
        )
        context.event_bus.emit(move_event)

        return NodeState.SUCCESS


class ActionFlowFieldMove(DecisionNode):
    """
    Move towards goal using pre-computed Flow Field (O(1) lookup).

    Use this for hordes: compute flow field once per turn from player position,
    then 100+ zombies each do O(1) lookup of their direction.

    Reads:
    - context.flow_fields["goal"] or context.custom["flow_field"]: FlowField instance
    - entity Position

    Emits:
    - MovementIntentEvent with flow field direction

    Returns:
    - SUCCESS if movement emitted
    - FAILURE if no flow field or stuck

    Note:
    - Assumes flow field is already updated with goal by a system
    - Extremely fast for large hordes
    """

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        # Get flow field
        flow_field = (
            context.custom.get("flow_field") if context.custom
            else context.flow_fields.get("goal") if context.flow_fields
            else None
        )

        if not flow_field:
            return NodeState.FAILURE

        my_pos = context.registry.get_component(entity_id, Position)
        if not my_pos:
            return NodeState.FAILURE

        # Get direction from flow field
        dx, dy = flow_field.get_move((my_pos.x, my_pos.y))

        if dx == 0 and dy == 0:
            # Stuck or at goal
            return NodeState.FAILURE

        from pyrogue_engine.systems.spatial.movement import MovementIntentEvent

        move_event = MovementIntentEvent(
            entity_id=entity_id,
            dx=dx,
            dy=dy
        )
        context.event_bus.emit(move_event)

        return NodeState.SUCCESS


class ActionWander(DecisionNode):
    """
    Move in a random adjacent direction.

    Emits:
    - MovementIntentEvent with random direction

    Returns:
    - Always SUCCESS (wander always succeeds, though may be blocked by collision)

    Use as fallback: if no target, just wander around.
    """

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        import random

        # Random direction in 8-directional grid
        dx = random.randint(-1, 1)
        dy = random.randint(-1, 1)

        # Exclude (0, 0) case
        if dx == 0 and dy == 0:
            dx, dy = random.choice([(-1, 0), (1, 0), (0, -1), (0, 1)])

        from pyrogue_engine.systems.spatial.movement import MovementIntentEvent

        move_event = MovementIntentEvent(
            entity_id=entity_id,
            dx=dx,
            dy=dy
        )
        context.event_bus.emit(move_event)

        return NodeState.SUCCESS


class Wander3DAction(DecisionNode):
    """
    Move in a random direction in 3D space (X, Y, Z axes).

    Used by Worker Bees to navigate through 3D dungeon while digging tunnels.
    Movement can be in any of the three dimensions or combinations.

    Emits:
    - MovementIntentEvent with random dx, dy, dz

    Returns:
    - Always SUCCESS (wander always succeeds, though may be blocked by collision)
    """

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        import random

        # Random direction in 3D space
        dx = random.randint(-1, 1)
        dy = random.randint(-1, 1)
        dz = random.randint(-1, 1)

        # Exclude (0, 0, 0) case - must move in at least one direction
        if dx == 0 and dy == 0 and dz == 0:
            # Pick a random axis to move along
            axis = random.choice(['x', 'y', 'z'])
            direction = random.choice([-1, 1])
            if axis == 'x':
                dx = direction
            elif axis == 'y':
                dy = direction
            else:
                dz = direction

        from pyrogue_engine.systems.spatial.movement import MovementIntentEvent

        move_event = MovementIntentEvent(
            entity_id=entity_id,
            dx=dx,
            dy=dy,
            dz=dz
        )
        context.event_bus.emit(move_event)

        return NodeState.SUCCESS


class ActionWait(DecisionNode):
    """
    Do nothing this turn (no-op action).

    Always returns SUCCESS.

    Use as fallback or when AI is indecisive.
    """

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        return NodeState.SUCCESS


class ActionUpdateMemory(DecisionNode):
    """
    Update a key in memory.

    This is a helper node for storing results of decisions.
    For example, after seeing a target, mark the time you saw it.

    Note:
    - Requires memory_key and memory_value in constructor
    - Always returns SUCCESS
    """

    def __init__(self, memory_key: str, memory_value=None):
        self.memory_key = memory_key
        self.memory_value = memory_value

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        memory.set(self.memory_key, self.memory_value)
        return NodeState.SUCCESS


class DigAction(DecisionNode):
    """
    Emit an intent to destroy whatever is on the current tile.

    Used by Drunkard Bees to carve out tunnels during Phase 1.

    Reads:
    - entity Position

    Emits:
    - map.destroy.intent event

    Returns:
    - SUCCESS if intent emitted
    - FAILURE if no Position component
    """

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        pos = context.registry.get_component(entity_id, Position)
        if not pos:
            return NodeState.FAILURE

        from pyrogue_engine.core.events import Event

        # Emit intent to destroy the tile at current 3D position
        event = Event(
            "map.destroy.intent",
            metadata={
                "builder_id": entity_id,
                "x": pos.x,
                "y": pos.y,
                "z": pos.z,
                "ap_cost": 10.0
            }
        )
        context.event_bus.emit(event)

        return NodeState.SUCCESS


class AutomataStepAction(DecisionNode):
    """
    Phase 1: Apply Cellular Automata logic to smooth tunnels.

    Reads a 3x3 local grid:
    - If surrounded by walls (>= 5 walls), build a wall (smoothing).
    - If open space (< 5 walls), destroy local wall (carving).

    Parameters:
    - wall_tag: The tag to use when building walls (e.g., "Terrain.Wall.Stone")

    Reads:
    - entity Position
    - registry for nearby walls

    Emits:
    - map.build.intent or map.destroy.intent

    Returns:
    - SUCCESS if intent emitted
    - FAILURE if no Position component
    """

    def __init__(self, wall_tag: str = "Terrain.Wall.Stone", **kwargs):
        self.wall_tag = wall_tag

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        pos = context.registry.get_component(entity_id, Position)
        if not pos:
            return NodeState.FAILURE

        from pyrogue_engine.systems.spatial.components import Tags

        # Count walls in 3x3 grid centered on entity
        wall_count = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue  # Skip center tile
                check_x = pos.x + dx
                check_y = pos.y + dy
                # Query registry for entities at this position with wall tags
                entities_at_tile = context.registry.get_entities_by_position(check_x, check_y)
                for e in entities_at_tile:
                    tags = context.registry.get_component(e, Tags)
                    if tags and any(tag.startswith("Terrain.Wall") for tag in tags.tags):
                        wall_count += 1

        from pyrogue_engine.core.events import Event

        # Smoothing: if surrounded by walls, build a wall
        if wall_count >= 5:
            event = Event(
                "map.build.intent",
                metadata={
                    "builder_id": entity_id,
                    "x": pos.x,
                    "y": pos.y,
                    "build_tag": self.wall_tag,
                    "ap_cost": 20.0
                }
            )
        # Carving: if open space, destroy local wall
        else:
            event = Event(
                "map.destroy.intent",
                metadata={
                    "builder_id": entity_id,
                    "x": pos.x,
                    "y": pos.y,
                    "ap_cost": 10.0
                }
            )

        context.event_bus.emit(event)
        return NodeState.SUCCESS


class DropPheromoneAction(DecisionNode):
    """
    Phase 3: Drop an invisible pheromone marker tracking distance from start.

    Used by Scout Bees to create a distance field that other entities can read.
    The pheromone value is the number of steps the bee has taken.

    Reads:
    - entity Position
    - memory["steps_taken"]: Number of steps taken

    Emits:
    - map.pheromone.intent event

    Returns:
    - Always SUCCESS
    """

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        pos = context.registry.get_component(entity_id, Position)
        if not pos:
            return NodeState.FAILURE

        # Bee remembers how many steps it has taken
        steps = memory.get("steps_taken", 0) + 1
        memory.set("steps_taken", steps)

        from pyrogue_engine.core.events import Event

        # Emit intent to spawn a pheromone marker at this tile
        event = Event(
            "map.pheromone.intent",
            metadata={
                "x": pos.x,
                "y": pos.y,
                "distance_value": steps
            }
        )
        context.event_bus.emit(event)

        return NodeState.SUCCESS


class CastSpellAction(DecisionNode):
    """
    Cast a spell (used by Architect or any entity with SpellCastable).

    This action integrates the spell system into the AI decision tree.
    The Architect uses this to summon worker bees during world generation phases.

    Respects world max_bees constraint—spell execution will be rejected if limit reached.

    Reads:
    - entity SpellCastable component (must exist)
    - world_gen config for max_bees

    Emits:
    - spell.cast event (picked up by SpellSystem)

    Returns:
    - SUCCESS if spell cast intent emitted
    - FAILURE if entity has no SpellCastable, spell doesn't exist, or max_bees exceeded
    """

    def __init__(self, spell_id: str):
        """
        Initialize action.

        Args:
            spell_id: The spell to cast (e.g., "summon_worker_bee")
        """
        self.spell_id = spell_id

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        from pyrogue_engine.systems.rpg.components import ActionPoints
        from pyrogue_engine.systems.rpg.spell_system import SpellCastable
        from pyrogue_engine.core.events import Event

        # Check if entity has spells
        spellcaster = context.registry.get_component(entity_id, SpellCastable)
        if not spellcaster or self.spell_id not in spellcaster.spells:
            return NodeState.FAILURE

        # Check if entity has enough AP
        ap = context.registry.get_component(entity_id, ActionPoints)
        if not ap:
            return NodeState.FAILURE

        spell = spellcaster.spells[self.spell_id]
        if ap.current < spell.ap_cost:
            return NodeState.FAILURE

        # Emit spell cast intent (SpellSystem will validate and execute)
        context.event_bus.emit(
            Event(
                "spell.cast",
                metadata={
                    "caster_id": entity_id,
                    "spell_id": self.spell_id,
                }
            )
        )

        return NodeState.SUCCESS


class BroadcastMessageAction(DecisionNode):
    """
    Broadcast a message to all players (via the outbound queue).

    Used by the Architect to announce world generation phases and events.
    Messages are replicated to all connected players.

    Reads:
    - entity Position (for context)

    Emits:
    - network.broadcast event (replicate=True)

    Returns:
    - Always SUCCESS
    """

    def __init__(self, msg: str):
        """
        Initialize action.

        Args:
            msg: Message to broadcast (e.g., "The Architect decrees: Let the depths be carved.")
        """
        self.msg = msg

    def tick(self, entity_id: int, memory, context: TreeContext) -> NodeState:
        from pyrogue_engine.core.events import Event

        # Emit broadcast event
        context.event_bus.emit(
            Event(
                "network.broadcast",
                replicate=True,
                metadata={
                    "source_entity_id": entity_id,
                    "message": self.msg,
                    "type": "world_announcement"
                }
            )
        )

        return NodeState.SUCCESS
