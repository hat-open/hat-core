from pathlib import Path

from hat.doit import common


__all__ = ['task_cache_tools',
           'task_cache_tools_plantuml']


plantuml_url = 'http://downloads.sourceforge.net/project/plantuml/plantuml.jar'

cache_dir = Path('cache/tools')
plantuml_path = cache_dir / 'plantuml.jar'


def task_cache_tools():
    """Cache tools - all"""
    return {'actions': None,
            'task_dep': ['cache_tools_plantuml']}


def task_cache_tools_plantuml():
    """Cache tools - plantuml"""
    return {'actions': [(common.mkdir_p, [plantuml_path.parent]),
                        f"wget -q -c -O {plantuml_path} {plantuml_url}"],
            'uptodate': [plantuml_path.exists]}
