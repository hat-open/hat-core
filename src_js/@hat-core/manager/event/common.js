import * as common from '@hat-core/manager/common';


export function setAddress(deviceId, address) {
    common.execute(deviceId, 'set_address', address);
}


export function register(deviceId, text, withSourceTimestamp) {
    common.execute(deviceId, 'register', text, withSourceTimestamp);
}
