r"""PEG Parser

Implementation of PEG parser as described in paper "Parsing Expression
Grammars: A Recognition-Based Syntactic Foundation" (Bryan Ford, 2004).
PEG's grammar itself can be defined by PEG grammar::

    # Hierarchical syntax
    Grammar    <- Spacing Definition+ EndOfFile
    Definition <- Identifier LEFTARROW Expression
    Expression <- Sequence (SLASH Sequence)*
    Sequence   <- Prefix*
    Prefix     <- (AND / NOT)? Suffix
    Suffix     <- Primary (QUESTION / STAR / PLUS)?
    Primary    <- Identifier !LEFTARROW
                / OPEN Expression CLOSE
                / Literal
                / Class
                / DOT

    # Lexical syntax
    Identifier <- IdentStart IdentCont* Spacing
    IdentStart <- [a-zA-Z_]
    IdentCont  <- IdentStart / [0-9]
    Literal    <- ['] (!['] Char)* ['] Spacing
                / ["] (!["] Char)* ["] Spacing
    Class      <- '[' (!']' Range)* ']' Spacing
    Range      <- Char '-' Char / Char
    Char       <- '\\' [nrt'"\[\]\\]
                / '\\' 'x' Hex Hex
                / !'\\' .
    Hex        <- [0-9a-fA-F]

    LEFTARROW  <- '<-' Spacing
    SLASH      <- '/' Spacing
    AND        <- '&' Spacing
    NOT        <- '!' Spacing
    QUESTION   <- '?' Spacing
    STAR       <- '*' Spacing
    PLUS       <- '+' Spacing
    OPEN       <- '(' Spacing
    CLOSE      <- ')' Spacing
    DOT        <- '.' Spacing

    Spacing    <- (Space / Comment)*
    Comment    <- '#' (!EndOfLine .)* EndOfLine
    Space      <- ' ' / '\t' / EndOfLine
    EndOfLine  <- '\r\n' / '\n' / '\r'
    EndOfFile  <- !.

Example usage of PEG parser::

    import functools
    import hat.peg

    grammar = hat.peg.Grammar(r'''
        Expr    <- Sum
        Sum     <- Product (('+' / '-') Product)*
        Product <- Value (('*' / '/') Value)*
        Value   <- Spacing ([0-9]+ / '(' Expr ')') Spacing
        Spacing <- ' '*
    ''', 'Expr')
    ast = grammar.parse('1 + 2 * 3 + (4 - 5) * 6 + 7')
    result = hat.peg.walk_ast(ast, {
        'Expr': lambda n, c: c[0],
        'Sum': lambda n, c: functools.reduce(
            (lambda acc, x: acc + x[1] if x[0] == '+' else acc - x[1]),
            zip(c[1::2], c[2::2]),
            c[0]),
        'Product': lambda n, c: functools.reduce(
            (lambda acc, x: acc * x[1] if x[0] == '*' else acc / x[1]),
            zip(c[1::2], c[2::2]),
            c[0]),
        'Value': lambda n, c: (c[2] if c[1] == '(' else
                               int(''.join(c[1:-1])))})
    assert result == 8

"""

import collections.abc
import functools
import typing

from hat import util


Data = typing.Union[str, bytes]


Node = util.namedtuple(
    ['Node', """Abstract syntax tree node.

    Node names are identifiers of parser's definitions and values
    are other nodes or Data representing matched `Literal`, `Class` or
    `Dot` leafs.

    """],
    ['name', 'str: node name (production definition identifier)'],
    ['value', 'List[Union[Node,Data]]: subnodes or leafs'])


