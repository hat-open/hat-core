from pathlib import Path
import contextlib
import subprocess
import sys
import tempfile

from hat import util
from hat.doit import common

from .key import authorized_keys_path


__all__ = ['task_cache_vm_win10',
           'task_cache_vm_win10_run']


win10_url = 'https://aka.ms/windev_VM_virtualbox'

cache_dir = Path('cache/vm')
zip_path = cache_dir / 'win10.zip'
img_path = cache_dir / 'win10.qcow2'

ssh_port = 5555
http_port = 8088


def task_cache_vm_win10():
    r"""Cache VM win10 - create image

    After task finishes, user should execute `doit cache_vm_win10_run --save`
    and inside VM:
        * download 'http://10.0.2.100/win10_init.ps1'
        * in admin cmd execute:
            powershell -executionpolicy bypass C:\Users\User\Downloads\win10_init.ps1

    """  # NOQA
    def create():
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['wget', '--show-progress', '-q', '-c',
                        '-O', str(zip_path), str(win10_url)],
                       check=True)

        with _create_tmpdir() as tmpdir:
            subprocess.run(['unzip', '-q', str(zip_path.resolve())],
                           cwd=str(tmpdir),
                           check=True)

            ova_path = util.first(tmpdir.glob('*.ova'))
            subprocess.run(['tar', '-x', '-f', str(ova_path.resolve())],
                           cwd=str(tmpdir),
                           check=True)

            vmdk_path = util.first(tmpdir.glob('*.vmdk'))
            subprocess.run(['qemu-img', 'convert', '-f', 'vmdk', '-O', 'qcow2',
                            str(vmdk_path), str(img_path)],
                           check=True)

    return {'actions': [create],
            'uptodate': [img_path.exists]}


def task_cache_vm_win10_run():
    """Cache VM win10 - run image with GUI"""
    hostfwd = f'tcp::{ssh_port}-:22'
    guestfwd = f'tcp:10.0.2.100:80-cmd:nc 127.0.0.1 {http_port}'
    netdev = f'user,id=net0,hostfwd={hostfwd},guestfwd={guestfwd}'

    def run(save):
        with _create_tmpdir() as tmpdir:
            shared_dir = tmpdir / 'share'
            _init_shared_dir(shared_dir)

            if save:
                tmp_img_path = img_path
            else:
                tmp_img_path = tmpdir / 'img.qcow2'
                subprocess.run(['qemu-img', 'create', '-q',
                                '-F', 'qcow2', '-f', 'qcow2',
                                '-b', str(img_path.resolve()),
                                str(tmp_img_path)],
                               check=True)

            with common.StaticWebServer(shared_dir, http_port):
                subprocess.run(['qemu-system-x86_64'] +
                               (['-enable-kvm'] if sys.platform == 'linux'
                                else []) +
                               ['-cpu', 'host',
                                '-hda', str(tmp_img_path),
                                '-m', '2G',
                                '-device', 'e1000,netdev=net0',
                                '-netdev', netdev,
                                '-usb',
                                '-device', 'usb-tablet',
                                '-rtc', 'base=localtime'],
                               check=True)

    return {'actions': [run],
            'params': [{'name': 'save',
                        'default': False,
                        'long': 'save',
                        'type': bool,
                        'help': 'save changes to disk image'}],
            'task_dep': ['cache_vm_key',
                         'cache_vm_win10']}


@contextlib.contextmanager
def _create_tmpdir():
    with tempfile.TemporaryDirectory(dir=str(cache_dir),
                                     prefix='tmp') as tmpdir:
        yield Path(tmpdir)


def _init_shared_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    for k, v in _shared_files.items():
        if isinstance(v, Path):
            common.cp_r(v, path / k)
        else:
            with open(path / k, 'w', encoding='utf-8') as f:
                f.write(v)


