# Network Dictionary Architecture: Tags → Integer IDs

## The Problem

In a multiplayer game with FOV culling, sending full tag strings for every entity every frame is wasteful:

```json
// OLD: ~60 bytes per entity
{
  "id": 42,
  "tags": ["NPC.WizBot", "Dangerous", "Animated"]
}
```

With 100+ entities per client per frame, this balloons network traffic despite FOV culling savings.

## The Solution: Dynamic Tag Registry

Instead of hardcoding tag IDs (which violates THE CONSTITUTION's Principle 2), we generate them dynamically at server startup and send a one-time handshake:

### Phase 1: Server Startup (Build the Dictionary)

```python
# In headless_server.py, when TagManager initializes:
tag_manager = TagManager("tags.json")

# TagManager._build_network_dictionary() automatically runs:
# "NPC.WizBot" → 1
# "Dangerous" → 2
# "Animated" → 3
# ... (dynamically assigned, deterministic across restarts)
```

### Phase 2: Client Handshake (One-Time Transfer)

When a client connects, send the entire dictionary in a special handshake packet:

```json
{
  "type": "dictionary",
  "tags": {
    "1": "NPC.WizBot",
    "2": "Dangerous",
    "3": "Animated"
  }
}
```

The client caches this in memory (JavaScript):

```javascript
const tagDictionary = {
  1: "NPC.WizBot",
  2: "Dangerous",
  3: "Animated"
};
```

### Phase 3: Game Loop (Lightning Fast)

Now your replication packets shrink dramatically:

```json
// NEW: ~12 bytes per entity
{
  "id": 42,
  "tags": [1, 2, 3]
}
```

The client decodes:
```javascript
const tags = [1, 2, 3];
const tagStrings = tags.map(id => tagDictionary[id]);
// → ["NPC.WizBot", "Dangerous", "Animated"]
```

Then passes `tagStrings` to the renderer, which looks them up in theme.json.

### Phase 4: Client Renderer (Theme Lookup)

```javascript
// Client has theme.json loaded
const theme = {
  mapping: {
    "NPC.WizBot": { char: "W", fg: "cyan", bg: "black" }
  }
};

// Renderer receives integer-packed tags
const tags = [1, 2, 3];

// Decode to strings
const tagStrings = tags.map(id => tagDictionary[id]);

// Look up in theme
const renderInfo = theme.mapping[tagStrings[0]];  // Find first match
```

## Complete Data Flow

```
Server Startup
└─ TagManager loads tags.json
└─ _build_network_dictionary() assigns sequential IDs
└─ tag_manager.tag_to_id = {"NPC.WizBot": 1, "Dangerous": 2, ...}
└─ tag_manager.id_to_tag = {1: "NPC.WizBot", 2: "Dangerous", ...}

Client Connects
└─ Server sends handshake: {type: "dictionary", tags: {1: "NPC.WizBot", ...}}
└─ Client caches: tagDictionary = {1: "NPC.WizBot", ...}

Game Loop (Every 50ms)
└─ Server: registry.get_component(entity_id, Tags) → ["NPC.WizBot", "Dangerous"]
└─ Server: tag_manager.tags_to_ids(["NPC.WizBot", "Dangerous"]) → [1, 2]
└─ Packet: {id: 42, pos: {x: 10, y: 15}, tags: [1, 2]}  ✓ Packed!
└─ Send to client: 12 bytes instead of 60 bytes

Client Receives
└─ tags: [1, 2] → tagDictionary → ["NPC.WizBot", "Dangerous"]
└─ gameState.applyFrame({tags: [1, 2]})  // Keep as IDs until render time
└─ Renderer reads tags: [1, 2] → lookup theme → "W", cyan, black
└─ Canvas draws cyan "W"
```

## Architecture Purity

This design maintains all THE CONSTITUTION principles:

✓ **Server Pure**: Python code still says `if "NPC.WizBot" in tags:` — completely readable, no magic numbers

✓ **No Hardcoded IDs**: The integer mapping is generated at runtime from data files (tags.json)

✓ **Client Decoupled**: Client receives compressed data and makes its own rendering decisions

✓ **Bandwidth Crushed**: 10-12 bytes vs. 60+ bytes per entity per frame

## Implementation Checklist

- [x] **TagManager**: Extended with `_build_network_dictionary()`, `tags_to_ids()`, `ids_to_tags()`, `export_network_dictionary()`
- [x] **Tile Theme System**: Created `web_client/themes/default.json` with palette and tag→sprite mappings
- [x] **TileRenderer**: Updated to load theme.json, look up tags in theme, no longer reads TileSprite component
- [x] **WizBot**: Removed TileSprite, added Tags component
- [ ] **Handshake Packet**: Server sends dictionary to client on "connected" event
- [ ] **Replication Packets**: Server sends tag IDs [1, 2, 3] instead of tag strings
- [ ] **Client Decoder**: Web client decodes tag IDs using dictionary before passing to renderer

## Next Steps

### 1. Wire Up the Handshake (Server)

In `headless_server.py`, when `handle_client_connected` is called:

```python
async def handle_client_connected(client_id: str, websocket: Any):
    """Called when WebSocket client connects"""
    session_id = str(uuid.uuid4())
    connected_sessions[client_id] = session_id
    websocket_connections[client_id] = websocket

    # Send tag dictionary as first message
    dictionary_packet = {
        "type": "dictionary",
        "tags": tag_manager.export_network_dictionary()
    }
    await websocket.send_json(dictionary_packet)

    # Then emit connection event
    event_bus.emit(SessionEvents.client_connected(session_id, client_id))
    print(f"[Network] Client {client_id} connected → session {session_id[:8]}...")
    return session_id
```

### 2. Update Replication to Send Tag IDs (Server)

When building entity replication packets, replace tag strings with IDs:

```python
# In ReplicationSystem or entity serialization:
def serialize_entity(entity_id: int, tag_manager: TagManager):
    tags = registry.get_component(entity_id, Tags)

    # Convert tag strings to IDs
    tag_ids = tag_manager.tags_to_ids(tags) if tags else []

    return {
        "id": entity_id,
        "tags": tag_ids,  # [1, 2, 3] instead of ["NPC.WizBot", "Dangerous"]
        "PositionComponent": ...
    }
```

### 3. Update Client to Store Dictionary (Web)

In `web_client/js/network.js` or main.js:

```javascript
class GameNetwork {
    constructor(config) {
        this.tagDictionary = {};  // Add this
        ...
    }

    _onMessage(event) {
        try {
            const data = JSON.parse(event.data);

            // Store the dictionary when it arrives
            if (data.type === "dictionary") {
                this.tagDictionary = data.tags;  // {1: "NPC.WizBot", ...}
                console.log(`[Network] Received tag dictionary with ${Object.keys(data.tags).length} entries`);
                return;
            }

            // Call frame handlers for other packets
            for (const handler of this.frameHandlers) {
                handler(data);
            }
        } catch (e) {
            this._callErrorHandlers(e);
        }
    }
}
```

### 4. Update Client Decoder (Web)

In `web_client/js/game_state.js`, decode tag IDs when applying frames:

```javascript
applyFrame(frame) {
    if (!frame.delta) return;

    const delta = frame.delta;

    // Decode tag IDs to strings
    if (delta.updates) {
        for (const [entityIdStr, componentUpdates] of Object.entries(delta.updates)) {
            // If tags are integers, decode them
            if (componentUpdates.Tags && Array.isArray(componentUpdates.Tags)) {
                const firstTag = componentUpdates.Tags[0];
                if (typeof firstTag === "number") {
                    // Tag IDs detected — decode using dictionary
                    componentUpdates.Tags = componentUpdates.Tags.map(id =>
                        window.gameNetwork?.tagDictionary?.[id] || `Unknown(${id})`
                    );
                }
            }

            // ... rest of applyFrame logic
        }
    }
}
```

## Benefits Summary

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Bytes per entity tags | 60+ | 8-12 | ~85% |
| Bandwidth for 100 entities/frame | 6000 | 800 | 80% reduction |
| Scaling to 200 players | Bandwidth limits | Viable | Game-changer |

## See Also

- `MEMORY.md` → Separation of Identity Architecture
- `web_client/themes/default.json` → Rendering mappings (instantly swappable)
- `pyrogue_engine/core/tags/tag_manager.py` → Network dictionary generation
