import r from '@hat-core/renderer';
import * as u from '@hat-core/util';
import * as node from '@hat-core/node';


// zoom - [0.1, 10]
// x - [0, 1]
// y - [0, 1]
export function createSvgPageState(zoom, x, y) {
    return {
        zoom,
        anchor: {x, y},
        pan: {
            active: false,
            mouseDownPosition: null,
            anchorDown: null
        },
        initial: {
            zoom,
            anchor: {x, y}
        }
    };
}


export const svgPage = u.curry((path, svg) => {

    const svgWidth = node.getData(['attrs', 'width'], svg) || 0;
    const svgHeight = node.getData(['attrs', 'height'], svg) || 0;
    const panActive = r.get(path, 'pan', 'active');
    const zoom = r.get(path, 'zoom');
    const anchorX = svgWidth * r.get(path, 'anchor', 'x');
    const anchorY = svgHeight * r.get(path, 'anchor', 'y');
    const viewBoxX = anchorX - (svgWidth / 2) * zoom;
    const viewBoxY = anchorY - (svgHeight / 2) * zoom;
    const viewBoxWidth = svgWidth * zoom;
    const viewBoxHeight = svgHeight * zoom;
    const viewBoxRatio = svgWidth / svgHeight;
    const viewBox = `${viewBoxX} ${viewBoxY} ${viewBoxWidth} ${viewBoxHeight}`;

    function getMouse(el, pageX, pageY) {
        const pageSize = el.getBoundingClientRect();
        const pageRatio = pageSize.width / pageSize.height;
        const pageWidth = (pageRatio > viewBoxRatio) ?
            pageRatio * viewBoxHeight :
            viewBoxWidth;
        const pageHeight = (pageRatio > viewBoxRatio) ?
            viewBoxHeight :
            viewBoxWidth / pageRatio;
        const pageLeft = viewBoxX - (pageWidth - viewBoxWidth) / 2;
        const pageTop = viewBoxY - (pageHeight - viewBoxHeight) / 2;
        const cursorPosition = {
            x: pageX / (pageSize.x + pageSize.width),
            y: pageY / (pageSize.y + pageSize.height)
        };
        const mouse = {
            x: pageLeft + cursorPosition.x * pageWidth,
            y: pageTop + cursorPosition.y * pageHeight
        };
        return mouse;
    }

    function pan(oldAnchor, x, y) {
        const anchor = {
            x: oldAnchor.x + x / svgWidth,
            y: oldAnchor.y + y / svgHeight
        };
        r.set([path, 'anchor'], anchor);
    }

    function calcZoom(amount) {
        const factor = 5;
        let newZoom = amount > 0 ?
            zoom - (zoom / factor) * amount :
            (factor * zoom) / (factor + amount);
        newZoom = Math.max(newZoom, 0.1);
        newZoom = Math.min(newZoom, 10);
        return newZoom;
    }

    function reset() {
        r.change(path, state => u.merge(state, state.initial));
    }

    return ['div.svg-page', {
        class: {
            panning: panActive
        },
        props: {
            tabIndex: -1
        },
        on: {
            wheel: evt => {
                const mouse = getMouse(evt.currentTarget, evt.pageX, evt.pageY);
                const newZoom = calcZoom(evt.wheelDelta / 100);
                const anchor = {
                    x: (newZoom != zoom) ?
                        (mouse.x + (anchorX - mouse.x) * newZoom / zoom) / svgWidth :
                        anchorX / svgWidth,
                    y: (newZoom != zoom) ?
                        (mouse.y + (anchorY - mouse.y) * newZoom / zoom) / svgHeight :
                        anchorY / svgHeight
                };
                r.change(path, u.pipe(
                    u.set('zoom', newZoom),
                    u.set('anchor', anchor)
                ));
            },
            mousedown: evt => {
                r.change(path, state => u.set('pan', {
                    active: true,
                    mouseDownPosition: {x: evt.pageX, y: evt.pageY},
                    anchorDown: state.anchor
                }, state));
            },
            mouseup: () => r.set([path, 'pan', 'active'], false),
            mouseleave: () => r.set([path, 'pan', 'active'], false),
            mousemove: evt => {
                const panActive = r.get(path, 'pan', 'active');
                if (!panActive)
                    return ;
                const mouseDownPosition = r.get(path, 'pan', 'mouseDownPosition');
                const mouseDown = getMouse(evt.currentTarget, mouseDownPosition.x, mouseDownPosition.y);
                const mouse = getMouse(evt.currentTarget, evt.pageX, evt.pageY);
                const anchorDown = r.get(path, 'pan', 'anchorDown');
                pan(anchorDown, mouseDown.x - mouse.x, mouseDown.y - mouse.y);
            },
            keydown: evt => {
                const anchor = r.get(path, 'anchor');
                const panFactor = evt.altKey ? 10 : 1;
                const zoomFactor = evt.altKey ? 3 : 1;
                const panValue = 10 * panFactor;
                const zoomValue = 1 * zoomFactor;
                switch(evt.key) {
                    case 'ArrowLeft':
                        pan(anchor, -1 * panValue, 0);
                        break;
                    case 'ArrowRight':
                        pan(anchor, panValue, 0);
                        break;
                    case 'ArrowUp':
                        pan(anchor, 0, -1 * panValue);
                        break;
                    case 'ArrowDown':
                        pan(anchor, 0, panValue);
                        break;
                    case '+':
                        r.set([path, 'zoom'], calcZoom(zoomValue));
                        break;
                    case '-':
                        r.set([path, 'zoom'], calcZoom(-1 * zoomValue));
                        break;
                    case 'Home':
                        reset();
                        break;
                }
            }
        }},
        u.pipe(
            node.setData(['attrs', 'height'], '100%'),
            node.setData(['attrs', 'width'], '100%'),
            node.setData(['attrs', 'preserveAspectRatio'], 'xMidYMid'),
            node.setData(['attrs', 'viewBox'], viewBox)
        )(svg),
        ['div.zoom-in', {
            on: {
                mousedown: evt => evt.stopPropagation(),
                wheel: evt => evt.stopPropagation(),
                click: () => r.set([path, 'zoom'], calcZoom(1))
            }},
            ['span.fa.fa-plus']
        ],
        ['div.zoom-out', {
            on: {
                mousedown: evt => evt.stopPropagation(),
                wheel: evt => evt.stopPropagation(),
                click: () => r.set([path, 'zoom'], calcZoom(-1))
            }},
            ['span.fa.fa-minus']
        ],
        ['div.zoom-reset', {
            on: {
                mousedown: evt => evt.stopPropagation(),
                wheel: evt => evt.stopPropagation(),
                click: reset
            }},
            ['span.fa.fa-dot-circle-o']
        ]
    ];
});
