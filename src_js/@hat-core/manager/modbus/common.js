import r from '@hat-core/renderer';

import * as common from '@hat-core/manager/common';


export function setProperty(deviceId, path, value) {
    common.execute(deviceId, 'set_property', path, value);
}


export function read(deviceId, modbusDeviceId, dataType, startAddress, quantity) {
    common.execute(deviceId, 'read', modbusDeviceId, dataType, startAddress, quantity);
}


export function write(deviceId, modbusDeviceId, dataType, startAddress, values) {
    common.execute(deviceId, 'write', modbusDeviceId, dataType, startAddress, values);
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
