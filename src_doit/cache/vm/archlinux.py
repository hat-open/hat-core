from pathlib import Path
import subprocess
import sys
import contextlib
import tempfile

from hat.doit import common

from .key import authorized_keys_path


__all__ = ['task_cache_vm_archlinux',
           'task_cache_vm_archlinux_run']


archlinux_url = 'http://archlinux.iskon.hr/iso/2020.02.01/archlinux-2020.02.01-x86_64.iso'  # NOQA

cache_dir = Path('cache/vm')
iso_path = cache_dir / 'archlinux.iso'
img_path = cache_dir / 'archlinux.qcow2'

ssh_port = 5555
http_port = 8088


def task_cache_vm_archlinux():
    """Cache VM archlinux - create image"""
    hostfwd = f'tcp::{ssh_port}-:22'
    guestfwd = f'tcp:10.0.2.100:80-cmd:nc 127.0.0.1 {http_port}'
    netdev = f'user,id=net0,hostfwd={hostfwd},guestfwd={guestfwd}'

    def create():
        iso_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['wget', '--show-progress', '-q', '-c',
                        '-O', str(iso_path), str(archlinux_url)],
                       check=True)

        subprocess.run(['qemu-img', 'create', '-f', 'qcow2',
                        str(img_path), '20G'],
                       check=True)

        with _create_tmpdir() as tmpdir:
            shared_dir = tmpdir / 'shared'
            _init_shared_dir(shared_dir)

            tmp_iso_path = tmpdir / iso_path.name
            syslinux_cfg_path = tmpdir / 'archiso_sys.cfg'
            iso_syslinux_cfg_path = 'arch/boot/syslinux/archiso_sys.cfg'
            common.cp_r(iso_path, tmp_iso_path)
            _iso_extract(tmp_iso_path, iso_syslinux_cfg_path,
                         syslinux_cfg_path)
            with open(syslinux_cfg_path, encoding='utf-8') as f:
                syslinux_cfg = f.readlines()
            syslinux_cfg = ['DEFAULT arch64\n'] + syslinux_cfg[2:-2]
            syslinux_cfg[-1] = (syslinux_cfg[-1].strip() + ' script=' +
                                'http://10.0.2.100/archlinux_init.sh\n')
            with open(syslinux_cfg_path, 'w', encoding='utf-8') as f:
                f.writelines(syslinux_cfg)
            _iso_update(tmp_iso_path, syslinux_cfg_path,
                        iso_syslinux_cfg_path)

            with common.StaticWebServer(shared_dir, http_port):
                subprocess.run(['qemu-system-x86_64'] +
                               (['-enable-kvm'] if sys.platform == 'linux'
                                else []) +
                               ['-cpu', 'host',
                                '-hda', str(img_path),
                                '-cdrom', str(tmp_iso_path),
                                '-boot', 'd',
                                '-m', '2G',
                                '-device', 'e1000,netdev=net0',
                                '-netdev', netdev,
                                '-usb',
                                '-device', 'usb-tablet'],
                               check=True)

    return {'actions': [create],
            'task_dep': ['cache_vm_key'],
            'uptodate': [img_path.exists]}


def task_cache_vm_archlinux_run():
    """Cache VM archlinux - run image"""
    hostfwd = f'tcp::{ssh_port}-:22'
    guestfwd = f'tcp:10.0.2.100:80-cmd:nc 127.0.0.1 {http_port}'
    netdev = f'user,id=net0,hostfwd={hostfwd},guestfwd={guestfwd}'

    def run(save):
        with _create_tmpdir() as tmpdir:
            shared_dir = tmpdir / 'shared'
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
                               ['-enable-kvm',
                                '-cpu', 'host',
                                '-hda', str(tmp_img_path),
                                '-m', '2G',
                                '-device', 'e1000,netdev=net0',
                                '-netdev', netdev,
                                '-usb',
                                '-device', 'usb-tablet'],
                               check=True)

    return {'actions': [run],
            'params': [{'name': 'save',
                        'default': False,
                        'long': 'save',
                        'type': bool,
                        'help': 'save changes to disk image'}],
            'task_dep': ['cache_vm_archlinux']}


@contextlib.contextmanager
def _create_tmpdir():
    with tempfile.TemporaryDirectory(dir=str(cache_dir),
                                     prefix='tmp') as tmpdir:
        yield Path(tmpdir)


def _iso_extract(iso_path, src_path, dst_path):
    subprocess.run(['xorriso', '-dev', str(iso_path),
                    '-boot_image', 'any', 'keep',
                    '-osirrox', 'on',
                    '-extract', str(src_path), str(dst_path)],
                   check=True)


def _iso_update(iso_path, src_path, dst_path):
    subprocess.run(['xorriso', '-dev', str(iso_path),
                    '-boot_image', 'any', 'keep',
                    '-osirrox', 'on',
                    '-update', str(src_path), str(dst_path)],
                   check=True)


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
    'requirements.pacman.win.txt': Path('requirements.pacman.win.txt'),
    'requirements.pacman.linux.txt': Path('requirements.pacman.linux.txt'),
    'package.json': Path('package.json'),
    'archlinux_init.sh': r"""#!/bin/bash
set -e

parted -s /dev/sda mklabel msdos
parted -s /dev/sda mkpart primary 2048s 2G
parted -s /dev/sda mkpart primary 2G 100%
mkfs.ext4 /dev/sda2
mkswap /dev/sda1
swapon /dev/sda1

mount /dev/sda2 /mnt
echo 'Server = http://archlinux.iskon.hr/$repo/os/$arch' \
    > /etc/pacman.d/mirrorlist
pacstrap /mnt \
    base linux linux-firmware \
    dhcpcd grub openssh neovim \
    $(curl http://10.0.2.100/requirements.pacman.linux.txt)
genfstab -U /mnt >> /mnt/etc/fstab

arch-chroot /mnt /bin/bash << EOF_ROOT
set -e

ln -sf /usr/share/zoneinfo/Europe/Zagreb /etc/localtime
echo "en_US.UTF-8 UTF-8" > /etc/locale.gen
locale-gen
echo "LANG=en_US.UTF-8" > locale.conf
echo "hatvm" > /etc/hostname
echo "PermitUserEnvironment yes" >> /etc/ssh/sshd_config

systemctl enable dhcpcd
systemctl enable sshd

mkinitcpio -P

grub-install /dev/sda
echo "GRUB_TIMEOUT=0" >> /etc/default/grub
grub-mkconfig -o /boot/grub/grub.cfg

passwd -d -u root
useradd -m -G wheel,users,power hat
passwd -d -u hat

su -s /bin/bash hat << EOF_HAT
set -e

mkdir -p /home/hat/.ssh
curl "http://10.0.2.100/authorized_keys" > /home/hat/.ssh/authorized_keys
echo "PATH=/home/hat/python/bin:/usr/bin" > /home/hat/.ssh/environment
echo "export PATH=/home/hat/python/bin:/usr/bin" > /home/hat/.bashrc
echo "export PATH=/home/hat/python/bin:/usr/bin" > /home/hat/.bash_profile

mkdir -p /home/hat/cache
curl "http://10.0.2.100/requirements.pip.txt" > \
    /home/hat/cache/requirements.pip.txt
curl "http://10.0.2.100/package.json" > \
    /home/hat/cache/package.json

python -m venv /home/hat/python
/home/hat/python/bin/pip -q install -r /home/hat/cache/requirements.pip.txt

cd /home/hat/cache && yarn install

EOF_HAT

EOF_ROOT

sync
shutdown now"""
}