_shared_files = {
    'authorized_keys': authorized_keys_path,
    'requirements.pip.txt': Path('requirements.pip.txt'),
    'requirements.msys2.txt': Path('requirements.msys2.txt'),
    'package.json': Path('package.json'),

    'win10_sshd_config': r"""
PermitUserEnvironment yes
AuthorizedKeysFile .ssh/authorized_keys
Subsystem sftp sftp-server.exe
""",

    'environment': "Path={}".format(';'.join([
        r"C:\Windows\System32\OpenSSH",
        r"C:\Python38",
        r"C:\Python38\Scripts",
        r"C:\msys64\mingw64\bin",
        r"C:\msys64\usr\bin",
        r"C:\Windows\system32",
        r"C:\Windows",
        r"C:\Windows\System32\Wbem",
        r"C:\Windows\System32\WindowsPowerShell\v1.0",
        r"C:\Program Files\dotnet",
        r"C:\nodejs",
        r"C:\Yarn\bin"
    ])),

    'win10_init.ps1': r"""
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False
Set-MpPreference -DisableRealtimeMonitoring $true
Set-Service -Name wuauserv -StartupType Disabled

$wc = New-Object System.Net.WebClient
$wc.DownloadFile("http://10.0.2.100/win10_sshd_config",
                 "c:\\Users\\User\\Downloads\\sshd_config")
$wc.DownloadFile("http://10.0.2.100/authorized_keys",
                 "c:\\Users\\User\\Downloads\\authorized_keys")
$wc.DownloadFile("http://10.0.2.100/environment",
                 "c:\\Users\\User\\Downloads\\environment")
$wc.DownloadFile("http://10.0.2.100/requirements.pip.txt",
                 "c:\\Users\\User\\Downloads\\requirements.pip.txt")
$wc.DownloadFile("http://10.0.2.100/requirements.msys2.txt",
                 "c:\\Users\\User\\Downloads\\requirements.msys2.txt")
$wc.DownloadFile("http://10.0.2.100/package.json",
                 "c:\\Users\\User\\Downloads\\package.json")
$wc.DownloadFile("https://www.python.org/ftp/python/3.8.9/python-3.8.9-amd64.exe",
                 "c:\\Users\\User\\Downloads\\python-3.8.9-amd64.exe")
$wc.DownloadFile("https://repo.msys2.org/distrib/x86_64/msys2-x86_64-20210228.exe",
                 "c:\\Users\\User\\Downloads\\msys2-x86_64-20210228.exe")
$wc.DownloadFile("https://nodejs.org/dist/v14.16.1/node-v14.16.1-x64.msi",
                 "c:\\Users\\User\\Downloads\\node-v14.16.1-x64.msi")
$wc.DownloadFile("https://yarnpkg.com/latest.msi",
                 "c:\\Users\\User\\Downloads\\yarn.msi")

New-Item -ItemType Directory c:\ProgramData\ssh
New-Item -ItemType Directory c:\Users\User\.ssh
Copy-Item -Force -Path c:\Users\User\Downloads\sshd_config -Destination c:\ProgramData\ssh\
Copy-Item -Force -Path c:\Users\User\Downloads\authorized_keys -Destination c:\Users\User\.ssh\
Copy-Item -Force -Path c:\Users\User\Downloads\environment -Destination c:\Users\User\.ssh\
Copy-Item -Force -Path c:\Users\User\Downloads\package.json -Destination c:\Users\User\

Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Set-Service -Name sshd -StartupType Automatic
Start-Service -Name sshd

$env:Path = "C:\Windows\System32\OpenSSH;C:\Python38;C:\Python38\Scripts;C:\msys64\mingw64\bin;C:\msys64\usr\bin;" + $env:Path
$env:Path += ";C:\nodejs;C:\Yarn\bin"
[Environment]::SetEnvironmentVariable(
    "Path", $env:Path, [System.EnvironmentVariableTarget]::Machine)

cmd /C "c:\Users\User\Downloads\python-3.8.9-amd64.exe InstallAllUsers=1 TargetDir=c:\Python38 /passive"
cmd /C "c:\Users\User\Downloads\node-v14.16.1-x64.msi INSTALLDIR=C:\nodejs /passive"
cmd /C "c:\Users\User\Downloads\yarn.msi INSTALLDIR=c:\Yarn /passive"

cmd /C "pip install -r c:\Users\User\Downloads\requirements.pip.txt"
cmd /C "cd c:\Users\User && yarn install"

cmd /C "c:\Users\User\Downloads\msys2-x86_64-20210228.exe install -c --root c:\msys64"
cmd.exe /C "pacman -Syu --noconfirm"
cmd.exe /C "pacman -Syu --noconfirm"
c:\msys64\usr\bin\bash -c "pacman -S --noconfirm \$(< c:/Users/User/Downloads/requirements.msys2.txt)"

"""  # NOQA
}
