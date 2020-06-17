/** @module "@hat-core"/util
 *
 * Utility library for manipulation of JSON data.
 *
 * Main characteristics:
 *   - input/output data types are limited to JSON data, functions and
 *     `undefined` (sparse arrays and complex objects with prototype chain are
 *     not supported)
 *   - functional API with curried functions (similar to ramdajs)
 *   - implementation based on natively supported browser JS API
 *   - scope limited to most used functions in hat projects
 *   - usage of `paths` instead of `lenses`

 * TODO: define convetion for naming arguments based on their type and
 *       semantics
 */

/**
 * Path can be an object property name, array index, or array of Paths
 *
 * TODO: explain paths and path compositions (include examples)
 *
 * @typedef {String|Number|Path[]} module:"@hat-core"/util.Path
 */

/**
 * Identity function returning same value provided as argument.
 *
 * @function
 * @sig a -> a
 * @param {*} x input value
 * @return {*} same value as input
 */
export const identity = x => x;

/**
 * Check if value is `null` or `undefined`.
 *
 * For same argument, if this function returns `true`, functions `isBoolean`,
 * `isInteger`, `isNumber`, `isString`, `isArray` and `isObject` will return
 * `false`.
 *
 * @function
 * @sig * -> Boolean
 * @param {*} x input value
 * @return {Boolean}
 */
export const isNil = x => x == null;

/**
 * Check if value is Boolean.
 *
 * For same argument, if this function returns `true`, functions `isNil`,
 * `isInteger`, `isNumber`, `isString`, `isArray` and `isObject` will return
 * `false`.
 *
 * @function
 * @sig * -> Boolean
 * @param {*} x input value
 * @return {Boolean}
 */
export const isBoolean = x => typeof(x) == 'boolean';

/**
 * Check if value is Integer.
 *
 * For same argument, if this function returns `true`, function `isNumber` will
 * also return `true`.
 *
 * For same argument, if this function returns `true`, functions `isNil`,
 * `isBoolean`, `isString`, `isArray` and `isObject` will return `false`.
 *
 * @function
 * @sig * -> Boolean
 * @param {*} x input value
 * @type {Boolean}
 */
export const isInteger = Number.isInteger;

/**
 * Check if value is Number.
 *
 * For same argument, if this function returns `true`, function `isInteger` may
 * also return `true` if argument is integer number.
 *
 * For same argument, if this function returns `true`, functions `isNil`,
 * `isBoolean`, `isString`, `isArray` and `isObject` will return `false`.
 *
 * @function
 * @sig * -> Boolean
 * @param {*} x input value
 * @return {Boolean}
 */
export const isNumber = x => typeof(x) == 'number';

/**
 * Check if value is String.
 *
 * For same argument, if this function returns `true`, functions `isNil`,
 * `isBoolean`, `isInteger`, `isNumber`, `isArray`, and `isObject` will return
 * `false`.
 *
 * @function
 * @sig * -> Boolean
 * @param {Any} x input value
 * @type {Boolean}
 */
export const isString = x => typeof(x) == 'string';

/**
 * Check if value is Array.
 *
 * For same argument, if this function returns `true`, functions `isNil`,
 * `isBoolean`, `isInteger`, `isNumber`, `isString`, and `isObject` will return
 * `false`.
 *
 * @function
 * @sig * -> Boolean
 * @param {*} x input value
 * @return {Boolean}
 */
export const isArray = Array.isArray;

/**
 * Check if value is Object.
 *
 * For same argument, if this function returns `true`, functions `isNil`,
 * `isBoolean`, `isInteger`, `isNumber`, `isString`, and `isArray` will return
 * `false`.
 *
 * @function
 * @sig * -> Boolean
 * @param {*} x input value
 * @return {Boolean}
 */
export const isObject = x => typeof(x) == 'object' &&
                             !isArray(x) &&
                             !isNil(x);

/**
 * Strictly parse integer from string
 *
 * If provided string doesn't represent integer value, `NaN` is returned.
 *
 * @function
 * @sig String -> Number
 * @param {String} value
 * @return {Number}
 */
export function strictParseInt(value) {
    if (/^(-|\+)?([0-9]+)$/.test(value))
        return Number(value);
    return NaN;
}

/**
 * Strictly parse floating point number from string
 *
 * If provided string doesn't represent valid number, `NaN` is returned.
 *
 * @function
 * @sig String -> Number
 * @param {String} value
 * @return {Number}
 */
export function strictParseFloat(value) {
    if (/^(-|\+)?([0-9]+(\.[0-9]+)?)$/.test(value))
        return Number(value);
    return NaN;
}

/**
 * Create new deep copy of input value.
 *
 * In case of Objects or Arrays, new instances are created with elements
 * obtained by recursivly calling `clone` in input argument values.
 *
 * @function
 * @sig * -> *
 * @param {*} x value
 * @return {*} copy of value
 */
