
import r from '@hat-core/renderer';
import * as u from '@hat-core/util';


export const textInput = (path, label, validator) => textInputWithRenderer(r, path, label, validator);
export const passwordInput = (path, label, validator) => passwordInputWithRenderer(r, path, label, validator);
export const enableableTextInput = (enablePath, valuePath, label, validator) => enableableTextInputWithRenderer(r, enablePath, valuePath, label, validator);
export const checkboxInput = (path, label) => checkboxInputWithRenderer(r, path, label);
export const selectInput = (path, label, values) => selectInputWithRenderer(r, path, label, values);
export const enableableSelectInput = (enablePath, valuePath, label, values) => enableableSelectInputWithRenderer(r, enablePath, valuePath, label, values);


export function textInputWithRenderer(r, path, label, validator) {
    return inputWithRenderer(r, 'text', false, [], path, label, validator);
}


export function passwordInputWithRenderer(r, path, label, validator) {
    return inputWithRenderer(r, 'password', false, [], path, label, validator);
}


export function enableableTextInputWithRenderer(r, enablePath, valuePath, label, validator) {
    return inputWithRenderer(r, 'text', true, enablePath, valuePath, label, validator);
}


export function checkboxInputWithRenderer(r, path, label) {
    return ['label',
        ['input', {
            props: {
                type: 'checkbox',
                checked: r.get(path)
            },
            on: {
                change: evt => r.set(path, evt.target.checked)
            }}
        ],
        ' ' + label
    ];
}


export function selectInputWithRenderer(r, path, label, values) {
    return selectWithRenderer(r, false, [], path, label, values);
}


export function enableableSelectInputWithRenderer(r, enablePath, valuePath, label, values) {
    return selectWithRenderer(r, true, enablePath, valuePath, label, values);
}


export function notEmptyValidator(value) {
    if (!value)
        return 'invalid value';
}


export function floatValidator(value) {
    const floatValue = u.strictParseFloat(value);
    if (!Number.isFinite(floatValue))
        return 'not valid number';
}


export function integerValidator(value) {
    const intValue = u.strictParseInt(value);
    if (!Number.isFinite(intValue))
        return 'not valid number';
}


export function tcpPortValidator(value) {
    const intValue = u.strictParseInt(value);
    if (!Number.isFinite(intValue) || intValue < 0 || intValue > 0xFFFF)
        return 'not valid TCP port';
}


export function createChainValidator(...validators) {
    return value => {
        for (let validator of validators) {
            let result = validator(value);
            if (result)
                return result;
        }
    };
}


export function createUniqueValidator() {
    const values = new Set();
    return value => {
        if (values.has(value))
            return 'duplicate value';
        values.add(value);
    };
}


function inputWithRenderer(r, type, showEnable, enablePath, valuePath, label, validator) {
    const enabled = showEnable ? r.get(enablePath) : true;
    const value = r.get(valuePath);
    const title = (validator ? validator(value) : null);
    return ['div',
        ['label',
            (!showEnable ? [] :
                ['input', {
                    props: {
                        type: 'checkbox',
                        checked: enabled
                    },
                    on: {
                        change: evt => r.set(enablePath, evt.target.checked),
                    }}
                ]),
            (showEnable ? ' ' : '') + label
        ],
        ['input', {
            class: {
                invalid: title
            },
            props: {
                type: type,
                title: (title ? title : ''),
                value: value,
                disabled: !enabled
            },
            on: {
                change: evt => r.set(valuePath, evt.target.value)
            }},
        ]
    ];
}


function selectWithRenderer(r, showEnable, enablePath, valuePath, label, values) {
    const enabled = showEnable ? r.get(enablePath) : true;
    const selectedValue = r.get(valuePath);
    const invalid = values.find(
        i => u.equals(selectedValue, (u.isArray(i) ? i[0] : i))) === undefined;
    const allValues = (invalid ? u.append(selectedValue, values) : values);
    return ['div',
        ['label',
            (!showEnable ? [] :
                ['input', {
                    props: {
                        type: 'checkbox',
                        checked: enabled
                    },
                    on: {
                        change: evt => r.set(enablePath, evt.target.checked)
                    }}
                ]),
            (showEnable ? ' ' : '') + label
        ],
        ['select', {
            class: {
                invalid: invalid
            },
            props: {
                disabled: !enabled,
            },
            on: {
                change: evt => r.set(valuePath, evt.target.value)
            }},
            allValues.map(i => {
                const value = (u.isArray(i) ? i[0] : i);
                const label = (u.isArray(i) ? i[1] : i);
                return ['option', {
                    props: {
                        selected: selectedValue == value,
                        value: value
                    }},
                    label
                ];
            })
        ]
    ];
}
