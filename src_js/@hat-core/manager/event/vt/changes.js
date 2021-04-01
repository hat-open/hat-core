import r from '@hat-core/renderer';
import * as datetime from '@hat-core/syslog/datetime';


export function main(deviceId) {
    const changes = r.get('remote', 'devices', deviceId, 'data', 'changes');

    return ['div.subpage.changes',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-type', 'Type'],
                    ['th.col-id', 'Server'],
                    ['th.col-id', 'Instance'],
                    ['th.col-timestamp', 'Timestamp'],
                    ['th.col-timestamp', 'Source timestamp'],
                    ['th.col-payload', 'Payload']
                ]
            ],
            ['tbody',
                changes.map(event => ['tr',
                    ['td.col-type',
                        event.event_type.join(', ')
                    ],
                    ['td.col-id',
                        String(event.event_id.server)
                    ],
                    ['td.col-id',
                        String(event.event_id.instance)
                    ],
                    ['td.col-timestamp',
                        datetime.utcTimestampToLocalString(event.timestamp)
                    ],
                    ['td.col-timestamp',
                        datetime.utcTimestampToLocalString(event.source_timestamp)
                    ],
                    ['td.col-payload',
                        JSON.stringify(event.payload)
                    ]
                ])
            ]
        ]
    ];
}
