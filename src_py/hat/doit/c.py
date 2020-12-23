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


def get_task_lib(lib_path, src_paths, src_dir, build_dir, *,
                 ld=ld, ld_flags=[], libs=[]):
    obj_paths = [_get_obj_path(src_path, src_dir, build_dir)
                 for src_path in src_paths]
    shared_flag = '-mdll' if sys.platform == 'win32' else '-shared'
    return {'actions': [(common.mkdir_p, [lib_path.parent]),
                        [ld, *[str(obj_path) for obj_path in obj_paths],
                         '-o', str(lib_path), shared_flag, *ld_flags, *libs]],
            'file_dep': obj_paths,
            'targets': [lib_path]}


def get_task_objs(src_paths, src_dir, build_dir, *,
                  cc=cc, cpp_flags=[], cc_flags=[]):
    for src_path in src_paths:
        dep_path = _get_dep_path(src_path, src_dir, build_dir)
        obj_path = _get_obj_path(src_path, src_dir, build_dir)
        header_paths = _parse_dep(dep_path)
        yield {'name': str(obj_path),
               'actions': [(common.mkdir_p, [obj_path.parent]),
                           [cc, *cpp_flags, *cc_flags, '-c',
                            '-o', str(obj_path), str(src_path)]],
               'file_dep': [src_path, dep_path, *header_paths],
               'targets': [obj_path]}


def get_task_deps(src_paths, src_dir, build_dir, *,
                  cpp=cpp, cpp_flags=[]):
    for src_path in src_paths:
        dep_path = _get_dep_path(src_path, src_dir, build_dir)
        yield {'name': str(dep_path),
               'actions': [(common.mkdir_p, [dep_path.parent]),
                           [cpp, *cpp_flags, '-MM', '-o', str(dep_path),
                            str(src_path)]],
               'file_dep': [src_path],
               'targets': [dep_path]}


def _get_dep_path(src_path, src_dir, build_dir):
    return (build_dir / src_path.relative_to(src_dir)).with_suffix('.d')


def _get_obj_path(src_path, src_dir, build_dir):
    return (build_dir / src_path.relative_to(src_dir)).with_suffix('.o')


def _parse_dep(path):
    if not path.exists():
        return []
    with open(path, 'r') as f:
        content = f.readlines()
    content[0] = content[0][content[0].find(':')+1:]
    return list(itertools.chain.from_iterable(
        (Path(path) for path in i.replace(' \\\n', '').strip().split(' '))
        for i in content))
