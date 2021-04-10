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
    return await common.execute(deviceId, 'send_command', cmd);
}


export async function addData(deviceId) {
    return await common.execute(deviceId, 'add_data');
}


export function removeData(deviceId, dataId) {
    return common.execute(deviceId, 'remove_data', dataId);
}


export function changeData(deviceId, dataId, path, value) {
    return common.execute(deviceId, 'change_data', dataId, path, value);
}


export async function addCommand(deviceId) {
    return await common.execute(deviceId, 'add_command');
}


export function removeCommand(deviceId, commandId) {
    return common.execute(deviceId, 'remove_command', commandId);
}


export function changeCommand(deviceId, commandId, path, value) {
    return common.execute(deviceId, 'change_command', commandId, path, value);
}
