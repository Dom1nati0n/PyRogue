# Web Client

Browser-based game interface for PyRogue. Connects to headless game server via WebSocket.

## Features

- 7x12 ASCII tile rendering (customizable)
- Real-time game state updates via WebSocket
- Full keyboard input support (arrow keys, WASD, VI keys)
- Turn-based debouncing
- Responsive design
- Delta-based state synchronization (only changed entities sent)

## Running

1. Start the headless game server (see main README)
2. Serve the web client: `python -m http.server 8001`
3. Open `http://localhost:8001` in browser

## Configuration

Edit `js/config.js` to customize:
- Server host/port
- Tile size (7x12, 5x8, 10x16, or custom)
- Viewport dimensions
- Input key bindings
- Debug logging

## Architecture

- `network.js` - WebSocket connection, frame reception, input sending
- `game_state.js` - Local mirror of server game state, delta application
- `tile_renderer.js` - Canvas rendering of entities as ASCII tiles
- `input_handler.js` - Keyboard input mapping and validation
- `main.js` - Entry point, initialization, game loop
- `config.js` - Configuration constants

## Protocol

**Server → Client** (Frame):
```json
{
  "type": "frame",
  "frame_number": 42,
  "player_id": 1,
  "delta": {
    "updates": {
      "5": {
        "PositionComponent": {"x": 10, "y": 15},
        "TileSprite": {"char": "g", "fg_color": [255, 0, 0], "bg_color": [0, 0, 0]}
      }
    },
    "deletions": [12],
    "new_entities": []
  }
}
```

**Client → Server** (Input):
```json
{
  "action": "move",
  "direction": "north"
}
```

## Tile Size Support

The renderer automatically scales to any tile size. Change `CONFIG.TILE_WIDTH` and `CONFIG.TILE_HEIGHT` to customize:

```javascript
CONFIG.TILE_WIDTH = 10;   // pixels per character width
CONFIG.TILE_HEIGHT = 16;  // pixels per character height
```

Or use presets: `setTileSize("small")`, `setTileSize("medium")`, `setTileSize("large")`

## Security

- All input validated server-side before processing
- No off-screen entities sent to client (FOV enforced)
- No game logic in browser
- Server is source of truth