export function clone(x) {
    if (isArray(x))
        return Array.from(x, clone);
    if (isObject(x)) {
        let ret = {};
        for (let i in x)
            ret[i] = clone(x[i]);
        return ret;
    }
    return x;
}

/**
 * Combine two arrays in single array of pairs
 *
 * The returned array is truncated to the length of the shorter of the two
 * input arrays.
 *
 * @function
 * @sig [a] -> [b] -> [[a,b]]
 * @param {Array} arr1
 * @param {Array} arr2
 * @return {Array}
 */
export function zip(arr1, arr2) {
    return Array.from((function*() {
        for (let i = 0; i < arr1.length || i < arr2.length; ++i)
            yield [arr1[i], arr2[i]];
    })());
}

/**
 * Convert object to array of key, value pairs
 *
 * @function
 * @sig Object -> [[String,*]]
 * @param {Object} obj
 * @return {Array}
 */
export function toPairs(obj) {
    return Object.entries(obj);
}

/**
 * Convert array of key, value pairs to object
 *
 * @function
 * @sig [[String,*]] -> Object
 * @param {Array} arr
 * @return {Object}
 */
export function fromPairs(arr) {
    let ret = {};
    for (let [k, v] of arr)
        ret[k] = v;
    return ret;
}

/**
 * Flatten nested arrays.
 *
 * Create array with same elements as in input array where all elements which
 * are also arrays are replaced with elements of resulting recursive
 * application of flatten function.
 *
 * @function
 * @sig [a] -> [b]
 * @param {Array} arr
 * @return {Array}
 */
export function flatten(arr) {
    return Array.from((function* flatten(x) {
        if (isArray(x)) {
            for (let i of x)
                yield* flatten(i);
        } else {
            yield x;
        }
    })(arr));
}

/**
 * Pipe function calls
 *
 * Pipe provides functional composition with reversed order. First function
 * may have any arity and all other functions are called with only single
 * argument (result from previous function application).
 *
 * In case when no function is provided, pipe returns identity function.
 *
 * @function
 * @sig (((a1, a2, ..., an) -> b1), (b1 -> b2), ..., (bm1 -> bm)) -> ((a1, a2, ..., an) -> bm)
 * @param {...Function} fns functions
 * @return {Function}
 */
export function pipe(...fns) {
    if (fns.length < 1)
        return identity;
    return function (...args) {
        let ret = fns[0].apply(this, args);
        for (let fn of fns.slice(1))
            ret = fn(ret);
        return ret;
    };
}

/**
 * Apply list of functions to same arguments and return list of results
 *
 * @function
 * @sig ((a1 -> ... -> an -> b1), ..., (a1 -> ... -> an -> bm)) -> (a1 -> ... -> an -> [b1,...,bm])
 * @param {...Function} fns functions
 * @return {Function}
 */
export function flap(...fns) {
    return (...args) => fns.map(fn => fn.apply(this, args));
}

/**
 * Curry function with fixed arguments lenth
 *
 * Function arity is determined based on function's length property.
 *
 * @function
 * @sig (* -> a) -> (* -> a)
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
 *
 * @function
 * @sig a -> b -> Boolean
 * @param {*} x
 * @param {*} y
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
 * Create array by repeating same value
 * (curried function)
 *
 * @function
 * @sig a -> Number -> [a]
 * @param {*} x
 * @param {Number} n
 * @return {Array}
 */
export const repeat = curry((x, n) => Array.from({length: n}, _ => x));

/**
 * Get value referenced by path
 * (curried function)
 *
 * If input value doesn't contain provided path value, `undefined` is returned.
 *
 * @function
 * @sig Path -> a -> b
 * @param {Path} path
 * @param {*} x
 * @return {*}
 */
export const get = curry((path, x) => {
    let ret = x;
    for (let i of flatten(path)) {
        if (ret === null || typeof(ret) != 'object')
            return undefined;
        ret = ret[i];
    }
    return ret;
});

/**
 * Change value referenced with path by appling function
 * (curried function)
 *
 * @function
 * @sig Path -> (a -> b) -> c -> c
 * @param {Path} path
 * @param {Function} fn
 * @param {*} x
 * @return {*}
 */
export const change = curry((path, fn, x) => {
    return (function change(path, x) {
        if (path.length < 1)
            return fn(x);
        const [first, ...rest] = path;
        if (isInteger(first)) {
            x = (isArray(x) ? Array.from(x) : repeat(undefined, first));
        } else if (isString(first)) {
            x = (isObject(x) ? Object.assign({}, x) : {});
        } else {
            throw 'invalid path';
        }
        x[first] = change(rest, x[first]);
        return x;
    })(flatten(path), x);
});

