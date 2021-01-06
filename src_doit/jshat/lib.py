from pathlib import Path
import shutil

from hat import json
from hat.doit import common


__all__ = ['task_jshat_lib_util',
           'task_jshat_lib_renderer',
           'task_jshat_lib_future',
           'task_jshat_lib_juggler']


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
                         readme_path=Path('README.hat-core.util.rst'),
                         mappings=mappings)


def task_jshat_lib_renderer():
    """JsHat library - build @hat-core/renderer"""
    def mappings():
        dst_dir = _get_dst_dir('@hat-core/renderer')
        src_js = src_dir / '@hat-core/renderer.js'
        yield src_js, dst_dir / 'index.js'

    version = common.get_version()
    return _get_task_lib(name='@hat-core/renderer',
                         desc='Hat virtual DOM renderer',
                         readme_path=Path('README.rst'),
                         mappings=mappings,
                         deps={'snabbdom': '*',
                               '@hat-core/util': f'~{version}'})


def task_jshat_lib_future():
    """JsHat library - build @hat-core/future"""
    def mappings():
        dst_dir = _get_dst_dir('@hat-core/future')
        src_js = src_dir / '@hat-core/future.js'
        yield src_js, dst_dir / 'index.js'

    return _get_task_lib(name='@hat-core/future',
                         desc='Hat async future implementation',
                         readme_path=Path('README.rst'),
                         mappings=mappings)


def task_jshat_lib_juggler():
    """JsHat library - build @hat-core/juggler"""
    def mappings():
        dst_dir = _get_dst_dir('@hat-core/juggler')
        src_js = src_dir / '@hat-core/juggler.js'
        yield src_js, dst_dir / 'index.js'

    version = common.get_version()
    return _get_task_lib(name='@hat-core/juggler',
                         desc='Hat juggler client library',
                         readme_path=Path('README.rst'),
                         mappings=mappings,
                         deps={'jiff': '*',
                               '@hat-core/util': f'~{version}'})


def _get_task_lib(name, desc, readme_path, mappings, deps={}):
    dst_dir = _get_dst_dir(name)
    src_paths = [readme_path, *(src_path for src_path, _ in mappings())]
    dst_package_path = dst_dir / 'package.json'
    dst_readme_path = dst_dir / 'README.md'
    dst_paths = [dst_package_path, dst_readme_path,
                 *(dst_path for _, dst_path in mappings())]
    return {'actions': [(common.mkdir_p, [dst_dir]),
                        f'pandoc {readme_path} -o {dst_readme_path}',
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
    version = common.get_version(common.VersionType.SEMVER)
    dst_dir = _get_dst_dir(name)
    package = {'name': name,
               'version': version,
               'description': desc,
               'homepage': 'https://github.com/hat-open/hat-core',
               'bugs': 'https://github.com/hat-open/hat-core/issues',
               'license': 'MIT',
               'main': 'index.js',
               'repository': 'hat-open/hat-core',
               'dependencies': deps}
    json.encode_file(package, dst_dir / 'package.json')
