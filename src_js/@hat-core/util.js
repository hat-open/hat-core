/** @module "@hat-core"/util
 */

/**
 * Path can be an object property name, array index, or array of Paths
 * @typedef {string|number|Path[]} module:"@hat-core"/util.Path
 */

/**
 * Identity function
 * @function
 * @param {Any} obj input object
 * @return {Any} same object as input
 */
export const identity = obj => obj;

/**
 * Check if value is Array (wrapper for Array.isArray)
 * @function
 * @param {Any} arr input object
 * @return {Boolean}
 */
export const isArray = Array.isArray;

/**
 * Check if value is Object (not `true` from Array or `null`)
 * @function
 * @param {Any} obj input object
 * @return {Boolean}
 */
export const isObject = obj => obj !== null &&
                               typeof(obj) == 'object' &&
                               !isArray(obj);

/**
 * Check if value is number
 * @function
 * @param {Any} n input object
 * @return {Boolean}
 */
export const isNumber = n => typeof(n) == 'number';

/**
 * Check if value is integer
 * @function
 * @param {Any} n input object
 * @type {Boolean}
 */
export const isInteger = Number.isInteger;

/**
 * Check if value is string
 * @function
 * @param {Any} str input object
 * @type {Boolean}
 */
export const isString = str => typeof(str) == 'string';

/**
 * Strictly parse integer from string
 * @param {String} value
 * @return {Number}
 */
export function strictParseInt(value) {
    if (/^(-|\+)?([0-9]+)$/.test(value))
        return Number(value);
    return NaN;
}

/**
 * Strictly parse float from string
 * @param {String} value
 * @return {Number}
 */
export function strictParseFloat(value) {
    if (/^(-|\+)?([0-9]+(\.[0-9]+)?)$/.test(value))
        return Number(value);
    return NaN;
}

/**
 * Create new deep copy of input value
 * @param {Any} value
 * @return {Any} copy of value
 */
export function clone(obj) {
    if (isArray(obj))
        return Array.from(obj, clone);
    if (isObject(obj)) {
        let ret = {};
        for (let i in obj)
            ret[i] = clone(obj[i]);
        return ret;
    }
    return obj;
}

/**
 * Combine two arrays in single array of pairs
 * @param {Array<Any>} arr1
 * @param {Array<Any>} arr2
 * @return {Array<Array<Any>>}
 */
export function zip(arr1, arr2) {
    return Array.from((function*() {
        for (let i = 0; i < arr1.length || i < arr2.length; ++i)
            yield [arr1[i], arr2[i]];
    })());
}

/**
 * Convert object to array of key, value pairs
 * @param {Object} obj
 * @return {Array<Array>}
 */
export function toPairs(obj) {
    return Object.entries(obj);
}

/**
 * Convert array of key, value pairs to object
 * @param {Array<Array>} arr
 * @return {Object}
 */
export function fromPairs(arr) {
    let ret = {};
    for (let [k, v] of arr)
        ret[k] = v;
    return ret;
}

/**
 * Flatten nested arrays
 * @param {Array} arr
 * @return {Generator}
 */
export function* flatten(arr) {
    if (isArray(arr)) {
        for (let i of arr)
            if (isArray(i))
                yield* flatten(i);
            else
                yield i;
    } else {
        yield arr;
    }
}

/**
 * Pipe function calls (functional composition with reversed order)
 * @param {...Function} fns functions
 * @return {Function}
 */
export function pipe(...fns) {
    if (fns.length < 1)
        throw 'no functions';
    return function (...args) {
        let ret = fns[0].apply(this, args);
        for (let fn of fns.slice(1))
            ret = fn(ret);
        return ret;
    };
}

/**
 * Apply list of functions to same arguments and return list of results
 * @param {...Function} fns functions
 * @return {Function}
 */
export function flap(...fns) {
    return (...args) => fns.map(fn => fn.apply(this, args));
}

/**
 * Curry function with fixed arguments lenth
 * @param {Function} fn
 * @return {Function}
 */
export function curry(fn) {
    let wrapper = function(oldArgs) {
        return function(...args) {
            args = oldArgs.concat(args);
            if (args.length >= fn.length)
                return fn(...args);
            return wrapper(args);
        };
    };
    return wrapper([]);
}

/**
 * Deep object equality
 * (curried function)
 * @function
 * @param {Any} x
 * @param {Any} y
 * @return {Boolean}
 */
