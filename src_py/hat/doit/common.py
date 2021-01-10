from pathlib import Path
import datetime
import enum
import functools
import itertools
import os
import shutil
import subprocess
import sys

import mako.lookup
import mako.template
import packaging.version


now = datetime.datetime.now()


def mkdir_p(*paths):
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


def rm_rf(*paths):
    for path in paths:
        p = Path(path)
        if not p.exists():
            continue
        if p.is_dir():
            shutil.rmtree(str(p), ignore_errors=True)
        else:
            p.unlink()


def cp_r(src, dest):
    src = Path(src)
    dest = Path(dest)
    if src.is_dir():
        shutil.copytree(str(src), str(dest))
    else:
        shutil.copy2(str(src), str(dest))


class StaticWebServer:

    def __init__(self, dir, port):
        self._p = subprocess.Popen([sys.executable,
                                    '-m', 'http.server',
                                    '-b', '127.0.0.1',
                                    '-d', str(dir),
                                    str(port)],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._p.terminate()


class VersionType(enum.Enum):
    SEMVER = 0
    PIP = 1


@functools.lru_cache
def get_version(version_type=VersionType.SEMVER):
    with open('VERSION', encoding='utf-8') as f:
        version = f.read().strip()

    if version.endswith('dev'):
        version += now.strftime("%Y%m%d")

    if version_type == VersionType.SEMVER:
        return version

    elif version_type == VersionType.PIP:
        return packaging.version.Version(version).public

    raise ValueError()


def mako_build(tmpl_dir, src_path, dst_path, params):
    tmpl_lookup = mako.lookup.TemplateLookup(directories=[str(tmpl_dir)],
                                             input_encoding='utf-8')
    tmpl_uri = tmpl_lookup.filename_to_uri(str(src_path))
    tmpl = tmpl_lookup.get_template(tmpl_uri)
    output = tmpl.render(**params)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(output)


class SphinxOutputType(enum.Enum):
    HTML = 'html'
    LATEX = 'latex'


def sphinx_build(out_type, src, dest):
    mkdir_p(dest)
    subprocess.run([sys.executable, '-m', 'sphinx', '-q', '-b', out_type.value,
                    str(src), str(dest)],
                   check=True)


def latex_build(src, dest):
    mkdir_p(dest)
    for i in src.glob('*.tex'):
        subprocess.run(['xelatex', '-interaction=batchmode',
                        f'-output-directory={dest.resolve()}', i.name],
                       cwd=src, stdout=subprocess.DEVNULL, check=True)


if sys.platform == 'win32':
    lib_suffix = '.dll'
elif sys.platform == 'darwin':
    lib_suffix = '.dylib'
else:
    lib_suffix = '.so'

cpp = os.environ.get('CPP', 'cpp')
cc = os.environ.get('CC', 'cc')
ld = os.environ.get('LD', 'cc')


class CBuild:

    def __init__(self, src_paths, src_dir, build_dir, *,
                 cpp=cpp, cc=cc, ld=ld,
                 cpp_flags=[], cc_flags=[], ld_flags=[],
                 libs=[]):
        self._src_paths = src_paths
        self._src_dir = src_dir
        self._build_dir = build_dir
        self._cpp = cpp
        self._cc = cc
        self._ld = ld
        self._cpp_flags = cpp_flags
        self._cc_flags = cc_flags
        self._ld_flags = ld_flags

    def get_task_lib(self, lib_path):
        obj_paths = [self._get_obj_path(src_path)
                     for src_path in self._src_paths]
        shared_flag = '-mdll' if sys.platform == 'win32' else '-shared'
        return {'actions': [(mkdir_p, [lib_path.parent]),
                            [ld, *[str(obj_path) for obj_path in obj_paths],
                             '-o', str(lib_path), shared_flag,
                             *self._ld_flags]],
                'file_dep': obj_paths,
                'targets': [lib_path]}

    def get_task_objs(self):
        for src_path in self._src_paths:
            dep_path = self._get_dep_path(src_path)
            obj_path = self._get_obj_path(src_path)
            header_paths = self._parse_dep(dep_path)
            yield {'name': str(obj_path),
                   'actions': [(mkdir_p, [obj_path.parent]),
                               [cc, *self._cpp_flags, *self._cc_flags, '-c',
                                '-o', str(obj_path), str(src_path)]],
                   'file_dep': [src_path, dep_path, *header_paths],
                   'targets': [obj_path]}

    def get_task_deps(self):
        for src_path in self._src_paths:
            dep_path = self._get_dep_path(src_path)
            yield {'name': str(dep_path),
                   'actions': [(mkdir_p, [dep_path.parent]),
                               [cpp, *self._cpp_flags, '-MM',
                                '-o', str(dep_path), str(src_path)]],
                   'file_dep': [src_path],
                   'targets': [dep_path]}

    def _get_dep_path(self, src_path):
        return (self._build_dir /
                src_path.relative_to(self._src_dir)).with_suffix('.d')

    def _get_obj_path(self, src_path):
        return (self._build_dir /
                src_path.relative_to(self._src_dir)).with_suffix('.o')

    def _parse_dep(self, path):
        if not path.exists():
            return []
        with open(path, 'r') as f:
            content = f.readlines()
        if not content:
            return []
        content[0] = content[0][content[0].find(':')+1:]
        return list(itertools.chain.from_iterable(
            (Path(path) for path in i.replace(' \\\n', '').strip().split(' '))
            for i in content))
