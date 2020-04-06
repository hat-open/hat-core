from pathlib import Path
import itertools
import os
import sys

from hat.doit import common


if sys.platform == 'win32':
    lib_suffix = '.dll'
elif sys.platform == 'darwin':
    lib_suffix = '.dylib'
else:
    lib_suffix = '.so'

cpp = os.environ.get('CPP', 'cpp')
cc = os.environ.get('CC', 'cc')
ld = os.environ.get('LD', 'cc')


def get_task_lib(src_dir, dep_dir, lib, *, ld=ld, ld_flags=[], libs=[]):
    objs = [_get_obj_path(src_dir, dep_dir, src)
            for src in src_dir.rglob('*.c')]
    objs_str = list(map(str, objs))
    shared_flag = '-mdll' if sys.platform == 'win32' else '-shared'
    return {'actions': [(common.mkdir_p, [lib.parent]),
                        [ld] + objs_str + ['-o', str(lib), shared_flag] +
                        ld_flags + libs],
            'file_dep': objs,
            'targets': [lib]}


def get_task_objs(src_dir, dep_dir, *, cc=cc, cpp_flags=[], cc_flags=[]):
    for src in src_dir.rglob('*.c'):
        dep = _get_dep_path(src_dir, dep_dir, src)
        obj = _get_obj_path(src_dir, dep_dir, src)
        headers = _parse_dep(dep)
        yield {'name': str(obj),
               'actions': [(common.mkdir_p, [obj.parent]),
                           [cc] + cpp_flags + cc_flags +
                           ['-c', '-o', str(obj), str(src)]],
               'file_dep': [src, dep] + headers,
               'targets': [obj]}


def get_task_deps(src_dir, dep_dir, *, cpp=cpp, cpp_flags=[]):
    for src in src_dir.rglob('*.c'):
        dep = _get_dep_path(src_dir, dep_dir, src)
        yield {'name': str(dep),
               'actions': [(common.mkdir_p, [dep.parent]),
                           [cpp] + cpp_flags +
                           ['-MM', '-o', str(dep), str(src)]],
               'file_dep': [src],
               'targets': [dep]}


def _get_dep_path(src_dir, dep_dir, src):
    return (dep_dir / src.relative_to(src_dir)).with_suffix('.d')


def _get_obj_path(src_dir, dep_dir, src):
    return (dep_dir / src.relative_to(src_dir)).with_suffix('.o')


def _parse_dep(dep):
    if not dep.exists():
        return []
    with open(dep, 'r') as f:
        content = f.readlines()
    content[0] = content[0][content[0].find(':')+1:]
    return list(itertools.chain.from_iterable(
        (Path(path) for path in i.replace(' \\\n', '').strip().split(' '))
        for i in content))
