/** @module @hat-core/renderer
 */

import {init as snabbdomInit} from 'snabbdom/build/package/init';
import {h as snabbdomH} from 'snabbdom/build/package/h';
import {classModule as snabbdomClass} from 'snabbdom/build/package/modules/class';
import {datasetModule as snabbdomDataset} from 'snabbdom/build/package/modules/dataset';
import {eventListenersModule as snabbdomEvent} from 'snabbdom/build/package/modules/eventlisteners';
import {styleModule as snabbdomStyle} from 'snabbdom/build/package/modules/style';

import * as u from '@hat-core/util';


// patched version of snabbdom's es/modules/attributes.js
const snabbdomAttributes = (() => {
    function updateAttrs(oldVnode, vnode) {
        var key, elm = vnode.elm, oldAttrs = oldVnode.data.attrs, attrs = vnode.data.attrs;
        if (!oldAttrs && !attrs)
            return;
        if (oldAttrs === attrs)
            return;
        oldAttrs = oldAttrs || {};
        attrs = attrs || {};
        for (key in attrs) {
            var cur = attrs[key];
            var old = oldAttrs[key];
            if (old !== cur) {
                if (cur === true) {
                    elm.setAttribute(key, "");
                }
                else if (cur === false) {
                    elm.removeAttribute(key);
                }
                else {
                    elm.setAttribute(key, cur);
                }
            }
        }
        for (key in oldAttrs) {
            if (!(key in attrs)) {
                elm.removeAttribute(key);
            }
        }
    }
    return { create: updateAttrs, update: updateAttrs };
})();


// patched version of snabbdom's es/modules/props.js
const snabbdomProps = (() => {
    function updateProps(oldVnode, vnode) {
        var key, cur, old, elm = vnode.elm, oldProps = oldVnode.data.props, props = vnode.data.props;
        if (!oldProps && !props)
            return;
        if (oldProps === props)
            return;
        oldProps = oldProps || {};
        props = props || {};
        for (key in oldProps) {
            if (!props[key]) {
                if (key === 'style') {
                    elm[key] = '';
                } else {
                    delete elm[key];
                }
            }
        }
        for (key in props) {
            cur = props[key];
            old = oldProps[key];
            if (old !== cur && (key !== 'value' || elm[key] !== cur)) {
                elm[key] = cur;
            }
        }
    }
    return { create: updateProps, update: updateProps };
})();


const patch = snabbdomInit([
    snabbdomAttributes,
    snabbdomClass,
    snabbdomDataset,
    snabbdomEvent,
    snabbdomProps,
    snabbdomStyle
]);


function vhFromArray(node) {
    if (!node)
        return [];
    if (u.isString(node))
        return node;
    if (!u.isArray(node))
        throw 'Invalid node structure';
    if (node.length < 1)
        return [];
    if (typeof node[0] != 'string')
        return node.map(vhFromArray);
    const hasData = node.length > 1 && u.isObject(node[1]);
    const children = u.pipe(
        u.map(vhFromArray),
        u.flatten,
        Array.from
    )(node.slice(hasData ? 2 : 1));
    const result = hasData ?
        snabbdomH(node[0], node[1], children) :
        snabbdomH(node[0], children);
    return result;
}

/**
 * Virtual DOM renderer
 */
export class Renderer extends EventTarget {

    /**
     * Calls `init` method
     * @param {HTMLElement} [el=document.body]
     * @param {Any} [initState=null]
     * @param {Function} [vtCb=null]
     * @param {Number} [maxFps=30]
     */
    constructor(el, initState, vtCb, maxFps) {
        super();
        this.init(el, initState, vtCb, maxFps);
    }

    /**
     * Initialize renderer
     * @param {HTMLElement} [el=document.body]
     * @param {Any} [initState=null]
     * @param {Function} [vtCb=null]
     * @param {Number} [maxFps=30]
     * @return {Promise}
     */
    init(el, initState, vtCb, maxFps) {
        this._state = null;
        this._changes = [];
        this._promise = null;
        this._timeout = null;
        this._lastRender = null;
        this._vtCb = vtCb;
        this._maxFps = u.isNumber(maxFps) ? maxFps : 30;
        this._vNode = el || document.querySelector('body');
        if (initState)
            return this.change(_ => initState);
        return new Promise(resolve => { resolve(); });
    }

    /**
      * Render
      */
    render() {
        if (!this._vtCb)
            return;
        this._lastRender = performance.now();
        const vNode = vhFromArray(this._vtCb(this));
        patch(this._vNode, vNode);
        this._vNode = vNode;
        this.dispatchEvent(new CustomEvent('render', {detail: this._state}));
    }

    /**
     * Get current state value referenced by `paths`
     * @param {...Path} paths
     * @return {Any}
     */
    get(...paths) {
        return u.get(paths, this._state);
    }

    /**
     * Change current state value referenced by `path`
     * @param {Path} path
     * @param {Any} value
     * @return {Promise}
     */
    set(path, value) {
        if (arguments.length < 2) {
            value = path;
            path = [];
        }
        return this.change(path, _ => value);
    }

    /**
     * Change current state value referenced by `path`
     * @param {Path} path
     * @param {Function} cb
     * @return {Promise}
     */
    change(path, cb) {
        if (arguments.length < 2) {
            cb = path;
            path = [];
        }
        this._changes.push([path, cb]);
        if (this._promise)
            return this._promise;
        this._promise = new Promise((resolve, reject) => {
            setTimeout(() => {
                try {
                    this._change();
                } catch(e) {
                    this._promise = null;
                    reject(e);
                    throw e;
                }
                this._promise = null;
                resolve();
            }, 0);
        });
        return this._promise;
    }

    _change() {
        let change = false;
        while (this._changes.length > 0) {
            const [path, cb] = this._changes.shift();
            const view = u.get(path);
            const oldState = this._state;
            this._state = u.change(path, cb, this._state);
            if (this._state && u.equals(view(oldState),
                                        view(this._state)))
                continue;
            change = true;
            if (!this._vtCb || this._timeout)
                continue;
            const delay = (!this._lastRender || !this._maxFps ?
                0 :
                (1000 / this._maxFps) -
                (performance.now() - this._lastRender));
            this._timeout = setTimeout(() => {
                this._timeout = null;
                this.render();
            }, (delay > 0 ? delay : 0));
        }
        if (change)
            this.dispatchEvent(
                new CustomEvent('change', {detail: this._state}));
    }
}
// Renderer.prototype.set = u.curry(Renderer.prototype.set);
// Renderer.prototype.change = u.curry(Renderer.prototype.change);


/**
 * Default renderer
 * @static
 * @type {Renderer}
 */
const defaultRenderer = (() => {
    const r = (window && window.__hat_default_renderer) || new Renderer();
    if (window)
        window.__hat_default_renderer = r;
    return r;
})();
export default defaultRenderer;
