/**
 * Game State - Local mirror of server game state.
 *
 * Maintains entities and their components.
 * Applies delta updates from server.
 * Queries for rendering.
 */

class GameState {
    constructor() {
        this.entities = {};      // entity_id → {components: {...}} — authoritative server state
        this.frameCount = 0;
        this.playerEntityId = null;  // Set when server identifies local player
        this.localPlayerPos = null;  // {x, y} — predicted position, may be ahead of server
        this.lastProcessedSeq = 0;   // Last sequence_id confirmed by server
    }

    /**
     * Set the local player's entity ID. Called on handshake or when server assigns it.
     *
     * @param {number} entityId
     */
    setPlayerEntity(entityId) {
        this.playerEntityId = entityId;
        // Seed localPlayerPos from whatever the server has right now
        const pos = this.getComponent(entityId, "PositionComponent");
        if (pos) {
            this.localPlayerPos = { x: pos.x, y: pos.y };
        }
    }

    /**
     * Apply an optimistic (unconfirmed) move to the local player position.
     * Called immediately when the player presses a key, before server confirms.
     *
     * @param {number} dx
     * @param {number} dy
     */
    applyOptimisticMove(dx, dy) {
        if (!this.localPlayerPos) return;
        this.localPlayerPos = {
            x: this.localPlayerPos.x + dx,
            y: this.localPlayerPos.y + dy,
        };
    }

    /**
     * Reconcile local predicted position with server authoritative state.
     *
     * Step 1: Snap localPlayerPos to server's confirmed position.
     * Step 2: Re-apply any unconfirmed pending inputs on top.
     *
     * This is the "rubberband fix" — if the server rejected a move (e.g. wall),
     * the player snaps back to where the server says they are, then any
     * still-pending inputs are replayed. If all predictions were correct,
     * the final position is identical to what was already shown — no visible change.
     *
     * @param {number} confirmedSeq - last_processed_sequence_id from server frame
     * @param {Array} pendingInputs - Unconfirmed inputs from PredictionBuffer
     */
    reconcile(confirmedSeq, pendingInputs) {
        if (!this.playerEntityId) return;

        // Snap to authoritative server position
        const serverPos = this.getComponent(this.playerEntityId, "PositionComponent");
        if (!serverPos) return;

        this.localPlayerPos = { x: serverPos.x, y: serverPos.y };
        this.lastProcessedSeq = confirmedSeq;

        // Re-apply any inputs the server hasn't processed yet
        for (const input of pendingInputs) {
            if (input.seq > confirmedSeq) {
                this.localPlayerPos = {
                    x: this.localPlayerPos.x + input.dx,
                    y: this.localPlayerPos.y + input.dy,
                };
            }
        }
    }

    /**
     * Apply a Delta Sync packet from server.
     *
     * Handles three packet types:
     * - "spawn": New entity entering client's FOV (full data: position + tags)
     * - "update": Existing entity moved (minimal data: just position)
     * - "despawn": Entity left FOV (minimal data: just entity ID)
     *
     * @param {Object} packet - Delta packet from server
     */
    applyFrame(packet) {
        // Handle the three Delta Sync packet types
        const entityId = packet.id;

        if (packet.type === "spawn") {
            // Create new entity with full data
            this.entities[entityId] = {
                components: {
                    PositionComponent: packet.p ? { x: packet.p[0], y: packet.p[1] } : null,
                    Tags: packet.t || []
                }
            };

            // Seed localPlayerPos when the player entity first spawns
            if (entityId === this.playerEntityId && packet.p && !this.localPlayerPos) {
                this.localPlayerPos = { x: packet.p[0], y: packet.p[1] };
            }

            if (CONFIG.DEBUG) {
                console.log(`[GameState] Spawn entity ${entityId} at [${packet.p}]`);
            }

        } else if (packet.type === "update") {
            // Update existing entity (usually just position)
            if (this.entities[entityId]) {
                if (packet.p) {
                    this.entities[entityId].components.PositionComponent = {
                        x: packet.p[0],
                        y: packet.p[1]
                    };
                }
            }

        } else if (packet.type === "despawn") {
            // Entity left FOV, remove it from local state
            delete this.entities[entityId];

            if (CONFIG.DEBUG) {
                console.log(`[GameState] Despawn entity ${entityId}`);
            }
        }
    }

    /**
     * Get all entities.
     *
     * @returns {Array} Array of {id, components}
     */
    getAllEntities() {
        return Object.entries(this.entities).map(([id, entity]) => ({
            id: parseInt(id),
            ...entity,
        }));
    }

    /**
     * Get entities with specific components.
     *
     * @param {...String} componentNames - Component names to filter by
     * @returns {Array} Filtered entities
     */
    getEntitiesWith(...componentNames) {
        return this.getAllEntities().filter(entity => {
            return componentNames.every(name => name in entity.components);
        });
    }

    /**
     * Get a specific entity.
     *
     * @param {Number} entityId
     * @returns {Object|null} Entity or null
     */
    getEntity(entityId) {
        return this.entities[entityId] || null;
    }

    /**
     * Get a component from an entity.
     *
     * @param {Number} entityId
     * @param {String} componentName
     * @returns {Object|null} Component data or null
     */
    getComponent(entityId, componentName) {
        const entity = this.entities[entityId];
        if (!entity) return null;
        return entity.components[componentName] || null;
    }

    /**
     * Clear all state.
     */
    clear() {
        this.entities = {};
        this.frameCount = 0;
    }

    /**
     * Get stats about the state.
     *
     * @returns {Object} {entityCount, componentCount, ...}
     */
    getStats() {
        let componentCount = 0;
        for (const entity of Object.values(this.entities)) {
            componentCount += Object.keys(entity.components).length;
        }

        return {
            entityCount: Object.keys(this.entities).length,
            componentCount,
            frameCount: this.frameCount,
        };
    }
}
