import r from '@hat-core/renderer';

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
    deviceId;
    return ['div.data'];
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