export const equals = curry((x, y) => {
    if (x === y)
        return true;
    if (typeof(x) != 'object' ||
        typeof(y) != 'object' ||
        x === null ||
        y === null)
        return false;
    if (Array.isArray(x) && Array.isArray(y)) {
        if (x.length != y.length)
            return false;
        for (let [a, b] of zip(x, y)) {
            if (!equals(a, b))
                return false;
        }
        return true;
    } else if (!Array.isArray(x) && !Array.isArray(y)) {
        if (Object.keys(x).length != Object.keys(y).length)
            return false;
        for (let key in x) {
            if (!(key in y))
                return false;
        }
        for (let key in x) {
            if (!equals(x[key], y[key]))
                return false;
        }
        return true;
    }
    return false;
});

/**
 * Get value from `obj` referenced by `path`
 * (curried function)
 * @function
 * @param {Path} path
 * @param {Any} obj
 * @return {Any}
 */
export const get = curry((path, obj) => {
    let ret = obj;
    for (let i of flatten(path)) {
        if (ret === null || typeof(ret) != 'object')
            return undefined;
        ret = ret[i];
    }
    return ret;
});

/**
 * Change `obj` by appling function `fn` to value referenced by `path`
 * (curried function)
 * @function
 * @param {Path} path
 * @param {Function} fn
 * @param {Any} obj
 * @return {Any} changed `obj`
 */
export const change = curry((path, fn, obj) => {
    function _change(path, obj) {
        if (isInteger(path[0])) {
            obj = (isArray(obj) ? Array.from(obj) : []);
        } else if (isString(path[0])) {
            obj = (isObject(obj) ? Object.assign({}, obj) : {});
        } else {
            throw 'invalid path';
        }
        if (path.length > 1) {
            obj[path[0]] = _change(path.slice(1), obj[path[0]]);
        } else {
            obj[path[0]] = fn(obj[path[0]]);
        }
        return obj;
    }
    path = Array.from(flatten(path));
    if (path.length < 1)
        return fn(obj);
    return _change(path, obj);
});

/**
 * Change `obj` by setting value referenced by `path` to `val`
 * (curried function)
 * @function
 * @param {Path} path
 * @param {Any} val
 * @param {Any} obj
 * @return {Any} changed `obj`
 */
export const set = curry((path, val, obj) => change(path, _ => val, obj));

/**
 * Change `obj` by omitting value referenced by `path`
 * (curried function)
 * @function
 * @param {Path} path
 * @param {Any} obj
 * @return {Any} changed `obj`
 */
export const omit = curry((path, obj) => {
    function _omit(path, obj) {
        if (isInteger(path[0])) {
            obj = (isArray(obj) ? Array.from(obj) : []);
        } else if (isString(path[0])) {
            obj = (isObject(obj) ? Object.assign({}, obj) : {});
        } else {
            throw 'invalid path';
        }
        if (path.length > 1) {
            obj[path[0]] = _omit(path.slice(1), obj[path[0]]);
        } else if (isInteger(path[0])) {
            obj.splice(path[0], 1);
        } else {
            delete obj[path[0]];
        }
        return obj;
    }
    path = Array.from(flatten(path));
    if (path.length < 1)
        return undefined;
    return _omit(path, obj);
});

/**
 * Change `obj` by moving value from `srcPath` to `dstPath`
 * (curried function)
 * @function
 * @param {Path} srcPath
 * @param {Path} dstPath
 * @param {Any} obj
 * @return {Any} changed `obj`
 */
export const move = curry((srcPath, dstPath, obj) => pipe(
    set(dstPath, get(srcPath, obj)),
    omit(srcPath)
)(obj));

/**
 * Sort `arr` by with comparison function `fn`
 * (curried function)
 * @function
 * @param {Function} fn
 * @param {Array} arr
 * @return {Array} sorted `arr`
 */
export const sortBy = curry((fn, arr) => Array.from(arr).sort((x, y) => {
    let xVal = fn(x);
    let yVal = fn(y);
    if (xVal < yVal)
        return -1;
    if (xVal > yVal)
        return 1;
    return 0;
}));

/**
 * Create object which is subset `obj` containing only properties defined by
 * `arr`
 * (curried function)
 * @function
 * @param {Array} arr
 * @param {Object} obj
 * @return {Object} subset of `obj`
 */
export const pick = curry((arr, obj) => {
    const ret = {};
    for (let i of arr)
        if (i in obj)
            ret[i] = obj[i];
    return ret;
});

/**
 * Change `ao` by applying function `fn` to it's elements
 * (curried function)
 * @function
 * @param {Function} fn
 * @param {Array|Object} ao
 * @return {Array|Object} modified `ao`
 */
