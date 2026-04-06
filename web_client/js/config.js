/**
 * Configuration for the web client.
 */

const CONFIG = {
    SERVER_HOST: "localhost",
    SERVER_PORT: 8000,
    SERVER_WS_URL: () => `ws://${CONFIG.SERVER_HOST}:${CONFIG.SERVER_PORT}/game`,
    PLAYER_ID: 1,

    TILE_WIDTH: 7,
    TILE_HEIGHT: 12,
    FONT: "monospace",
    FONT_SIZE: 12,

    VIEWPORT_COLS: 80,
    VIEWPORT_ROWS: 24,

    TILE_SIZES: {
        "small": { width: 5, height: 8 },
        "medium": { width: 7, height: 12 },
        "large": { width: 10, height: 16 },
    },

    ENABLE_VI_KEYS: true,
    ENABLE_ARROW_KEYS: true,
    ENABLE_WASD_KEYS: true,
    TURN_DEBOUNCE: true,
};

function setTileSize(size) {
    if (CONFIG.TILE_SIZES[size]) {
        CONFIG.TILE_WIDTH = CONFIG.TILE_SIZES[size].width;
        CONFIG.TILE_HEIGHT = CONFIG.TILE_SIZES[size].height;
    }
}

function calculateCanvasDimensions() {
    return {
        width: CONFIG.VIEWPORT_COLS * CONFIG.TILE_WIDTH,
        height: CONFIG.VIEWPORT_ROWS * CONFIG.TILE_HEIGHT,
    };
}
