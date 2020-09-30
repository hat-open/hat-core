from pathlib import Path

__all__ = ['task_jshat_app',
           'task_jshat_app_watch']


build_dir = Path('build/jshat/app')


def task_jshat_app():
    """JsHat application - build all"""
    return {'actions': ['yarn run --silent build '
                        '--config webpack.app.config.js'],
            'task_dep': ['jshat_deps',
                         'jshat_assets']}


def task_jshat_app_watch():
    """JsHat application - build all on change"""
    return {'actions': ['yarn run --silent watch '
                        '--config webpack.app.config.js'],
            'task_dep': ['jshat_deps',
                         'jshat_assets']}


# def task_jshat_analyze():
#     """JsHat - profile and analyze build"""
#     def analyze(args):
#         for name in args:
#             subprocess.run(['yarn', 'run', '--silent', 'analyze',
#                             str(build_dir / f'{name}/{name}.js'),
#                             str(build_dir / f'{name}/{name}.js.map')],
#                            check=True)
#     return {'actions': [analyze],
#             'pos_arg': 'args',
#             'task_dep': ['jshat']}
