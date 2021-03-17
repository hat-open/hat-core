import * as common from '@hat-core/manager-event/common';


export function main() {
    return ['div.page.register',
        ['label.source-timestamp',
            ['input', {
                props: {
                    type: 'checkbox',
                    checked: r.get('register', 'withSourceTimestamp')
                },
                on: {
                    change: evt => r.set(['register', 'withSourceTimestamp'], evt.target.checked)
                }
            }],
            ' source timestamp'
        ],
        ['textarea.text', {
            props: {
                value: r.get('register', 'text')
            },
            on: {
                change: evt => r.set(['register', 'text'], evt.target.value)
            }
        }],
        ['button.register', {
            on: {
                click: common.register
            }},
            'Register'
        ]
    ];
}
