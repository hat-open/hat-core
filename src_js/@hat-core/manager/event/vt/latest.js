import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as datetime from '@hat-core/syslog/datetime';


export function main(deviceId) {
    const latest = r.get('remote', 'devices', deviceId, 'data', 'latest') || [];
    const eventTree = getEventTree(latest);

    return ['div.subpage.latest',
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
                eventTree.children.map(node => eventTreeNode(deviceId, node))
            ]
        ]
    ];
}


function eventTreeNode(deviceId, node) {
    const expandedPath = ['pages', deviceId, 'latest', 'expanded'];

    const expandedNodes = r.get(expandedPath) || [];
    const isExpanded = Boolean(u.find(u.equals(node.type), expandedNodes));

    let expandIcon;
    let expandClick;
    if (!node.children.length) {
        expandIcon = '.fa-square-o';
        expandClick = _ => null;
    } else if (!isExpanded) {
        expandIcon = '.fa-plus-square-o';
        expandClick = _ => r.change(expandedPath, u.pipe(
            i => i || [],
            u.append(node.type)
        ));
    } else {
        expandIcon = '.fa-minus-square-o';
        expandClick = _ => r.change(expandedPath, u.pipe(
            i => i || [],
            u.filter(i => !u.equals(node.type, i))
        ));
    }

    const type = node.type[node.type.length - 1];
    const serverId = !node.event ? '' : String(node.event.event_id.server);
    const instanceId = !node.event ? '' : String(node.event.event_id.instance);
    const timestamp = !node.event ? '' : datetime.utcTimestampToLocalString(node.event.timestamp);
    const sourceTimestamp = !node.event ? '' : datetime.utcTimestampToLocalString(node.event.source_timestamp);
    const payload = !node.event ? '' : JSON.stringify(node.event.payload);

    return [
        ['tr',
            ['td.col-type', {
                props: {
                    title: type
                }},
                [`span.expand-icon.fa.${expandIcon}`, {
                    props: {
                        style: `margin-left: ${(node.type.length - 1) * 1}rem`},
                    on: {
                        click: expandClick}
                }],
                type
            ],
            ['td.col-id', {props: {title: serverId}}, serverId],
            ['td.col-id', {props: {title: instanceId}}, instanceId],
            ['td.col-timestamp', {props: {title: timestamp}}, timestamp],
            ['td.col-timestamp', {props: {title: sourceTimestamp}}, sourceTimestamp],
            ['td.col-payload', {props: {title: payload}}, payload]
        ],
        (!isExpanded ? [] :
            node.children.map(i => eventTreeNode(deviceId, i)))
    ];
}


function getEventTree(latest) {
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
        [], u.reduce(
            (acc, val) => u.set([val.event_type, '*'], val, acc),
            {},
            latest));
}
