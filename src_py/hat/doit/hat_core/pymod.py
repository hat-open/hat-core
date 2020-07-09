from pathlib import Path
import sys

from hat.doit import c
from hat.doit import common


__all__ = ['task_pymod',
           'task_pymod_sqlite3',
           'task_pymod_sqlite3_lib',
           'task_pymod_sqlite3_obj',
           'task_pymod_sqlite3_dep']


sqlite3_src_dir = Path('src_c')
sqlite3_dst_dir = Path('build/pymod/_sqlite3')
sqlite3_src_paths = [*(sqlite3_src_dir / 'sqlite3').rglob('*.c'),
                     *(sqlite3_src_dir / 'pymod/_sqlite3').rglob('*.c')]
sqlite3_lib_path = (sqlite3_dst_dir / '_sqlite3').with_suffix(
    '.pyd' if sys.platform == 'win32' else '.so')
sqlite3_mod_path = Path('src_py/hat/sqlite3') / sqlite3_lib_path.name

sqlite3_cpp_flags = ['-DMODULE_NAME="_sqlite3"',
                     f"-I{sqlite3_src_dir / 'sqlite3'}"]
sqlite3_cc_flags = ['-fPIC', '-O2', '-Wno-return-local-addr']
sqlite3_ld_flags = []

if sys.platform == 'linux':
    sqlite3_cpp_flags += ['-I/usr/include/python3.8']
elif sys.platform == 'darwin':
    python_dir = Path(sys.executable).parent.parent
    python_version = f'{sys.version_info.major}.{sys.version_info.minor}'
    conf_path = f"lib/python{python_version}/config-{python_version}-darwin/"
    sqlite3_ld_flags += [f"-L{python_dir / conf_path}",
                         "-lpython3.8"]
elif sys.platform == 'win32':
    python_dir = Path(sys.executable).parent
    sqlite3_cpp_flags += [f"-I{python_dir / 'include'}"]
    sqlite3_ld_flags += [f"-L{python_dir / 'libs'}",
                         "-lpython38"]


def task_pymod():
    """Python module - build all"""
    return {'actions': None,
            'task_dep': ['pymod_sqlite3']}


def task_pymod_sqlite3():
    """Python module - sqlite3"""
    return {'actions': [(common.cp_r, [sqlite3_lib_path,
                                       sqlite3_mod_path])],
            'file_dep': [sqlite3_lib_path],
            'targets': [sqlite3_mod_path]}


def task_pymod_sqlite3_lib():
    """Python module - build sqlite3 dynamic library"""
    return c.get_task_lib(
        sqlite3_lib_path, sqlite3_src_paths, sqlite3_src_dir, sqlite3_dst_dir,
        ld_flags=sqlite3_ld_flags)


def task_pymod_sqlite3_obj():
    """Python module - build sqlite3 .o files"""
    yield from c.get_task_objs(
        sqlite3_src_paths, sqlite3_src_dir, sqlite3_dst_dir,
        cpp_flags=sqlite3_cpp_flags, cc_flags=sqlite3_cc_flags)


def task_pymod_sqlite3_dep():
    """Python module - build sqlite3 .d files"""
    yield from c.get_task_deps(
        sqlite3_src_paths, sqlite3_src_dir, sqlite3_dst_dir,
        cpp_flags=sqlite3_cpp_flags)
