/** @module @hat-core/juggler
 */

import jiff from 'jiff';

import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as future from '@hat-core/future';


function getDefaultAddress() {
    const protocol = window.location.protocol == 'https:' ? 'wss' : 'ws';
    const hostname = window.location.hostname || 'localhost';
    const port = window.location.port;
    return `${protocol}://${hostname}` + (port ? `:${port}` : '') + '/ws';
}


/**
 * Juggler client connection
 *
 * Available events:
 *  - open - connection is opened (detail is undefined)
 *  - close - connection is closed (detail is undefined)
 *  - message - received new message (detail is received message)
 *  - change - remote data changed (detail is new remote data)
 */
export class Connection extends EventTarget {

    /**
     * Create connection
     * @param {string} address Juggler server address, formatted as
     *     ``ws[s]://<host>[:<port>][/<path>]``. If not provided, hostname
     *     and port obtained from ``widow.location`` are used instead, with
     *     ``ws`` as a path.
     * @param {number} syncDelay sync delay in ms
     */
    constructor(address=getDefaultAddress(), syncDelay=100) {
        super();
        this._syncDelay = syncDelay;
        this._localData = null;
        this._remoteData = null;
        this._delayedSyncID = null;
        this._syncedLocalData = null;
        this._ws = new WebSocket(address);
        this._ws.addEventListener('open', () => this._onOpen());
        this._ws.addEventListener('close', () => this._onClose());
        this._ws.addEventListener('message', evt => this._onMessage(evt.data));
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
            throw new Error("connection not open");
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
            throw new Error("connection not open");
        }
        this._localData = data;
        if (this._delayedSyncID != null)
            return;
        this._delayedSyncID = setTimeout(
            () => { this._onSync(); },
            this._syncDelay);
    }

    _onOpen() {
        this.dispatchEvent(new CustomEvent('open'));
    }

    _onClose() {
        if (this._delayedSyncID != null) {
            clearTimeout(this._delayedSyncID);
            this._delayedSyncID = null;
        }
        this.dispatchEvent(new CustomEvent('close'));
    }

    _onMessage(data) {
        try {
            const msg = JSON.parse(data);
            if (msg.type == 'DATA') {
                this._remoteData = jiff.patch(msg.payload, this._remoteData);
                this.dispatchEvent(new CustomEvent('change', {detail: this._remoteData}));
            } else if (msg.type == 'MESSAGE') {
                this.dispatchEvent(new CustomEvent('message', {detail: msg.payload}));
            } else {
                throw new Error('unsupported message type');
            }
        } catch (e) {
            this._ws.close();
            throw e;
        }
    }

    _onSync() {
        const patch = jiff.diff(this._syncedLocalData, this._localData);
        if (patch.length > 0) {
            this._ws.send(JSON.stringify({
                type: 'DATA',
                payload: patch
            }));
            this._syncedLocalData = this._localData;
        }
        this._delayedSyncID = null;
    }

}


/**
 * Juggler based application
 *
 * Available events:
 *  - connected - connected to server (detail is undefined)
 *  - disconnected - disconnected from server (detail is undefined)
 *  - message - received new message (detail is received message)
 */
export class Application extends EventTarget {

    /**
     * Create application
     * @param {?module:@hat-core/util.Path} localPath local data state path
     * @param {?module:@hat-core/util.Path} remotePath remote data state path
     * @param {object} localRpcCbs local RPC function callbacs
     * @param {module:@hat-core/renderer.Renderer} renderer renderer
     * @param {string} address juggler server address, see
     *     {@link module:@hat-core/juggler.Connection}
     */
    constructor(
        localPath=null,
        remotePath=null,
        localRpcCbs={},
        renderer=r,
        address=getDefaultAddress(),
        syncDelay=100,
        retryDelay=5000) {

        super();
        this._localPath = localPath;
        this._remotePath = remotePath;
        this._localRpcCbs = localRpcCbs;
        this._renderer = renderer;
        this._address = address;
        this._syncDelay = syncDelay;
        this._retryDelay = retryDelay;
        this._conn = null;
        this._lastRpcId = 0;
        this._rpcFutures = new Map();
        this._rpc = new Proxy({}, {
            get: (_, action) => (...args) => this._rpcCall(action, args)
        });

        if (localPath != null)
            renderer.addEventListener('change', () => this._onRendererChange());

        u.delay(() => this._connectLoop());
    }

    /**
     * RPC proxy
     * @type {*}
     */
    get rpc() {
        return this._rpc;
    }

    /**
     * Send message
     * @param {*} msg
     */
    send(msg) {
        if (!this._conn)
            throw new Error("connection closed");
        this._conn.send(msg);
    }

    _onOpen() {
        if (this._localPath)
            this._conn.setLocalData(this._renderer.get(this._localPath));
        this.dispatchEvent(new CustomEvent('connected'));
    }

    _onClose() {
        if (this._remotePath)
            this._renderer.set(this._remotePath, null);
        this.dispatchEvent(new CustomEvent('disconnected'));
    }

    _onMessage(msg) {
        if (u.isObject(msg) && msg.type == 'rpc') {
            this._onRpcMessage(msg);
        } else {
            this.dispatchEvent(new CustomEvent('message', {detail: msg}));
        }
    }

    _onRpcMessage(msg) {
        if (msg.direction == 'request') {
            this._onRpcReqMessage(msg);
        } else if (msg.direction == 'response') {
            this._onRpcResMessage(msg);
        }
    }

    _onRpcReqMessage(msg) {
        let success;
        let result;
        try {
            result = this._localRpcCbs[msg.action](...msg.args);
            success = true;
        } catch (e) {
            result = String(e);
            success = false;
        }
        this.send({
            type: 'rpc',
            id: msg.id,
            direction: 'response',
            success: success,
            result: result
        });
    }

    _onRpcResMessage(msg) {
        const f = this._rpcFutures.get(msg.id);
        this._rpcFutures.delete(msg.id);
        if (msg.success) {
            f.setResult(msg.result);
        } else {
            f.setError(msg.result);
        }
    }

    _onConnectionChange(data) {
        if (this._remotePath == null)
            return;
        this._renderer.set(this._remotePath, data);
    }

    _onRendererChange() {
        if (!this._conn || this._conn.readyState != WebSocket.OPEN)
            return;
        this._conn.setLocalData(this._renderer.get(this._localPath));
    }

    _rpcCall(action, args) {
        this._lastRpcId += 1;
        this.send({
            type: 'rpc',
            id: this._lastRpcId,
            direction: 'request',
            action: action,
            args: args});
        const f = future.create();
        this._rpcFutures.set(this._lastRpcId, f);
        return f;
    }

    async _connectLoop() {
        while (true) {
            this._conn = new Connection(this._address, this._syncDelay);
            this._conn.addEventListener('open', () => this._onOpen());
            this._conn.addEventListener('close', () => this._onClose());
            this._conn.addEventListener('message', evt => this._onMessage(evt.detail));
            this._conn.addEventListener('change', evt => this._onConnectionChange(evt.detail));

            const closeFuture = future.create();
            this._conn.addEventListener('close', () => closeFuture.setResult());
            await closeFuture;
            this._conn = null;
            await u.sleep(this._retryDelay);
        }
    }

}
