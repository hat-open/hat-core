import PIL.ImageFont

from hat import peg


def parse(fonts_path, definitions, starting, delimiter, data):
    grammar = peg.Grammar(definitions, starting, delimiter)
    definitions = _definitions_to_json(grammar.definitions)
    if data:
        debugger = _Debugger(fonts_path)
        grammar.parse(data, debugger.step)
        results = debugger.results
        text_size = debugger.text_size
    else:
        results = []
        text_size = {}
    return {'definitions': definitions,
            'results': results,
            'text_size': text_size}


class _Debugger:

    def __init__(self, fonts_path):
        self._results = []
        self._text_size = {}
        self._font = PIL.ImageFont.truetype(
            font=str(fonts_path / 'RobotoMono/RobotoMono-Regular.ttf'),
            size=10)

    @property
    def results(self):
        return self._results

    @property
    def text_size(self):
        return self._text_size

    def step(self, result, data, call_stack):
        if not result.node or not result.node.name:
            return
        self._results.append({
            'ast': self._node_to_json(result.node.reduce()),
            'data': {'input': data,
                     'parsed': (data[:-len(result.data)] if result.data
                                else data),
                     'remaining': result.data},
            'call_stack': [i.name for i in call_stack]})

    def _node_to_json(self, node):
        if not isinstance(node, peg.Node):
            text = repr(node)[1:-1]
            self._calculate_text_size(text)
            return text
        text = node.name
        self._calculate_text_size(text)
        return {'name': text,
                'value': [self._node_to_json(i) for i in node.value]}

    def _calculate_text_size(self, text):
        if text in self._text_size:
            return
        self._text_size[text] = list(self._font.getsize(text))


def _definitions_to_json(definitions):
    return {k: _expression_to_json(v) for k, v in definitions.items()}


def _expression_to_json(expression):
    if not isinstance(expression, peg.Expression):
        return expression
    result = {'type': type(expression).__name__,
              'value': []}
    if result['type'] in {'Sequence', 'Choice'}:
        result['value'] = [_expression_to_json(i)
                           for i in expression.expressions]
    elif result['type'] in {'Not', 'And', 'OneOrMore', 'ZeroOrMore',
                            'Optional'}:
        result['value'] = [_expression_to_json(expression.expression)]
    elif result['type'] in {'PlainStr', 'RegExStr', 'Identifier'}:
        result['value'] = expression.value
    return result
