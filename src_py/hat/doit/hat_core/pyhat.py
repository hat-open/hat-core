from pathlib import Path
import datetime
import platform
import shutil
import sys

import packaging.version

from hat.doit import common
from hat.doit.hat_core.duktape import lib_path as duktape_lib_path
from hat.doit.hat_core.pymod import sqlite3_mod_path


__all__ = ['task_pyhat_util',
           'task_pyhat_peg',
           'task_pyhat_sbs',
           'task_pyhat_chatter',
           'task_pyhat_juggler',
           'task_pyhat_duktape',
           'task_pyhat_sqlite3',
           'task_pyhat_drivers']


build_dir = Path('build/pyhat')
src_json_dir = Path('schemas_json')
src_sbs_dir = Path('schemas_sbs')
src_py_dir = Path('src_py')


def task_pyhat_clean():
    """PyHat - clean"""
    return {'actions': [(common.rm_rf, [build_dir])]}


def task_pyhat_util():
    """PyHat - build hat-util"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-util')
        for i in (src_py_dir / 'hat/util').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        src_json = src_json_dir / 'logging.yaml'
        yield src_json, (dst_dir / 'hat/schemas_json'
                                 / src_json.relative_to(src_json_dir))

    return _get_task_build(name='hat-util',
                           description='Hat utility modules',
                           dependencies=['pyyaml',
                                         'jsonschema',
                                         'jsonpatch'],
                           mappings=mappings)


def task_pyhat_peg():
    """PyHat - build hat-peg"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-peg')
        src_py = src_py_dir / 'hat/peg.py'
        yield src_py, dst_dir / src_py.relative_to(src_py_dir)

    return _get_task_build(name='hat-peg',
                           description='Hat PEG parser',
                           dependencies=['hat-util'],
                           mappings=mappings)


def task_pyhat_sbs():
    """PyHat - build hat-sbs"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-sbs')
        for i in (src_py_dir / 'hat/sbs').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)

    return _get_task_build(name='hat-sbs',
                           description='Hat simple binary serializer',
                           dependencies=['hat-util',
                                         'hat-peg'],
                           mappings=mappings)


def task_pyhat_chatter():
    """PyHat - build hat-chatter"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-chatter')
        src_py = src_py_dir / 'hat/chatter.py'
        yield src_py, dst_dir / src_py.relative_to(src_py_dir)
        schemas_sbs_hat = src_sbs_dir / 'hat.sbs'
        yield schemas_sbs_hat, (dst_dir / 'hat/schemas_sbs'
                                / schemas_sbs_hat.relative_to(src_sbs_dir))
        schemas_sbs_ping = src_sbs_dir / 'hat/ping.sbs'
        yield schemas_sbs_ping, (dst_dir / 'hat/schemas_sbs'
                                 / schemas_sbs_ping.relative_to(src_sbs_dir))

    return _get_task_build(name='hat-chatter',
                           description='Hat Chatter protocol',
                           dependencies=['hat-util',
                                         'hat-sbs'],
                           mappings=mappings)


def task_pyhat_juggler():
    """PyHat - build hat-juggler"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-juggler')
        src_py = src_py_dir / 'hat/juggler.py'
        yield src_py, dst_dir / src_py.relative_to(src_py_dir)

    return _get_task_build(name='hat-juggler',
                           description='Hat Juggler protocol',
                           dependencies=['aiohttp',
                                         'hat-util'],
                           mappings=mappings)


def task_pyhat_duktape():
    """PyHat - build hat-duktape"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-duktape')
        src_py = src_py_dir / 'hat/duktape.py'
        dst_py = dst_dir / src_py.relative_to(src_py_dir)
        yield src_py, dst_py
        yield duktape_lib_path, dst_py.parent / duktape_lib_path.name

    return _get_task_build(name='hat-duktape',
                           description='Hat Python Duktape JS wrapper',
                           dependencies=[],
                           mappings=mappings,
                           platform_specific=True,
                           task_dep=['duktape'])


