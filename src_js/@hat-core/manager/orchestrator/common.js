
import * as common from '@hat-core/manager/common';


export function setAddress(deviceId, address) {
    common.execute(deviceId, 'set_address', address);
}


export function start(deviceId, componentId) {
    common.execute(deviceId, 'start', componentId);
}


export function stop(deviceId, componentId) {
    common.execute(deviceId, 'stop', componentId);
}


export function setRevive(deviceId, componentId, revive) {
    common.execute(deviceId, 'set_revive', componentId, revive);
}
