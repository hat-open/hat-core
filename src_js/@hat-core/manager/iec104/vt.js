import r from '@hat-core/renderer';
import * as u from '@hat-core/util';

import * as common from '@hat-core/manager/iec104/common';


export function master() {
    const deviceId = r.get('deviceId');

    return ['div.page.iec104.master',
        properties(deviceId),
        masterControl(deviceId),
        masterData(deviceId)
    ];
}


export function slave() {
    const deviceId = r.get('deviceId');

    return ['div.page.iec104.slave',
        properties(deviceId),
        slaveControl(deviceId),
        slaveData(deviceId),
        slaveCommands(deviceId),
        slavePanel(deviceId)
    ];
}


function properties(deviceId) {
    const properties = r.get('remote', 'devices', deviceId, 'data', 'properties');

    return ['div.properties',
        [['host', 'Host', 'text'],
         ['port', 'Port', 'number'],
         ['response_timeout', 'Response timeout', 'number'],
         ['supervisory_timeout', 'Supervisory timeout', 'number'],
         ['test_timeout', 'Test timeout', 'number'],
         ['send_window_size', 'Send window', 'number'],
         ['receive_window_size', 'Receive window', 'number']
        ].map(([property, label, type]) => [
            ['label', label],
            ['input', {
                props: {
                    type: type,
                    value: properties[property]
                },
                on: {
                    change: evt => common.setProperty(deviceId, property, evt.target.value)
                }
            }]
        ])
    ];
}


function masterControl(deviceId) {
    const selectedTypePath = ['pages', deviceId, 'control', 'type'];

    const selectedType = r.get(selectedTypePath)  || 'interrogate';

    return ['div.control',
        ['div.header',
            [['interrogate', 'Interrogate'],
             ['counterInterrogate', 'Counter interrogate'],
             ['command', 'Command']
            ].map(([type, label]) => ['div', {
                class: {
                    selected: selectedType == type
                },
                on: {
                    click: _ => r.set(selectedTypePath, type)
                }},
                label
            ])
        ],
        {
            'interrogate': masterControlInterrogate,
            'counterInterrogate': masterControlCounterInterrogate,
            'command': masterControlCommand
        }[selectedType](deviceId)
    ];
}


function masterControlInterrogate(deviceId) {
    const dataPath = ['pages', deviceId, 'control', 'interrogate'];
    const asduPath = [dataPath, 'asdu'];

    const asdu = r.get(asduPath) || 0xFFFF;

    return ['div.content',
        ['div.form',
            ['label', 'ASDU'],
            ['input', {
                props: {
                    type: 'number',
                    value: asdu
                },
                on: {
                    change: evt => r.set(asduPath, evt.target.value)
                }
            }]
        ],
        ['button', {
            on: {
                click: _ => common.interrogate(deviceId, asdu)
            }},
            'Interrogate'
        ]
    ];
}


function masterControlCounterInterrogate(deviceId) {
    const dataPath = ['pages', deviceId, 'control', 'counterInterrogate'];
    const asduPath = [dataPath, 'asdu'];
    const freezePath = [dataPath, 'freeze'];

    const asdu = r.get(asduPath) || 0xFFFF;
    const freeze = r.get(freezePath) || 'READ';

    return ['div.content',
        ['div.form',
            ['label', 'ASDU'],
            ['input', {
                props: {
                    type: 'number',
                    value: asdu
                },
                on: {
                    change: evt => r.set(asduPath, evt.target.value)
                }
            }],
            ['label', 'Freeze'],
            ['select', {
                on: {
                    change: evt => r.set(freezePath, evt.target.value)
                }},
                ['READ', 'FREEZE', 'FREEZE_AND_RESET', 'RESET'].map(i => ['option', {
                    props: {
                        selected: i == freeze,
                    }},
                    i
                ])
            ]
        ],
        ['button', {
            on: {
                click: _ => common.counterInterrogate(deviceId, asdu, freeze)
            }},
            'Counter interrogate'
        ]
    ];
}


function masterControlCommand(deviceId) {
    const dataPath = ['pages', deviceId, 'control', 'command'];

    dataPath;

    return ['div.content',
        ['div.form'],
        ['button', {
            on: {
                click: null
            }},
            'Send command'
        ]
    ];
}


