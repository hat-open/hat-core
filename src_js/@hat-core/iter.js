import * as u from '@hat-core/util';


export function* enumerate(x) {
    let counter = 0;
    for (const i of x)
        yield [(counter++), i];
}


export function* chain(x) {
    for (const i of x)
        yield* i;
}


export function* count(start, step=1) {
    let i = start;
    for (;;) {
        yield i;
        i += step;
    }
}


export function* cycle(x) {
    const cache = [];
    for (const i of x) {
        cache.push(i);
        yield i;
    }
    if (!cache.length)
        return;
    for (;;) {
        yield* cache;
    }
}


export function* repeat(x) {
    for (;;)
        yield x;
}


export const map = u.curry(function* (fn, x) {
    for (const i of x)
        yield fn(i);
});


export const filter = u.curry(function* (fn, x) {
    for (const i of x)
        if (fn(i))
            yield i;
});


export const zip = u.curry(function* (x, y) {
    const is = x[Symbol.iterator]();
    const js = y[Symbol.iterator]();
    for (;;) {
        const i = is.next();
        const j = js.next();
        if (i.done || j.done)
            break;
        yield [i.value, j.value];
    }
});


export const slice = u.curry(function* (start, stop, x) {
    let counter = 0;
    for (const i of x) {
        if (counter >= stop)
            break;
        if (counter >= start)
            yield i;
        counter++;
    }
});
