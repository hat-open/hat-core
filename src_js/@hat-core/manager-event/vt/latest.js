import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as datetime from '@hat-core/syslog/datetime';

import * as common from '@hat-core/manager-event/common';


export function main() {
    const eventTree = common.getLatestEventTree();
    return ['div.page.latest',
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
                eventTree.children.map(eventTreeNode)
            ]
        ]
    ];
}


function eventTreeNode(node) {
    const isExpanded = Boolean(u.find(u.equals(node.type),
                                      r.get('latest', 'expanded')));
    let expandIcon;
    let expandClick;
    if (!node.children.length) {
        expandIcon = '.fa-square-o';
        expandClick = _ => null;
    } else if (!isExpanded) {
        expandIcon = '.fa-plus-square-o';
        expandClick = _ => r.change(['latest', 'expanded'], u.append(node.type));
    } else {
        expandIcon = '.fa-minus-square-o';
        expandClick = _ => r.change(['latest', 'expanded'], u.filter(i => !u.equals(node.type, i)));
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
            node.children.map(eventTreeNode))
    ];
}
