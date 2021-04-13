import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as iter from '@hat-core/iter';

import * as common from '@hat-core/manager/iec104/common';


const dataTypes = ['', 'Single', 'Double', 'StepPosition',
                   'Bitstring', 'Normalized', 'Scaled', 'Floating',
                   'BinaryCounter'];

const commandTypes = ['', 'Single', 'Double', 'Regulating', 'Normalized',
                      'Scaled', 'Floating'];


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
        slaveData(deviceId),
        slaveCommands(deviceId),
        slavePanel(deviceId)
    ];
}


function properties(deviceId) {
    const properties = r.get('remote', 'devices', deviceId, 'data', 'properties');

    const onChange = u.curry((property, value) => common.setProperty(deviceId, property, value));

    return ['div.properties',
        formEntryText('Host', properties.host, onChange('host')),
        formEntryNumber('Port', properties.port, onChange('port')),
        formEntryNumber('Response timeout', properties.response_timeout, onChange('response_timeout')),
        formEntryNumber('Supervisory timeout', properties.supervisory_timeout, onChange('supervisory_timeout')),
        formEntryNumber('Test timeout', properties.test_timeout, onChange('test_timeout')),
        formEntryNumber('Send window', properties.send_window_size, onChange('send_window_size')),
        formEntryNumber('Receive window', properties.receive_window_size, onChange('receive_window_size'))
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
                    change: evt => r.set(asduPath, evt.target.valueAsNumber)
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
                    change: evt => r.set(asduPath, evt.target.valueAsNumber)
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
        tableData(iter.map(i => [null, i], data))
    ];
}


function slaveData(deviceId) {
    const selectedPath = ['pages', deviceId, 'selected'];

    const data = r.get('remote', 'devices', deviceId, 'data', 'data') || {};
    const [selectedType, selectedId] = r.get(selectedPath) || [];

    const isSelected = id => selectedType == 'data' && selectedId == id;
    const onClick = id => r.set(selectedPath, ['data', id]);
    const onRemove = id => common.removeData(deviceId, id);

    return ['div.data',
        tableData(Object.entries(data), isSelected, onClick, onRemove),
        ['div.control',
            ['button', {
                on: {
                    click: _ => common.addData(deviceId)
                }},
                ['span.fa.fa-plus'],
                ' Add data'
            ]
        ]
    ];
}


function slaveCommands(deviceId) {
    const selectedPath = ['pages', deviceId, 'selected'];

    const commands = r.get('remote', 'devices', deviceId, 'data', 'commands') || {};
    const [selectedType, selectedId] = r.get(selectedPath) || [];

    const isSelected = id => selectedType == 'command' && selectedId == id;
    const onClick = id => r.set(selectedPath, ['command', id]);
    const onRemove = id => common.removeCommand(deviceId, id);

    return ['div.commands',
        tableCommands(Object.entries(commands), isSelected, onClick, onRemove),
        ['div.control',
            ['button', {
                on: {
                    click: _ => common.addCommand(deviceId)
                }},
                ['span.fa.fa-plus'],
                ' Add command'
            ]
        ]
    ];
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

    const onChange = u.curry((path, value) => common.changeData(deviceId, selectedDataId, path, value));

    return ['div.panel',
        formEntrySelect('Type', selectedData.type, dataTypes, onChange('type')),
        formEntryNumber('ASDU', selectedData.asdu, onChange('asdu')),
        formEntryNumber('IO', selectedData.io, onChange('io'))
    ];
}


function slavePanelCommand(deviceId, selectedCommandId) {
    const selectedCommand = r.get('remote', 'devices', deviceId, 'data', 'commands', selectedCommandId);
    if (!selectedCommand)
        return [];

    const onChange = u.curry((path, value) => common.changeCommand(deviceId, selectedCommandId, path, value));

    return ['div.panel',
        formEntrySelect('Type', selectedCommand.type, commandTypes, onChange('type')),
        formEntryNumber('ASDU', selectedCommand.asdu, onChange('asdu')),
        formEntryNumber('IO', selectedCommand.io, onChange('io')),
        formEntryCheckbox('Success', selectedCommand.success, onChange('success'))
    ];
}


