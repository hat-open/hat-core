import r from '@hat/renderer';
import * as u from '@hat/util';
import * as qt from '@hat/qt';

import * as mainCommon from '@hat/peg_browser/main/common';
import * as mainVt from '@hat/peg_browser/main/vt';
import * as browserCommon from '@hat/peg_browser/browser/common';
import * as browserVt from '@hat/peg_browser/browser/vt';


import 'peg_browser/main.scss';


function main() {
    qt.init().then(({hatPegBrowserProxy}) => {
        window.hatPegBrowserProxy = hatPegBrowserProxy;
        const root = document.body.appendChild(document.createElement('div'));
        let state;
        let vt;
        if (hatPegBrowserProxy.type == 'browser') {
            state = browserCommon.createState(hatPegBrowserProxy.data);
            vt = browserVt.browser;
        } else {
            state = mainCommon.defaultState;
            vt = mainVt.main;
        }
        r.init(root, state, vt);
    });
}


window.addEventListener('load', main);
window.r = r;
window.u = u;
