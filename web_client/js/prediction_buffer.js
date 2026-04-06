/**
 * Prediction Buffer - Client-Side Prediction for Predictive Sync Mode.
 *
 * Stores unconfirmed inputs so they can be re-applied after server reconciliation.
 * Each input tracks its sequence number and position delta for replay.
 *
 * Flow:
 *   1. Player presses key → optimistic move applied immediately
 *   2. Input added to pendingInputs with sequence_id
 *   3. Server frame arrives with last_processed_sequence_id
 *   4. All inputs up to that seq are confirmed and discarded
 *   5. Remaining unconfirmed inputs are replayed on top of server position
 */

const DIRECTION_DELTAS = {
    up:        { dx:  0, dy: -1 },
    down:      { dx:  0, dy:  1 },
    left:      { dx: -1, dy:  0 },
    right:     { dx:  1, dy:  0 },
    upleft:    { dx: -1, dy: -1 },
    upright:   { dx:  1, dy: -1 },
    downleft:  { dx: -1, dy:  1 },
    downright: { dx:  1, dy:  1 },
};

class PredictionBuffer {
    constructor() {
        this.sequenceNumber = 0;
        this.pendingInputs = [];  // [{seq, action, direction, dx, dy}]
    }

    /**
     * Get the next sequence number. Call before sending each input.
     * @returns {number}
     */
    nextSeq() {
        return ++this.sequenceNumber;
    }

    /**
     * Record a sent input so it can be replayed during reconciliation.
     *
     * @param {number} seq - Sequence number
     * @param {string} action - Action type ("move", "wait", etc.)
     * @param {string|null} direction - Direction string for move actions
     */
    add(seq, action, direction) {
        const delta = (action === "move" && direction)
            ? (DIRECTION_DELTAS[direction] || { dx: 0, dy: 0 })
            : { dx: 0, dy: 0 };

        this.pendingInputs.push({ seq, action, direction, ...delta });
    }

    /**
     * Discard all inputs confirmed by the server (seq <= confirmedSeq).
     *
     * @param {number} confirmedSeq - Last sequence ID the server processed
     */
    confirmUpTo(confirmedSeq) {
        this.pendingInputs = this.pendingInputs.filter(i => i.seq > confirmedSeq);
    }

    /**
     * Get all unconfirmed inputs in order, for replaying after reconciliation.
     *
     * @returns {Array}
     */
    getUnconfirmed() {
        return [...this.pendingInputs];
    }

    /**
     * Reset on disconnect or reconnect.
     */
    reset() {
        this.sequenceNumber = 0;
        this.pendingInputs = [];
    }
}
