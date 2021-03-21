import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as datetime from '@hat-core/syslog/datetime';


export function main() {
    return ['div#main',
        sidebar(),
        device(),
        log()
    ];
}


function sidebar() {
    const devices = r.get('devices');
    return ['div.sidebar',
        ['div.devices',
            u.map((_, id) => sidebarDevice(id), devices)
        ],
        ['div.add',
            ['button',
                ['span.fa.fa-plug'],
                ' Add master'
            ],
            ['button',
                ['span.fa.fa-server'],
                ' Add slave'
            ]
        ]
    ];
}


function sidebarDevice(id) {
    const selected = r.get('selected') == id;
    return ['div.device', 'device'];
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
