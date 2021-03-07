/** @module @hat-core/juggler
 */

import jiff from 'jiff';

import * as u from '@hat-core/util';
import * as future from '@hat-core/future';


/**
 * Settings
 * @property {number} settings.syncDelay sync delay [ms]
 * @property {number} settings.retryDelay retry delay [ms]
 */
export const settings = {
    syncDelay: 100,
    retryDelay: 5000
};


/** Juggler client connection */
export class Connection {
    /**
     * Create connection
     * @param {?string} address Juggler server address, formatted as
     *     ``ws[s]://<host>[:<port>][/<path>]``. If not provided, hostname
     *     and port obtained from ``widow.location`` are used instead, with
     *     ``ws`` as a path.
     */
    constructor(address) {
        this._localData = null;
        this._remoteData = null;
        this._onOpen = () => {};
        this._onClose = () => {};
        this._onMessage = () => {};
        this._onRemoteDataChange = () => {};
        this._delayedSyncID = null;
        this._syncedLocalData = null;

        address = address || (() => {
            const protocol = window.location.protocol == 'https:' ? 'wss' : 'ws';
            const hostname = window.location.hostname || 'localhost';
            const port = window.location.port;
            return `${protocol}://${hostname}` + (port ? `:${port}` : '') + '/ws';
        })();
        this._ws = new WebSocket(address);
        this._ws.onopen = () => this._onOpen();
        this._ws.onclose = () => {
            clearTimeout(this._delayedSyncID);
            this._onClose();
        };
        this._ws.onmessage = (evt) => {
            try {
                let msg = JSON.parse(evt.data);
                if (msg.type == 'DATA') {
                    this._remoteData = jiff.patch(msg.payload, this._remoteData);
                    this._onRemoteDataChange(this._remoteData);
                } else if (msg.type == 'MESSAGE') {
                    this._onMessage(msg.payload);
                } else {
                    throw new Error('unsupported message type');
                }
            } catch (e) {
                this._ws.close();
                throw e;
            }
        };
    }

    /**
     * Local data
     * @type {*}
     */
    get localData() {
        return this._localData;
    }

    /**
     * Remote data
     * @type {*}
     */
    get remoteData() {
        return this._remoteData;
    }

    /**
     * WebSocket ready state
     * @type {number}
     */
    get readyState() {
        return this._ws.readyState;
    }

    /**
     * Set on open callback
     * @type {function}
     */
    set onOpen(cb) {
        this._onOpen = cb;
    }

    /**
     * Set on close callback
     * @type {function}
     */
    set onClose(cb) {
        this._onClose = cb;
    }

    /**
     * Set on message callback
     * @type {function(*)}
     */
    set onMessage(cb) {
        this._onMessage = cb;
    }

    /**
     * Set on remote data change callback
     * @type {function(*)}
     */
    set onRemoteDataChange(cb) {
        this._onRemoteDataChange = cb;
    }

    /**
     * Close connection
     */
    close() {
        this._ws.close(1000);
    }

    /**
     * Send message
     * @param {*} msg
     */
    send(msg) {
        if (this.readyState != WebSocket.OPEN) {
            throw new Error("Connection not open");
        }
        this._ws.send(JSON.stringify({
            type: 'MESSAGE',
            payload: msg
        }));
    }

    /**
     * Set local data
     * @param {*} data
     */
    setLocalData(data) {
        if (this.readyState != WebSocket.OPEN) {
            throw new Error("Connection not open");
        }
        this._localData = data;
        if (this._delayedSyncID == null) {
            this._delayedSyncID = setTimeout(() => {
                const patch = jiff.diff(this._syncedLocalData, this._localData);
                if (patch.length > 0) {
                    this._ws.send(JSON.stringify({
                        type: 'DATA',
                        payload: patch
                    }));
                    this._syncedLocalData = this._localData;
                }
                this._delayedSyncID = null;
            }, settings.syncDelay);
        }
    }
}


/** Juggler based application */
export class Application {
    /**
     * Create application
     * @param {module:@hat-core/renderer.Renderer} r renderer
     * @param {?string} address juggler server address, see
     *     {@link module:@hat-core/juggler.Connection}
     * @param {?module:@hat-core/util.Path} localPath local data state path
     * @param {?module:@hat-core/util.Path} remotePath remote data state path
     * @param {?object} rpcCbs local RPC function callbacs
     */
    constructor(r, address, localPath, remotePath, rpcCbs) {
        this._conn = null;
        this._onMessage = () => {};

        if (localPath != null) {
            r.addEventListener('change', () => {
                if (this._conn && this._conn.readyState == WebSocket.OPEN) {
                    this._conn.setLocalData(r.get(localPath));
                }
            });
        }

        let lastRpcId = 0;
        const rpcCalls = new Map();
        this._rpc = new Proxy({}, {
            get: (_, action) => (...args) => {
                lastRpcId += 1;
                this._conn.send({
                    type: 'rpc',
                    id: lastRpcId,
                    direction: 'request',
                    action: action,
                    args: args});
                const f = future.create();
                rpcCalls.set(lastRpcId, f);
                return f;
            }
        });

        u.delay(async () => {
            while (true) {
                const closeFuture = future.create();
                this._conn = new Connection(address);
                this._conn._onOpen = () =>{
                    if (localPath != null) {
                        this._conn.setLocalData(r.get(localPath));
                    }
                };
                this._conn._onMessage = msg => {
                    if (u.isObject(msg) && msg.type == 'rpc') {
                        if (msg.direction == 'request') {
                            let success;
                            let result;
                            try {
                                result = (rpcCbs || {})[msg.action](...msg.args);
                                success = true;
                            } catch (e) {
                                result = String(e);
                                success = false;
                            }
                            this._conn.send({
                                type: 'rpc',
                                id: msg.id,
                                direction: 'response',
                                success: success,
                                result: result
                            });
                        } else if (msg.direction == 'response') {
                            const f = rpcCalls.get(msg.id);
                            rpcCalls.delete(msg.id);
                            if (msg.success) {
                                f.setResult(msg.result);
                            } else {
                                f.setError(msg.result);
                            }
                        }
                    } else {
                        this._onMessage(msg);
                    }
                };
                this._conn._onRemoteDataChange = data => {
                    if (remotePath != null) r.set(remotePath, data);
                };
                this._conn._onClose = () => {
                    if (remotePath != null) r.set(remotePath, null);
                    this._conn = null;
                    closeFuture.setResult();
                };
                await closeFuture;
                await u.sleep(settings.retryDelay);
            }
        });
    }

    /**
     * RPC proxy
     * @type {*}
     */
    get rpc() {
        return this._rpc;
    }

    /**
     * Set on message callback
     * @type {function(*)}
     */
    set onMessage(cb) {
        this._onMessage = cb;
        if (this._conn) {
            this._conn._onMessage = cb;
        }
    }

    /**
     * Send message
     * @param {*} msg
     */
    send(msg) {
        if(this._conn) {
            this._conn.send(msg);
        } else {
            throw new Error("Connection closed");
        }
    }
}
