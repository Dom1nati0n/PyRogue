# Tag System - Hierarchical Property Inheritance

## Philosophy

**Tags are intrinsic properties, not temporary effects.**

A gold coin **IS** made of gold (Intrinsic). Being on fire IS not permanent—it's a temporary status effect (Extrinsic).

Tags are immutable within a game loop. They define WHAT something fundamentally IS:
- Material composition (gold, iron, wood, leather)
- Behavioral personality (aggressive, cowardly, curious, loyal)
- Structural shape (wall, floor, debris)
- Logical function (trigger, conductor, sensor)

## Hierarchy and Inheritance

Tags form a **Directed Acyclic Graph (DAG)** where properties flow DOWN the hierarchy.

```
Material (no properties)
├─ Metal (Conductive: true, Opaque: true, AcousticDampening: 5)
│  ├─ Iron (Magnetic: true, ThermalLimit: 1538)
│  ├─ Copper (ThermalLimit: 1085)
│  └─ Gold (ThermalLimit: 1064)
└─ Stone (Opaque: true, AcousticDampening: 8)
   ├─ Granite (ThermalLimit: 1200)
   └─ Limestone (ThermalLimit: 900)
```

**Property Merging**: Child properties override parent properties (child wins).

Example: `Material.Metal.Iron` has these properties:
```
From Material.Metal:
- Conductive: true
- Opaque: true
- AcousticDampening: 5

From Material.Metal.Iron:
- Magnetic: true
- ThermalLimit: 1538

Final (merged):
- Conductive: true (from Metal)
- Opaque: true (from Metal)
- AcousticDampening: 5 (from Metal)
- Magnetic: true (from Iron)
- ThermalLimit: 1538 (from Iron)
```

## Core Components

### Tag

A single tag with hierarchical properties.

```python
from pyrogue_engine.core.tags import Tag

tag = Tag(
    name="Material.Metal.Iron",
    properties={
        "Conductive": true,
        "Opaque": true,
        "AcousticDampening": 5,
        "Magnetic": true,
        "ThermalLimit": 1538
    },
    transition_result="Material.Liquid.Magma"  # Optional
)
```

### Tags (ECS Component)

Component holding all tags for an entity.

```python
from pyrogue_engine.core.tags import Tags

# Create entity
entity = registry.create_entity()

# Add tags
iron_tag = manager.create_tag("Material.Metal.Iron")
trigger_tag = manager.create_tag("Logic.Trigger")
registry.add_component(entity, Tags(tags=[iron_tag, trigger_tag]))

# Query tags
tags_component = registry.get_component(entity, Tags)

# Check if has tag
if tags_component.has_tag("Material.Metal.Iron"):
    print("This is an iron item")

# Get most specific tag of a category
material_tag = tags_component.get_tag_with_hierarchy("Material")
print(f"Material: {material_tag.name}")  # Material.Metal.Iron

# Get property from any tag
is_conductive = tags_component.get_property("Conductive")
```

### TagManager

Loads tags.json and provides property lookup with inheritance.

```python
from pyrogue_engine.core.tags import TagManager

# Load tag ontology
manager = TagManager("tags.json")

# Create tag with inherited properties
iron_tag = manager.create_tag("Material.Metal.Iron")
# Returns Tag with all 5 properties merged from hierarchy

# Get single property (with inheritance)
conductive = manager.get_property("Material.Metal.Iron", "Conductive")
# Returns: true (from Material.Metal)

# Get all properties (merged)
all_props = manager.get_all_properties("Material.Metal.Iron")
# Returns: {Conductive: true, Opaque: true, AcousticDampening: 5, Magnetic: true, ThermalLimit: 1538}

# Check if tag exists
if manager.tag_exists("Material.Metal.Iron"):
    print("Valid tag")

# Get transition result (for state changes)
transition = manager.get_transition_result("Material.Metal.Iron")
# Returns: "Material.Liquid.Magma"
```

## Classification System

Tags are classified into three categories that determine behavior when entity is `Unidentified`:

### Intrinsic Tags
**Always active.** Cannot be hidden by `Unidentified` status.

Examples:
- `Material.*` (what the item is fundamentally made of)
- `Living.*` (biological properties)
- `Shape.*` (structural form)
- `Mind.*` (behavioral traits)
- `Bond.*` (social relationships)

These are essential to what the entity IS. You can't hide that a sword is made of iron—you might not know its NAME, but you still feel its weight and metallicness.

### Utility Tags
**Disabled by `Unidentified`.** Hidden from player discovery.

Examples:
- `Logic.*` (triggers, conductors, sensors)
- `Container.*` (inventory slots)
- `Property.*` (special characteristics)

These are **functional abilities** you'd discover through use or study. A hidden door might have `Logic.Trigger` that opens when touched, but an unidentified item wouldn't reveal this.

### Hazard Tags
**Always fire, even when `Unidentified`.** For safety and fairness.

Examples:
- `Logic.Trigger` → explosives always trigger, identifiable or not
- `Logic.Trap` → traps always work
- `Status.Burning` → fire always burns

