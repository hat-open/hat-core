import r from '@hat/renderer';
import * as u from '@hat/util';
import * as texteditor from '@hat/common/texteditor';


export const defaultState = {
    saveFilePath: null,
    starting: '',
    delimiter: '',
    definitions: u.pipe(
        u.set('showGutter', true),
        u.set('showPrintMargin', true)
    )(texteditor.state),
    data: u.pipe(
        u.set('showGutter', true),
        u.set('showPrintMargin', true)
    )(texteditor.state)
};


export function actNew() {
    r.set(defaultState);
}


export function actOpen() {
    window.hatPegBrowserProxy.act_open(result => {
        if (result)
            r.set(result);
    });
}


export function actSave() {
    const state = r.get();
    window.hatPegBrowserProxy.act_save(state, result => {
        if (result)
            r.set('saveFilePath', result);
    });
}


export function actSaveAs() {
    const state = r.get();
    window.hatPegBrowserProxy.act_save_as(state, result => {
        if (result)
            r.set('saveFilePath', result);
    });
}


export function actParse() {
    const state = r.get();
    window.hatPegBrowserProxy.act_parse(state);
}
