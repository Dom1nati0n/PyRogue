/**
 * Tile Renderer - Render game state to Canvas as ASCII tiles.
 *
 * Uses a decoupled theme system: takes Position + Tags components from server,
 * looks up rendering info (char, colors) from a local theme.json file.
 * Supports custom tile sizes and instant theme swapping.
 */

class TileRenderer {
    constructor(canvasElement, config) {
        this.canvas = canvasElement;
        this.ctx = canvasElement.getContext("2d");
        this.config = config;
        this.theme = null;         // Theme will be loaded asynchronously

        // Calculate canvas size
        const dims = calculateCanvasDimensions();
        this.canvas.width = dims.width;
        this.canvas.height = dims.height;

        // Interpolation state — smooth entity movement between server ticks
        this.renderPos = {};       // entityId → {x, y} — current fractional render position
        this.prevPos = {};         // entityId → {x, y} — position before last server update
        this.lastTickTime = 0;     // ms timestamp when last frame arrived from server
        this.tickDuration = 50;    // ms between server ticks (matches 20 Hz tick_rate)

        this.setupFont();
        this.loadTheme("themes/default.json");
    }

    /**
     * Load a theme JSON file asynchronously.
     *
     * @param {string} themePath - Path to theme.json file
     */
    async loadTheme(themePath) {
        try {
            const response = await fetch(themePath);
            if (!response.ok) throw new Error(`Failed to load theme: ${response.status}`);
            this.theme = await response.json();
            console.log(`[TileRenderer] Theme loaded: "${this.theme.name}"`);
        } catch (e) {
            console.error(`[TileRenderer] Failed to load theme from ${themePath}:`, e);
            // Fallback: create minimal theme
            this.theme = {
                name: "Fallback",
                palette: { white: "#ffffff", black: "#000000" },
                mapping: {},
                fallback: { char: "?", fg: "white", bg: "black" }
            };
        }
    }

    /**
     * Resolve a color name from the theme's palette to a hex color.
     *
     * @param {string} colorName - Palette color name (e.g., "stone_light")
     * @returns {string} Hex color or white fallback
     * @private
     */
    _resolveColor(colorName) {
        if (!colorName) return "#ffffff";
        if (colorName === "transparent") return null;  // Signals "don't fill background"

        if (this.theme && this.theme.palette && this.theme.palette[colorName]) {
            return this.theme.palette[colorName];
        }

        // Fallback: assume it's already a hex color
        if (colorName.startsWith("#")) return colorName;

        return "#ffffff";  // Default white
    }

    /**
     * Look up rendering info for an entity based on its Tags.
     *
     * Uses a hierarchical matching strategy:
     * 1. Try exact match for full tag chain (e.g., "Terrain.Wall.Stone")
     * 2. Try progressively less specific (e.g., "Terrain.Wall", "Terrain")
     * 3. Return fallback if no match found
     *
     * @param {Array} tags - Array of tag strings from entity
     * @returns {Object} {char, fg_color, bg_color} or fallback
     * @private
     */
    _lookupRenderingForTags(tags) {
        if (!this.theme) return this._getFallbackSprite();
        if (!tags || tags.length === 0) return this._getFallbackSprite();

        const mapping = this.theme.mapping || {};

        // Try exact matches in order of tags
        for (const tag of tags) {
            if (mapping[tag]) {
                return this._spriteFromTheme(mapping[tag]);
            }
        }

        // Try progressively less specific matches (e.g., "Terrain.Wall" if "Terrain.Wall.Stone" not found)
        for (const tag of tags) {
            const parts = tag.split(".");
            for (let i = parts.length - 1; i > 0; i--) {
                const partial = parts.slice(0, i).join(".");
                if (mapping[partial]) {
                    return this._spriteFromTheme(mapping[partial]);
                }
            }
        }

        // Fallback
        return this._getFallbackSprite();
    }

    /**
     * Convert theme sprite definition to RGB colors.
     *
     * @param {Object} themeSprite - {char, fg, bg} from theme
     * @returns {Object} {char, fg_color, bg_color} with RGB arrays
     * @private
     */
    _spriteFromTheme(themeSprite) {
        const fg = this._resolveColor(themeSprite.fg || "white");
        const bg = this._resolveColor(themeSprite.bg || "black");

        return {
            char: themeSprite.char || "?",
            fg_color: fg ? this._hexToRgb(fg) : [255, 255, 255],
            bg_color: bg ? this._hexToRgb(bg) : [0, 0, 0]
        };
    }

    /**
     * Get the fallback sprite (for unmapped tags).
     *
     * @returns {Object} {char, fg_color, bg_color}
     * @private
     */
    _getFallbackSprite() {
        if (this.theme && this.theme.fallback) {
            return this._spriteFromTheme(this.theme.fallback);
        }
        return {
            char: "?",
            fg_color: [255, 255, 255],
            bg_color: [0, 0, 0]
        };
    }

    /**
     * Convert hex color to RGB array.
     * Example: "#FF0000" → [255, 0, 0]
     *
     * @param {string} hex - Hex color (e.g., "#FF0000")
     * @returns {Array} [r, g, b]
     * @private
     */
    _hexToRgb(hex) {
        if (!hex || !hex.startsWith("#")) return [255, 255, 255];
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? [
            parseInt(result[1], 16),
            parseInt(result[2], 16),
            parseInt(result[3], 16)
        ] : [255, 255, 255];
    }

