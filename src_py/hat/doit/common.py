from pathlib import Path
import contextlib
import shutil
import socket
import subprocess


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
        self._p = subprocess.Popen(['python',
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
