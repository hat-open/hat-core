/** @module "@hat-core"/node
 */

import * as u from '@hat-core/util';

/**
 * Check if value is node (an `Array` whose first item is `String`)
 * @param {Any} node input object
 * @return {Boolean}
 */
export function isNode(node) {
    return u.isArray(node) && node.length > 0 && u.isString(node[0]);
}

/**
 * Normalize node structure by flattening arrays which are not nodes
 * @param {Any} node
 * @return {Any} normalized nodes
 */
export function normalize(node) {
    if (!u.isArray(node) || node.length < 1)
        return node;
    const result = u.reduce(
        (acc, i) => isNode(i) ?
            u.append(i, acc) :
            u.concat(acc, i),
        [], u.map(normalize, node));
    return result.length == 1 && isNode(result[0]) ? result[0] : result;
}

/**
 * Prefix node ids with `idPrefix`
 * (curried function)
 * @function
 * @param {String} idPrefix
 * @param {Any} node
 * @return {Any} prefixed nodes
 */
export const prefixIds = u.curry((idPrefix, node) => {
    if (!u.isArray(node) || node.length < 1)
        return node;
    const hasTag = u.isString(node[0]);
    const children = u.map(prefixIds(idPrefix),
                           node.slice(hasTag ? 1 : 0));
    if (!hasTag)
        return children;
    const tag = node[0].replace(/#([^.]+)/,
                                id => '#' + idPrefix + id.substr(1));
    return u.concat([tag], children);
});

/**
 * Find node paths of nodes which satisfy `selector`
 * (curried function)
 * @function
 * @param {String} selector
 * @param {Any} node
 * @return {Array<Path>} node paths
 */