/**
 * Replace value referenced with path with another value
 * (curried function)
 *
 * @function
 * @sig Path -> (a -> b) -> c -> c
 * @param {Path} path
 * @param {*} val
 * @param {*} x
 * @return {*}
 */
export const set = curry((path, val, x) => change(path, _ => val, x));

/**
 * Omitting value referenced by path
 * (curried function)
 *
 * @function
 * @sig Path -> a -> a
 * @param {Path} path
 * @param {*} x
 * @return {*}
 */
export const omit = curry((path, x) => {
    function _omit(path, x) {
        if (isInteger(path[0])) {
            x = (isArray(x) ? Array.from(x) : []);
        } else if (isString(path[0])) {
            x = (isObject(x) ? Object.assign({}, x) : {});
        } else {
            throw 'invalid path';
        }
        if (path.length > 1) {
            x[path[0]] = _omit(path.slice(1), x[path[0]]);
        } else if (isInteger(path[0])) {
            x.splice(path[0], 1);
        } else {
            delete x[path[0]];
        }
        return x;
    }
    path = flatten(path);
    if (path.length < 1)
        return undefined;
    return _omit(path, x);
});

/**
 * Change by moving value from source path to destination path
 * (curried function)
 *
 * @function
 * @sig Path -> Path -> a -> a
 * @param {Path} srcPath
 * @param {Path} dstPath
 * @param {*} x
 * @return {*}
 */
export const move = curry((srcPath, dstPath, x) => pipe(
    set(dstPath, get(srcPath, x)),
    omit(srcPath)
)(x));

/**
 * Sort array
 * (curried function)
 *
 * Comparison function receives two arguments representing array elements and
 * should return:
 *   - negative number in case first argument is more significant then second
 *   - zero in case first argument is equaly significant as second
 *   - positive number in case first argument is less significant then second
 *
 * @function
 * @sig ((a, a) -> Number) -> [a] -> [a]
 * @param {Function} fn
 * @param {Array} arr
 * @return {Array}
 */
export const sort = curry((fn, arr) => Array.from(arr).sort(fn));

/**
 * Sort array based on results of appling function to it's elements
 * (curried function)
 *
 * Resulting order is determined by comparring function application results
 * with greater then and lesser then operators.
 *
 * @function
 * @sig (a -> b) -> [a] -> [a]
 * @param {Function} fn
 * @param {Array} arr
 * @return {Array}
 */
export const sortBy = curry((fn, arr) => sort((x, y) => {
    const xVal = fn(x);
    const yVal = fn(y);
    if (xVal < yVal)
        return -1;
    if (xVal > yVal)
        return 1;
    return 0;
}, arr));

/**
 * Create object containing only subset of selected properties
 * (curried function)
 *
 * @function
 * @sig [String] -> a -> a
 * @param {Array} arr
 * @param {Object} obj
 * @return {Object}
 */
export const pick = curry((arr, obj) => {
    const ret = {};
    for (let i of arr)
        if (i in obj)
            ret[i] = obj[i];
    return ret;
});

/**
 * Change array or object by appling function to it's elements
 * (curried function)
 *
 * For each element, provided function is called with element value,
 * index/key and original container.
 *
 * @function
 * @sig ((a, Number, [a]) -> b) -> [a] -> [b]
 * @sig ((a, String, {String: a}) -> b) -> {String: a} -> {String: b}
 * @param {Function} fn
 * @param {Array|Object} x
 * @return {Array|Object}
 */
export const map = curry((fn, x) => {
    if (isArray(x))
        return x.map(fn);
    const res = {};
    for (let k in x)
        res[k] = fn(x[k], k, x);
    return res;
});

/**
 * Change array to contain only elements for which function returns `true`
 * (curried function)
 *
 * @function
 * @sig (a -> Boolean) -> [a] -> [a]
 * @param {Function} fn
 * @param {Array} arr
 * @return {Array}
 */
export const filter = curry((fn, arr) => arr.filter(fn));

/**
 * Append value to end of array
 * (curried function)
 *
 * @function
 * @sig a -> [a] -> [a]
 * @param {*} val
 * @param {Array} arr
 * @return {Array}
 */
export const append = curry((val, arr) => arr.concat([val]));

/**
 * Reduce array values by appling function
 * (curried function)
 *
 * For each array element, provided function is called with accumulator,
 * current value, current index and source array.
 *
 * TODO: support objects
 *
 * @function
 * @sig ((b, a, Number, [a]) -> b) -> b -> [a] -> b
 * @param {Function} fn
 * @param {*} val initial accumulator value
 * @param {Array} arr
 * @return {*} reduced value
 */
export const reduce = curry((fn, val, arr) => arr.reduce(fn, val));

