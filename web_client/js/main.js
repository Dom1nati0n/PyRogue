let gameNetwork;
let gameState;
let predictionBuffer;
let tileRenderer;
let inputHandler;
let uiManager;

async function init() {
    try {
        gameNetwork = new GameNetwork(CONFIG);
        gameState = new GameState();
        predictionBuffer = new PredictionBuffer();

        const canvas = document.getElementById("game-canvas");
        if (!canvas) throw new Error("Canvas not found");

        tileRenderer = new TileRenderer(canvas, CONFIG);
        inputHandler = new InputHandler(CONFIG, gameNetwork, predictionBuffer, gameState);
        uiManager = new UIManager(gameState, tileRenderer, inputHandler);

        gameNetwork.onFrame((frame) => {
            if (frame.type === "frame") {
                // Apply authoritative server state
                gameState.applyFrame(frame);

                // Server reconciliation: snap player to server pos, replay unconfirmed inputs
                const confirmedSeq = frame.last_processed_sequence_id;
                if (confirmedSeq !== undefined) {
                    const pending = predictionBuffer.getUnconfirmed();
                    gameState.reconcile(confirmedSeq, pending);
                    predictionBuffer.confirmUpTo(confirmedSeq);
                }

                // Tell renderer a new tick arrived — advances interpolation start point
                tileRenderer.onNewFrame(performance.now());

            } else if (frame.type === "connected") {
                // Server assigned player entity — seed prediction state
                if (frame.player_entity_id !== undefined) {
                    gameState.setPlayerEntity(frame.player_entity_id);
                }
            } else if (frame.type === "ok") {
                inputHandler.onActionResponse(frame);
            } else if (frame.type === "error") {
                uiManager.addMessage("Error: " + frame.message, "important");
            }
        });

        gameNetwork.onError((error) => {
            predictionBuffer.reset();
            uiManager.showError(`Network: ${error.message || error}`);
        });

        await gameNetwork.connect();
        uiManager.clearError();
        uiManager.addMessage("Connected to server!", "success");
        startGameLoop();

    } catch (e) {
        uiManager?.showError(e.message);
    }
}

function gameLoop(now) {
    tileRenderer.render(gameState, gameState.localPlayerPos, now);
    uiManager.updateUI();
    requestAnimationFrame(gameLoop);
}

function startGameLoop() {
    requestAnimationFrame(gameLoop);
}

document.addEventListener("DOMContentLoaded", init);