export const findPaths = u.curry((selector, node) => {
    selector = selector.trim();
    selector = selector.replace(/ *, */g, ',');
    selector = selector.replace(/ *> */g, '>');
    selector = selector.replace(/  +/g, ' ');

    let paths = [];
    const complexSelectors = selector.split(',');

    const findComplex = (selectors, combinators, node, onlyChildren, first) => {
        const selector = selectors[0];
        const combinator = combinators ? combinators[0] : null;

        const findTags = selector.match(/^[^.#:]+/g);
        const findIds = selector.match(/#[^.#:]+/g);
        const findClasses = selector.match(/\.[^.#:]+/g);
        const findPseudoClasses = selector.match(/:[^.#:]+/g);

        const isMatch = node => {
            const tags = node[0].match(/^[^.#:]+/g);
            const ids = node[0].match(/#[^.#:]+/g) || [];
            const classes = node[0].match(/\.[^.#:]+/g) || [];
            return (tags && (!findTags || findTags[0] == '*' || tags[0] == findTags[0])) &&
                (!findIds || findIds.every(i => u.contains(i, ids))) &&
                (!findClasses || findClasses.every(i => u.contains(i, classes)));
        };

        const findChildren = node => {
            const childrenPaths = [];
            const hasTag = u.isString(node[0]);
            const children = node.slice(hasTag ? 1 : 0);
            const find = node => {
                if (!u.isArray(node) || node.length < 1)
                    return [];
                let paths = [];
                const hasTag = u.isString(node[0]);
                if (hasTag) {
                    paths.push([]);
                } else {
                    const children = node;
                    for (let i in children) {
                        find(children[i]).forEach(path =>
                            paths.push(u.concat([parseInt(i)], path)));
                    }
                }
                return paths;
            };
            for (let i in children) {
                find(children[i]).forEach(path =>
                    childrenPaths.push(u.concat([parseInt(i) + (hasTag ? 1 : 0)], path)));
            }
            return childrenPaths;
        };

        const getMatchPaths = (allPaths, node) => {
            const matchPaths = u.filter(i => isMatch(u.get(i, node)), allPaths);
            return u.reduce((acc, pseudo) => {
                let pseudoPath = undefined;
                if (pseudo == ':first-child') {
                    if (allPaths.length > 0) pseudoPath = allPaths[0];
                } else if (pseudo == ':last-child') {
                    if (allPaths.length > 0) pseudoPath = allPaths[allPaths.length-1];
                } else if (pseudo.startsWith(':nth-child')) {
                    const index = parseInt(pseudo.slice(11, pseudo.length-1)) - 1;
                    if (allPaths.length > index) pseudoPath = allPaths[index];
                } else if (pseudo.startsWith(':nth-last-child')) {
                    const index = allPaths.length - parseInt(pseudo.slice(16, pseudo.length-1));
                    if (allPaths.length > index) pseudoPath = allPaths[index];
                } else if (pseudo == ':only-child') {
                    if (allPaths.length == 1) pseudoPath = allPaths[0];
                } else if (pseudo == ':first-of-type') {
                    if (matchPaths.length > 0) pseudoPath = matchPaths[0];
                } else if (pseudo == ':last-of-type') {
                    if (matchPaths.length > 0) pseudoPath = matchPaths[matchPaths.length-1];
                } else if (pseudo.startsWith(':nth-of-type')) {
                    const index = parseInt(pseudo.slice(13, pseudo.length-1)) - 1;
                    if (matchPaths.length > index) pseudoPath = matchPaths[index];
                } else if (pseudo.startsWith(':nth-last-of-type')) {
                    const index = matchPaths.length - parseInt(pseudo.slice(18, pseudo.length-1));
                    if (matchPaths.length > index) pseudoPath = matchPaths[index];
                } else if (pseudo == ':only-of-type') {
                    if (matchPaths.length == 1) pseudoPath = matchPaths[0];
                } else {
                    return acc;
                }
                return pseudoPath == undefined ? [] : u.filter(path => u.equals(path, pseudoPath), acc);
            }, matchPaths, findPseudoClasses || []);
        };

        const findCompound = node => {
            const allChildrenPaths = findChildren(node);
            let paths = getMatchPaths(allChildrenPaths, node);
            if (!onlyChildren) {
                allChildrenPaths.forEach(childPath => {
                    const descendantPaths = u.map(u.concat(childPath), findCompound(u.get(childPath, node)));
                    paths = u.union(paths, descendantPaths);
                });
            }
            return paths;
        };

        let queryPaths = findCompound(node);
        const hasTag = u.isString(node[0]);
        if (first && hasTag) {
            queryPaths = u.concat(queryPaths, getMatchPaths([[]], node));
        }
        if (!combinator) {
            return queryPaths;
        }
        let paths = [];
        queryPaths.forEach(queryPath => {
            const resultPaths = u.map(u.concat(queryPath), findComplex(
                selectors.slice(1), combinators.slice(1), u.get(queryPath, node), combinator == '>'));
            paths = u.union(paths, resultPaths);
        });
        return paths;
    };

    complexSelectors.forEach(selector => {
        const compoundSelectors = selector.split(/ |>/);
        const combinators = selector.match(/ |>/g);
        const resultPaths = findComplex(compoundSelectors, combinators, node, false, true);
        paths = u.union(paths, resultPaths);
    });
    return paths;
});

/**
 * Strip node ids
 * @param {Any} node
 * @return {Any} stripped nodes
 */
export function stripIds(node) {
    if (!u.isArray(node) || node.length < 1)
        return node;
    const hasTag = u.isString(node[0]);
    const children = u.map(stripIds, node.slice(hasTag ? 1 : 0));
    if (!hasTag)
        return children;
    const tag = node[0].replace(/#([^.]+)/, '');
    return u.concat([tag], children);
}

/**
 * Change nodes by appling function `fn` to nodes that satisfy `selector`
 * (curried function)
 * @function
 * @param {String} selector
 * @param {Function} fn
 * @param {Any} node
 * @return {Any} changed nodes
 */
export const change = u.curry((selector, fn, node) => {
    return u.pipe(
        findPaths(selector),
        u.sortBy(u.pipe(
            u.flatten,
            Array.from,
            u.length
        )),
        u.reverse,
        u.reduce((node, path) => u.change(path, fn, node), node)
    )(node);
});

/**
 * Get data from `node` referenced by `path`
 * (curried function)
 * @function
 * @param {Path} path
 * @param {Node} node
 * @return {Any} data
 */
export const getData = u.curry((path, node) => {
    if (!isNode(node))
        throw 'invalid node';
    if (node.length < 2 || !u.isObject(node[1]))
        return null;
    return u.get(path, node[1]);
});

/**
 * Change `node` by appling function `fn` to data referenced by `path`
 * (curried function)
 * @function
 * @param {Path} path
 * @param {Function} fn
 * @param {Node} node
 * @return {Node} changed `node`
 */
export const changeData = u.curry((path, fn, node) => {
    if (!isNode(node))
        throw 'invalid node';
    if (node.length < 2 || !u.isObject(node[1]))
        return u.insert(1, u.change(path, fn, null), node);
    return u.change(1, u.change(path, fn), node);
});

/**
 * Change `node` by setting data referenced `path` to `val`
 * (curried function)
 * @function
 * @param {Path} path
 * @param {Any} val
 * @param {Node} node
 * @return {Node} changed `node`
 */
export const setData = u.curry((path, val, node) => changeData(path, _ => val, node));

/**
 * Get `node` children
 * @param {Node} node
 * @return {Array} children
 */
export function getChildren(node) {
    if (!isNode(node))
        throw 'invalid node';
    const childrenIndex = getData([], node) ? 2 : 1;
    return node.slice(childrenIndex);
}

/**
 * Change `node` by appling function `fn` to children
 * (curried function)
 * @function
 * @param {Function} fn
 * @param {Node} node
 * @return {Node} changed `node`
 */
export const changeChildren = u.curry((fn, node) => {
    if (!isNode(node))
        throw 'invalid node';
    const childrenIndex = getData([], node) ? 2 : 1;
    return u.concat(node.slice(0, childrenIndex),
                    fn(node.slice(childrenIndex)));
});

/**
 * Change `node` by setting children to `val`
 * (curried function)
 * @function
 * @param {Any} val
 * @param {Node} node
 * @return {Node} changed `node`
 */
export const setChildren = u.curry((val, node) => changeChildren(_ => val, node));

/**
 * Encode style
 * @param {Object} style
 * @return {String}
 */
export function encodeStyle(style) {
    return u.toPairs(style || {}).map(([k, v]) => k + ": " + v).join('; ');
}

/**
 * Decode style
 * @param {String} styleStr
 * @return {Object}
 */
export function decodeStyle(styleStr) {
    return u.fromPairs((styleStr || '').split(';').map(i => i.split(':').map(x => x.trim())));
}
