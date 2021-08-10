from pathlib import Path

from hat.doit import common


__all__ = ['task_cache_vm_key']


cache_dir = Path('cache/vm')
ssh_key_path = cache_dir / 'ssh.key'
authorized_keys_path = cache_dir / 'authorized_keys'


def task_cache_vm_key():
    """Cache VM key - create ssh key and authorized_keys files"""
    return {'actions': [(common.rm_rf, [ssh_key_path,
                                        authorized_keys_path]),
                        (common.mkdir_p, [ssh_key_path.parent,
                                          authorized_keys_path.parent]),
                        f'ssh-keygen -q -N "" -m PEM -C hat -f {ssh_key_path}',
                        f'mv {ssh_key_path}.pub {authorized_keys_path}'],
            'uptodate': [ssh_key_path.exists,
                         authorized_keys_path.exists]}
