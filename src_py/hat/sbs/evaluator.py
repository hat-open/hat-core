import typing

from hat.sbs import common
from hat.sbs import parser


def evaluate_modules(modules: typing.Iterable[parser.AstModule]
                     ) -> typing.Dict[common.Ref, common.Type]:
    """Evaluate modules."""
    refs = dict(_builtin_refs)
    modules_dict = {module.name: module for module in modules}
    for module in modules_dict.values():
        for ast_type_def in module.type_defs.values():
            if ast_type_def.args:
                continue
            ref = common.Ref(module.name, ast_type_def.name)
            refs[ref] = _resolve_ref(modules_dict, ref, [])
    return refs


def _resolve_ref(modules_dict, ref, args):
    if ref in _builtin_arg_refs:
        ast_type_def = _builtin_arg_refs[ref]
    else:
        ast_type_def = modules_dict[ref.module].type_defs[ref.name]

    if len(args) != len(ast_type_def.args):
        raise Exception("number of arguments doesn't match type definition")

    mappings = dict(zip((common.Ref(None, arg)
                         for arg in ast_type_def.args),
                        args))
    return _resolve_type(modules_dict, ref.module, ast_type_def.type, mappings)


def _resolve_type(modules_dict, module, ast_type, mappings):
    ref = common.Ref(ast_type.module, ast_type.name)
    args = [_resolve_type(modules_dict, module, arg, mappings)
            for arg in ast_type.args]
    entries = [(entry.name,
                _resolve_type(modules_dict, module, entry.type, mappings))
               for entry in ast_type.entries]

    if ref in mappings:
        if args:
            raise Exception("supstituted types dont support arguments")
        return mappings[ref]

    if ref in _builtin_refs:
        if args:
            raise Exception("simple builtin types dont have arguments")
        return ref

    if ref in _builtin_arg_refs:
        return _resolve_ref(modules_dict, ref, args)

    if ref == common.Ref(None, 'Array'):
        if len(args) != 1:
            raise Exception('Array requires one argument')
        return common.ArrayType(args[0])

    if ref == common.Ref(None, 'Tuple'):
        return common.TupleType(entries)

    if ref == common.Ref(None, 'Union'):
        return common.UnionType(entries)

    if not ref.module:
        ref = ref._replace(module=module)

    if not args:
        return ref

    return _resolve_ref(modules_dict, ref, args)


_builtin_refs = {common.Ref(None, 'Boolean'): common.BooleanType(),
                 common.Ref(None, 'Integer'): common.IntegerType(),
                 common.Ref(None, 'Float'): common.FloatType(),
                 common.Ref(None, 'String'): common.StringType(),
                 common.Ref(None, 'Bytes'): common.BytesType(),
                 common.Ref(None, 'None'): common.TupleType([])}


_builtin_arg_refs = {
    common.Ref(None, 'Maybe'): parser.AstTypeDef(
        name='Maybe',
        args=['a'],
        type=parser.AstType(
            module=None,
            name='Union',
            entries=[
                parser.AstEntry(
                    name='Nothing',
                    type=parser.AstType(
                        module=None,
                        name='Tuple',
                        entries=[],
                        args=[])),
                parser.AstEntry(
                    name='Just',
                    type=parser.AstType(
                        module=None,
                        name='a',
                        entries=[],
                        args=[]))],
            args=[]))
}
