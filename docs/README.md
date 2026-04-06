# PyRogue - Headless Server + Web Client

Completely decoupled rendering system. Engine sends pure game state. Clients are the lens.

## Quick Start

### 1. Start the server
```bash
cd pyrogue_engine_release
python headless_server.py
```

### 2. Serve the web client
```bash
cd pyrogue_engine_release/web_client
python -m http.server 8001
```

### 3. Open in browser
```
http://localhost:8001
```

You should see a canvas with white @ symbol (player) and red g symbols (goblins).

## Architecture

```
pyrogue_engine/              Pure game logic (no rendering)
├── core/                    ECS foundation (Registry, Events, Tags)
├── systems/                 Reactive game systems
│   ├── spatial/            Movement, FOV, collision
│   ├── rpg/                Combat, actions, effects
│   └── ai/                 Decision trees, NPC behavior
├── entities/               Template-based entity factory
└── generation/             Procedural level generation

pyrogue_client/              Presentation layer (mirrors engine state)
web_client/                  Web-based UI (Canvas + ASCII tiles)
```

**Key Components:**
- **headless_server.py** - Game engine loop + WebSocket + input validation
- **pyrogue_engine/systems/rpg/network_input_validator.py** - Anti-cheat validation
- **web_client/** - Browser interface (Canvas + ASCII tiles)

## Protocol

Server sends:
```json
{
  "type": "frame",
  "frame_number": 42,
  "delta": {
    "updates": {"5": {"PositionComponent": {"x": 10, "y": 15}}},
    "deletions": [],
    "new_entities": []
  }
}
```

Client sends:
```json
{"action": "move", "direction": "up"}
```

## Design Principles

1. **Engine is blind to rendering** - Server sends game state, not render commands
2. **FOV enforced server-side** - Clients only see what they should
3. **Input validated server-side** - All actions checked before becoming events
4. **Delta updates** - Only changed entities sent (performance)
5. **Custom tile sizes** - Change CONFIG in JavaScript, no server coupling
