from pathlib import Path
import functools
import subprocess
import tempfile

from hat.doit import common


__all__ = ['task_jshat_app',
           'task_jshat_app_orchestrator',
           'task_jshat_app_monitor',
           'task_jshat_app_gui',
           'task_jshat_app_syslog',
           'task_jshat_app_manager_event',
           'task_jshat_app_manager_hue',
           'task_jshat_app_manager_iec104']


build_dir = Path('build/jshat/app')
static_dir = Path('static_web/app')
src_js_dir = Path('src_js')
src_scss_dir = Path('src_scss')
node_modules_dir = Path('node_modules')
favicon_path = Path('logo/favicon.ico')


def task_jshat_app():
    """JsHat application - build all"""
    return {'actions': None,
            'task_dep': ['jshat_app_orchestrator',
                         'jshat_app_monitor',
                         'jshat_app_gui',
                         'jshat_app_syslog',
                         'jshat_app_manager_event',
                         'jshat_app_manager_hue',
                         'jshat_app_manager_iec104']}


def task_jshat_app_orchestrator():
    """JsHat application - build orchestrator"""
    return _get_task_build('orchestrator',
                           'Hat Orchestrator',
                           src_js_dir / '@hat-core/orchestrator/main.js')


def task_jshat_app_monitor():
    """JsHat application - build monitor"""
    return _get_task_build('monitor',
                           'Hat Monitor',
                           src_js_dir / '@hat-core/monitor/main.js')


def task_jshat_app_gui():
    """JsHat application - build gui"""
    return _get_task_build('gui',
                           'Hat GUI',
                           src_js_dir / '@hat-core/gui/main.js')


def task_jshat_app_syslog():
    """JsHat application - build syslog"""
    return _get_task_build('syslog',
                           'Hat Syslog',
                           src_js_dir / '@hat-core/syslog/main.js')


def task_jshat_app_manager_event():
    """JsHat application - build manager_event"""
    return _get_task_build('manager-event',
                           'Hat Event Manager',
                           src_js_dir / '@hat-core/manager-event/main.js')


def task_jshat_app_manager_hue():
    """JsHat application - build manager-hue"""
    return _get_task_build('manager-hue',
                           'Hat Hue Manager',
                           src_js_dir / '@hat-core/manager-hue/main.js')


def task_jshat_app_manager_iec104():
    """JsHat application - build manager-iec104"""
    return _get_task_build('manager-iec104',
                           'Hat IEC104 Manager',
                           src_js_dir / '@hat-core/manager-iec104/main.js')


def _get_task_build(name, title, entry, task_dep=[]):
    return {'actions': [functools.partial(_build_app, name, title, entry)],
            'pos_arg': 'args',
            'task_dep': ['jshat_deps',
                         *task_dep]}


def _build_app(name, title, entry, args):
    args = args or []
    conf = _webpack_conf.format(
        name=name,
        entry=entry.resolve(),
        build_dir=build_dir.resolve(),
        src_js_dir=src_js_dir.resolve(),
        src_scss_dir=src_scss_dir.resolve(),
        node_modules_dir=node_modules_dir.resolve())
    index_html = _index_html.format(title=title,
                                    script=f'{name}.js')

    dst_dir = build_dir / name
    dst_dir.mkdir(parents=True, exist_ok=True)
    with open(dst_dir / 'index.html', 'w', encoding='utf-8') as f:
        f.write(index_html)
    common.cp_r(favicon_path, dst_dir / 'favicon.ico')

    app_static_dir = static_dir / name
    for i in app_static_dir.glob('*'):
        common.cp_r(i, dst_dir / i.relative_to(app_static_dir))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config_path = tmpdir / 'webpack.config.js'
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(conf)
        subprocess.run([str(node_modules_dir / '.bin/webpack'),
                        '--config', str(config_path),
                        *args],
                       check=True)


_index_html = r"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="{script}"></script>
</head>
<body>
</body>
</html>
"""


_webpack_conf = r"""
module.exports = {{
    mode: 'none',
    entry: '{entry}',
    output: {{
        filename: '{name}.js',
        path: '{build_dir}/{name}'
    }},
    module: {{
        rules: [
            {{
                test: /\.scss$/,
                use: [
                    "style-loader",
                    "css-loader",
                    "resolve-url-loader",
                    {{
                        loader: "sass-loader",
                        options: {{ sourceMap: true }}
                    }}
                ]
            }},
            {{
                test: /\.woff2$/,
                use: [
                    {{
                        loader: "file-loader",
                        options: {{ name: "fonts/[name].[ext]" }}
                    }}
                ]
            }}
        ]
    }},
    resolve: {{
        modules: [
            '{src_js_dir}',
            '{src_scss_dir}/app',
            '{node_modules_dir}'
        ]
    }},
    watchOptions: {{
        ignored: /node_modules/
    }},
    devtool: 'source-map',
    stats: 'errors-only'
}};
"""
