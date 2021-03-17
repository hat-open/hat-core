import r from '@hat-core/renderer';

import * as latest from '@hat-core/manager-event/vt/latest';
import * as changes from '@hat-core/manager-event/vt/changes';
import * as register from '@hat-core/manager-event/vt/register';


export function main() {
    const page = r.get('page');

    let pageVt;
    if (page == 'latest') {
        pageVt = latest.main();
    } else if (page == 'changes') {
        pageVt = changes.main();
    } else if (page == 'register') {
        pageVt = register.main();
    } else {
        pageVt = ['div.page'];
    }

    return ['div#main',
        header(),
        pageVt
    ];
}


function header() {
    const selectedPage = r.get('page');
    return ['div.header',
        [
            ['latest', 'Latest'],
            ['changes', 'Changes'],
            ['register', 'Register']
        ].map(([page, title]) => ['div', {
            class: {
                selected: selectedPage == page
            },
            on: {
                click: _ => r.set('page', page)
            }},
            title
        ])
    ];
}
