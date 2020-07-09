import * as u from '@hat/util';
import r from '@hat/renderer';
import * as mousechange from '@hat/mousechange';
import {createSvgPageState, svgPage} from '@hat/common/svg';

import {astToSvg} from '@hat/peg_browser/browser/ast';


export const defaultState = {
    selectedDefinition: null,
    definitions: {},
    selectedResult: null,
    timelineMousechange: mousechange.state,
    results: []
};


export const defaultResultState = {
    ast: [],
    astSvgPage: createSvgPageState(1, 0.5, 0.5),
    data: {
        input: '',
        parsed: '',
        remaining: ''
    },
    callStack: []
};


export function createState(data) {
    return u.pipe(
        u.set('definitions', data.definitions),
        u.set('results', data.results.map(result => u.pipe(
            u.set('ast', astToSvg(data.text_size, result.ast)),
            u.set('data', result.data),
            u.set('callStack', result.call_stack)
        )(defaultResultState)))
    )(defaultState);
}


export function onMouseLeave() {
    r.change('timelineMousechange', mousechange.stop);
}


export function onMouseUp() {
    r.change('timelineMousechange', mousechange.stop);
}


export function onMouseMove(evt) {
    r.change('timelineMousechange', mousechange.move(evt));
}


export function getSelectedDefinition() {
    return r.get('selectedDefinition');
}


export function setSelectedDefinition(definition) {
    r.set('selectedDefinition', definition);
}


export function getAllDefinitions() {
    return Object.keys(r.get('definitions'));
}


export function getDefinitionNode(definition) {
    return r.get('definitions', definition);
}


export function getSelectedResult() {
    return r.get('selectedResult') || 0;
}


export function getResultsCount() {
    return r.get('results').length;
}


export function selectPreviousResult() {
    const selectedResult = getSelectedResult();
    r.set('selectedResult', Math.max(0, selectedResult - 1));
}


export function selectNextResult() {
    const selectedResult = getSelectedResult();
    const resultsCount = getResultsCount();
    r.set('selectedResult', Math.min(resultsCount - 1, selectedResult + 1));
}


export function timelineSliderMarkMouseDown(evt) {
    // TODO
    evt;
}


export function getCallStack() {
    const selectedResult = getSelectedResult();
    return r.get('results', selectedResult, 'callStack') || [];
}


export function getData(dataType) {
    const selectedResult = getSelectedResult();
    return r.get('results', selectedResult, 'data', dataType) || '';
}


export function getAst() {
    const selectedResult = getSelectedResult();
    const svg = r.get('results', selectedResult, 'ast') || [];
    return svgPage(['results', selectedResult, 'astSvgPage'], svg);
}
