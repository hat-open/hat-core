import ace from 'brace';

import r from '@hat-core/renderer';
import * as u from '@hat-core/util';

require('brace/mode/javascript');
require('brace/mode/python');
require('brace/mode/json');
require('brace/mode/yaml');
require('brace/mode/text');
require('brace/theme/monokai');
require('brace/ext/language_tools');
require('brace/ext/searchbox');


export const state = {
    value: '',
    position: null,
    mode: 'text',
    showPrintMargin: false,
    showGutter: false
};


export function textEditor(path) {
    return ['div.texteditor', {
        textEditor: {
            path: path,
            editor: null
        },
        hook: {
            create: (emptyVnode, vnode) => {
                const editor = ace.edit(vnode.elm);
                vnode.elm.aceEditor = editor;
                editor.$blockScrolling = Infinity;
                vnode.data.textEditor.editor = editor;
                u.delay(() => update(vnode));
            },
            update: (oldVnode, vnode) => {
                vnode.data.textEditor.editor = oldVnode.data.textEditor.editor;
                update(vnode);
            },
            destroy: vnode => {
                const editor = vnode.data.textEditor.editor;
                editor.removeAllListeners('change');
                editor.removeAllListeners('blur');
                editor.destroy();
                vnode.data.textEditor.editor = null;
            }
        }
    }];
}


function update(vnode) {
    const editor = vnode.data.textEditor.editor;
    const path = vnode.data.textEditor.path;
    const value = r.get(path, 'value');
    const position = r.get(path, 'position');
    const mode = r.get(path, 'mode');
    const showPrintMargin = r.get(path, 'showPrintMargin');
    const showGutter = r.get(path, 'showGutter');
    const onChange = () => {
        u.delay(() => {
            const value = editor.getValue();
            const position = u.clone(editor.getCursorPosition());
            r.change(path, u.pipe(
                u.set('value', value),
                u.set('position', position)
            ));
        });
    };
    editor.removeAllListeners('change');
    editor.removeAllListeners('blur');
    if (value != editor.getValue())
        editor.setValue(value, -1);
    if (position && !u.equals(position, editor.getCursorPosition()))
        editor.moveCursorToPosition(position);
    editor.setOptions({
        showPrintMargin: showPrintMargin,
        showGutter: showGutter
    });
    editor.getSession().setMode(`ace/mode/${mode}`);
    editor.on('change', onChange);
    editor.on('blur', onChange);
}
