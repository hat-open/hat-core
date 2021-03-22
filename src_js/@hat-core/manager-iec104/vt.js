import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as datetime from '@hat-core/syslog/datetime';

import * as common from '@hat-core/manager-iec104/common';


export function main() {
    return ['div#main',
        sidebar(),
        device(),
        log()
    ];
}


function sidebar() {
    const devices = r.get('remote', 'devices') || [];
    return ['div.sidebar',
        ['div.devices',
            u.toPairs(devices).map(([deviceId, device]) => {
                const name = device.properties.name;
                const selected = r.get('selectedDeviceId') == deviceId;
                return ['div.device', {
                    class: {
                        selected: selected
                    }},
                    ['span.status.fa.fa-circle', {
                        class: {
                            [device.properties.status]: true
                        }
                    }],
                    ['span.name', name],
                    ['button.remove', {
                        on: {
                            click: _ => common.removeDevice(deviceId)
                        }},
                        ['span.fa.fa-trash-o']
                    ]
                ];
            })
        ],
        ['div.add',
            ['button', {
                on: {
                    click: common.createMaster
                }},
                ['span.fa.fa-plug'],
                ' Add master'
            ],
            ['button', {
                on: {
                    click: common.createSlave
                }},
                ['span.fa.fa-server'],
                ' Add slave'
            ]
        ]
    ];
}


function device() {
    return ['div.device',
        'device'
    ];
}


function log() {
    const items = r.get('remote', 'log') || [];
    return ['div.log',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-timestamp', 'Timestamp'],
                    ['th.col-message', 'Message']
                ]
            ],
            ['tbody', items.map(i =>
                ['tr',
                    ['td.col-timestamp', datetime.utcTimestampToLocalString(i.timestamp)],
                    ['td.col-message', i.message]
                ]
            )]
        ]
    ];
}
