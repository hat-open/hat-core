import r from '@hat-core/renderer';
import * as u from '@hat-core/util';

import * as vt from '@hat-core/manager-iec104/vt';

import 'manager-iec104/main.scss';


function main() {
    const root = document.body.appendChild(document.createElement('div'));
    r.init(root, common.defaultState, vt.main);
    common.init();
}


window.addEventListener('load', main);
window.r = r;
window.u = u;
