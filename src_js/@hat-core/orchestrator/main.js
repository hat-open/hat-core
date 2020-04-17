import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as juggler from '@hat-core/juggler';


import 'orchestrator/main.scss';


const defaultState = {
    remote: null
};


let app = null;


function main() {
    const root = document.body.appendChild(document.createElement('div'));
    r.init(root, defaultState, vt);
    app = new juggler.Application(r, null, null, 'remote');
}


function vt() {
    const remote = r.get('remote');
    if (remote == null) return ['div'];

    const components = r.get('remote', 'components');
    return ['div.orchestrator',
        ['table',
            ['thead',
                ['tr',
                    ['th.col-component', 'Component'],
                    ['th.col-delay', 'Delay'],
                    ['th.col-revive', 'Revive'],
                    ['th.col-status', 'Status'],
                    ['th.col-action', 'Action']
                ]
            ],
            ['tbody', components.map(component =>
                ['tr',
                    ['td.col-component', component.name],
                    ['td.col-delay', String(component.delay)],
                    ['td.col-revive',
                        ['input', {
                            props: {
                                type: 'checkbox',
                                checked: component.revive
                            },
                            on: {
                                change: evt => app.send({
                                    type: 'revive',
                                    payload: {
                                        id: component.id,
                                        value: evt.target.checked
                                    }
                                })
                            }}
                        ]
                    ],
                    ['td.col-status', component.status],
                    ['td.col-action',
                        ['button', {
                            props: {
                                title: 'Stop',
                                disabled: u.contains(
                                    component.status, ['STOPPING', 'STOPPED'])
                            },
                            on: {
                                click: () => app.send({
                                    type: 'stop',
                                    payload: { id: component.id }
                                })
                            }},
                            ['span.fa.fa-times']
                        ],
                        ['button', {
                            props: {
                                title: 'Start',
                                disabled: u.contains(
                                    component.status,
                                    ['STARTING', 'RUNNING', 'STOPPING'])
                            },
                            on: {
                                click: () => app.send({
                                    type: 'start',
                                    payload: { id: component.id }
                                })
                            }},
                            ['span.fa.fa-play']
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
