from hat.sbs import serializer


def generate_c(repo, dir_path, file_name='sbs_defs', prefix='hat_sbs_defs'):
    """Generate C header and source files

    Args:
        repo (hat.sbs.repository.Repository): repository
        dir_path (pathlib.Path): output directory path
        file_name (str): header and source file names without suffix
        prefix (str): variable names prefix

    """
    with open(dir_path / f'{file_name}.h', 'w', encoding='utf-8') as f_h:
        with open(dir_path / f'{file_name}.c', 'w', encoding='utf-8') as f_c:
            f_h.write('// clang-format off\n'
                      f'#ifndef {prefix.upper()}_H\n'
                      f'#define {prefix.upper()}_H\n\n'
                      '#include <hat/sbs.h>\n\n'
                      '#ifdef __cplusplus\n'
                      'extern "C" {\n'
                      '#endif\n\n\n')
            f_c.write('// clang-format off\n'
                      f'#include "{file_name}.h"\n\n\n')
            for type_ref, type_def in repo._refs.items():
                name = _c_ref_to_name(prefix, type_ref)
                f_c.write(f'hat_sbs_def_t static_{name};\n')
            for type_ref, type_def in repo._refs.items():
                name = _c_ref_to_name(prefix, type_ref)
                value = _c_def_to_value(repo, prefix, type_def)
                f_c.write(f'hat_sbs_def_t static_{name} = {value};\n')
            for type_ref in repo._refs.keys():
                name = _c_ref_to_name(prefix, type_ref)
                f_h.write(f'extern hat_sbs_def_t *{name};\n')
                f_c.write(f'hat_sbs_def_t *{name} = &static_{name};\n')
            f_h.write('\n\n'
                      '#ifdef __cplusplus\n'
                      '}\n'
                      '#endif\n\n'
                      '#endif\n')


def _c_def_to_value(repo, prefix, t):
    if isinstance(t, serializer.Ref):
        name = _c_ref_to_name(prefix, t)
        return ('{.type = HAT_SBS_DEF_TYPE_USER,'
                ' .user = {.def = &static_' + name + '}}')
    if isinstance(t, serializer.BooleanType):
        return ('{.type = HAT_SBS_DEF_TYPE_BUILTIN,'
                ' .builtin = '
                '{.type = HAT_SBS_TYPE_BOOLEAN, .simple_d = {.dummy = NULL}}}')
    if isinstance(t, serializer.IntegerType):
        return ('{.type = HAT_SBS_DEF_TYPE_BUILTIN,'
                ' .builtin = '
                '{.type = HAT_SBS_TYPE_INTEGER, .simple_d = {.dummy = NULL}}}')
    if isinstance(t, serializer.FloatType):
        return ('{.type = HAT_SBS_DEF_TYPE_BUILTIN,'
                ' .builtin = '
                '{.type = HAT_SBS_TYPE_FLOAT, .simple_d = {.dummy = NULL}}}')
    if isinstance(t, serializer.StringType):
        return ('{.type = HAT_SBS_DEF_TYPE_BUILTIN,'
                ' .builtin = '
                '{.type = HAT_SBS_TYPE_STRING, .simple_d = {.dummy = NULL}}}')
    if isinstance(t, serializer.BytesType):
        return ('{.type = HAT_SBS_DEF_TYPE_BUILTIN,'
                ' .builtin = '
                '{.type = HAT_SBS_TYPE_BYTES, .simple_d = {.dummy = NULL}}}')
    if isinstance(t, serializer.ArrayType):
        _def = '&((hat_sbs_def_t)' + _c_def_to_value(repo, prefix, t.t) + ')'
        return ('{.type = HAT_SBS_DEF_TYPE_BUILTIN,'
                ' .builtin = '
                '{.type = HAT_SBS_TYPE_ARRAY,'
                ' .array_d = '
                '{.def = ' + _def + ' }}}')
    if isinstance(t, serializer.TupleType):
        defs = ('((hat_sbs_def_t*[]){' +
                ', '.join('&((hat_sbs_def_t)' +
                          _c_def_to_value(repo, prefix, i) +
                          ')'
                          for _, i in t.entries) +
                '})'
                if t.entries else 'NULL')
        return ('{.type = HAT_SBS_DEF_TYPE_BUILTIN,'
                ' .builtin = '
                '{.type = HAT_SBS_TYPE_TUPLE,'
                ' .tuple_d = '
                '{.defs = ' + defs + ','
                ' .defs_len = ' + str(len(t.entries)) + '}}}')
    if isinstance(t, serializer.UnionType):
        defs = ('((hat_sbs_def_t*[]){' +
                ', '.join('&((hat_sbs_def_t)' +
                          _c_def_to_value(repo, prefix, i) +
                          ')'
                          for _, i in t.entries) +
                '})'
                if t.entries else 'NULL')
        return ('{.type = HAT_SBS_DEF_TYPE_BUILTIN,'
                ' .builtin = '
                '{.type = HAT_SBS_TYPE_UNION,'
                ' .union_d = '
                '{.defs = ' + defs + ','
                ' .defs_len = ' + str(len(t.entries)) + '}}}')
    raise ValueError()


def _c_ref_to_name(prefix, ref):
    ref_module = _c_normalize_name(ref.module or '')
    ref_name = _c_normalize_name(ref.name)
    return f'{prefix}__{ref_module}__{ref_name}'


def _c_normalize_name(name):
    return name
