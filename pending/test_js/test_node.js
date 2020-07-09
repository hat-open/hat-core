import assert from 'assert';

import * as n from '@hat/node';
import * as u from '@hat/util';


describe('node', function() {
    describe('findPaths', function() {
        const node1 = [
            'div#1#2.a.b',
                ['span.a.b.c#3',
                    [
                        [
                            ['div#4',
                                ['div#5'],
                                ['span#6']
                            ],
                        ],
                        ['div.b.c.d']
                    ]
                ],
                ['div'],
                [
                    ['div']
                ]
        ];
        const node2 = [node1];
        const pairs = [
            ['*',
             [ [], [1], [1, 1, 0, 0], [1, 1, 0, 0, 1], [1, 1, 0, 0, 2], [1, 1, 1], [2], [3, 0] ]],
            ['div',
             [ [], [1, 1, 0, 0], [1, 1, 0, 0, 1], [1, 1, 1], [2], [3, 0] ]],
            ['* *',
             [ [1], [1, 1, 0, 0], [1, 1, 0, 0, 1], [1, 1, 0, 0, 2], [1, 1, 1], [2], [3, 0] ]],
            ['div div',
             [ [1, 1, 0, 0], [1, 1, 0, 0, 1], [1, 1, 1], [2], [3, 0] ]],
            ['div div div',
             [ [1, 1, 0, 0, 1] ]],
            ['div div div div',
             [ ]],
            ['div > div',
             [ [1, 1, 0, 0, 1], [2], [3, 0] ]],
            ['div div > span',
             [ [1, 1, 0, 0, 2] ]],
            ['div > span > div',
             [  [1, 1, 0, 0], [1, 1, 1] ]],
            ['div, span',
             [ [], [1], [1, 1, 0, 0], [1, 1, 0, 0, 1], [1, 1, 0, 0, 2], [1, 1, 1], [2], [3, 0] ]],
            ['span, div span',
             [ [1], [1, 1, 0, 0, 2] ]],
            ['div#1',
             [ [] ]],
            ['div#1#2#3',
             [ ]],
            ['div#1.a',
             [ [] ]],
            ['.a.b',
             [ [], [1] ]],
            ['#4 > *',
             [ [1, 1, 0, 0, 1], [1, 1, 0, 0, 2] ]],
            ['div:first-child',
             [ [], [1, 1, 0, 0], [1, 1, 0, 0, 1] ]],
            ['div:nth-child(2)',
             [ [2],  [1, 1, 1] ]],
            ['div:first-of-type',
             [ [], [2], [1, 1, 0, 0], [1, 1, 0, 0, 1] ]],
            ['div:first-child > span',
             [ [1], [1, 1, 0, 0, 2] ]]
        ];
        for (let pair of pairs) {
            it('should be true for selector "' + pair[0] + '" and path ' + JSON.stringify(pair[1]),
               function () {
                   assert.deepStrictEqual(new Set(n.findPaths(pair[0], node1)),
                                          new Set(pair[1]));
               });
        }
        for (let pair of pairs) {
            it('should be true for selector "' + pair[0] + '" and path ' + JSON.stringify(u.map(u.concat([0]), pair[1])),
               function() {
                   assert.deepStrictEqual(new Set(n.findPaths(pair[0], node2)),
                                          new Set(u.map(u.concat([0]), pair[1])));
               });
        }
    });
});
