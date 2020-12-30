from pathlib import Path
import sys
import sysconfig

from hat.doit import c


__all__ = ['task_pymod',
           'task_pymod_sqlite3',
           'task_pymod_sqlite3_obj',
           'task_pymod_sqlite3_dep',
           'task_pymod_sbs',
           'task_pymod_sbs_obj',
           'task_pymod_sbs_dep']


def _get_cpp_flags():
    include_path = sysconfig.get_path('include')

    if sys.platform == 'linux':
        return [f'-I{include_path}']

    elif sys.platform == 'darwin':
        return []

    elif sys.platform == 'win32':
        return [f'-I{include_path}']

    raise Exception('unsupported platform')


def _get_ld_flags():
    stdlib_path = sysconfig.get_path('stdlib')

    if sys.platform == 'linux':
        return []

    elif sys.platform == 'darwin':
        python_version = f'{sys.version_info.major}.{sys.version_info.minor}'
        return [f"-L{stdlib_path}",
                f"-lpython{python_version}"]

    elif sys.platform == 'win32':
        python_version = f'{sys.version_info.major}{sys.version_info.minor}'
        return [f"-L{stdlib_path}",
                f"-lpython{python_version}"]

    raise Exception('unsupported platform')


mod_suffix = '.pyd' if sys.platform == 'win32' else '.so'
src_dir = Path('src_c')
build_dir = Path('build/pymod')

cpp_flags = _get_cpp_flags()
cc_flags = ['-fPIC', '-O2']
# cc_flags = ['-fPIC', '-O0', '-ggdb']
ld_flags = _get_ld_flags()


sqlite3_mod_name = '_sqlite3'
sqlite3_build_dir = build_dir / 'sqlite3'
sqlite3_src_paths = [*(src_dir / 'sqlite3').rglob('*.c'),
                     *(src_dir / 'pymod/sqlite3').rglob('*.c')]
sqlite3_mod_path = (Path('src_py/hat/sqlite3') /
                    f'{sqlite3_mod_name}{mod_suffix}')

sqlite3_cpp_flags = [*cpp_flags,
                     f'-DMODULE_NAME="{sqlite3_mod_name}"',
                     f"-I{src_dir / 'sqlite3'}"]
sqlite3_cc_flags = [*cc_flags,
                    '-Wno-return-local-addr']
sqlite3_ld_flags = [*ld_flags]


sbs_mod_name = '_cserializer'
sbs_build_dir = build_dir / 'sbs'
sbs_src_paths = [src_dir / 'hat/sbs.c',
                 *(src_dir / 'pymod/sbs').rglob('*.c')]
sbs_mod_path = Path('src_py/hat/sbs') / f'{sbs_mod_name}{mod_suffix}'

sbs_cpp_flags = [*cpp_flags,
                 f'-DMODULE_NAME="{sbs_mod_name}"',
                 f"-I{src_dir}"]
sbs_cc_flags = [*cc_flags]
sbs_ld_flags = [*ld_flags]


def task_pymod():
    """Python module - build all"""
    return {'actions': None,
            'task_dep': ['pymod_sqlite3',
                         'pymod_sbs']}


def task_pymod_sqlite3():
    """Python module - build sqlite3 dynamic library"""
    return c.get_task_lib(
        sqlite3_mod_path, sqlite3_src_paths, src_dir, sqlite3_build_dir,
        ld_flags=sqlite3_ld_flags)


def task_pymod_sqlite3_obj():
    """Python module - build sqlite3 .o files"""
    yield from c.get_task_objs(sqlite3_src_paths, src_dir, sqlite3_build_dir,
                               cpp_flags=sqlite3_cpp_flags,
                               cc_flags=sqlite3_cc_flags)


def task_pymod_sqlite3_dep():
    """Python module - build sqlite3 .d files"""
    yield from c.get_task_deps(sqlite3_src_paths, src_dir, sqlite3_build_dir,
                               cpp_flags=sqlite3_cpp_flags)


def task_pymod_sbs():
    """Python module - build sbs dynamic library"""
    return c.get_task_lib(
        sbs_mod_path, sbs_src_paths, src_dir, sbs_build_dir,
        ld_flags=sbs_ld_flags)


def task_pymod_sbs_obj():
    """Python module - build sbs .o files"""
    yield from c.get_task_objs(sbs_src_paths, src_dir, sbs_build_dir,
                               cpp_flags=sbs_cpp_flags,
                               cc_flags=sbs_cc_flags)


def task_pymod_sbs_dep():
    """Python module - build sbs .d files"""
    yield from c.get_task_deps(sbs_src_paths, src_dir, sbs_build_dir,
                               cpp_flags=sbs_cpp_flags)