## Usage Examples

### Example 1: Material Property Query

```python
manager = TagManager("tags.json")

# Does iron conduct electricity?
is_conductive = manager.get_property("Material.Metal.Iron", "Conductive")
if is_conductive:
    electrical_damage *= 2.0

# At what temperature does iron melt?
melt_temp = manager.get_property("Material.Metal.Iron", "ThermalLimit")
if current_temp > melt_temp:
    # Trigger transition to Material.Liquid.Magma
    transition_result = manager.get_transition_result("Material.Metal.Iron")
    entity.swap_tag("Material.Metal.Iron", manager.create_tag(transition_result))
```

### Example 2: Behavioral Tags

```python
# Create an aggressive wolf
wolf_mind = manager.create_tag("Mind.Trait.Aggressive")
wolf_urge = manager.create_tag("Mind.Urge.Hunting")

# Check behavioral properties
damage_bonus = wolf_mind.properties.get("DamageBonusMultiplier", 1.0)
# Returns: 1.1 (aggressive wolves deal 10% more damage)
```

### Example 3: Item Examination

```python
def examine_item(entity_id):
    tags = registry.get_component(entity_id, Tags)
    if not tags:
        return "It's too mysterious to examine."

    output = []
    for tag in tags.tags:
        output.append(f"{tag.name}:")
        for prop_key, prop_value in tag.properties.items():
            output.append(f"  {prop_key}: {prop_value}")

    return "\n".join(output)
```

### Example 4: Tag Classification and Unidentified

```python
# Entity has Unidentified status
entity = registry.get_component(entity_id, Tags)
has_unidentified = entity.has_tag("Unidentified")

for tag in entity.tags:
    # Check if this tag should be revealed
    is_active = manager.is_tag_active(tag.name, has_unidentified)

    if is_active:
        # Reveal this property
        examine_output.append(f"{tag.name}: {tag.properties}")
    else:
        # Hide utility tags from unidentified items
        examine_output.append(f"{tag.name}: ???")
```

## Complete Tag Ontology

### Material Tags
- `Material.Metal.*` (Iron, Copper, Gold)
- `Material.Stone.*` (Granite, Limestone)
- `Material.Wood.*` (Oak, Pine)
- `Material.Cloth`, `Material.Leather`, `Material.Glass`
- `Material.Liquid.*` (Water, Magma, Oil)
- `Material.Gas.*` (Steam, OilSmoke)
- `Material.Charcoal`, `Material.Ash`

### Living Tags
- `Living.Humanoid.Human`
- `Living.Animal`
- `Living.Plant`

### Feature Tags
- `Feature.Door.Open`, `Feature.Door.Closed`
- `Feature.Window`

### Shape Tags
- `Shape.Solid`, `Shape.Floor`, `Shape.Wall`, `Shape.Debris`

### Logic Tags (Utility)
- `Logic.Conductor`, `Logic.Trigger`, `Logic.Output`, `Logic.Input`
- `Logic.Storage`, `Logic.Sensor`, `Logic.Actuator`

### Status Tags
- `Status.Burning`, `Status.Melting`, `Status.Charring`
- `Status.Soaked`, `Status.Hot`, `Status.Cold`, `Status.Brittle`

### Mind Tags
- `Mind.Trait.*` (Aggressive, Cowardly, Curious, Loyal, Calm)
- `Mind.Mood.*` (Calm, Alert, Angry, Terrified, Excited)
- `Mind.Urge.*` (Wandering, Patrolling, Hunting, Fleeing, Guarding, Exploring, Panicking, Resting)

### Bond Tags
- `Bond.Allegiance.*` (Wolfpack, BanditClan, GoblinTribe, PlayerFollowers)
- `Bond.Role.*` (Alpha, Packmate, Shaman, Scout, Follower)

## Integration Checklist

- [ ] TagManager loads tags.json at game startup
- [ ] Entities have Tags component
- [ ] Systems query tags for properties (fire system checks `Fuel`, etc.)
- [ ] Transition system handles `TransitionResult`
- [ ] Unidentified status uses `is_tag_active()` for correct gating
- [ ] Entity factories populate tags from templates
- [ ] Examine system displays tag properties appropriately

## Performance Notes

- **TagManager flattening**: O(total_tags) on startup, then O(1) lookups
- **get_property()**: O(hierarchy_depth) worst case, usually 3-4 levels
- **get_all_properties()**: O(hierarchy_depth) with property merging
- **Tags component queries**: O(1) per tag lookup

For 300+ entity types with 15+ tags each: negligible overhead.

## Key Principles

1. **Tags are immutable within a game loop** (use events to change tags)
2. **Properties merge from parent to child** (child wins)
3. **Classification gates visibility** (Intrinsic always shown, Utility hidden by Unidentified, Hazard always works)
4. **Flattened lookup enables O(1) tag existence checks**
5. **Inheritance avoids data duplication** (all metals share conductive property)