    /**
     * Call this each time a new server frame arrives.
     * Snapshots current render positions as the interpolation start points.
     *
     * @param {number} now - performance.now() timestamp
     */
    onNewFrame(now) {
        this.prevPos = {};
        for (const [id, pos] of Object.entries(this.renderPos)) {
            this.prevPos[id] = { ...pos };
        }
        this.lastTickTime = now;
    }

    /**
     * Setup font for rendering.
     */
    setupFont() {
        const fontSizeAdjusted = this.config.FONT_SIZE;
        this.ctx.font = `${fontSizeAdjusted}px ${this.config.FONT}`;
        this.ctx.textBaseline = "top";
        this.ctx.imageSmoothingEnabled = false;
    }

    /**
     * Render game state to canvas.
     *
     * Uses theme-based rendering: entities have Tags, which are looked up in theme.json
     * to determine how to draw them. This decouples rendering from game logic.
     *
     * Local player is rendered at localPlayerPos (predicted, zero-latency feel).
     * All other entities are interpolated between their previous and current
     * server positions over the tick window — buttery smooth at 60 FPS even
     * though the server only updates at 20 Hz.
     *
     * @param {GameState} gameState - Current game state
     * @param {Object|null} localPlayerPos - {x, y} predicted player position, or null
     * @param {number} now - performance.now() timestamp
     */
    render(gameState, localPlayerPos, now) {
        // Clear canvas
        this.ctx.fillStyle = this._colorToString([0, 0, 0]);
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Interpolation factor: 0 = just received tick, 1 = next tick due
        const elapsed = now - this.lastTickTime;
        const t = Math.min(elapsed / this.tickDuration, 1.0);

        // Get all entities with Position component (Tags are optional but provide rendering hint)
        const entities = gameState.getEntitiesWith("PositionComponent");

        // Sort by depth
        entities.sort((a, b) => {
            const aPos = a.components.PositionComponent;
            const bPos = b.components.PositionComponent;
            return (aPos.y * 1000 + aPos.x) - (bPos.y * 1000 + bPos.x);
        });

        // Render each entity
        for (const entity of entities) {
            const isLocalPlayer = (entity.id === gameState.playerEntityId);
            this._renderEntity(entity, isLocalPlayer ? localPlayerPos : null, t);
        }
    }

    /**
     * Render a single entity.
     *
     * Looks up rendering info from theme based on entity's Tags component.
     * Falls back to default sprite if no Tags or no theme match.
     *
     * @param {Object} entity
     * @param {Object|null} overridePos - If set, render at this {x,y} instead of server pos
     * @param {number} t - Interpolation factor [0, 1]
     * @private
     */
    _renderEntity(entity, overridePos, t) {
        const serverPos = entity.components.PositionComponent;

        if (!serverPos) return;

        // Look up rendering based on Tags (decoupled from game logic)
        const tags = entity.components.Tags || [];
        const sprite = this._lookupRenderingForTags(tags);

        let x, y;

        if (overridePos) {
            // Local player: use predicted position directly (no interpolation needed)
            x = overridePos.x;
            y = overridePos.y;
        } else {
            // Other entities: interpolate between previous and current server position
            const prev = this.prevPos[entity.id];
            if (prev && (prev.x !== serverPos.x || prev.y !== serverPos.y)) {
                x = prev.x + (serverPos.x - prev.x) * t;
                y = prev.y + (serverPos.y - prev.y) * t;
            } else {
                x = serverPos.x;
                y = serverPos.y;
            }
        }

        // Sync renderPos for next frame's prevPos snapshot
        this.renderPos[entity.id] = { x, y };

        // Calculate screen position
        const screenX = x * this.config.TILE_WIDTH;
        const screenY = y * this.config.TILE_HEIGHT;

        // Render tile background
        const bgColor = sprite.bg_color || [0, 0, 0];
        this.ctx.fillStyle = this._colorToString(bgColor);
        this.ctx.fillRect(screenX, screenY, this.config.TILE_WIDTH, this.config.TILE_HEIGHT);

        // Render character
        const fgColor = sprite.fg_color || [255, 255, 255];
        this.ctx.fillStyle = this._colorToString(fgColor);
        this.ctx.fillText(sprite.char, screenX + 1, screenY + 1);
    }

    /**
     * Convert RGB tuple to CSS color string.
     *
     * @private
     */
    _colorToString(color) {
        if (!color || !Array.isArray(color)) {
            return "rgb(255, 255, 255)";
        }
        return `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
    }

    /**
     * Clear the canvas.
     */
    clear() {
        this.ctx.fillStyle = "rgb(0, 0, 0)";
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    /**
     * Resize canvas and font.
     */
    resize() {
        this.setupFont();
        const dims = calculateCanvasDimensions();
        this.canvas.width = dims.width;
        this.canvas.height = dims.height;
    }

    /**
     * Set tile size and re-render.
     */
    setTileSize(size) {
        setTileSize(size);
        this.resize();
    }
}
