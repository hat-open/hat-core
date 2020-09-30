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
            form.checkboxInput('remember', 'Remember'),
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
    const zigbeeChannelValues = [
        [0, 'Undefined'],
        [11, '11'],
        [15, '15'],
        [20, '20'],
        [25, '25']
    ];
    return ['div.page',
        ['div.grid',
            configItemText('name', 'Name'),
            configItemChoice('zigbeechannel', 'ZigBee channel', zigbeeChannelValues),
            configItemText('bridgeid', 'Bridge ID'),
            configItemText('mac', 'MAX address'),
            configItemBoolean('dhcp', 'DHCP'),
            configItemText('ipaddress', 'IP address'),
            configItemText('netmask', 'Network mask'),
            configItemText('gateway', 'Gateway'),
            configItemText('proxyaddress', 'Proxy address'),
            configItemNumber('proxyport', 'Proxy port'),
            configItemText('UTC', 'UTC'),
            configItemText('localtime', 'localtime'),
            configItemText('timezone', 'timezone'),
            configItemText('modelid', 'modelid'),
            configItemText('swversion', 'swversion'),
            configItemText('apiversion', 'apiversion'),
            configItemNumber(['swupdate', 'updatestate'], 'Update state'),
            configItemBoolean(['swupdate', 'checkforupdate'], 'Check for update'),
            configItemBoolean(['swupdate', 'devicetypes', 'bridge'], 'Update bridge'),
            configItemText(['swupdate', 'url'], 'Update url'),
            configItemText(['swupdate', 'text'], 'Update text'),
            configItemBoolean(['swupdate', 'notify'], 'Update notify'),
            configItemBoolean('linkbutton', 'linkbutton'),
            configItemBoolean('portalservices', 'portalservices'),
            configItemText('portalconnection', 'portalconnection'),
        ]
    ];
}


function configItemText(pathSuffix, label) {
    const path = ['state', 'config', pathSuffix];
    return [
        form.textInput(path, label).slice(1),
        ['button', {
            on: {
                click: _ => common.setConf(
                    null, u.set(pathSuffix, r.get(path), {}))
            }},
            ['span.fa.fa-check']
        ],
    ];
}


function configItemChoice(pathSuffix, label, values) {
    const path = ['state', 'config', pathSuffix];
    return [
        form.selectInput(path, label, values).slice(1),
        ['button', {
            on: {
                click: _ => common.setConf(
                    null, u.set(pathSuffix, r.get(path), {}))
            }},
            ['span.fa.fa-check']
        ]
    ];
}


function configItemBoolean(pathSuffix, label) {
    const path = ['state', 'config', pathSuffix];
    return [
        ['div'],
        form.checkboxInput(path, label),
        ['button', {
            on: {
                click: _ => common.setConf(
                    null, u.set(pathSuffix, r.get(path), {}))
            }},
            ['span.fa.fa-check']
        ]
    ];
}


function configItemNumber(pathSuffix, label) {
    const path = ['state', 'config', pathSuffix];
    return [
        form.textInput(path, label, form.floatValidator).slice(1),
        ['button', {
            on: {
                click: _ => common.setConf(
                    null, u.set(pathSuffix, u.strictParseFloat(r.get(path)) || null, {}))
            }},
            ['span.fa.fa-check']
        ],
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
