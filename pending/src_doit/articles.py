from pathlib import Path
import subprocess

import docutils.core

from hat.doit import common


__all__ = ['task_articles']


src_dir = Path('articles')
dst_dir = Path('build/articles')


def get_article_names():
    for i in src_dir.glob('*'):
        if not i.is_dir():
            continue
        name = i.name
        if name.startswith('_'):
            continue
        yield name


def task_articles():
    """Articles - build"""
    for name in get_article_names():
        yield {'name': name,
               'actions': [(_build_article, [name])],
               'task_dep': ['jshat_deps']}


def _build_article(name):
    article_src_dir = src_dir / name
    article_dst_dir = dst_dir / name

    common.rm_rf(article_dst_dir)
    article_dst_dir.mkdir(parents=True, exist_ok=True)

    for src_path in article_src_dir.rglob('*'):
        if src_path.is_dir() or src_path.name.startswith('_'):
            continue
        dst_path = article_dst_dir / src_path.relative_to(article_src_dir)
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.suffix == '.scss':
            dst_path = dst_path.with_suffix('.css')
            _build_scss(src_path, dst_path)

        elif src_path.suffix == '.rst':
            dst_path = dst_path.with_suffix('.html')
            _build_rst(src_path, dst_path)

        else:
            common.cp_r(src_path, dst_path)


def _build_scss(src_path, dst_path):
    subprocess.run(['node_modules/.bin/sass', '--no-source-map',
                    str(src_path), str(dst_path)],
                   check=True)


def _build_rst(src_path, dst_path):
    with open(src_path, encoding='utf-8') as src_f:
        with open(dst_path, 'w', encoding='utf-8') as dst_f:
            docutils.core.publish_file(
                source=src_f,
                destination=dst_f,
                writer_name='html',
                settings_overrides={'embed_stylesheet': False,
                                    'stylesheet_path': 'main.css'})
