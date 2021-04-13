import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as datetime from '@hat-core/syslog/datetime';

import * as common from '@hat-core/manager/common';

import * as orchestratorVt from '@hat-core/manager/orchestrator/vt';
import * as monitorVt from '@hat-core/manager/monitor/vt';
import * as eventVt from '@hat-core/manager/event/vt/main';
import * as iec104Vt from '@hat-core/manager/iec104/vt';
import * as modbusVt from '@hat-core/manager/modbus/vt';


const deviceTypeTitles = {
    orchestrator: 'Orchestrator',
    monitor: 'Monitor Server',
    event: 'Event Server',
    iec104_master: 'IEC104 Master',
    iec104_slave: 'IEC104 Slave',
    modbus_master: 'Modbus Master',
    modbus_slave: 'Modbus Slave',
};


export function main() {
    return ['div#main',
        globalHeader(),
        deviceHeader(),
        sidebar(),
        page(),
        log(),
        addDialog(),
        settingsDialog()
    ];
}


function globalHeader() {
    return ['div.header.global',
        ['button', {
            on: {
                click: common.showSettingsDialog
            }},
            ['span.fa.fa-cog'],
            ' Settings'
        ],
        ['button', {
            on: {
                click: common.save
            }},
            ['span.fa.fa-floppy-o'],
            ' Save'
        ]
    ];
}


function deviceHeader() {
    const deviceId = r.get('deviceId');
    if (!deviceId)
        return ['div.header.device'];

    const device = r.get('remote', 'devices', deviceId);
    if (!device)
        return ['div.header.device'];

    return ['div.header.device',
        ['label', deviceTypeTitles[device.type]],
        ['input', {
            props: {
                type: 'text',
                value: device.name
            },
            on: {
                change: evt => common.setName(deviceId, evt.target.value)
            }
        }],
        ['label',
            ['input', {
                props: {
                    type: 'checkbox',
                    checked: device.auto_start
                },
                on: {
                    change: evt => common.setAutoStart(deviceId, evt.target.checked)
                }
            }],
            ' Auto start'
        ],
        ['button', {
            on: {
                click: _ => common.start(deviceId)
            }},
            ['span.fa.fa-play'],
            ' Start'
        ],
        ['button', {
            on: {
                click: _ => common.stop(deviceId)
            }},
            ['span.fa.fa-stop'],
            ' Stop'
        ],
        ['button', {
            on: {
                click: _ => common.remove(deviceId)
            }},
            ['span.fa.fa-minus'],
            ' Remove'
        ]
    ];
}


function sidebar() {
    const devices = r.get('remote', 'devices') || [];
    const selectedDeviceId = r.get('deviceId');
    return ['div.sidebar',
        ['div.devices',
            u.toPairs(devices).map(([deviceId, device]) => {
                const selected = selectedDeviceId == deviceId;
                return ['div.device', {
                    class: {
                        selected: selected
                    },
                    on: {
                        click: _ => r.set('deviceId', deviceId)
                    }},
                    ['span.status.fa.fa-circle', {
                        class: {
                            [device.status]: true
                        }
                    }],
                    ['span.name', device.name],
                    ' ',
                    ['span.type', `(${deviceTypeTitles[device.type]})`]
                ];
            })
        ],
        ['button.add', {
            on: {
                click: common.showAddDialog
            }},
            ['span.fa.fa-plus'],
            ' Add device'
        ]
    ];
}


function page() {
    const deviceId = r.get('deviceId');
    if (!deviceId)
        return ['div.page'];

    const deviceType = r.get('remote', 'devices', deviceId, 'type');

    if (deviceType == 'orchestrator')
        return orchestratorVt.main();

    if (deviceType == 'monitor')
        return monitorVt.main();

    if (deviceType == 'event')
        return eventVt.main();

    if (deviceType == 'iec104_master')
        return iec104Vt.master();

    if (deviceType == 'iec104_slave')
        return iec104Vt.slave();

    if (deviceType == 'modbus_master')
        return modbusVt.master();

    if (deviceType == 'modbus_slave')
        return modbusVt.slave();

    return ['div.page'];
}


