from pathlib import Path


__all__ = ['task_format',
           'task_format_chat']


def task_format():
    """Format - format all"""
    return {'actions': None,
            'task_dep': ['format_chat']}


def task_format_chat():
    """Format - format chat with clang format"""
    files = [*Path('src_c/hat').rglob('*.c'),
             *Path('src_c/hat').rglob('*.h'),
             *Path('src_c/pymod/sbs').rglob('*.c'),
             *Path('src_c/pymod/sbs').rglob('*.h')]
    for f in files:
        yield {'name': str(f),
               'actions': ['clang-format -style=file -i ' + str(f)],
               'file_dep': [str(f)]}
