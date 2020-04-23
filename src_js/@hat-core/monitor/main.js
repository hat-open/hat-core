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
    app = new juggler.Application(r, null, null, 'remote');
}


function setRank(cid, mid, rank) {
    app.send({type: 'set_rank', payload: {
        cid: cid, mid: mid, rank: rank
    }});
}


function vt() {
    if (!r.get('remote'))
        return  ['div.monitor'];
    const local_mid = r.get('remote', 'mid');
    const components = r.get('remote', 'components');
    return ['div.monitor',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-name', 'Name'],
                    ['th.col-group', 'Group'],
                    ['th.col-address', 'Address'],
                    ['th.col-local', 'Local'],
                    ['th.col-blessing', 'Blessing'],
                    ['th.col-ready', 'Ready'],
                    ['th.col-rank', 'Rank']
                ]
            ],
            ['tbody', components.map(({cid, mid, name, group, address, rank, blessing, ready}) =>
                ['tr',
                    ['td.col-name', name],
                    ['td.col-group', group],
                    ['td.col-address', address || ''],
                    ['td.col-local', (mid == local_mid ? ['span.fa.fa-check'] : '')],
                    ['td.col-blessing', (blessing !== null ? String(blessing) : '')],
                    ['td.col-ready', (ready !== null ? String(ready) : '')],
                    ['td.col-rank',
                        ['div',
                            ['button', {
                                on: {
                                    click: _ => setRank(cid, mid, rank - 1)
                                }},
                                ['span.fa.fa-chevron-left']
                            ],
                            ['div', String(rank)],
                            ['button', {
                                on: {
                                    click: _ => setRank(cid, mid, rank + 1)
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


window.addEventListener('load', main);
window.r = r;
window.u = u;
