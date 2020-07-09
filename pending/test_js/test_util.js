import assert from 'assert';

import * as u from '@hat/util';


describe('util', function() {

    describe('identity', function() {
        it('should return same object', function() {
            const inputs = [1, 'asdfasd', null, undefined, true, {}];
            for (let input of inputs)
                assert.strictEqual(u.identity(input), input);
        });
    });

    describe('isArray', function() {
        it('should be true for []', function() {
            assert.strictEqual(u.isArray([]), true);
        });
        it('should be true for [1, 2, 3]', function() {
            assert.strictEqual(u.isArray([1, 2, 3]), true);
        });
        it('should be false for {}', function() {
            assert.strictEqual(u.isArray({}), false);
        });
        it('should be false for 1', function() {
            assert.strictEqual(u.isArray(1), false);
        });
        it('should be false for null', function() {
            assert.strictEqual(u.isArray(null), false);
        });
        it('should be false for undefined', function() {
            assert.strictEqual(u.isArray(undefined), false);
        });
    });

    describe('isObject', function() {
        it('should be true for {}', function() {
            assert.strictEqual(u.isObject({}), true);
        });
        it('should be true for {a: []}', function() {
            assert.strictEqual(u.isObject({a: []}), true);
        });
        it('should be false for []', function() {
            assert.strictEqual(u.isObject([]), false);
        });
        it('should be false for 1', function() {
            assert.strictEqual(u.isObject(1), false);
        });
        it('should be false for null', function() {
            assert.strictEqual(u.isObject(null), false);
        });
        it('should be false for undefined', function() {
            assert.strictEqual(u.isObject(undefined), false);
        });
    });

    describe('union', function() {
        it('should be [1, 2, 3] for [1, 2] U [2, 3]', function() {
            assert.deepStrictEqual(
                u.union([1, 2], [2, 3]),
                [1, 2, 3]);
        });
        it('should be [[], [1], [1, 2], [3, 4]] ' +
            'for[[], [1], [1, 2]] U [[1, 2], [], [3, 4]]', function() {
            assert.deepStrictEqual(
                u.union([[], [1], [1, 2]], [[1, 2], [], [3, 4]]),
                [[], [1], [1, 2], [3, 4]]);
        });
    });

});
