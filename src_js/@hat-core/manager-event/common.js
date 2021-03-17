import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as juggler from '@hat-core/juggler';


let app = null;


export const defaultState = {
    remote: null,
    page: 'latest',
    latest: {
        expanded: []
    },
    register: {
        text: '',
        withSourceTimestamp: false
    }
};


export function init() {
    app = new juggler.Application(null, 'remote');
}


export function getLatestEventTree() {
    const createNode = (eventType, node) => ({
        'event': node['*'],
        'type': eventType,
        'children': u.pipe(
            u.toPairs,
            u.filter(([k, _]) => k != '*'),
            u.sortBy(u.get(0)),
            u.map(([k, v]) => createNode(u.append(k, eventType), v))
        )(node)
    });
    return createNode(
        [], u.reduce((acc, val) => u.set([val.event_type, '*'], val, acc),
                     {},
                     r.get('remote', 'latest') || []));
}


export function register() {
    const text = r.get('register', 'text');
    const withSourceTimestamp = r.get('register', 'withSourceTimestamp');
    app.rpc.register(text, withSourceTimestamp);
}
