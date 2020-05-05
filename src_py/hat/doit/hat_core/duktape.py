from pathlib import Path

from hat.doit import c
from hat.doit import common


__all__ = ['task_duktape',
           'task_duktape_lib',
           'task_duktape_obj',
           'task_duktape_dep']


src_dir = Path('src_c/duktape')
dst_dir = Path('build/duktape')
src_py_dir = Path('src_py')
lib_path = (dst_dir / 'duktape').with_suffix(c.lib_suffix)
src_py_lib_path = src_py_dir / 'hat/duktape' / lib_path.name


def task_duktape():
    """Duktape - build"""
    return {'actions': [(common.cp_r, [lib_path, src_py_lib_path])],
            'targets': [src_py_lib_path],
            'file_dep': [lib_path]}


def task_duktape_lib():
    """Duktape - build dynamic library"""
    return c.get_task_lib(src_dir, dst_dir, lib_path)


def task_duktape_obj():
    """Duktape - build .o files"""
    yield from c.get_task_objs(src_dir, dst_dir, cc_flags=['-fPIC'])


def task_duktape_dep():
    """Duktape - build .d files"""
    yield from c.get_task_deps(src_dir, dst_dir)
