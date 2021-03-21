import * as juggler from '@hat-core/juggler';


let app;

export function init() {
    app = new juggler.Application('local', 'remote');
}