export const map = curry((fn, ao) => isArray(ao) ?
    ao.map(fn) :
    pipe(toPairs,
         x => x.map(([k, v]) => [k, fn(v)]),
         fromPairs)(ao));

/**
 * Change `arr` to contain only elements for which function `fn` returns `true`
 * (curried function)
 * @function
 * @param {Function} fn
 * @param {Array} arr
 * @return {Array} filtered `arr`
 */
export const filter = curry((fn, arr) => arr.filter(fn));

/**
 * Append `val` to end of `arr`
 * (curried function)
 * @function
 * @param {Any} val
 * @param {Array} arr
 * @return {Array} `arr` with appended `val`
 */
export const append = curry((val, arr) => arr.concat([val]));

/**
 * Reduce `arr` values by appling function `fn`
 * (curried function)
 * @function
 * @param {Function} fn
 * @param {Any} val initial accumulator value
 * @param {Array} arr
 * @return {Any} reduced value
 */
export const reduce = curry((fn, val, arr) => arr.reduce(fn, val));

/**
 * Merge two objects
 * (curried function)
 * @function
 * @param {Object} obj1
 * @param {Object} obj2
 * @return {Object} combined `obj1` and `obj2`
 */
export const merge = curry((obj1, obj2) => Object.assign({}, obj1, obj2));

/**
 * Merge multiple objects
 * (curried function)
 * @function
 * @param {...Object} objs
 * @return {Object} combined `objs`
 */
export const mergeAll = reduce(merge, {});

/**
 * Find element in `arr` for which function `fn` returns `true`
 * (curried function)
 * @function
 * @param {Function} fn
 * @param {Array} arr
 * @return {Any}
 */
export const find = curry((fn, arr) => arr.find(fn));

/**
 * Concatenate two arrays
 * (curried function)
 * @function
 * @param {Array} arr1
 * @param {Array} arr2
 * @return {Array} concatenated `arr1` and `arr2`
 */
export const concat = curry((arr1, arr2) => arr1.concat(arr2));

/**
 * Create union of two arrays using `equals` to check equality
 * (curried function)
 * @function
 * @param {Array} arr1
 * @param {Array} arr2
 * @return {Array} union of `arr1` and `arr2`
 */
export const union = curry((arr1, arr2) => {
    return reduce((acc, val) => {
        if (!find(equals(val), arr1))
            acc = append(val, acc);
        return acc;
    }, arr1, arr2);
});

/**
 * Check if `arr` contains `val`
 * (curried function)
 * @function
 * @param {Any} val
 * @param {Array} arr
 * @return {Boolean}
 */
export const contains = curry((val, arr) => arr.includes(val));

/**
 * Insert `val` into `arr` on index `idx`
 * (curried function)
 * @function
 * @param {Number} idx
 * @param {Any} val
 * @param {Array} arr
 * @return {Array}
 */
// TODO: Array.from(arr).splice(idx, 0, val) not working?
export const insert = curry((idx, val, arr) =>
    arr.slice(0, idx).concat([val], arr.slice(idx)));

/**
 * Get array slice
 * (curried function)
 * @function
 * @param {Number} begin
 * @param {Number} end
 * @param {Array} arr
 * @return {Array}
 */
export const slice = curry((begin, end, arr) => arr.slice(begin, end));

/**
 * Reverse array
 * @param  {Array} arr
 * @return {Array}
 */
export function reverse(arr) {
    return Array.from(arr).reverse();
}

/**
 * Array length
 * @param  {Array} arr
 * @return {Number}
 */
export function length(arr) {
    return arr.length;
}

/**
 * Create promise that resolves in `t` milliseconds
 * @param {Number} t
 * @return {Promise}
 */
export function sleep(t) {
    return new Promise(resolve => {
        setTimeout(() => { resolve(); }, t);
    });
}

/**
 * Increment value
 * @param  {Number} val
 * @return {Number}
 */
export function inc(val) {
    return val + 1;
}

/**
 * Decrement value
 * @param  {Number} val
 * @return {Number}
 */
export function dec(val) {
    return val - 1;
}

/**
 * Logical not
 * @param  {Any} val
 * @return {Boolean}
 */
export function not(val) {
    return !val;
}

/**
 * Delay function call `fn(...args)` for `t` milliseconds
 * @param {Function} fn
 * @param {Number} [t=0]
 * @param {...Any} args
 * @return {Promise}
 */
export function delay(fn, t, ...args) {
    return new Promise(resolve => {
        setTimeout(() => { resolve(fn(...args)); }, t || 0);
    });
}
