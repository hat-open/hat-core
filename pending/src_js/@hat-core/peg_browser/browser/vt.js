import * as u from '@hat/util';

import * as common from '@hat/peg_browser/browser/common';


export function browser() {
    return ['div#browser', {
        on: {
            mouseleave: common.onMouseLeave,
            mouseup: common.onMouseUp,
            mousemove: common.onMouseMove
        }},
        definitionsList(),
        definitionsView(),
        timeline(),
        callStack(),
        data('input'),
        data('parsed'),
        data('remaining'),
        astView()
    ];
}


function definitionsList() {
    const selectedDefinition = common.getSelectedDefinition();
    const definitions = common.getAllDefinitions();
    return ['div.definitions-list',
        ['div.title', 'Definitions'],
        ['div.content', definitions.map(definition =>
            ['div.item', {
                class: {
                    selected: definition == selectedDefinition
                },
                on: {
                    click: _ => common.setSelectedDefinition(definition)
                }},
                definition
            ]
        )]
    ];
}


function definitionsView() {
    const definition = common.getSelectedDefinition();
    const node = common.getDefinitionNode(definition);
    if (!node)
        return ['div.definitions-view'];
    return ['div.definitions-view',
        ['div.title', definition],
        ['div.content',
            definitionsNode(node)
        ]
    ];
}


function definitionsNode(node) {
    return ['div.node', (node.type != 'Identifier' ? {} : {
        class: {
            identifier: true
        },
        on: {
            click: _ => common.setSelectedDefinition(node.value)
        }}),
        ['div.type', node.type],
        (u.isArray(node.value) ?
            ['div.value', node.value.map(definitionsNode)] :
            ['pre.value', node.value]
        )
    ];
}


function timeline() {
    const selectedResult = common.getSelectedResult();
    const resultsCount = common.getResultsCount();
    return ['div.timeline',
        ['div.title', 'Timeline'],
        ['div.content',
            ['button', {
                on: {
                    click: common.selectPreviousResult
                }},
                '<'
            ],
            ['div.slider',
                timelineSliderMark()
            ],
            ['button', {
                on: {
                    click: common.selectNextResult
                }},
                '>'
            ],
            ['div.position', (resultsCount ?
                `${selectedResult + 1} / ${resultsCount}` :
                ''
            )]
        ]
    ];
}


function timelineSliderMark() {
    const resultsCount = common.getResultsCount();
    if (resultsCount < 2)
        return [];
    const selectedResult = common.getSelectedResult();
    const width = Math.max(100 / resultsCount, 5);
    const left = (100 - width) * selectedResult / (resultsCount - 1);
    return ['div.mark', {
        props: {
            style: `width: ${width}%; left: ${left}%`
        },
        on: {
            mousedown: common.timelineSliderMarkMouseDown
        }
    }];
}


function callStack() {
    const callStack = common.getCallStack();
    return ['div.call-stack',
        ['div.title', 'Call stack'],
        ['div.content', callStack.map(definition =>
            ['div.item', {
                on: {
                    click: _ => common.setSelectedDefinition(definition)
                }},
                definition
            ]
        )]
    ];
}


function data(dataType) {
    const data = common.getData(dataType);
    return [`div.data-${dataType}`,
        ['div.title', `Data ${dataType}`],
        ['pre', data]
    ];
}


function astView() {
    const ast = common.getAst();
    return ['div.ast-view',
        ['div.title', 'AST'],
        ['div.content', ast]
    ];
}
