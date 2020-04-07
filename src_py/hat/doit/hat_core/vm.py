from pathlib import Path, PurePosixPath, PureWindowsPath
import contextlib
import functools
import subprocess
import sys
import tempfile
import time

from hat.doit import common
from hat.doit.hat_core.cache.vm.archlinux import img_path as archlinux_img_path
from hat.doit.hat_core.cache.vm.archlinux import img_path as win10_img_path
from hat.doit.hat_core.cache.vm.key import ssh_key_path


__all__ = ['task_vm_archlinux',
           'task_vm_win10']


build_dir = Path('build/vm')


def task_vm_archlinux():
    """VM - run task in archlinux"""
    return _get_task(img_path=archlinux_img_path,
                     localtime=False,
                     user='hat',
                     cwd=PurePosixPath('~/hat'),
                     dst_dir=build_dir / 'archlinux',
                     task_dep=['cache_vm_key',
                               'cache_vm_archlinux'])


def task_vm_win10():
    """VM - run task in win10"""
    return _get_task(img_path=win10_img_path,
                     localtime=True,
                     user='User',
                     cwd=PureWindowsPath('c:\\hat'),
                     dst_dir=build_dir / 'win10',
                     task_dep=['cache_vm_key',
                               'cache_vm_win10'])


def _get_task(img_path, localtime, user, cwd, dst_dir, task_dep):
    return {'actions': [functools.partial(_run, img_path, localtime,
                                          user, cwd, dst_dir)],
            'params': [{'name': 'pip',
                        'long': 'pip',
                        'type': bool,
                        'default': False,
                        'help': 'pip install'},
                       {'name': 'get_build',
                        'long': 'get-build',
                        'type': bool,
                        'default': False,
                        'help': 'get build dir'},
                       {'name': 'get_dist',
                        'long': 'get-dist',
                        'type': bool,
                        'default': False,
                        'help': 'get dist dir'}],
            'pos_arg': 'args',
            'task_dep': task_dep}


def _run(img_path, localtime, user, cwd, dst_dir, pip, get_build, get_dist,
         args):
    with _create_tmpdir() as tmpdir:
        archive_path = tmpdir / 'archive.tar.gz'
        cmd = f'doit {" ".join(args)}'
        _create_archive(archive_path)

        with _VM(img_path, localtime, user, tmpdir) as vm:
            vm.connect()
            vm.ssh(f'rm -rf {cwd} && mkdir -p {cwd}')
            vm.scp(str(archive_path), f"{user}@127.0.0.1:'{cwd}'")
            vm.ssh(f'cd {cwd} && tar -xf {archive_path.name}')
            if pip:
                vm.ssh(f'cd {cwd} && pip -q install -r requirements.pip.txt')
            vm.ssh(f'cd {cwd} && echo ++ running && {cmd}')
            if get_build:
                dst_dir.mkdir(parents=True, exist_ok=True)
                common.rm_rf(dst_dir / 'build')
                vm.scp(f"{user}@127.0.0.1:'{cwd / 'build'}'", dst_dir,
                       recursive=True)
            if get_dist:
                dst_dir.mkdir(parents=True, exist_ok=True)
                common.rm_rf(dst_dir / 'dist')
                vm.scp(f"{user}@127.0.0.1:'{cwd / 'dist'}'", dst_dir,
                       recursive=True)


@contextlib.contextmanager
def _create_tmpdir():
    build_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(build_dir),
                                     prefix='tmp') as tmpdir:
        yield Path(tmpdir)


def _create_archive(path):
    p = subprocess.run(['git', 'stash', 'create'],
                       stdout=subprocess.PIPE,
                       check=True)
    stash_id = p.stdout.decode().strip() or 'HEAD'
    subprocess.run(['git', 'archive', '-o', str(path), stash_id],  check=True)


class _VM:

    def __init__(self, img_path, localtime, user, tmpdir):
        tmp_img_path = tmpdir / 'img.qcow2'
        subprocess.run(['qemu-img', 'create', '-q',
                        '-F', 'qcow2', '-f', 'qcow2',
                        '-b', str(img_path.resolve()),
                        str(tmp_img_path)],
                       check=True)
        self._user = user
        self._ssh_port = common.get_free_tcp_port()
        self._known_hosts_path = tmpdir / 'known_hosts'

        cmd = ['qemu-system-x86_64',
               '-cpu', 'host',
               '-hda', str(tmp_img_path),
               '-m', '2G',
               '-device', 'e1000,netdev=net0',
               '-netdev', f'user,id=net0,hostfwd=tcp::{self._ssh_port}-:22',
               '-display', 'none',
               '-nographic']
        if sys.platform == 'linux':
            cmd.append('-enable-kvm')
        if localtime:
            cmd.extend(['-rtc', 'base=localtime'])

        self._p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._p.terminate()

    def connect(self):
        for _ in range(10):
            time.sleep(5)
            with contextlib.suppress(Exception):
                self.ssh('echo ++ connected')
                break
        else:
            raise Exception("can't connect to vm guest")

    def ssh(self, cmd):
        subprocess.run(f'ssh'
                       f' -o UserKnownHostsFile={self._known_hosts_path}'
                       f' -o StrictHostKeyChecking=no'
                       f' -i {ssh_key_path}'
                       f' -p {self._ssh_port}'
                       f' {self._user}@127.0.0.1'
                       f' "{cmd}"',
                       shell=True, check=True)

    def scp(self, src, dst, recursive=False):
        subprocess.run(f'scp -q'
                       f' {"-r" if recursive else ""}'
                       f' -o UserKnownHostsFile={self._known_hosts_path}'
                       f' -o StrictHostKeyChecking=no'
                       f' -i {ssh_key_path}'
                       f' -P {self._ssh_port}'
                       f' {src} {dst}',
                       shell=True, check=True)
