import typing

from hat import json
import hat.peg


class AstType(typing.NamedTuple):
    module: typing.Optional[str]
    name: str
    entries: typing.List['AstEntry']
    args: typing.List['AstType']


class AstEntry(typing.NamedTuple):
    name: str
    type: AstType


class AstTypeDef(typing.NamedTuple):
    name: str
    args: typing.List[str]
    type: AstType


class AstModule(typing.NamedTuple):
    name: str
    type_defs: typing.Dict[str, AstTypeDef]


def parse(schema: str) -> AstModule:
    """Parse SBS schema"""
    ast = _grammar.parse(schema)
    return hat.peg.walk_ast(ast, _actions)


def module_to_json(module: AstModule) -> json.Data:
    """Create JSON data representation of module definition"""
    return {'name': module.name,
            'type_defs': {k: {'name': v.name,
                              'args': v.args,
                              'type': _type_to_json(v.type)}
                          for k, v in module.type_defs.items()}}


def module_from_json(data: json.Data) -> AstModule:
    """Create module definition from JSON data"""
    return AstModule(name=data['name'],
                     type_defs={k: AstTypeDef(name=v['name'],
                                              args=v['args'],
                                              type=_type_from_json(v['type']))
                                for k, v in data['type_defs'].items()})


def _type_to_json(t):
    return {'module': t.module,
            'name': t.name,
            'entries': [{'name': i.name,
                         'type': _type_to_json(i.type)}
                        for i in t.entries],
            'args': [_type_to_json(i) for i in t.args]}


def _type_from_json(data):
    return AstType(module=data['module'],
                   name=data['name'],
                   entries=[AstEntry(name=i['name'],
                                     type=_type_from_json(i['type']))
                            for i in data['entries']],
                   args=[_type_from_json(i) for i in data['args']])


_grammar = hat.peg.Grammar(r'''
    Module          <- OWS 'module' MWS Identifier TypeDefinitions OWS EOF
    TypeDefinitions <- (MWS TypeDefinition (MWS TypeDefinition)*)?
    TypeDefinition  <- Identifier OWS ArgNames? OWS '=' OWS Type

    Type            <- TSimple
                     / TArray
                     / TTuple
                     / TUnion
                     / TIdentifier
    TSimple         <- 'Boolean'
                     / 'Integer'
                     / 'Float'
                     / 'String'
                     / 'Bytes'
    TArray          <- 'Array' OWS '(' OWS Type OWS ')'
    TTuple          <- 'Tuple' OWS '{' OWS Entries? OWS '}'
    TUnion          <- 'Union' OWS '{' OWS Entries? OWS '}'
    TIdentifier     <- Identifier ('.' Identifier)? (OWS ArgTypes)?

    Entries         <- Entry (MWS Entry)*
    Entry           <- Identifier OWS ':' OWS Type

    ArgNames        <- '(' OWS Identifiers? OWS ')'
    ArgTypes        <- '(' OWS Types? OWS ')'
    Identifiers     <- Identifier (MWS Identifier)*
    Types           <- Type (MWS Type)*

    Identifier      <- [A-Za-z][A-Za-z0-9_]*

    # mandatory white-space
    MWS             <- (WS / Comment)+
    # optional white-space
    OWS             <- (WS / Comment)*

    Comment         <- '#' (!EOL .)* EOL
    WS              <- ',' / ' ' / '\t' / EOL
    EOL             <- '\r\n' / '\n' / '\r'
    EOF             <- !.
''', 'Module')


_actions = {
    'Module': lambda n, c: AstModule(name=c[3],
                                     type_defs=c[4]),
    'TypeDefinitions': lambda n, c: {c[i].name: c[i]
                                     for i in range(1, len(c), 2)},
    'TypeDefinition': lambda n, c: AstTypeDef(name=c[0],
                                              args=c[2] or [],
                                              type=c[-1]),
    'Type': lambda n, c: c[0],
    'TSimple': lambda n, c: AstType(module=None,
                                    name=c[0],
                                    entries=[],
                                    args=[]),
    'TArray': lambda n, c: AstType(module=None,
                                   name='Array',
                                   entries=[],
                                   args=[c[4]]),
    'TTuple': lambda n, c: AstType(module=None,
                                   name='Tuple',
                                   entries=c[4] or [],
                                   args=[]),
    'TUnion': lambda n, c: AstType(module=None,
                                   name='Union',
                                   entries=c[4] or [],
                                   args=[]),
    'TIdentifier': lambda n, c: AstType(module=(c[0]
                                                if len(c) > 1 and c[1] == '.'
                                                else None),
                                        name=(c[2]
                                              if len(c) > 1 and c[1] == '.'
                                              else c[0]),
                                        entries=[],
                                        args=(c[-1] if len(c) > 1 and not c[-2]
                                              else [])),
    'Entries': lambda n, c: [c[i] for i in range(0, len(c), 2)],
    'Entry': lambda n, c: AstEntry(name=c[0],
                                   type=c[-1]),
    'ArgNames': lambda n, c: c[2] or [],
    'ArgTypes': lambda n, c: c[2] or [],
    'Identifiers': lambda n, c: [c[i] for i in range(0, len(c), 2)],
    'Types': lambda n, c: [c[i] for i in range(0, len(c), 2)],
    'Identifier': lambda n, c: ''.join(c)}