def walk_ast(node, actions, default_action=None):
    """Simple depth-first abstract syntax tree parser.

    Actions are key value pairs where keys represent node names and values
    are callables that should be called for appropriate node. Each callable
    receives matched node and list of results from recursively applying
    this function on child nodes. For nodes which name doesn't match any
    action, default action is used. If default action is not defined,
    callable ``lambda node, children: None`` is assumed.

    Args:
        actions (Dict[str,Callable[[Node,List[Any]],Any]]): actions
        default_action (Optional[Callable[[Node,List[Any]],Any]]):
            default action

    """
    default_action = default_action or (lambda n, c: None)
    action = actions.get(node.name, default_action)
    children = [walk_ast(i, actions, default_action)
                if isinstance(i, Node) else i
                for i in node.value]
    return action(node, children)


class Grammar:
    """PEG Grammar.

    Args:
        definitions (Union[str,Dict[str,Expression]]): grammar definitions
        starting (str): starting definition name

    """

    def __init__(self, definitions, starting):
        if isinstance(definitions, str):
            data = definitions.encode('utf-8')
            ast = _peg_grammar.parse(data)
            definitions = walk_ast(ast, _peg_actions)
            definitions = {k: _reduce_expression(v)
                           for k, v in definitions.items()}
        self._definitions = definitions
        self._starting = starting

    @property
    def definitions(self):
        """Dict[str,Expression]: definitions"""
        return self._definitions

    @property
    def starting(self):
        """str: starting definition name"""
        return self._starting

    def parse(self, data, debug_cb=None):
        """Parse input data.

        `debug_cb` is optional function which can be used for monitoring and
        debugging parse steps. It is called each time named definition
        is successfully or unsuccessfully matched. This function receives
        match result and match call stack.

        Args:
            data (Data): input data
            debug_cb (Optional[Callable[[MatchResult,MatchCallStack],None]]):
                debug callback

        Returns:
            Node

        Raises:
            Exception

        """
        if isinstance(data, str):
            data_fn = functools.partial(str, encoding='utf-8')
            data = data.encode('utf-8')
        else:
            data_fn = bytes
        state = _State(grammar=self,
                       data=memoryview(data),
                       call_stack=_MatchCallStack(None, None),
                       data_fn=data_fn,
                       debug_cb=debug_cb)
        result = _match(state, self._starting)
        if result.node is None:
            raise Exception("could not match starting definition")
        x = _reduce_node(data_fn, result.node)
        return x


Sequence = util.namedtuple('Sequence', ['expressions', 'List[Expression]'])
Choice = util.namedtuple('Choice', ['expressions', 'List[Expression]'])
Not = util.namedtuple('Not', ['expression', 'Expression'])
And = util.namedtuple('And', ['expression', 'Expression'])
OneOrMore = util.namedtuple('OneOrMore', ['expression', 'Expression'])
ZeroOrMore = util.namedtuple('ZeroOrMore', ['expression', 'Expression'])
Optional = util.namedtuple('Optional', ['expression', 'Expression'])
Identifier = util.namedtuple('Identifier', ['value', 'str'])
Literal = util.namedtuple('Literal', ['value', 'bytes'])
Class = util.namedtuple('Class', ['values', 'List[Union[int,Tuple[int,int]]]'])
Dot = util.namedtuple('Dot')
Expression = typing.Union[Sequence, Choice, Not, And, OneOrMore, ZeroOrMore,
                          Optional, Identifier, Literal, Class, Dot]


MatchResult = util.namedtuple(
    'MatchResult',
    ['node', 'Optional[Node]: None if match failed'],
    ['rest', 'Data: remaining input data'])


MatchCallFrame = util.namedtuple(
    'MatchCallFrame',
    ['name', 'str: definition name'],
    ['data', 'Data: input data'])


MatchCallStack = typing.Iterable[MatchCallFrame]


def console_debug_cb(result, call_stack):
    """Simple console debugger.

    Args:
        result (MatchResult): match result
        call_stack (MatchCallStack): match call stack

    """
    success = '+++' if result.node else '---'
    stack = ', '.join(frame.name for frame in call_stack)
    consumed = util.first(call_stack).data[:-len(result.rest)]
    print(success, stack)
    print('<<<', consumed)
    print('>>>', result.rest, flush=True)


