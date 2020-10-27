from pathlib import Path

from hat.doit import common


__all__ = ['task_timestamp']


build_dir = Path('build')
timestamp_path = build_dir / 'timestamp'


def task_timestamp():
    """Generate build timestamp"""
    return {'actions': [_generate_timestamp]}


def _generate_timestamp():
    timestamp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timestamp_path, 'w', encoding='utf-8') as f:
        f.write(str(common.now.timestamp()))
