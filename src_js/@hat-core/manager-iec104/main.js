import r from '@hat-core/renderer';
import * as u from '@hat-core/util';

import * as defaultState from '@hat-core/manager-iec104/state';
import * as common from '@hat-core/manager-iec104/common';
import * as vt from '@hat-core/manager-iec104/vt';

import 'manager-iec104/main.scss';


function main() {
    const root = document.body.appendChild(document.createElement('div'));
    r.init(root, defaultState.main, vt.main);
    common.init();
}


window.addEventListener('load', main);
window.r = r;
window.u = u;
