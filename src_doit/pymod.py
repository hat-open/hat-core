from pathlib import Path
import sys
import sysconfig

from hat.doit import common


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
    if sys.platform == 'linux':
        return []

    elif sys.platform == 'darwin':
        python_version = f'{sys.version_info.major}.{sys.version_info.minor}'
        stdlib_path = (Path(sysconfig.get_path('stdlib')) /
                       f'config-{python_version}-darwin')
        return [f"-L{stdlib_path}",
                f"-lpython{python_version}"]

    elif sys.platform == 'win32':
        data_path = sysconfig.get_path('data')
        python_version = f'{sys.version_info.major}{sys.version_info.minor}'
        return [f"-L{data_path}",
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
sqlite3_mod_path = (Path('src_py/hat/sqlite3') /
                    f'{sqlite3_mod_name}{mod_suffix}')
sqlite3_build = common.CBuild(
    src_paths=[*(src_dir / 'sqlite3').rglob('*.c'),
               *(src_dir / 'pymod/sqlite3').rglob('*.c')],
    src_dir=src_dir,
    build_dir=build_dir / 'sqlite3',
    cpp_flags=[*cpp_flags,
               f'-DMODULE_NAME="{sqlite3_mod_name}"',
               f"-I{src_dir / 'sqlite3'}"],
    cc_flags=[*cc_flags,
              '-Wno-return-local-addr'],
    ld_flags=ld_flags)


sbs_mod_name = '_cserializer'
sbs_mod_path = Path('src_py/hat/sbs') / f'{sbs_mod_name}{mod_suffix}'
sbs_build = common.CBuild(
    src_paths=[src_dir / 'hat/sbs.c',
               *(src_dir / 'pymod/sbs').rglob('*.c')],
    src_dir=src_dir,
    build_dir=build_dir / 'sbs',
    cpp_flags=[*cpp_flags,
               f'-DMODULE_NAME="{sbs_mod_name}"',
               f"-I{src_dir}"],
    cc_flags=cc_flags,
    ld_flags=ld_flags)


def task_pymod():
    """Python module - build all"""
    return {'actions': None,
            'task_dep': ['pymod_sqlite3',
                         'pymod_sbs']}


def task_pymod_sqlite3():
    """Python module - build sqlite3 dynamic library"""
    return sqlite3_build.get_task_lib(sqlite3_mod_path)


def task_pymod_sqlite3_obj():
    """Python module - build sqlite3 .o files"""
    yield from sqlite3_build.get_task_objs()


def task_pymod_sqlite3_dep():
    """Python module - build sqlite3 .d files"""
    yield from sqlite3_build.get_task_deps()


def task_pymod_sbs():
    """Python module - build sbs dynamic library"""
    return sbs_build.get_task_lib(sbs_mod_path)


def task_pymod_sbs_obj():
    """Python module - build sbs .o files"""
    yield from sbs_build.get_task_objs()


def task_pymod_sbs_dep():
    """Python module - build sbs .d files"""
    yield from sbs_build.get_task_deps()