class _MatchCallStack(util.namedtuple('_MatchCallStack', 'frame', 'previous')):

    def __iter__(self):
        current = self
        while current and current.frame:
            yield current.frame
            current = current.previous


_State = util.namedtuple('_State', 'grammar', 'data', 'call_stack',
                         'data_fn', 'debug_cb')


def _match(state, name):
    call_frame = MatchCallFrame(name, state.data)
    if call_frame in state.call_stack:
        raise Exception('Infinite matching recursion detected')
    state = state._replace(
        call_stack=_MatchCallStack(call_frame, state.call_stack))
    result = _match_expression(state, state.grammar.definitions[name])
    if result.node:
        result = result._replace(
            node=result.node._replace(name=name))
    if state.debug_cb:
        debug_result = MatchResult(
            node=(_reduce_node(state.data_fn, result.node)
                  if result.node else None),
            rest=state.data_fn(result.rest))
        debug_call_stack = [i._replace(data=state.data_fn(i.data))
                            for i in state.call_stack]
        state.debug_cb(debug_result, debug_call_stack)
    return result


def _match_expression(state, expression):
    t = type(expression)
    if t == Choice:
        return _match_choice(state, expression)
    if t == Sequence:
        return _match_sequence(state, expression)
    if t == Not:
        return _match_not(state, expression)
    if t == And:
        return _match_and(state, expression)
    if t == OneOrMore:
        return _match_oneormore(state, expression)
    if t == ZeroOrMore:
        return _match_zeroormore(state, expression)
    if t == Optional:
        return _match_optional(state, expression)
    if t == Identifier:
        return _match_identifier(state, expression)
    if t == Literal:
        return _match_literal(state, expression)
    if t == Class:
        return _match_class(state, expression)
    if t == Dot:
        return _match_dot(state, expression)
    raise ValueError('unsupported expression type')


def _match_choice(state, expression):
    for i in expression.expressions:
        result = _match_expression(state, i)
        if result.node:
            return result
    return MatchResult(None, state.data)


def _match_sequence(state, expression):
    nodes = []
    for i in expression.expressions:
        result = _match_expression(state, i)
        if not result.node:
            return MatchResult(None, state.data)
        nodes.append(result.node)
        state = state._replace(data=result.rest)
    return MatchResult(Node(None, nodes), state.data)


def _match_not(state, expression):
    result = _match_expression(state, expression.expression)
    return (MatchResult(None, state.data) if result.node
            else MatchResult(Node(None, []), state.data))


def _match_and(state, expression):
    node = _match_expression(state, expression.expression).node
    return MatchResult(Node(None, []) if node else None, state.data)


def _match_oneormore(state, expression):
    return _match_expression(state, Sequence([
        expression.expression,
        ZeroOrMore(expression.expression)]))


def _match_zeroormore(state, expression):
    nodes = []
    while True:
        result = _match_expression(state, expression.expression)
        if not result.node:
            return MatchResult(Node(None, nodes), state.data)
        nodes.append(result.node)
        state = state._replace(data=result.rest)


def _match_optional(state, expression):
    result = _match_expression(state, expression.expression)
    if result.node:
        return result
    return MatchResult(Node(None, []), state.data)


def _match_identifier(state, expression):
    result = _match(state, expression.value)
    if result.node:
        result = result._replace(node=Node(None, [result.node]))
    return result


def _match_literal(state, expression):
    data = state.data[:len(expression.value)]
    if data != expression.value:
        return MatchResult(None, state.data)
    rest = state.data[len(expression.value):]
    return MatchResult(Node(None, [data]), rest)