function masterData(deviceId) {
    const data = r.get('remote', 'devices', deviceId, 'data', 'data') || [];

    return ['div.data',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-str.hidden'],    // type
                    ['th.col-int.hidden'],    // asdu
                    ['th.col-int.hidden'],    // io
                    ['th.hidden'],            // value
                    ['th.col-bool.hidden'],   // quality-invalid
                    ['th.col-bool.hidden'],   // quality-not_topical
                    ['th.col-bool.hidden'],   // quality-substituted
                    ['th.col-bool.hidden'],   // quality-blocked
                    ['th.col-bool.hidden'],   // quality-overflow
                    ['th.col-int.hidden'],    // time-years
                    ['th.col-short.hidden'],  // time-months
                    ['th.col-short.hidden'],  // time-day_of_month
                    ['th.col-short.hidden'],  // time-day_of_week
                    ['th.col-short.hidden'],  // time-hours
                    ['th.col-short.hidden'],  // time-minutes
                    ['th.col-long.hidden'],   // time-milliseconds
                    ['th.col-bool.hidden'],   // time-invalid
                    ['th.col-bool.hidden'],   // time-summer_time
                    ['th.col-str.hidden'],    // cause
                    ['th.col-bool.hidden']    // is_test
                ],
                ['tr',
                    ['th', {props: {rowSpan: 2}}, 'Type'],
                    ['th', {props: {rowSpan: 2}}, 'ASDU'],
                    ['th', {props: {rowSpan: 2}}, 'IO'],
                    ['th', {props: {rowSpan: 2}}, 'Value'],
                    ['th', {props: {colSpan: 5}}, 'Quality'],
                    ['th', {props: {colSpan: 9}}, 'Time'],
                    ['th', {props: {rowSpan: 2}}, 'Cause'],
                    ['th', {props: {rowSpan: 2}}, 'Test']
                ],
                ['tr',
                    ['th', 'IN'],
                    ['th', 'NT'],
                    ['th', 'SU'],
                    ['th', 'BL'],
                    ['th', 'OV'],
                    ['th', 'Y'],
                    ['th', 'M'],
                    ['th', 'DoM'],
                    ['th', 'DoW'],
                    ['th', 'H'],
                    ['th', 'MIN'],
                    ['th', 'MS'],
                    ['th', 'IN'],
                    ['th', 'ST']
                ]
            ],
            ['tbody', data.map(i => {
                const val = (...path) => {
                    const x = u.get(path, i);
                    if (u.isNil(x))
                        return '';
                    if (u.isBoolean(x))
                        return ['span.fa.fa-' + (x ? 'check' : 'times')];
                    if (u.isObject(x))
                        return JSON.stringify(x);
                    return String(x);
                };
                return ['tr',
                    ['td.col-str', val('type')],
                    ['td.col-int', val('asdu')],
                    ['td.col-int', val('io')],
                    ['td', val('value')],
                    ['td.col-bool', val('quality', 'invalid')],
                    ['td.col-bool', val('quality', 'not_topical')],
                    ['td.col-bool', val('quality', 'substituted')],
                    ['td.col-bool', val('quality', 'blocked')],
                    ['td.col-bool', val('quality', 'overflow')],
                    ['td.col-int', val('time', 'years')],
                    ['td.col-short', val('time', 'months')],
                    ['td.col-short', val('time', 'day_of_month')],
                    ['td.col-short', val('time', 'day_of_week')],
                    ['td.col-short', val('time', 'hours')],
                    ['td.col-short', val('time', 'minutes')],
                    ['td.col-long', val('time', 'milliseconds')],
                    ['td.col-bool', val('time', 'invalid')],
                    ['td.col-bool', val('time', 'summer_time')],
                    ['td.col-str', val('cause')],
                    ['td.col-bool', val('is_test')]
                ];
            })]
        ]
    ];
}


function slaveControl(deviceId) {
    deviceId;
    return ['div.control'];
}


function slaveData(deviceId) {
    deviceId;
    return ['div.data'];
}


function slaveCommands(deviceId) {
    deviceId;
    return ['div.commands'];
}


function slavePanel(deviceId) {
    const [selectedType, selectedId] = r.get('pages', deviceId, 'selected') || [];

    if (selectedType == 'data')
        return slavePanelData(deviceId, selectedId);

    if (selectedType == 'command')
        return slavePanelCommand(deviceId, selectedId);

    return [];
}


function slavePanelData(deviceId, selectedDataId) {
    const selectedData = r.get('remote', 'devices', deviceId, 'data', 'data', selectedDataId);
    if (!selectedData)
        return [];

    return ['div.panel.data'];
}


function slavePanelCommand(deviceId, selectedCommandId) {
    const selectedCommand = r.get('remote', 'devices', deviceId, 'data', 'commands', selectedCommandId);
    if (!selectedCommand)
        return [];

    return ['div.panel.command'];
}
