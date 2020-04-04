from pathlib import Path
import datetime
import shutil

from hat.doit import common
from hat.util import json


__all__ = ['task_jshat_lib_util',
           'task_jshat_lib_renderer',
           'task_jshat_lib_future']


src_dir = Path('src_js')
build_dir = Path('build/jshat/lib')


def task_jshat_lib_util():
    """JsHat library - build @hat-core/util"""
    def mappings():
        dst_dir = _get_dst_dir('@hat-core/util')
        src_js = src_dir / '@hat-core/util.js'
        yield src_js, dst_dir / 'index.js'

    return _get_task_lib(name='@hat-core/util',
                         desc='Hat utility module',
                         mappings=mappings)


def task_jshat_lib_renderer():
    """JsHat library - build @hat-core/renderer"""
    def mappings():
        dst_dir = _get_dst_dir('@hat-core/renderer')
        src_js = src_dir / '@hat-core/renderer.js'
        yield src_js, dst_dir / 'index.js'

    return _get_task_lib(name='@hat-core/renderer',
                         desc='Hat virtual DOM renderer',
                         mappings=mappings,
                         deps={'snabbdom': '*',
                               '@hat-core/util': '*'})


def task_jshat_lib_future():
    """JsHat library - build @hat-core/future"""
    def mappings():
        dst_dir = _get_dst_dir('@hat-core/future')
        src_js = src_dir / '@hat-core/future.js'
        yield src_js, dst_dir / 'index.js'

    return _get_task_lib(name='@hat-core/future',
                         desc='Hat async future implementation',
                         mappings=mappings)


def _get_task_lib(name, desc, mappings, deps={}):
    dst_dir = _get_dst_dir(name)
    src_paths = ['README.rst', *(src_path for src_path, _ in mappings())]
    package_path = dst_dir / 'package.json'
    readme_path = dst_dir / 'README.md'
    dst_paths = [package_path, readme_path,
                 *(dst_path for _, dst_path in mappings())]
    return {'actions': [(common.mkdir_p, [dst_dir]),
                        f'pandoc README.rst -o {readme_path}',
                        (_copy_files, [mappings]),
                        (_create_package_json, [name, desc, deps])],
            'file_dep': src_paths,
            'targets': dst_paths}


def _get_dst_dir(name):
    return build_dir / name


def _copy_files(mappings):
    for src_path, dst_path in mappings():
        if not dst_path.parent.exists():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(src_path), str(dst_path))


def _create_package_json(name, desc, deps):
    version = _get_version()
    dst_dir = _get_dst_dir(name)
    package = {'name': name,
               'version': version,
               'description': desc,
               'homepage': 'https://hat-open.github.io/hat-core',
               'bugs': 'https://github.com/hat-open/hat-core/issues',
               'license': 'MIT',
               'main': 'index.js',
               'repository': 'hat-open/hat-core',
               'dependencies': deps}
    json.encode_file(package, dst_dir / 'package.json')


def _get_version():
    with open('VERSION', encoding='utf-8') as f:
        version = f.read().strip()
    if version.endswith('dev'):
        version += datetime.datetime.now().strftime("%Y%m%d")
    return version
