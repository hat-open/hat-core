import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as juggler from '@hat-core/juggler';
import * as datetime from '@hat-core/syslog/datetime';


import 'event-viewer/main.scss';


const defaultState = {
    remote: null,
    local: {
        expanded: []
    }
};


let app = null;


function main() {
    const root = document.body.appendChild(document.createElement('div'));
    r.init(root, defaultState, vt);

    // eslint-disable-next-line no-unused-vars
    app = new juggler.Application(r, null, null, 'remote');
}


function vt() {
    const eventTree = getEventTree();
    return ['div#main',
        ['table.events',
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
                eventTree.children.map(vtEventTree)
            ]
        ]
    ];
}


function vtEventTree(node) {
    const isExpanded = Boolean(u.find(u.equals(node.type),
                                      r.get('local', 'expanded')));
    let expandIcon;
    let expandClick;
    if (!node.children.length) {
        expandIcon = '.fa-square-o';
        expandClick = _ => null;
    } else if (!isExpanded) {
        expandIcon = '.fa-plus-square-o';
        expandClick = _ => expand(node.type);
    } else {
        expandIcon = '.fa-minus-square-o';
        expandClick = _ => combine(node.type);
    }
    return [
        ['tr',
            ['td.col-type',
                [`span.expand-icon.fa.${expandIcon}`, {
                    props: {
                        style: `margin-left: ${(node.type.length - 1) * 20}px`},
                    on: {
                        click: expandClick}
                }],
                node.type[node.type.length - 1]],
            ['td.col-id', (!node.event ? '' :
                String(node.event.event_id.server))],
            ['td.col-id', (!node.event ? '' :
                String(node.event.event_id.instance))],
            ['td.col-timestamp', (!node.event ? '' :
                datetime.utcTimestampToLocalString(node.event.timestamp))],
            ['td.col-timestamp', (!node.event ? '' :
                datetime.utcTimestampToLocalString(node.event.source_timestamp))],
            ['td.col-payload', (!node.event ? '' :
                JSON.stringify(node.event.payload))]
        ],
        (!isExpanded ? [] :
            node.children.map(vtEventTree))
    ];
}


function expand(eventType) {
    r.change(['local', 'expanded'], u.append(eventType));
}


function combine(eventType) {
    r.change(['local', 'expanded'], u.filter(i => !u.equals(eventType, i)));
}


function getEventTree() {
    const createNode = (eventType, node) => ({
        'event': node['*'],
        'type': eventType,
        'children': u.pipe(
            u.toPairs,
            u.filter(([k, _]) => k != '*'),
            u.sortBy(u.get(0)),
            u.map(([k, v]) => createNode(u.append(k, eventType), v))
        )(node)
    });
    return createNode(
        [], u.reduce((acc, val) => u.set([val.event_type, '*'], val, acc),
                     {},
                     r.get('remote') || []));
}


window.addEventListener('load', main);
window.r = r;
window.u = u;
