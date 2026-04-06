# Entities - Template-Based Entity Creation

This directory contains the data-driven entity factory system. Rather than scattering entity definitions across code, this module loads JSON templates and dynamically spawns entities with correct components.

## Quick Start

```python
from pyrogue_engine.entities import EntityFactory, TemplateRegistry
from pyrogue_engine.core import Registry

# 1. Load templates from JSON
templates = TemplateRegistry()
templates.load_creatures("content/creatures.json")
templates.load_items("content/items.json")

# 2. Create factory
factory = EntityFactory(registry, event_bus, tag_manager, templates)

# 3. Spawn entities
wolf_id = factory.spawn_creature("wolf", x=10, y=20)
sword_id = factory.spawn_item("iron_longsword", x=15, y=25)
```

## Directory Contents

### `template.py`
Dataclass definitions for all template types:
- `CreatureTemplate` — NPCs and monsters
- `ItemTemplate` — Equipment, consumables, etc.
- `TileTemplate` — Terrain tiles
- `GroupTemplate` — Named groups (spawns a leader + members)
- `LootTable` — Random item drops
- `MindTemplate` — AI decision tree reference
- `BondTemplate` — Relationship data

### `template_registry.py`
Loads JSON templates and caches them:
```python
registry.load_creatures("creatures.json")  # Load all creature types
registry.load_items("items.json")          # Load all item types
registry.get_creature("wolf")               # Fetch cached template
```

### `entity_factory.py`
Spawns entities from templates with all components:
```python
# Spawn a creature
wolf_id = factory.spawn_creature("wolf", x=10, y=20)

# Spawn an item
potion_id = factory.spawn_item("health_potion", x=15, y=25)

# Spawn a group (leader + followers)
leader_id, follower_ids = factory.spawn_group("wolfpack", x=30, y=40)

# Spawn a tile
floor_id = factory.spawn_tile("stone_floor", x=5, y=5)
```

### `populator.py`
Spawns entities into a LevelBlueprint (dungeon):
```python
from pyrogue_engine.generation import LevelBlueprint
from pyrogue_engine.entities import Populator

blueprint = ...  # Generated level
populator = Populator(factory)

# Spawn creatures at spawn points
populator.spawn_creatures(blueprint, registry)

# Spawn loot at treasure markers
populator.spawn_loot(blueprint, registry)
```

### `ENTITIES_GUIDE.md`
Detailed patterns and examples for entity definition.

---

## Template Format (JSON)

### Creatures
```json
{
  "creatures": {
    "wolf": {
      "displayName": "Wolf",
      "components": {
        "Position": {},
        "Health": {"current": 20, "maximum": 20},
        "Attributes": {"STR": 12, "DEX": 14, "CON": 13},
        "Brain": {"mindset_id": "wolf_pack"}
      },
      "tags": ["Living.Animal.Predator"],
      "mind": {
        "type": "Fallback",
        "children": [
          {"type": "ConditionHasTarget"},
          {"type": "ActionMeleeAttack"},
          {"type": "ActionWander"}
        ]
      }
    }
  }
}
```

### Items
```json
{
  "items": {
    "iron_longsword": {
      "displayName": "Iron Longsword",
      "components": {
        "Equipment": {"slot": "main_hand", "damage_type": "Slashing"}
      },
      "tags": ["Equipment.Weapon.Melee"]
    }
  }
}
```

### Groups
```json
{
  "groups": {
    "wolfpack": {
      "leader_creature": "wolf",
      "member_creatures": ["wolf", "wolf"],
      "spacing": 1
    }
  }
}
```

---

## Design Pattern: Data > Code

**DON'T** hardcode entity creation:
```python
# ❌ Bad
entity_id = registry.create_entity()
registry.add_component(entity_id, Position(10, 20))
registry.add_component(entity_id, Health(20, 20))
registry.add_component(entity_id, Attributes({"STR": 12}))
# ... dozens more lines
```

**DO** use templates:
```python
# ✅ Good
wolf_id = factory.spawn_creature("wolf", x=10, y=20)
```

Benefits:
- **Designers can tune values** without touching Python
- **Balance changes** happen in JSON, not recompilation
- **Consistency** — all wolves have identical stats
- **Reusability** — one template, spawn a thousand times

---

## Advanced: Custom Components

If a template needs a custom component not built into the engine:

1. Define it in your game code
2. Add a loader to `EntityFactory._add_component()`
3. Use it in JSON:

```python
# In your game code
@dataclass
class CustomAI:
    behavior: str

# In entity_factory.py
def _add_component(self, entity_id, component_name, component_data):
    if component_name == "CustomAI":
        self.registry.add_component(entity_id, CustomAI(**component_data))
    else:
        super()._add_component(...)
```

Then in JSON:
```json
{
  "wolf": {
    "components": {
      "CustomAI": {"behavior": "hunt_in_packs"}
    }
  }
}
```

---

## Why TemplateRegistry?

Templates are loaded once at startup and cached:
```python
templates = TemplateRegistry()
templates.load_creatures("creatures.json")

# First call: reads JSON, parses, caches
template1 = templates.get_creature("wolf")

# Second call: instant, from cache
template2 = templates.get_creature("wolf")
```

This is fast and memory-efficient.

---

## Integration with Systems

The factory only *creates* entities with components. Systems provide the behavior:

- **EntityFactory**: Creates wolf with Position(10, 20), Health(20, 20)
- **PerceptionSystem**: Listens to MovementEvent, computes FOV
- **CombatResolverSystem**: Listens to AttackIntentEvent, applies damage
- **AISystem**: Executes wolf's Brain every tick, emits intent events

Separation of concerns: factory spawns, systems make them alive.

---

## See Also

- **README.md** (systems/) — How game systems work
- **ENTITIES_GUIDE.md** — Deep dive into entity patterns
- **THE_CONSTITUTION.md** — Design principles
- **GENERATION_GUIDE.md** — Populating levels with entities