/**
 * Merge two objects
 * (curried function)
 *
 * If same property exist in both arguments, second argument's value is used
 * as resulting value
 *
 * @function
 * @sig a -> a -> a
 * @param {Object} x
 * @param {Object} y
 * @return {Object}
 */
export const merge = curry((x, y) => Object.assign({}, x, y));

/**
 * Merge multiple objects
 * (curried function)
 *
 * If same property exist in multiple arguments, value from the last argument
 * containing that property is used
 *
 * @function
 * @sig [a] -> a
 * @param {Object[]}
 * @return {Object}
 */
export const mergeAll = reduce(merge, {});

/**
 * Find element in array or object for which provided function returns `true`
 * (curried function)
 *
 * Until element is found, provided function is called for each element with
 * arguments: current element, current index/key and initial container.
 *
 * If searched element is not found, `undefined` is returned.
 *
 * @function
 * @sig ((a, Number, [a]) -> Boolean) -> [a] -> a
 * @sig ((a, String, {String: a}) -> Boolean) -> {String: a} -> a
 * @param {Function} fn
 * @param {Array|Object} x
 * @return {*}
 */
export const find = curry((fn, x) => {
    if (isArray(x))
        return x.find(fn);
    for (let k in x)
        if (fn(x[k], k, x))
            return x[k];
});

/**
 * Find element's index/key in array or object for which provided function
 * returns `true`
 * (curried function)
 *
 * Until element is found, provided function is called for each element with
 * arguments: current element, current index/key and initial container.
 *
 * If searched element is not found, `undefined` is returned.
 *
 * @function
 * @sig ((a, Number, [a]) -> Boolean) -> [a] -> a
 * @sig ((a, String, {String: a}) -> Boolean) -> {String: a} -> a
 * @param {Function} fn
 * @param {Array|Object} x
 * @return {*}
 */
export const findIndex = curry((fn, x) => {
    if (isArray(x))
        return x.findIndex(fn);
    for (let k in x)
        if (fn(x[k], k, x))
            return k;
});

/**
 * Concatenate two arrays
 * (curried function)
 *
 * @function
 * @sig [a] -> [a] -> [a]
 * @param {Array} x
 * @param {Array} y
 * @return {Array}
 */
export const concat = curry((x, y) => x.concat(y));

/**
 * Create union of two arrays using `equals` to check equality
 * (curried function)
 *
 * @function
 * @sig [a] -> [a] -> [a]
 * @param {Array} x
 * @param {Array} y
 * @return {Array}
 */
export const union = curry((x, y) => {
    return reduce((acc, val) => {
        if (!find(equals(val), x))
            acc = append(val, acc);
        return acc;
    }, x, y);
});

/**
 * Check if array contains value
 * (curried function)
 *
 * TODO: add support for objects (should we check for keys or values?)
 *
 * @function
 * @sig a -> [a] -> Boolean
 * @param {*} val
 * @param {Array|Object} x
 * @return {Boolean}
 */
export const contains = curry((val, arr) => arr.includes(val));

/**
 * Insert value into array on specified index
 * (curried function)
 *
 * @function
 * @sig Number -> a -> [a] -> [a]
 * @param {Number} idx
 * @param {*} val
 * @param {Array} arr
 * @return {Array}
 */
export const insert = curry((idx, val, arr) =>
    arr.slice(0, idx).concat([val], arr.slice(idx)));

/**
 * Get array slice
 * (curried function)
 *
 * @function
 * @sig Number -> Number -> [a] -> [a]
 * @param {Number} begin
 * @param {Number} end
 * @param {Array} arr
 * @return {Array}
 */
export const slice = curry((begin, end, arr) => arr.slice(begin, end));

/**
 * Reverse array
 *
 * @function
 * @sig [a] -> [a]
 * @param  {Array} arr
 * @return {Array}
 */
export function reverse(arr) {
    return Array.from(arr).reverse();
}

/**
 * Array length
 *
 * @function
 * @sig [a] -> Number
 * @param  {Array} arr
 * @return {Number}
 */
export function length(arr) {
    return arr.length;
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
 * Create promise that resolves in `t` milliseconds
 *
 * TODO: move to other module
 *
 * @function
 * @sig Number -> Promise
 * @param {Number} t
 * @return {Promise}
 */
export function sleep(t) {
    return new Promise(resolve => {
        setTimeout(() => { resolve(); }, t);
    });
}

/**
 * Delay function call `fn(...args)` for `t` milliseconds
 *
 * TODO: move to other module
 *
 * @function
 * @sig (((a1, a2, ..., an) -> _), Number, a1, a2, ..., an) -> Promise
 * @param {Function} fn
 * @param {Number} [t=0]
 * @param {...} args
 * @return {Promise}
 */
export function delay(fn, t, ...args) {
    return new Promise(resolve => {
        setTimeout(() => { resolve(fn(...args)); }, t || 0);
    });
}