function log() {
    const items = r.get('remote', 'log') || [];
    return ['div.log',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-time', 'Time'],
                    ['th.col-message', 'Message']
                ]
            ],
            ['tbody', items.map(i =>
                ['tr',
                    ['td.col-time', datetime.utcTimestampToLocalString(i.timestamp)],
                    ['td.col-message', i.message]
                ]
            )]
        ]
    ];
}


function addDialog() {
    const open = r.get('addDialog', 'open');
    if (!open)
        return [];

    const selectedDeviceType = r.get('addDialog', 'deviceType');

    return ['div.overlay', {
        on: {
            click: evt => {
                evt.stopPropagation();
                common.hideAddDialog();
            }
        }},
        ['div.dialog.add', {
            on: {
                click: evt => evt.stopPropagation()
            }},
            ['select', {
                props: {
                    size: 10
                },
                on: {
                    change: evt => r.set(['addDialog', 'deviceType'], evt.target.value)
                }},
                u.toPairs(deviceTypeTitles).map(([deviceType, name]) => ['option', {
                    props: {
                        selected: deviceType == selectedDeviceType,
                        value: deviceType
                    }},
                    name
                ])
            ],
            ['button', {
                on: {
                    click: _ => {
                        if (!selectedDeviceType)
                            return;
                        common.add(selectedDeviceType);
                        common.hideAddDialog();
                    }
                }},
                ['span.fa.fa-plus'],
                ' Add device'
            ]
        ]
    ];
}


function settingsDialog() {
    const open = r.get('settingsDialog', 'open');
    if (!open)
        return [];

    const settings = r.get('remote', 'settings');

    return ['div.overlay', {
        on: {
            click: evt => {
                evt.stopPropagation();
                common.hideSettingsDialog();
            }
        }},
        ['div.dialog.settings', {
            on: {
                click: evt => evt.stopPropagation()
            }},
            ['span.title', 'UI'],
            ['label.label', 'Address*'],
            ['input', {
                props: {
                    type: 'text',
                    value: settings.ui.address
                },
                on: {
                    change: evt => common.setSettings(['ui', 'address'], evt.target.value)
                }
            }],
            ['span.title', 'Log'],
            ['label.label', 'Level*'],
            ['select', {
                on: {
                    change: evt => common.setSettings(['log', 'level'], evt.target.value)
                }},
                ['DEBUG', 'INFO', 'WARNING', 'ERROR'].map(level => ['option', {
                    props: {
                        selected: level == settings.log.level
                    }},
                    level
                ])
            ],
            ['span'],
            ['label',
                ['input', {
                    props: {
                        type: 'checkbox',
                        checked: settings.log.console.enabled
                    },
                    on: {
                        change: evt => common.setSettings(['log', 'console', 'enabled'], evt.target.checked)
                    }
                }],
                ' Console*'
            ],
            ['span'],
            ['label',
                ['input', {
                    props: {
                        type: 'checkbox',
                        checked: settings.log.syslog.enabled
                    },
                    on: {
                        change: evt => common.setSettings(['log', 'syslog', 'enabled'], evt.target.checked)
                    }
                }],
                ' Syslog*'
            ],
            ['label.label', 'Syslog host*'],
            ['input', {
                props: {
                    type: 'text',
                    value: settings.log.syslog.host
                },
                on: {
                    change: evt => common.setSettings(['log', 'syslog', 'host'], evt.target.value)
                }
            }],
            ['label.label', 'Syslog port*'],
            ['input', {
                props: {
                    type: 'number',
                    value: settings.log.syslog.port
                },
                on: {
                    change: evt => common.setSettings(['log', 'syslog', 'port'], evt.target.valueAsNumber)
                }
            }],
            ['span.note', '* changes applied on restart']
        ]
    ];
}
