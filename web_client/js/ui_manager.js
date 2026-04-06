/**
 * UI Manager - Updates interface panels from game state.
 *
 * Manages: stats, inventory, messages, status bar, mouse clicks.
 */

class UIManager {
    constructor(gameState, tileRenderer, inputHandler) {
        this.gameState = gameState;
        this.tileRenderer = tileRenderer;
        this.inputHandler = inputHandler;
        this.messages = [];
        this.maxMessages = 5;

        this._setupMouseHandling();
    }

    /**
     * Update all UI elements from current game state.
     */
    updateUI() {
        this._updateStats();
        this._updateInventory();
        this._updateStatus();
    }

    /**
     * Add a message to the log.
     */
    addMessage(text, type = "normal") {
        this.messages.push({ text, type });
        if (this.messages.length > this.maxMessages) {
            this.messages.shift();
        }
        this._updateMessages();
    }

    /**
     * Clear messages.
     */
    clearMessages() {
        this.messages = [];
        this._updateMessages();
    }

    // =========================================================================
    // Private: Update methods
    // =========================================================================

    _updateStats() {
        // Stats would come from player entity's components
        // For now, just show placeholder
        const hp = document.getElementById("stat-hp");
        const level = document.getElementById("stat-level");

        if (hp && level) {
            hp.textContent = "50/100";
            level.textContent = "1";
        }
    }

    _updateInventory() {
        // Would populate from player's inventory component
        const list = document.getElementById("inventory-list");
        if (!list) return;

        // Placeholder items
        const items = [
            { name: "Sword", equipped: true },
            { name: "Potion", count: 3 },
            { name: "Gold", count: 50 },
        ];

        list.innerHTML = "";
        for (const item of items) {
            const div = document.createElement("div");
            div.className = "inventory-item" + (item.equipped ? " equipped" : "");
            div.textContent = item.equipped
                ? `${item.name} (E)`
                : `${item.name}${item.count ? " x" + item.count : ""}`;
            list.appendChild(div);
        }
    }

    _updateMessages() {
        const log = document.getElementById("message-log");
        if (!log) return;

        log.innerHTML = "";
        for (const msg of this.messages) {
            const div = document.createElement("div");
            div.className = "message";
            if (msg.type === "important") div.className += " important";
            if (msg.type === "success") div.className += " success";
            div.textContent = msg.text;
            log.appendChild(div);
        }

        // Auto-scroll to bottom
        log.scrollTop = log.scrollHeight;
    }

    _updateStatus() {
        const status = document.getElementById("status-text");
        const stats = this.gameState.getStats();

        if (status) {
            status.textContent = `Ready | Entities: ${stats.entityCount} | Frame: ${stats.frameCount}`;
        }
    }

    // =========================================================================
    // Mouse handling
    // =========================================================================

    _setupMouseHandling() {
        const canvas = document.getElementById("game-canvas");
        if (!canvas) return;

        canvas.addEventListener("click", (e) => this._onCanvasClick(e));
        canvas.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            this._onCanvasRightClick(e);
        });
        canvas.addEventListener("mousemove", (e) => this._onCanvasMouseMove(e));
    }

    _onCanvasClick(e) {
        const pos = this._getClickTilePos(e);
        if (!pos) return;

        // Left click: move to that tile
        const action = {
            action: "move",
            target_x: pos.x,
            target_y: pos.y,
        };

        this.inputHandler.sendInput(action);
    }

    _onCanvasRightClick(e) {
        const pos = this._getClickTilePos(e);
        if (!pos) return;

        // Right click: interact/attack
        const action = {
            action: "interact",
            target_x: pos.x,
            target_y: pos.y,
        };

        this.inputHandler.sendInput(action);
    }

    _onCanvasMouseMove(e) {
        const pos = this._getClickTilePos(e);
        // Could highlight tile on hover here
    }

    _getClickTilePos(e) {
        const canvas = document.getElementById("game-canvas");
        if (!canvas) return null;

        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Convert pixel coords to tile coords
        const tileX = Math.floor(x / CONFIG.TILE_WIDTH);
        const tileY = Math.floor(y / CONFIG.TILE_HEIGHT);

        // Clamp to viewport bounds
        if (tileX < 0 || tileX >= CONFIG.VIEWPORT_COLS ||
            tileY < 0 || tileY >= CONFIG.VIEWPORT_ROWS) {
            return null;
        }

        return { x: tileX, y: tileY };
    }

    /**
     * Show error in error message box.
     */
    showError(message) {
        const errorDiv = document.getElementById("error-message");
        if (errorDiv) {
            errorDiv.innerHTML = `<p>${message}</p>`;
        }
    }

    /**
     * Clear error message.
     */
    clearError() {
        const errorDiv = document.getElementById("error-message");
        if (errorDiv) {
            errorDiv.innerHTML = "";
        }
    }
}
