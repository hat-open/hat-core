import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as juggler from '@hat-core/juggler';


import 'monitor/main.scss';


const defaultState = {
    remote: null
};


let app = null;


function main() {
    const root = document.body.appendChild(document.createElement('div'));
    r.init(root, defaultState, vt);
    app = new juggler.Application(null, 'remote');
}


function setRank(cid, rank) {
    app.send({type: 'set_rank', payload: {
        cid: cid,
        rank: rank
    }});
}


function vt() {
    if (!r.get('remote'))
        return  ['div.monitor'];
    return ['div.monitor',
        localComponentsVt(),
        globalComponentsVt()
    ];
}


function localComponentsVt() {
    const components = r.get('remote', 'local_components');
    return ['div',
        ['h1', 'Local components'],
        ['table',
            ['thead',
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
                                    click: _ => setRank(cid, rank - 1)
                                }},
                                ['span.fa.fa-chevron-left']
                            ],
                            ['div', String(rank)],
                            ['button', {
                                on: {
                                    click: _ => setRank(cid, rank + 1)
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


function globalComponentsVt() {
    const components = r.get('remote', 'global_components');
    return ['div',
        ['h1', 'Global components'],
        ['table',
            ['thead',
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


window.addEventListener('load', main);
window.r = r;
window.u = u;
