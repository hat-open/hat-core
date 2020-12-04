from pathlib import Path
import functools
import io
import subprocess
import tempfile

from hat import json
from hat.gui import vt


__all__ = ['task_jshat_app',
           'task_jshat_app_orchestrator',
           'task_jshat_app_monitor',
           'task_jshat_app_gui',
           'task_jshat_app_syslog',
           'task_jshat_app_event_viewer',
           'task_jshat_app_hue_manager',
           'task_jshat_app_hue_manager_assets']


build_dir = Path('build/jshat/app')
src_js_dir = Path('src_js')
src_scss_dir = Path('src_scss')
src_web_dir = Path('src_web')
node_modules_dir = Path('node_modules')


def task_jshat_app():
    """JsHat application - build all"""
    return {'actions': None,
            'task_dep': ['jshat_app_orchestrator',
                         'jshat_app_monitor',
                         'jshat_app_gui',
                         'jshat_app_syslog',
                         'jshat_app_event_viewer',
                         'jshat_app_hue_manager']}


def task_jshat_app_orchestrator():
    """JsHat application - build orchestrator"""
    return _get_task_build('orchestrator',
                           src_js_dir / '@hat-core/orchestrator/main.js')


def task_jshat_app_monitor():
    """JsHat application - build monitor"""
    return _get_task_build('monitor',
                           src_js_dir / '@hat-core/monitor/main.js')


def task_jshat_app_gui():
    """JsHat application - build gui"""
    return _get_task_build('gui',
                           src_js_dir / '@hat-core/gui/main.js')


def task_jshat_app_syslog():
    """JsHat application - build syslog"""
    return _get_task_build('syslog',
                           src_js_dir / '@hat-core/syslog/main.js')


def task_jshat_app_event_viewer():
    """JsHat application - build event-viewer"""
    return _get_task_build('event-viewer',
                           src_js_dir / '@hat-core/event-viewer/main.js')


def task_jshat_app_hue_manager():
    """JsHat application - build hue-manager"""
    return _get_task_build('hue-manager',
                           src_js_dir / '@hat-core/hue-manager/main.js',
                           task_dep=['jshat_app_hue_manager_assets'])


def task_jshat_app_hue_manager_assets():
    """JsHat assets - build hue-manager assets"""
    def mappings():
        yield 'bars', node_modules_dir / 'svg-loaders/svg-css-loaders/bars.svg'

    return _get_task_assets(src_js_dir / '@hat-core/hue-manager/assets.js',
                            mappings)


def _get_task_build(name, entry, task_dep=[]):
    return {'actions': [functools.partial(_build_app, name, entry)],
            'pos_arg': 'args',
            'task_dep': ['jshat_deps',
                         *task_dep]}


def _get_task_assets(dst_path, mappings):
    src_paths = [src_path for _, src_path in mappings()]
    return {'actions': [(_build_assets, [dst_path, mappings])],
            'file_dep': src_paths,
            'targets': [dst_path],
            'task_dep': ['jshat_deps']}


def _build_app(name, entry, args):
    args = args or []
    conf = _webpack_conf.format(
        name=name,
        entry=entry.resolve(),
        build_dir=build_dir.resolve(),
        src_js_dir=src_js_dir.resolve(),
        src_scss_dir=src_scss_dir.resolve(),
        src_web_dir=src_web_dir.resolve(),
        node_modules_dir=node_modules_dir.resolve())
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config_path = tmpdir / 'webpack.config.js'
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(conf)
        subprocess.run([str(node_modules_dir / '.bin/webpack'),
                        '--config', str(config_path),
                        *args],
                       check=True)


def _build_assets(dst_path, mappings):
    assets = {name: _build_asset(src_path) for name, src_path in mappings()}
    assets_str = json.encode(assets)
    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(f'export default {assets_str};')


def _build_asset(src_path):
    with open(src_path, encoding='utf-8') as f:
        src = f.read()
    if src_path.suffix == '.svg':
        return vt.parse(io.StringIO(src))
    return src


_webpack_conf = r"""
const path = require('path');
const CopyWebpackPlugin = require('{node_modules_dir}/copy-webpack-plugin');

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
                use: ["style-loader", "css-loader", "resolve-url-loader",
                      "sass-loader?sourceMap"]
            }},
            {{
                test: /\.woff2$/,
                use: "file-loader?name=fonts/[name].[ext]"
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
    plugins: [
        new CopyWebpackPlugin({{
            patterns: [{{from: '{src_web_dir}/app/{name}'}}]
        }})
    ],
    devtool: 'source-map',
    stats: 'errors-only'
}};
"""
