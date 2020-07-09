from pathlib import Path

import docutils.core

from hat.doit import common


__all__ = ['task_articles']


src_dir = Path('articles')
dst_dir = Path('build/articles')


def task_articles():
    """Articles - build"""

    for src_path in src_dir.rglob('*'):
        if src_path.is_dir():
            continue
        dst_path = dst_dir / src_path.relative_to(src_dir)

        if src_path.suffix == '.scss':
            if src_path.name.startswith('_'):
                continue
            dst_path = dst_path.with_suffix('.css')
            yield {'name': str(dst_path),
                   'actions': [(common.mkdir_p, [dst_path.parent]),
                               f'sassc {src_path} {dst_path}'],
                   'targets': [dst_path]}

        elif src_path.suffix == '.rst':
            if src_path.name.startswith('_'):
                continue
            dst_path = dst_path.with_suffix('.html')
            yield {'name': str(dst_path),
                   'actions': [(common.mkdir_p, [dst_path.parent]),
                               (_build_rst, [src_path, dst_path])],
                   'file_dep': [src_path],
                   'targets': [dst_path]}

        else:
            yield {'name': str(dst_path),
                   'actions': [(common.mkdir_p, [dst_path.parent]),
                               (common.cp_r, [src_path, dst_path])],
                   'file_dep': [src_path],
                   'targets': [dst_path]}


def _build_rst(src_path, dst_path):
    with open(src_path, encoding='utf-8') as src_f:
        with open(dst_path, 'w', encoding='utf-8') as dst_f:
            docutils.core.publish_file(
                source=src_f,
                destination=dst_f,
                writer_name='html',
                settings_overrides={'embed_stylesheet': False,
                                    'stylesheet_path': 'main.css'})