def _match_class(state, expression):
    if state.data:
        for i in expression.values:
            if isinstance(i, collections.abc.Sequence):
                matched = i[0] <= state.data[0] <= i[1]
            else:
                matched = state.data[0] == i
            if matched:
                return MatchResult(Node(None, [state.data[:1]]),
                                   state.data[1:])
    return MatchResult(None, state.data)


def _match_dot(state, expression):
    if not state.data:
        return MatchResult(None, state.data)
    return MatchResult(Node(None, [state.data[:1]]), state.data[1:])


def _reduce_expression(expr):
    if hasattr(expr, 'expressions'):
        if len(expr.expressions) == 1:
            return _reduce_expression(expr.expressions[0])
        return expr._replace(expressions=[_reduce_expression(i)
                                          for i in expr.expressions])
    if hasattr(expr, 'expression'):
        return expr._replace(expression=_reduce_expression(expr.expression))
    return expr


def _reduce_node(data_fn, node):
    return node._replace(value=list(_reduce_node_list(data_fn, node.value)))


def _reduce_node_list(data_fn, nodes):
    for node in nodes:
        if not isinstance(node, Node):
            yield data_fn(node)
        elif node.name is None:
            yield from _reduce_node_list(data_fn, node.value)
        else:
            yield _reduce_node(data_fn, node)


_peg_grammar = Grammar({
    'Grammar': Sequence([
        Identifier('Spacing'),
        OneOrMore(Identifier('Definition')),
        Identifier('EndOfFile')]),
    'Definition': Sequence([
        Identifier('Identifier'),
        Identifier('LEFTARROW'),
        Identifier('Expression')]),
    'Expression': Sequence([
        Identifier('Sequence'),
        ZeroOrMore(Sequence([
            Identifier('SLASH'),
            Identifier('Sequence')]))]),
    'Sequence': ZeroOrMore(Identifier('Prefix')),
    'Prefix': Sequence([
        Optional(Choice([
            Identifier('AND'),
            Identifier('NOT')])),
        Identifier('Suffix')]),
    'Suffix': Sequence([
        Identifier('Primary'),
        Optional(Choice([
            Identifier('QUESTION'),
            Identifier('STAR'),
            Identifier('PLUS')]))]),
    'Primary': Choice([
        Sequence([
            Identifier('Identifier'),
            Not(Identifier('LEFTARROW'))]),
        Sequence([
            Identifier('OPEN'),
            Identifier('Expression'),
            Identifier('CLOSE')]),
        Identifier('Literal'),
        Identifier('Class'),
        Identifier('DOT')]),
    'Identifier': Sequence([
        Identifier('IdentStart'),
        ZeroOrMore(Identifier('IdentCont')),
        Identifier('Spacing')]),
    'IdentStart': Class([(ord('a'), ord('z')),
                         (ord('A'), ord('Z')),
                         ord('_')]),
    'IdentCont': Choice([
        Identifier('IdentStart'),
        Class([(ord('0'), ord('9'))])]),
    'Literal': Choice([
        Sequence([
            Class([ord("'")]),
            ZeroOrMore(Sequence([
                Not(Class([ord("'")])),
                Identifier('Char')])),
            Class([ord("'")]),
            Identifier('Spacing')]),
        Sequence([
            Class([ord('"')]),
            ZeroOrMore(Sequence([
                Not(Class([ord('"')])),
                Identifier('Char')])),
            Class([ord('"')]),
            Identifier('Spacing')])]),
    'Class': Sequence([
        Literal(b'['),
        ZeroOrMore(Sequence([
            Not(Literal(b']')),
            Identifier('Range')])),
        Literal(b']'),
        Identifier('Spacing')]),
    'Range': Choice([
        Sequence([
            Identifier('Char'),
            Literal(b'-'),
            Identifier('Char')]),
        Identifier('Char')]),
    'Char': Choice([
        Sequence([
            Literal(b'\\'),
            Class([ord('n'), ord('r'), ord('t'), ord("'"), ord('"'),
                   ord('['), ord(']'), ord('\\')])]),
        Sequence([
            Literal(b'\\'),
            Literal(b'x'),
            Identifier('Hex'),
            Identifier('Hex')]),
        Sequence([
            Not(Literal(b'\\')),
            Dot()])]),
    'Hex': Class([(ord('0'), ord('9')),
                  (ord('a'), ord('f')),
                  (ord('A'), ord('F'))]),
    'LEFTARROW': Sequence([
        Literal(b'<-'),
        Identifier('Spacing')]),
    'SLASH': Sequence([
        Literal(b'/'),
        Identifier('Spacing')]),
    'AND': Sequence([
        Literal(b'&'),
        Identifier('Spacing')]),
    'NOT': Sequence([
        Literal(b'!'),
        Identifier('Spacing')]),
    'QUESTION': Sequence([
        Literal(b'?'),
        Identifier('Spacing')]),
    'STAR': Sequence([
        Literal(b'*'),
        Identifier('Spacing')]),
    'PLUS': Sequence([
        Literal(b'+'),
        Identifier('Spacing')]),
    'OPEN': Sequence([
        Literal(b'('),
        Identifier('Spacing')]),
    'CLOSE': Sequence([
        Literal(b')'),
        Identifier('Spacing')]),
    'DOT': Sequence([
        Literal(b'.'),
        Identifier('Spacing')]),
    'Spacing': ZeroOrMore(Choice([
        Identifier('Space'),
        Identifier('Comment')])),
    'Comment': Sequence([
        Literal(b'#'),
        ZeroOrMore(Sequence([
            Not(Identifier('EndOfLine')),
            Dot()])),
        Identifier('EndOfLine')]),
    'Space': Choice([
        Literal(b' '),
        Literal(b'\t'),
        Identifier('EndOfLine')]),
    'EndOfLine': Choice([
        Literal(b'\r\n'),
        Literal(b'\n'),
        Literal(b'\r')]),
    'EndOfFile': Not(Dot())
}, 'Grammar')


