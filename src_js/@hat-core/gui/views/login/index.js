import r from '@hat-core/renderer';
import * as form from '@hat-core/common/form';


import 'login/index.scss';


export async function init() {
    await r.set('view', {
        name: '',
        password: ''
    });
}


export function vt() {
    const namePath = ['view', 'name'];
    const passwordPath = ['view', 'password'];
    return ['div.login', {
        on: {
            keyup: evt => {
                if (evt.key == 'Enter') {
                    hat.conn.login(r.get(namePath), r.get(passwordPath));
                }
            }
        }},
        ['div.grid',
            form.textInput(namePath, 'Name').slice(1),
            form.passwordInput(passwordPath, 'Password').slice(1)
        ],
        ['button', {
            on: {
                click: () => hat.conn.login(r.get(namePath), r.get(passwordPath))
            }},
            'Login'
        ]
    ];
}


export function destroy() {}