function formEntryText(label, value, onChange) {
    return [
        ['label.label', label],
        ['input', {
            props: {
                type: 'text',
                value: value
            },
            on: {
                change: evt => onChange(evt.target.value)
            }
        }]
    ];
}


function formEntryNumber(label, value, onChange) {
    return [
        ['label.label', label],
        ['input', {
            props: {
                type: 'number',
                value: value
            },
            on: {
                change: evt => onChange(evt.target.valueAsNumber)
            }
        }]
    ];
}


function formEntryCheckbox(label, value, onChange) {
    return [
        ['span'],
        ['label',
            ['input', {
                props: {
                    type: 'checkbox',
                    checked: value
                },
                on: {
                    change: evt => onChange(evt.target.checked)
                }
            }],
            ` ${label}`
        ]
    ];
}


function formEntrySelect(label, selected, values, onChange) {
    return [
        ['label.label', label],
        ['select', {
            on: {
                change: evt => onChange(evt.target.value)
            }},
            values.map(i => ['option', {
                props: {
                    selected: i == selected
                }},
                i
            ])
        ]
    ];
}


function tableData(data, isSelected=null, onClick=null, onRemove=null) {
    return ['table',
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
                ['th.col-bool.hidden'],   // is_test
                (!onRemove ? [] : ['th.col-remove.hidden'])
            ],
            ['tr',
                ['th', {props: {rowSpan: 2}}, 'Type'],
                ['th', {props: {rowSpan: 2}}, 'ASDU'],
                ['th', {props: {rowSpan: 2}}, 'IO'],
                ['th', {props: {rowSpan: 2}}, 'Value'],
                ['th', {props: {colSpan: 5}}, 'Quality'],
                ['th', {props: {colSpan: 9}}, 'Time'],
                ['th', {props: {rowSpan: 2}}, 'Cause'],
                ['th', {props: {rowSpan: 2}}, 'Test'],
                (!onRemove ? [] : ['th', {props: {rowSpan: 2}}, 'Remove'])
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
        ['tbody', Array.from(data, ([id, i]) => {
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
            return ['tr', {
                class: {
                    selected: isSelected && isSelected(id)
                },
                on: {
                    click: _ => (onClick ? onClick(id) : null)
                }},
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
                ['td.col-bool', val('is_test')],
                (!onRemove ? [] : ['td.col-remove',
                    ['button', {
                        on: {
                            click: evt => {
                                evt.stopPropagation();
                                onRemove(id);
                            }
                        }},
                        ['span.fa.fa-times']
                    ]
                ])
            ];
        })]
    ];
}


function tableCommands(commands, isSelected, onClick, onRemove) {
    return ['table',
        ['thead',
            ['tr',
                ['th.col-str.hidden'],    // type
                ['th.col-int.hidden'],    // asdu
                ['th.col-int.hidden'],    // io
                ['th.hidden'],            // value
                ['th.col-bool.hidden'],   // success
                ['th.col-remove.hidden']
            ],
            ['tr',
                ['th', 'Type'],
                ['th', 'ASDU'],
                ['th', 'IO'],
                ['th', 'Value'],
                ['th', 'Res'],
                ['th', 'Remove']
            ]
        ],
        ['tbody', Array.from(commands, ([id, i]) => {
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
            return ['tr', {
                class: {
                    selected: isSelected(id)
                },
                on: {
                    click: _ => onClick(id)
                }},
                ['td.col-str', val('type')],
                ['td.col-int', val('asdu')],
                ['td.col-int', val('io')],
                ['td', val('value')],
                ['td.col-bool', val('success')],
                ['td.col-remove',
                    ['button', {
                        on: {
                            click: evt => {
                                evt.stopPropagation();
                                onRemove(id);
                            }
                        }},
                        ['span.fa.fa-times']
                    ]
                ]
            ];
        })]
    ];
}
