import * as u from '@hat/util';


export const state = {
    active: false,
    current: {
        x: 0,
        y: 0
    },
    previous: {
        x: 0,
        y: 0
    }
};


export const start = u.curry((evt, state) => {
    const position = getPosition(evt);
    return u.pipe(
        u.set('active', true),
        u.set('current', position),
        u.set('previous', position)
    )(state);
});


export function stop(state) {
    return u.set('active', false, state);
}


export const move = u.curry((evt, state) => {
    if (!state.active)
        return state;
    const position = getPosition(evt);
    return u.set('current', position, state);
});


export function getChange(state) {
    const {active, current, previous} = state;
    return {
        dx: active ? current.x - previous.x : 0,
        dy: active ? current.y - previous.y : 0
    };
}


function getPosition(evt) {
    return {
        x: evt.screenX,
        y: evt.screenY
    };
}
