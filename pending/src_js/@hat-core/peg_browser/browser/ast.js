import * as u from '@hat/util';


export const astToSvg = u.curry((textSize, node) => {
    node = processNode(textSize, node);
    const svg = nodeToSvg(node);
    return ['svg', {attrs: {width: node.w, height: node.h}}, svg];
});


const labelPadding = 10;


const processNode = u.curry((textSize, node) => {
    let label;
    let children;
    if (u.isString(node)) {
        label = node;
        children = [];
    } else {
        label = node.name;
        children = node.value.map(processNode(textSize));
    }
    const [label_w, label_h] = textSize[label];
    const [children_w, children_h] = u.reduce(
        ([w, h], i) => [w + i.w, Math.max(h, i.h)],
        [0, 0],
        children);
    const w = Math.max(children_w, label_w + 2 * labelPadding);
    const h = children_h + label_h + 2 * labelPadding;
    const label_x = w / 2;
    const label_y = labelPadding + label_h / 2;
    [, children] = u.reduce(
        ([offset, children], child) => [offset + child.w, u.append(u.pipe(
            u.set('x', offset),
            u.set('y', label_h + 2 * labelPadding)
        )(child), children)],
        [(w - children_w) / 2, []],
        children);
    const lines = children.map(i => ({
        x1: label_x,
        y1: label_h + labelPadding + 5,
        x2: i.x + i.w / 2,
        y2: label_h + 3 * labelPadding - 5}));
    return {x: 0, y: 0, w, h, label, label_x, label_y, children, lines};
});


function nodeToSvg(node) {
    return ['g', {
        attrs: {
            transform: `translate(${node.x} ${node.y})`
        }},
        ['text', {
            attrs: {
                x: node.label_x,
                y: node.label_y
            }},
            node.label
        ],
        node.children.map(nodeToSvg),
        node.lines.map(({x1, y1, x2, y2}) =>
            ['line', {attrs: {x1: x1, y1: y1, x2: x2, y2: y2}}]
        )
    ];
}
