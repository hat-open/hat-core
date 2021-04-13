import r from '@hat-core/renderer';

import * as common from '@hat-core/manager/common';


export function setProperty(deviceId, path, value) {
    common.execute(deviceId, 'set_property', path, value);
}


export function interrogate(deviceId, asdu) {
    common.execute(deviceId, 'interrogate', asdu);
}


export function counterInterrogate(deviceId, asdu, freeze) {
    common.execute(deviceId, 'counter_interrogate', asdu, freeze);
}


export async function sendCommand(deviceId, cmd) {
    await common.execute(deviceId, 'send_command', cmd);
}


export async function addData(deviceId) {
    const dataId = await common.execute(deviceId, 'add_data');
    r.set(['pages', deviceId, 'selected'], ['data', dataId]);
}


export function removeData(deviceId, dataId) {
    common.execute(deviceId, 'remove_data', dataId);
}


export function changeData(deviceId, dataId, path, value) {
    common.execute(deviceId, 'change_data', dataId, path, value);
}


export async function addCommand(deviceId) {
    const commandId = await common.execute(deviceId, 'add_command');
    r.set(['pages', deviceId, 'selected'], ['command', commandId]);
}


export function removeCommand(deviceId, commandId) {
    common.execute(deviceId, 'remove_command', commandId);
}


export function changeCommand(deviceId, commandId, path, value) {
    common.execute(deviceId, 'change_command', commandId, path, value);
}
