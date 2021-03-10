import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as juggler from '@hat-core/juggler';

import * as vt from '@hat-core/syslog/vt';
import * as state from '@hat-core/syslog/state';


import 'syslog/main.scss';


async function main() {
    const root = document.body.appendChild(document.createElement('div'));
    r.init(root, state.main, vt.main);
    new juggler.Application(['local', 'filter'], 'remote');
}


window.addEventListener('load', main);
window.r = r;
window.u = u;
