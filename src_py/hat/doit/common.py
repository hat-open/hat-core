from pathlib import Path
import contextlib
import enum
import functools
import shutil
import socket
import subprocess
import sys
import datetime

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


def get_free_tcp_port():
    with contextlib.closing(socket.socket()) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


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
def get_version(version_type=VersionType.SEMVER, timestamp_path=None):
    with open('VERSION', encoding='utf-8') as f:
        version = f.read().strip()

    if version.endswith('dev'):
        if timestamp_path:
            with open(timestamp_path, encoding='utf-8') as f:
                timestamp = datetime.datetime.fromtimestamp(float(f.read()))
        else:
            timestamp = now

        version += timestamp.strftime("%Y%m%d%H%M")

    if version_type == VersionType.SEMVER:
        return version

    elif version_type == VersionType.PIP:
        return packaging.version.Version(version).public

    raise ValueError()
