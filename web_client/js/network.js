class GameNetwork {
    constructor(config) {
        this.config = config;
        this.ws = null;
        this.isConnected = false;
        this.frameHandlers = [];
        this.errorHandlers = [];
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
    }

    async connect() {
        return new Promise((resolve, reject) => {
            try {
                const wsUrl = this.config.SERVER_WS_URL();
                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = () => this._onOpen();
                this.ws.onmessage = (event) => this._onMessage(event);
                this.ws.onerror = (event) => this._onError(event);
                this.ws.onclose = () => this._onClose();

                let timeout = setTimeout(() => reject(new Error("Connection timeout")), 5000);

                const originalOnOpen = this.ws.onopen;
                this.ws.onopen = () => {
                    originalOnOpen?.call(this.ws);
                    clearTimeout(timeout);
                    this._sendHandshake().then(resolve).catch(reject);
                };
            } catch (e) {
                reject(e);
            }
        });
    }

    async _sendHandshake() {
        return new Promise((resolve, reject) => {
            try {
                this.ws.send(JSON.stringify({ player_id: this.config.PLAYER_ID }));

                const confirmHandler = (data) => {
                    if (data.type === "connected") {
                        this.removeFrameHandler(confirmHandler);
                        resolve();
                    }
                };

                this.onFrame(confirmHandler);
                setTimeout(() => reject(new Error("Handshake timeout")), 3000);
            } catch (e) {
                reject(e);
            }
        });
    }

    sendInput(action) {
        if (!this.isConnected) return;
        try {
            this.ws.send(JSON.stringify(action));
        } catch (e) {
            this._callErrorHandlers(e);
        }
    }

    onFrame(handler) {
        this.frameHandlers.push(handler);
    }

    removeFrameHandler(handler) {
        this.frameHandlers = this.frameHandlers.filter(h => h !== handler);
    }

    onError(handler) {
        this.errorHandlers.push(handler);
    }

    _onOpen() {
        this.isConnected = true;
        this.reconnectAttempts = 0;
    }

    _onMessage(event) {
        try {
            const data = JSON.parse(event.data);
            for (const handler of this.frameHandlers) {
                try {
                    handler(data);
                } catch (e) {
                    // Silently ignore handler errors
                }
            }
        } catch (e) {
            this._callErrorHandlers(e);
        }
    }

    _onError(event) {
        this._callErrorHandlers(event);
    }

    _onClose() {
        this.isConnected = false;

        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * this.reconnectAttempts;
            setTimeout(() => {
                this.connect().catch(e => this._callErrorHandlers(e));
            }, delay);
        } else {
            this._callErrorHandlers(new Error("Connection failed"));
        }
    }

    _callErrorHandlers(error) {
        for (const handler of this.errorHandlers) {
            try {
                handler(error);
            } catch (e) {
                // Silently ignore handler errors
            }
        }
    }

    disconnect() {
        if (this.ws) this.ws.close();
    }
}
