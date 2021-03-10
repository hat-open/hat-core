/** @module @hat-core/future
 */


export function create() {
    const data = {
        done: false,
        error: false,
        result: undefined,
        resolve: null,
        reject: null
    };

    const future = new Promise((resolve, reject) => {
        data.resolve = resolve;
        data.reject = reject;
        if (data.error) {
            reject(data.result);
        } else if (data.done) {
            resolve(data.resolve);
        }
    });

    future.done = () => data.done;

    future.result = () => {
        if (!data.done)
            throw new Error('future is not done');
        if (data.error)
            throw data.error;
        return data.result;
    };

    future.setResult = result => {
        if (data.done)
            throw new Error('result already set');
        data.result = result;
        data.done = true;
        if (data.resolve)
            data.resolve(data.result);
    };

    future.setError = error => {
        if (data.done)
            throw new Error('result already set');
        data.error = true;
        data.result = error;
        data.done = true;
        if (data.reject)
            data.reject(error);
    };

    return future;
}
