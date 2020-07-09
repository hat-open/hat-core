import * as form from '@hat/common/form';
import * as texteditor from '@hat/common/texteditor';

import * as common from '@hat/peg_browser/main/common';


export function main() {
    return ['div#main',
        toolbar(),
        grammar(),
        data()
    ];
}


function toolbar() {
    const buttons = [['New', '.fa-file-o', common.actNew],
                     ['Open', '.fa-folder-open-o', common.actOpen],
                     ['Save', '.fa-floppy-o', common.actSave],
                     ['Save as', '.fa-floppy-o', common.actSaveAs],
                     ['Parse', '.fa-play', common.actParse]];
    return ['div.toolbar',
        buttons.map(([label, icon, action]) => ['button', {
            on: {
                click: action
            }},
            [`span.fa${icon}`],
            ` ${label}`
        ])
    ];
}


function grammar() {
    return ['div.grammar',
        ['div.title', 'Grammar'],
        ['div.form',
            form.textInput('starting', 'Starting'),
            form.textInput('delimiter', 'Delimiter')
        ],
        texteditor.textEditor('definitions'),
    ];
}


function data() {
    return ['div.data',
        ['div.title', 'Data'],
        texteditor.textEditor('data')
    ];
}
