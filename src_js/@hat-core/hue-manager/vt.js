import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as form from '@hat-core/common/form';
import * as common from '@hat-core/hue-manager/common';
import * as datetime from '@hat-core/syslog/datetime';


export function main() {
    return ['div#main',
        (r.get('connected') ?
            connected() :
            disconnected()),
        log()
    ];
}


function log() {
    return ['div#log',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-timestamp', 'Timestamp'],
                    ['th.col-msg', 'Log message']
                ]
            ],
            ['tbody', u.reverse(r.get('log')).map(i =>
                ['tr',
                    ['td.col-timestamp',
                        datetime.utcTimestampToLocalString(i.timestamp)
                    ],
                    ['td.col-msg', i.msg]
                ]
            )]
        ]
    ];
}


function disconnected() {
    return ['div#disconnected',
        ['div.form',
            form.textInput('url', 'Address').slice(1),
            form.textInput('user', 'Username').slice(1),
            ['div'],
            ['label',
                ['input', {
                    props: {
                        type: 'checkbox',
                        checked: r.get('remember')
                    },
                    on: {
                        change: evt => {
                            const checked = evt.target.checked
                            r.set('remember', checked);
                            if (!checked)
                                common.deleteSettings();
                        }
                    }}
                ],
                ' Remember'
            ],
            ['div'],
            ['div',
                ['button', {
                    on: {
                        click: common.createUser
                    }},'Create user'
                ],
                ['button', {
                    on: {
                        click: common.connect
                    }},
                    'Connect'
                ]
            ]
        ],
        discovery()
    ];
}


function connected() {
    const url = r.get('url');
    const page = r.get('page');
    let pageVt = ['div.page'];
    if (page == 'config') {
        pageVt = config();
    } else if (page == 'lights') {
        pageVt = lights();
    } else if (page == 'sensors') {
        pageVt = sensors();
    }
    return ['div#connected',
        ['div.toolbar',
            ['div.link', {
                class: {
                    selected: page == 'config'
                },
                on: {
                    click: _ => r.set('page', 'config')
                }},
                'Config'
            ],
            ['div.link', {
                class: {
                    selected: page == 'lights'
                },
                on: {
                    click: _ => r.set('page', 'lights')
                }},
                'Lights'
            ],
            ['div.link', {
                class: {
                    selected: page == 'sensors'
                },
                on: {
                    click: _ => r.set('page', 'sensors')
                }},
                'Sensors'
            ],
            ['div.spacer'],
            ['div',
                url,
                ' ',
                ['button', {
                    on: {
                        click: common.refresh
                    }},
                    ['span.fa.fa-refresh'],
                    ' Refresh'
                ],
                ' ',
                ['button', {
                    on: {
                        click: common.disconnect
                    }},
                    ['span.fa.fa-sign-out'],
                    ' Disconnect'
                ]
            ]
        ],
        pageVt
    ];
}


function discovery() {
    const enabled = r.get('discovery', 'enabled');
    const available = r.get('discovery', 'available');
    return ['div.discovery',
        ['table',
            ['thead',
                ['tr',
                    ['th', {
                        props: {
                            colSpan: 3
                        }},
                        'Discovery'
                    ]
                ],
                ['tr',
                    ['th.col-url', 'Address'],
                    ['th.col-name', 'Name'],
                    ['th.col-sel']
                ]
            ],
            ['tbody', (available.length < 1 ?
                ['tr',
                    ['td', {
                        props: {
                            colSpan: 3,
                            style: 'text-align: center'
                        }},
                        'No entries'
                    ]
                ] :
                available.map(i =>
                    ['tr',
                        ['td.col-url', i.url],
                        ['td.col-name', i.name],
                        ['td.col-sel',
                            ['button', {
                                on: {
                                    click: _ => r.set('url', i.url)
                                }},
                                ['span.fa.fa-check']
                            ]
                        ]
                    ]
                )
            )]
        ],
        ['div',
            ['button', {
                props: {
                    disabled: !enabled
                },
                on: {
                    click: common.discovery
                }},
                'Find hubs'
            ],
            form.textInput(['discovery', 'duration'], 'Duration (sec)',
                           form.floatValidator)
        ]
    ];
}


