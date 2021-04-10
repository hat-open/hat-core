import r from '@hat-core/renderer';

import * as common from '@hat-core/manager/monitor/common';


export function main() {
    const deviceId = r.get('deviceId');

    return ['div.page.monitor',
        header(deviceId),
        localComponents(deviceId),
        globalComponents(deviceId)
    ];
}


function header(deviceId) {
    const address = r.get('remote', 'devices', deviceId, 'data', 'address');

    return ['div.header',
        ['label', 'Address'],
        ['input', {
            props: {
                value: address
            },
            on: {
                change: evt => common.setAddress(deviceId, evt.target.value)
            }
        }]
    ];
}


function localComponents(deviceId) {
    const components = r.get('remote', 'devices', deviceId, 'data', 'local_components');

    return ['div.components',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-id.hidden'],
                    ['th.col-name.hidden'],
                    ['th.col-group.hidden'],
                    ['th.col-address.hidden'],
                    ['th.col-rank.hidden']
                ],
                ['tr',
                    ['th', {
                        props: {
                            colSpan: 5
                        }},
                        'Local components'
                    ]
                ],
                ['tr',
                    ['th.col-id', 'CID'],
                    ['th.col-name', 'Name'],
                    ['th.col-group', 'Group'],
                    ['th.col-address', 'Address'],
                    ['th.col-rank', 'Rank']
                ]
            ],
            ['tbody', components.map(({cid, name, group, address, rank}) =>
                ['tr',
                    ['td.col-id', String(cid)],
                    ['td.col-name', name || ''],
                    ['td.col-group', group || ''],
                    ['td.col-address', address || ''],
                    ['td.col-rank',
                        ['div',
                            ['button', {
                                on: {
                                    click: _ => common.setRank(cid, rank - 1)
                                }},
                                ['span.fa.fa-chevron-left']
                            ],
                            ['div', String(rank)],
                            ['button', {
                                on: {
                                    click: _ => common.setRank(cid, rank + 1)
                                }},
                                ['span.fa.fa-chevron-right']
                            ]
                        ]
                    ]
                ]
            )]
        ]
    ];
}


function globalComponents(deviceId) {
    const components = r.get('remote', 'devices', deviceId, 'data', 'global_components');

    return ['div.components',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-id.hidden'],
                    ['th.col-id.hidden'],
                    ['th.col-name.hidden'],
                    ['th.col-group.hidden'],
                    ['th.col-address.hidden'],
                    ['th.col-rank.hidden'],
                    ['th.col-blessing.hidden'],
                    ['th.col-ready.hidden']
                ],
                ['tr',
                    ['th', {
                        props: {
                            colSpan: 8
                        }},
                        'Global components'
                    ]
                ],
                ['tr',
                    ['th.col-id', 'CID'],
                    ['th.col-id', 'MID'],
                    ['th.col-name', 'Name'],
                    ['th.col-group', 'Group'],
                    ['th.col-address', 'Address'],
                    ['th.col-rank', 'Rank'],
                    ['th.col-blessing', 'Blessing'],
                    ['th.col-ready', 'Ready']
                ]
            ],
            ['tbody', components.map(({cid, mid, name, group, address, rank, blessing, ready}) =>
                ['tr',
                    ['td.col-id', String(cid)],
                    ['td.col-id', String(mid)],
                    ['td.col-name', name || ''],
                    ['td.col-group', group || ''],
                    ['td.col-address', address || ''],
                    ['td.col-rank', String(rank)],
                    ['td.col-blessing', (blessing !== null ? String(blessing) : '')],
                    ['td.col-ready', (ready !== null ? String(ready) : '')]
                ]
            )]
        ]
    ];
}
