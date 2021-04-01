import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as juggler from '@hat-core/juggler';


let app;


export const defaultState = {
    remote: null,
    local: null,
    deviceId: null,
    addDialog: {
        open: false,
        deviceType: null
    },
    settingsDialog: {
        open: false
    },
    pages: {}
};


export function init() {
    app = new juggler.Application('local', 'remote');
    window.app = app;
}


export function showSettingsDialog() {
    r.set('settingsDialog', u.set('open', true, defaultState.settingsDialog));
}


export function hideSettingsDialog() {
    r.set('settingsDialog', defaultState.settingsDialog);
}


export function setSettings(path, value) {
    app.rpc.set_settings(path, value);
}


export function save() {
    app.rpc.save();
}


export function showAddDialog() {
    r.set('addDialog', u.set('open', true, defaultState.addDialog));
}


export function hideAddDialog() {
    r.set('addDialog', defaultState.addDialog);
}


export async function add(deviceType) {
    const deviceId = await app.rpc.add(deviceType);
    select(deviceId);
}


export function select(deviceId) {
    r.set('deviceId', deviceId);
}


export async function remove(deviceId) {
    await app.rpc.remove(deviceId);
    r.change('pages', u.omit(deviceId));
}


export function start(deviceId) {
    app.rpc.start(deviceId);
}


export function stop(deviceId) {
    app.rpc.stop(deviceId);
}


export function setName(deviceId, name) {
    app.rpc.set_name(deviceId, name);
}


export function setAutoStart(deviceId, autoStart) {
    app.rpc.set_auto_start(deviceId, autoStart);
}


export async function execute(deviceId, action, ...args) {
    return await app.rpc.execute(deviceId, action, ...args);
}
