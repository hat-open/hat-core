from pathlib import Path

__all__ = ['task_jshat_view',
           'task_jshat_view_watch']


build_dir = Path('build/jshat/view')


def task_jshat_view():
    """JsHat view - build all"""
    return {'actions': ['yarn run --silent build '
                        '--config webpack.view.config.js'],
            'task_dep': ['jshat_deps']}


def task_jshat_view_watch():
    """JsHat view - build all on change"""
    return {'actions': ['yarn run --silent watch '
                        '--config webpack.view.config.js'],
            'task_dep': ['jshat_deps']}
