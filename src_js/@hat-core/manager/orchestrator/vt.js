import r from '@hat-core/renderer';
import * as u from '@hat-core/util';

import * as common from '@hat-core/manager/orchestrator/common';


export function main() {
    const deviceId = r.get('deviceId');

    return ['div.page.orchestrator',
        header(deviceId),
        components(deviceId)
    ];
}


function header(deviceId) {
    const address = r.get('remote', 'devices', deviceId, 'data', 'address');

    return ['div.header',
        ['label', 'Address'],
        ['input', {
            props: {
                value: address
            },
            on: {
                change: evt => common.setAddress(deviceId, evt.target.value)
            }
        }]
    ];
}


function components(deviceId) {
    const components = r.get('remote', 'devices', deviceId, 'data', 'components');

    return ['div.components',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-component', 'Component'],
                    ['th.col-delay', 'Delay'],
                    ['th.col-revive', 'Revive'],
                    ['th.col-status', 'Status'],
                    ['th.col-action', 'Action']
                ]
            ],
            ['tbody', components.map(component =>
                ['tr',
                    ['td.col-component', component.name],
                    ['td.col-delay', String(component.delay)],
                    ['td.col-revive',
                        ['input', {
                            props: {
                                type: 'checkbox',
                                checked: component.revive
                            },
                            on: {
                                change: evt => common.setRevive(deviceId, component.id, evt.target.checked)
                            }
                        }]
                    ],
                    ['td.col-status', component.status],
                    ['td.col-action',
                        ['button', {
                            props: {
                                title: 'Stop',
                                disabled: u.contains(
                                    component.status, ['STOPPING', 'STOPPED'])
                            },
                            on: {
                                click: _ => common.stop(deviceId, component.id)
                            }},
                            ['span.fa.fa-times']
                        ],
                        ['button', {
                            props: {
                                title: 'Start',
                                disabled: u.contains(
                                    component.status,
                                    ['STARTING', 'RUNNING', 'STOPPING'])
                            },
                            on: {
                                click: _ => common.start(deviceId, component.id)
                            }},
                            ['span.fa.fa-play']
                        ]
                    ]
                ]
            )]
        ]
    ];
}
