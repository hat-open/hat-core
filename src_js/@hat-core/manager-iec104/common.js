import * as juggler from '@hat-core/juggler';


let app;


export function init() {
    app = new juggler.Application('local', 'remote');
}


export function createMaster() {
    app.rpc.create_master();
}


export function createSlave() {
    app.rpc.create_slave();
}


export function removeDevice(deviceId) {
    app.rpc.remove_device(deviceId);
}


export function setProperty(deviceId, key, value) {
    app.rpc.set_property(deviceId, key, value);
}


export function start(deviceId) {
    app.rpc.start(deviceId);
}


export function stop(deviceId) {
    app.rpc.stop(deviceId);
}


export function interrogate(deviceId, asdu) {
    app.rpc.interrogate(deviceId, asdu);
}


export function sendCommand(deviceId, cmd) {
    app.rpc.send_command(deviceId, cmd);
}


export function addData(deviceId) {
    app.rpc.add_data(deviceId);
}


export function removeData(deviceId, dataId) {
    app.rpc.remove_data(deviceId, dataId);
}


export function setDataProperty(deviceId, dataId, key, value) {
    app.rpc.set_data_property(deviceId, dataId, key, value);
}


export function addCommand(deviceId) {
    app.rpc.add_command(deviceId);
}


export function removeCommand(deviceId, commandId) {
    app.rpc.remove_command(deviceId, commandId);
}


export function setCommandProperty(deviceId, commandId, key, value) {
    app.rpc.set_command_property(deviceId, commandId, key, value);
}
