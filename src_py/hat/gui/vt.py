"""Virtual tree XML parser"""

import xml.sax
import xml.sax.handler


def parse(file):
    r"""Parse XML document into virtual tree

    Each element is recursively parsed into a list with the following
    structure, starting from the root of a document:

        * First item is a valid CSS selector string, consisting of element tag
          name; and optionally `id` and `class` attributes if present.

        * If the element has attributes other than `id` or `class`, they are
          stored as a second item. The item is a dictionary which has an
          `attrs` key, whose value is another dictionary, with key-value pairs
          representing attribute names and their values, respectively.

        * All other items are element content. Each item is either a
          recursively parsed element child (a list), or text (a string).

    Resulting structure is JSON serializable.

    Namespace prefix declaration attributes (`xmlns:*`) are ignored.

    Example usage::

        import io
        import hat.gui.vt

        xml = '''\
            <html>
                <body>
                    <div id="first" class="c1 c2">
                        Banana
                    </div>
                    Orange
                    <br/>
                    <span id="second" style="color:green">
                        Watermelon
                    </span>
                </body>
            </html>
        '''
        stripped = ''.join(line.lstrip() for line in xml.split('\n'))
        stream = io.StringIO(stripped)
        parsed = hat.gui.vt.parse(stream)

    Output::

        ['html',
            ['body',
                ['div#first.c1.c2',
                    "Banana"
                ],
                "Orange",
                ['br'],
                ['span#second',
                    {'attrs':
                        {'style': "color:green"}
                    },
                    "Watermelon"
                ]
            ]
        ]

    Args:
        file: file stream

    Returns:
        hat.json.Data: json serializable virtual tree

    """
    handler = _ContentHandler()
    parser = xml.sax.make_parser()
    parser.setContentHandler(handler)
    parser.setFeature(xml.sax.handler.feature_external_ges, False)
    parser.setFeature(xml.sax.handler.feature_external_pes, False)
    parser.parse(file)
    return handler.root


class _ContentHandler(xml.sax.ContentHandler):

    def __init__(self):
        self._root = None
        self._stack = []

    @property
    def root(self):
        return self._root

    def startElement(self, name, attrs):
        attrs = {k.split(':')[-1]: v
                 for k, v in attrs.items()
                 if not k.startswith('xmlns:')}
        attrs = dict(attrs)
        elm_id = attrs.pop('id', '')
        elm_class = '.'.join(i for i in attrs.pop('class', '').split(' ') if i)
        element = [name +
                   (f'#{elm_id}' if elm_id else '') +
                   (f'.{elm_class}' if elm_class else '')]
        if attrs:
            element.append({'attrs': attrs})
        if self._stack:
            self._stack[-1].append(element)
        else:
            self._root = element
        self._stack.append(element)

    def endElement(self, name):
        self._stack.pop()

    def characters(self, content):
        self._stack[-1].append(content)