function config() {
    const users = r.get('state', 'config', 'whitelist') || {};
    return ['div.page',
        ['div.group',
            ['label.title', 'Bridge'],
            ['div.grid',
                configItemText('name', 'Name', true),
                configItemText('bridgeid', 'Bridge ID'),
                configItemText('swversion', 'Software version'),
                configItemText('modelid', 'Model ID'),
                configItemText('apiversion', 'API version'),
                configItemBoolean('factorynew', 'Factory new'),
                configItemBoolean('linkbutton', 'Link button', true),
                ['lable', 'ZigBee touchlink'],
                ['button', {
                    on: {
                        click: _ => common.setConf(null, {'touchlink': true})
                    }},
                    ['span.fa.fa-refresh'],
                    ' Connect'
                ],
                ['div']
            ]
        ],
        ['div.group',
            ['label.title', 'Software update'],
            ['div.grid',
                configItemText(['swupdate', 'updatestate'], 'Update state', true),  // number
                configItemBoolean(['swupdate', 'checkforupdate'], 'Check for update', true),
                configItemBoolean(['swupdate', 'devicetypes', 'bridge'], 'Update bridge', true),
                configItemText(['swupdate', 'url'], 'Update URL', true),
                configItemText(['swupdate', 'text'], 'Update text', true),
                configItemBoolean(['swupdate', 'notify'], 'Update notify', true)
            ]
        ],
        ['div.group',
            ['label.title', 'Time'],
            ['div.grid',
                configItemText('UTC', 'UTC time', true),
                configItemText('localtime', 'Local time', true),
                configItemText('timezone', 'Time zone', true)
            ]
        ],
        ['div.group',
            ['label.title', 'Network'],
            ['div.grid',
                configItemText('mac', 'MAC address', true),
                configItemBoolean('dhcp', 'DHCP', true),
                configItemText('ipaddress', 'IP address', true),
                configItemText('netmask', 'Network mask', true),
                configItemText('gateway', 'Gateway', true),
                configItemText('proxyaddress', 'Proxy address', true),
                configItemText('proxyport', 'Proxy port', true),  // number
                configItemChoice('zigbeechannel', 'ZigBee channel', [
                    [0, 'Undefined'],
                    [11, '11'],
                    [15, '15'],
                    [20, '20'],
                    [25, '25']
                ])
            ]
        ],
        ['div.group',
            ['label.title', 'Portal'],
            ['div.grid',
                configItemBoolean('portalservices', 'Service', true),
                configItemText('portalconnection', 'Connection'),
                configItemBoolean(['portalstate', 'signedon'], 'Signed'),
                configItemBoolean(['portalstate', 'incomming'], 'Incomming'),
                configItemBoolean(['portalstate', 'signedon'], 'Outgoing'),
                configItemText(['portalstate', 'communication'], 'Communication')
            ]
        ],
        ['div.group',
            ['label.title', 'Users'],
            ['table.users',
                ['thead',
                    ['tr',
                        ['th', 'Username'],
                        ['th', 'Last used'],
                        ['th', 'Created'],
                        ['th', 'Name'],
                        ['th']
                    ]
                ],
                ['tbody',
                    u.toPairs(users).map(([username, user]) =>
                        ['tr',
                            ['td', username],
                            ['td', user['last use date']],
                            ['td', user['create date']],
                            ['td', user.name],
                            ['td',
                                ['button', {
                                    on: {
                                        click: _ => common.deleteUser(username)
                                    }},
                                    ['span.fa.fa-times']
                                ]
                            ]
                        ]
                    )
                ]
            ]
        ]
    ];
}


function configItemText(pathSuffix, label, editable) {
    const path = ['state', 'config', pathSuffix];
    const value = String(r.get(path));
    return [
        ['label', label, ': '],
        (editable ?
            ['input', {
                props: {
                    type: 'text',
                    value: value
                }
            }] :
            ['label', value]),
        (editable ?
            ['button', {
                on: {
                    click: _ => common.setConf(
                        null, u.set(pathSuffix, r.get(path), {}))
                }},
                ['span.fa.fa-pencil']
            ] :
            ['div'])
    ];
}


function configItemBoolean(pathSuffix, label, editable) {
    const path = ['state', 'config', pathSuffix];
    const value = r.get(path);
    return [
        ['label', label, ': '],
        ['label', (value ?
            ['span.fa.fa-check'] :
            ['span.fa.fa-times']
        )],
        (editable ?
            ['button', {
                on: {
                    click: _ => common.setConf(
                        null, u.set(pathSuffix, !r.get(path), {}))
                }}, (value ?
                ['span.fa.fa-toggle-on'] :
                ['span.fa.fa-toggle-off']
            )] :
            ['div'])
    ];
}


function configItemChoice(pathSuffix, label, values) {
    const path = ['state', 'config', pathSuffix];
    const selectedValue = r.get(path);
    const allValues = (
        values.find(([i, _]) => u.equals(selectedValue, i)) === undefined ?
            u.append([selectedValue, String(selectedValue)], values) :
            values);
    return [
        ['label', label, ': '],
        ['select', {
            on: {
                change: evt => r.set(path, evt.target.value)
            }},
            allValues.map(([value, valueLabel]) =>
                ['option', {
                    props: {
                        selected: value == selectedValue,
                        value: value
                    }},
                    valueLabel
                ]
            )
        ],
        ['button', {
            on: {
                click: _ => common.setConf(
                    null, u.set(pathSuffix, r.get(path), {}))
            }},
            ['span.fa.fa-pencil']
        ]
    ];
}


function lights() {
    // const state = r.get('state', 'lights') || {};


    return ['div.page'];
}


function sensors() {
    // const state = r.get('state', 'sensors') || {};


    return ['div.page'];
}
