import r from '@hat/renderer';
import * as u from '@hat/util';

import * as common from '@hat/syslog/common';


export function main() {
    if (!r.get())
        return ['div'];

    return ['div#main', {
        on: {
            mouseleave: common.onMouseLeave,
            mouseup: common.onMouseUp,
            mousemove: common.onMouseMove
        }},
        ['div#toolbar',
            toolbarTimestamp(),
            ['div.spacer'],
            toolbarNavigation(),
            toolbarPageSize(),
            toolbarLiveUpdate(),
            toolbarMenu()
        ],
        ['div#content',
            contentTable(),
            contentMenu()
        ],
        ['div#footer',
            footerFilters()
        ],
        dialog()
    ];
}


function toolbarTimestamp() {
    return ['div.timestamp',
        ['div.title', 'Timestamp'],
        timestampPicker(['local', 'entry_timestamp_from'], 'From'),
        timestampPicker(['local', 'entry_timestamp_to'], 'To')
    ];
}


function toolbarNavigation() {
    if (common.isLiveUpdate())
        return [];

    return ['div.navigation',
        ['button', {
            on: {
                click: common.navigateFirst,
            }},
            ['span.fa.fa-fast-backward']
        ],
        ['button', {
            on: {
                click: common.navigateBack,
            }},
            ['span.fa.fa-step-backward']
        ],
        ['span.page', ` page ${common.getCurrentPage()} `],
        ['button', {
            on: {
                click: common.navigateNext,
            }},
            ['span.fa.fa-step-forward']
        ],
        ['button', {
            on: {
                click: common.navigateLast,
            }},
            ['span.fa.fa-fast-forward']
        ]
    ];
}


function toolbarPageSize() {
    const pageSizes = [20, 50, 100, 200];
    const pageSize = common.getPageSize();
    return ['div.page-size',
        ['span', 'Page size '],
        ['select', {
            on: {
                change: evt => common.setPageSize(evt.target.value)
            }},
            pageSizes.map(i => ['option', {
                props: {
                    value: i,
                    selected: i == pageSize
                }},
                String(i)
            ])
        ]
    ];
}


function toolbarLiveUpdate() {
    return ['label.live-update',
        ['input', {
            props: {
                type: 'checkbox',
                checked: common.isLiveUpdate()
            },
            on: {
                change: common.togleLiveUpdate
            }
        }],
        ' Live update'
    ];
}


function toolbarMenu() {
    return ['button.menu', {
        class: {
            togle: common.isMenuVisible()
        },
        on: {
            click: common.togleMenu
        }},
        ['span.fa.fa-bars'],
        ' MENU'
    ];
}


function contentTable() {
    const columns = common.getVisibleColumns();
    const entries = r.get('remote', 'entries');
    return ['div#table',
        ['table',
            ['thead',
                ['tr', columns.map(column => [
                    ['th', {
                        props: {
                            style: u.pipe(
                                w => w ? `${w}px` : 'auto',
                                w => `min-width: ${w}; max-width: ${w}; width: ${w}`
                            )(common.getColumnWidth(column))
                        }},
                        ['div',
                            ['span.label', common.getColumnLabel(column)],
                            {
                                'TEXT': contentTableFilterText,
                                'SELECT': contentTableFilterSelect,
                                'NONE': _ => []
                            }[common.getColumnFilterType(column)](column)
                        ]
                    ],
                    ['th.border', {
                        on: {
                            mousedown: evt => common.startColumnResize(evt, column)
                        }
                    }]
                ])]
            ],
            ['tbody', entries.map(entry =>
                ['tr', columns.map(column => [
                    [`td.${common.getColumnClass(column)}`,  {
                        on: {
                            dblclick: _ => common.openDialog(entry)
                        }},
                        common.getColumnValue(entry, column)
                    ],
                    ['th.border', {
                        on: {
                            mousedown: evt => common.startColumnResize(evt, column)
                        }
                    }]
                ])]
            )]
        ]
    ];
}


function contentTableFilterText(column) {
    return ['input.filter', {
        props: {
            type: 'text',
            value: common.getFilterValue(column)
        },
        on: {
            change: evt => common.setFilterValue(column, evt.target.value)
        }
    }];
}


function contentTableFilterSelect(column) {
    const value = common.getFilterValue(column);
    return ['select.filter', {
        on: {
            change: evt => common.setFilterValue(column, evt.target.value)
        }},
        common.getColumnSelectValues(column).map(i => ['option', {
            props: {
                selected: value == i
            }},
            String(i)
        ])
    ];
}


function contentMenu() {
    if (!common.isMenuVisible())
        return [];
    return ['div#menu', {
        props: {
            style: `width: ${common.getMenuWidth()}px`
        }},
        ['div.border', {
            on: {
                mousedown: common.startMenuResize
            }
        }],
        ['div.content',
            contentMenuReset(),
            contentMenuColumns()
        ]
    ];
}


function contentMenuReset() {
    return ['div.block',
        ['button', {
            on: {
                click: common.resetSettings
            }},
            'Reset settings'
        ]
    ];
}


function contentMenuColumns() {
    const columns = common.getAllColumns();
    return ['div.block',
        ['div.title', 'Columns'],
        ['div.columns', columns.map(column =>
            ['div.column',
                ['label',
                    ['input', {
                        on: {
                            change: _ => common.togleColumnVisible(column)
                        },
                        props: {
                            type: 'checkbox',
                            checked: common.isColumnVisible(column)
                        }
                    }],
                    common.getColumnLabel(column)
                ],
                ['button',
                    ['span.fa.fa-arrow-down']
                ],
                ['button',
                    ['span.fa.fa-arrow-up']
                ]
            ]
        )]
    ];
}


function footerFilters() {
    return ['div.filters'];
}


function dialog() {
    let entry = common.getDialogEntry();
    if (!entry)
        return [];
    return ['div#dialog', {
        on: {
            click: evt => {
                if (evt.currentTarget != evt.target)
                    return;
                common.closeDialog();
            }
        }},
        ['div.content',
            ['div.header',
                ['div.title', ` Entry ${entry.id}`],
                ['div.close', {
                    on: {
                        click: common.closeDialog
                    }
                }]
            ],
            ['div.entry', jsonObject(entry)]
        ]
    ];
}


function timestampPicker(path, text) {
    return ['div.timestamp-picker',
        ['input', {
            props: {
                type: 'text',
                placeholder: text
            }
        }],
        ['button',
            ['span.fa.fa-eraser']
        ]
    ];
}


function jsonObject(o) {
    return ['div.object', u.toPairs(o).map(([k, v]) =>
        ['div.item',
            ['div.key', `${k}:`],
            ['div.value', (u.isObject(v) ? jsonObject(v) : String(v))]
        ]
    )];
}