_peg_actions = {
    'Grammar': lambda n, c: {k: v for k, v in filter(bool, c)},
    'Definition': lambda n, c: (c[0].value, c[2]),
    'Expression': lambda n, c: Choice(list(c[::2])),
    'Sequence': lambda n, c: Sequence(c),
    'Prefix': lambda n, c: (c[0] if len(c) == 1 else
                            c[0](c[1])),
    'Suffix': lambda n, c: (c[0] if len(c) == 1 else
                            c[1](c[0])),
    'Primary': lambda n, c: (c[1] if c[0] is None else
                             c[0]),
    'Identifier': lambda n, c: Identifier(str(b''.join(c[:-1]),
                                              encoding='utf-8')),
    'IdentStart': lambda n, c: c[0],
    'IdentCont': lambda n, c: c[0],
    'Literal': lambda n, c: Literal(bytes(c[1:-2])),
    'Class': lambda n, c: Class(c[1:-2]),
    'Range': lambda n, c: (c[0] if len(c) == 1 else
                           (c[0], c[2])),
    'Char': lambda n, c: (c[0][0] if c[0] != b'\\' else
                          ord('\n') if c[1] == b'n' else
                          ord('\r') if c[1] == b'r' else
                          ord('\t') if c[1] == b't' else
                          ord("'") if c[1] == b"'" else
                          ord('"') if c[1] == b'"' else
                          ord('[') if c[1] == b'[' else
                          ord(']') if c[1] == b']' else
                          ord('\\') if c[1] == b'\\' else
                          int(b''.join(c[2:]), 16)),
    'Hex': lambda n, c: c[0],
    'AND': lambda n, c: And,
    'NOT': lambda n, c: Not,
    'QUESTION': lambda n, c: Optional,
    'STAR': lambda n, c: ZeroOrMore,
    'PLUS': lambda n, c: OneOrMore,
    'DOT': lambda n, c: Dot()
}