def task_pyhat_sqlite3():
    """PyHat - build hat-sqlite3"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-sqlite3')

        src_py = src_py_dir / 'hat/sqlite3.py'
        dst_py = dst_dir / src_py.relative_to(src_py_dir)
        yield src_py, dst_py

        dst_lib = dst_dir / sqlite3_mod_path.relative_to(src_py_dir)
        yield sqlite3_mod_path, dst_lib

    return _get_task_build(name='hat-sqlite3',
                           description='Hat Sqlite3 build',
                           dependencies=[],
                           mappings=mappings,
                           platform_specific=True,
                           task_dep=['pymod_sqlite3'])


def task_pyhat_drivers():
    """PyHat - build hat-drivers"""
    def mappings():
        dst_dir = _get_build_dst_dir('hat-drivers')
        for i in (src_py_dir / 'hat/drivers').rglob('*.py'):
            yield i, dst_dir / i.relative_to(src_py_dir)
        for i in (src_json_dir / 'drivers').rglob('*.yaml'):
            yield i, (dst_dir / 'hat/schemas_json'
                              / i.relative_to(src_json_dir))

    return _get_task_build(name='hat-drivers',
                           description='Hat communication drivers',
                           dependencies=['pyserial',
                                         'hat-util'],
                           mappings=mappings)


def _get_task_build(name, description, dependencies, mappings, *,
                    console_scripts=[], gui_scripts=[],
                    platform_specific=False, task_dep=[]):
    dst_dir = _get_build_dst_dir(name)
    setup_path = dst_dir / 'setup.py'
    manifest_path = dst_dir / 'MANIFEST.in'
    src_paths = list(src_path for src_path, _ in mappings())
    dst_paths = [setup_path] + list(dst_path for _, dst_path in mappings())
    return {'actions': [(common.mkdir_p, [dst_dir]),
                        (_copy_files, [mappings]),
                        (_create_manifest, [manifest_path, mappings]),
                        (_create_setup_py, [setup_path, name, description,
                                            dependencies, console_scripts,
                                            gui_scripts, platform_specific])],
            'file_dep': src_paths,
            'targets': dst_paths,
            'task_dep': task_dep}


def _get_build_dst_dir(name):
    return build_dir / name


def _copy_files(mappings):
    for src_path, dst_path in mappings():
        if not dst_path.parent.exists():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(src_path), str(dst_path))


def _create_setup_py(path, name, description, dependencies, console_scripts,
                     gui_scripts, platform_specific):
    plat_name = _get_plat_name() if platform_specific else 'any'
    version = _get_version()
    readme = _get_readme()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"from setuptools import setup\n\n\n"
                f"readme = r\"\"\"\n{readme}\n\"\"\"\n\n"
                f"setup(name={repr(name)},\n"
                f"      version={repr(version)},\n"
                f"      description={repr(description)},\n"
                f"      long_description=readme,\n"
                f"      long_description_content_type='text/x-rst',\n"
                f"      url='https://github.com/hat-open/hat-core',\n"
                f"      packages=['hat'],\n"
                f"      include_package_data=True,\n"
                f"      install_requires={repr(dependencies)},\n"
                f"      python_requires='>=3.8',\n"
                f"      classifiers=[\n"
                f"          'Programming Language :: Python :: 3',\n"
                f"          'License :: OSI Approved :: MIT License',\n"
                f"      ],\n"
                f"      options={{\n"
                f"          'bdist_wheel': {{\n"
                f"              'python_tag': 'cp38',\n"
                f"              'py_limited_api': 'cp38',\n"
                f"              'plat_name': '{plat_name}'\n"
                f"          }}\n"
                f"      }},\n"
                f"      entry_points={{\n"
                f"          'console_scripts': {repr(console_scripts)},\n"
                f"          'gui_scripts': {repr(gui_scripts)}\n"
                f"      }})\n")


def _create_manifest(path, mappings):
    with open(path, 'w', encoding='utf-8') as f:
        for _, i in mappings():
            f.write(f"include {i.relative_to(path.parent)}\n")


def _get_plat_name():
    arch, _ = platform.architecture()
    if sys.platform == 'win32' and arch == '32bit':
        return 'win32'
    if sys.platform == 'win32' and arch == '64bit':
        return 'win_amd64'
    if sys.platform == 'linux' and arch == '64bit':
        return 'manylinux1_x86_64'
    if sys.platform == 'darwin' and arch == '64bit':
        return 'macosx_10_13_x86_64'
    raise NotImplementedError()


def _get_version():
    with open('VERSION', encoding='utf-8') as f:
        version_str = f.read().strip()
    if version_str.endswith('dev'):
        version_str += datetime.datetime.now().strftime("%Y%m%d")
    version = packaging.version.Version(version_str)
    return version.public


def _get_readme():
    with open('README.rst', encoding='utf-8') as f:
        return f.read().strip()
