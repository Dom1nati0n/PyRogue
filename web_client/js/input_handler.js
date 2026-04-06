/**
 * Input Handler - Keyboard input and send to server.
 *
 * Supports:
 * - Arrow keys
 * - WASD
 * - VI keys (hjkl)
 * - Other game actions
 */

class InputHandler {
    constructor(config, network, predictionBuffer, gameState) {
        this.config = config;
        this.network = network;
        this.predictionBuffer = predictionBuffer;
        this.gameState = gameState;
        this.keys = {};  // Key state tracking
        this.isWaitingForResponse = false;  // Debounce for non-predictive mode

        this.keyMap = this._buildKeyMap();
        this._setupListeners();
    }

    /**
     * Build key → action mapping.
     *
     * @private
     */
    _buildKeyMap() {
        const map = {};

        // Movement
        if (this.config.ENABLE_ARROW_KEYS) {
            map["ArrowUp"] = { action: "move", direction: "up" };
            map["ArrowDown"] = { action: "move", direction: "down" };
            map["ArrowLeft"] = { action: "move", direction: "left" };
            map["ArrowRight"] = { action: "move", direction: "right" };
        }

        if (this.config.ENABLE_WASD_KEYS) {
            map["w"] = { action: "move", direction: "up" };
            map["s"] = { action: "move", direction: "down" };
            map["a"] = { action: "move", direction: "left" };
            map["d"] = { action: "move", direction: "right" };
        }

        if (this.config.ENABLE_VI_KEYS) {
            map["h"] = { action: "move", direction: "left" };
            map["j"] = { action: "move", direction: "down" };
            map["k"] = { action: "move", direction: "up" };
            map["l"] = { action: "move", direction: "right" };
            map["y"] = { action: "move", direction: "upleft" };
            map["u"] = { action: "move", direction: "upright" };
            map["b"] = { action: "move", direction: "downleft" };
            map["n"] = { action: "move", direction: "downright" };
        }

        // Other actions
        map[" "] = { action: "wait" };
        map["Enter"] = { action: "wait" };
        map["p"] = { action: "wait" };
        map["i"] = { action: "inventory" };

        return map;
    }

    /**
     * Setup keyboard listeners.
     *
     * @private
     */
    _setupListeners() {
        document.addEventListener("keydown", (e) => this._onKeyDown(e));
        document.addEventListener("keyup", (e) => this._onKeyUp(e));
    }

    /**
     * Handle keydown event.
     *
     * @private
     */
    _onKeyDown(event) {
        const key = event.key.toLowerCase();
        this.keys[key] = true;

        // Check if this is a mapped action
        const action = this.keyMap[key];

        if (action) {
            event.preventDefault();

            // In non-predictive fallback mode, debounce until server responds
            if (this.config.TURN_DEBOUNCE && !this.predictionBuffer && this.isWaitingForResponse) {
                return;
            }

            this._sendAction(action);
        }
    }

    /**
     * Handle keyup event.
     *
     * @private
     */
    _onKeyUp(event) {
        const key = event.key.toLowerCase();
        this.keys[key] = false;
    }

    /**
     * Send action to server.
     *
     * @private
     */
    _sendAction(action) {
        if (!this.network.isConnected) {
            return;
        }

        const payload = { action: action.action };

        // Copy all properties except action itself
        for (const key in action) {
            if (key !== "action") {
                payload[key] = action[key];
            }
        }

        // Predictive mode: optimistic execution before server confirms
        if (this.predictionBuffer && this.gameState) {
            const seq = this.predictionBuffer.nextSeq();
            payload.sequence_id = seq;
            this.predictionBuffer.add(seq, action.action, action.direction || null);

            // Immediately apply the predicted move to the local player position
            if (action.action === "move" && action.direction) {
                const delta = DIRECTION_DELTAS[action.direction] || { dx: 0, dy: 0 };
                this.gameState.applyOptimisticMove(delta.dx, delta.dy);
            }
        } else if (this.config.TURN_DEBOUNCE) {
            // Fallback: dumb terminal debounce
            this.isWaitingForResponse = true;
            setTimeout(() => { this.isWaitingForResponse = false; }, 50);
        }

        this.network.sendInput(payload);
    }

    /**
     * Called when server confirms action.
     *
     * @param {Object} response - Server response
     */
    onActionResponse(response) {
        if (response.type === "ok") {
            console.log("Action accepted:", response.action);
        } else if (response.type === "error") {
            console.warn("Action rejected:", response.message);
        }

        // Unlock input
        this.isWaitingForResponse = false;
    }

    /**
     * Check if a key is currently pressed.
     */
    isKeyPressed(key) {
        return this.keys[key.toLowerCase()] || false;
    }
}
