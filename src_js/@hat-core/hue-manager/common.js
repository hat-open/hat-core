import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as juggler from '@hat-core/juggler';
import * as future from '@hat-core/future';


export const defaultState = {
    url: 'http://192.168.0.30',
    user: '1zyh2QDVxcc8g1Vu56HRM6ukhKUnGN05brFmlb-x',
    remember: false,
    connected: false,
    discovery: {
        enabled: true,
        available: [],
        duration: '5'
    },
    log: [],
    page: 'config',
    state: {}
};


let rpc = null;


export function init() {
    const app = new juggler.Application(r, null, null, null);
    const transactions = new Map();
    let last_transaction = 0;

    app.onMessage = msg => {
        const f = transactions.get(msg.transaction);
        transactions.delete(msg.transaction);
        if (msg.error) {
            f.setError(msg.error);
        } else {
            f.setResult(msg.result);
        }
    };

    rpc = new Proxy({}, {
        get: (_, action) => (...args) => {
            last_transaction += 1;
            app.send({
                transaction: last_transaction,
                action: action,
                args: args});
            const f = future.create();
            transactions.set(last_transaction, f);
            return f;
        }
    });

    window.rpc = rpc;
}


export async function discovery() {
    const duration = u.strictParseFloat(r.get('discovery', 'duration')) || 5;
    await r.change('discovery', u.pipe(
        u.set('enabled', false),
        u.set('available', [])
    ));
    await log('Starting bridge discovery...');
    try {
        const available = await rpc.find_hubs(duration);
        await r.set(['discovery', 'available'], available);
        await log(`Bridge discovery finished with ${available.length} results`);
    } catch (e) {
        await log(`Error during bridge discovery: ${e}`);
    }
    await r.set(['discovery', 'enabled'], true);
}


export async function createUser() {
    const url = r.get('url');
    if (!url) {
        await log('Create user error: invalid address');
        return;
    }
    await log('Create user not implemented');
}


export async function connect() {
    const url = r.get('url');
    const user = r.get('user');
    if (!url) {
        await log('Create user error: invalid address');
        return;
    }
    if (!user) {
        await log('Create user error: invalid username');
        return;
    }
    try {
        await rpc.connect(url, user);
        await log(`Communication with ${url} as ${user}`);
        await r.set('connected', true);
    } catch (e) {
        await log(`Connect error: ${e}`);
    }
    if (r.get('connected'))
        refresh();
}


export async function disconnect() {
    try {
        await rpc.disconnect();
        await log(`Disconnected`);
    } catch (e) {
        await log(`Disconnect error: ${e}`);
    }
    await r.change(u.pipe(
        u.set('connected', false),
        u.set('page', 'config')
    ));
}


export async function refresh() {
    let state = {};
    try {
        state = await rpc.get(null);
        await log(`Global state updated`);
    } catch (e) {
        await log(`Update state error: ${e}`);
    }
    await r.set('state', state);
}


export async function setConf(deviceId, conf) {
    try {
        await rpc.set_conf(deviceId, conf);
        await log(`Configuration changed`);
    } catch (e) {
        await log(`Configuration change error: ${e}`);
    }
    await refresh();
}



async function log(msg) {
    await r.change('log', u.append({
        timestamp: Date.now() / 1000,
        msg: msg}));
}
