import r from '@hat-core/renderer';

import * as common from '@hat-core/manager/event/common';


export function main(deviceId) {
    const textPath = ['pages', deviceId, 'register', 'text'];
    const withSourceTimestampPath = ['pages', deviceId, 'register', 'withSourceTimestamp'];

    const text = r.get(textPath) || '';
    const withSourceTimestamp = r.get(withSourceTimestampPath) || false;

    return ['div.subpage.register',
        ['label.source-timestamp',
            ['input', {
                props: {
                    type: 'checkbox',
                    checked: withSourceTimestamp
                },
                on: {
                    change: evt => r.set(withSourceTimestampPath, evt.target.checked)
                }
            }],
            ' source timestamp'
        ],
        ['textarea.text', {
            props: {
                value: text
            },
            on: {
                change: evt => r.set(textPath, evt.target.value)
            }
        }],
        ['button.register', {
            on: {
                click: _ => common.register(deviceId, text, withSourceTimestamp)
            }},
            'Register'
        ]
    ];
}
