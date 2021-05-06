import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as datetime from '@hat-core/syslog/datetime';

import * as common from '@hat-core/manager/modbus/common';


const linkTypes = ['TCP', 'SERIAL'];

const modbusTypes = ['TCP', 'RTU', 'ASCII'];

const dataTypes = ['COIL', 'DISCRETE_INPUT', 'HOLDING_REGISTER', 'INPUT_REGISTER', 'QUEUE'];


export function master() {
    const deviceId = r.get('deviceId');

    return ['div.page.modbus.master',
        properties(deviceId),
        masterAction(deviceId),
        masterData(deviceId)
    ];
}


export function slave() {
    const deviceId = r.get('deviceId');

    return ['div.page.modbus.slave',
        properties(deviceId),
        slaveData(deviceId),
        slavePanel(deviceId)
    ];
}


function properties(deviceId) {
    const properties = r.get('remote', 'devices', deviceId, 'data', 'properties');

    const onChange = u.curry((property, value) => common.setProperty(deviceId, property, value));

    return ['div.properties',
        formEntrySelect('Link type', properties.link_type, linkTypes, onChange('link_type')),
        formEntrySelect('Modbus type', properties.modbus_type, modbusTypes, onChange('modbus_type')),
        (properties.link_type != 'TCP' ? [] : [
            formEntryText('Host', properties.tcp_host, onChange('tcp_host')),
            formEntryNumber('Port', properties.tcp_port, onChange('tcp_port'))
        ]),
        (properties.link_type != 'SERIAL' ? [] : [
            formEntryText('Serial port', properties.serial_port, onChange('serial_port')),
            formEntryNumber('Silent interval', properties.serial_silent_interval, onChange('serial_silent_interval'))
        ])
    ];
}


function masterAction(deviceId) {
    const actionPath = ['pages', deviceId, 'action'];

    const action = r.get(actionPath) || {
        action: 'READ',
        modbusDeviceId: 1,
        dataType: 'COIL',
        startAddress: 0,
        quantity: 1,
        values: '1'
    };

    const onChange = u.curry((property, value) => r.set(actionPath, u.set(property, value, action)));

    return ['div.action',
        ['div.form',
            formEntrySelect('Action', action.action, ['READ', 'WRITE'], onChange('action')),
            formEntryNumber('Device ID', action.modbusDeviceId, onChange('modbusDeviceId')),
            formEntrySelect('Data type', action.dataType, dataTypes, onChange('dataType')),
            formEntryNumber('Start address', action.startAddress, onChange('startAddress')),
            (action.action != 'READ' ? [] : [
                formEntryNumber('Quantity', action.quantity, onChange('quantity'))
            ]),
            (action.action != 'WRITE' ? [] : [
                formEntryText('Value', action.values, onChange('values'))
            ]),
        ],
        ['button', {
            on: {
                click: _ => {
                    if (action.action == 'READ') {
                        common.read(deviceId, action.modbusDeviceId, action.dataType, action.startAddress, action.quantity);
                    } else if (action.action == 'WRITE') {
                        const values = action.values.split(',').map(i => u.strictParseInt(i.trim()));
                        if (values.includes(NaN))
                            return;
                        common.write(deviceId, action.modbusDeviceId, action.dataType, action.startAddress, values);
                    }
                }
            }},
            'Execute'
        ]
    ];
}


function masterData(deviceId) {
    const data = r.get('remote', 'devices', deviceId, 'data', 'data') || [];

    const val = x => u.isNil(x) ? '' : String(x);

    return ['div.data',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-timestamp', 'Time'],
                    ['th.col-str', 'Action'],
                    ['th.col-int', 'Device ID'],
                    ['th.col-str', 'Data type'],
                    ['th.col-int', 'Start address'],
                    ['th', 'Value']
                ]
            ],
            ['tbody', data.map(i =>
                ['tr',
                    ['td.col-timestamp',
                        datetime.utcTimestampToLocalString(i.timestamp)
                    ],
                    ['td.col-str', val(i.action)],
                    ['td.col-int', val(i.device_id)],
                    ['td.col-str', val(i.data_type)],
                    ['td.col-int', val(i.start_address)],
                    ['td.col-str', val(i.value)]
                ]
            )]
        ]
    ];
}


function slaveData(deviceId) {
    const selectedPath = ['pages', deviceId, 'selected'];

    const data = r.get('remote', 'devices', deviceId, 'data', 'data') || {};
    const selected = r.get(selectedPath);

    const val = x => u.isNil(x) ? '' : String(x);

    return ['div.data',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-int', 'Device ID'],
                    ['th.col-str', 'Data type'],
                    ['th.col-int', 'Address'],
                    ['th', 'Value'],
                    ['th.col-remove']
                ]
            ],
            ['tbody', Array.from(Object.entries(data), ([id, i]) =>
                ['tr', {
                    class: {
                        selected: selected == id
                    },
                    on: {
                        click: _ => r.set(selectedPath, id)
                    }},
                    ['td.col-int', val(i.device_id)],
                    ['td.col-str', val(i.data_type)],
                    ['td.col-int', val(i.address)],
                    ['td', val(i.value)],
                    ['td.col-remove',
                        ['button', {
                            on: {
                                click: evt => {
                                    evt.stopPropagation();
                                    common.removeData(deviceId, id);
                                }
                            }},
                            ['span.fa.fa-times']
                        ]
                    ]
                ]
            )]
        ],
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


function slavePanel(deviceId) {
    const dataId = r.get('pages', deviceId, 'selected');
    if (u.isNil(dataId))
        return [];

    const data = r.get('remote', 'devices', deviceId, 'data', 'data', dataId);
    if (!data)
        return [];

    const onChange = u.curry((property, value) => common.changeData(deviceId, dataId, property, value));

    return ['div.panel',
        formEntryNumber('Device ID', data.device_id, onChange('device_id')),
        formEntrySelect('Data type', data.data_type, ['',  ...dataTypes], onChange('data_type')),
        formEntryNumber('Address', data.address, onChange('address')),
        formEntryNumber('Value', data.value, onChange('value'))
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
