from pathlib import Path
import subprocess
import tempfile


__all__ = ['task_jshat_view',
           'task_jshat_view_login',
           'task_jshat_view_login_watch']


build_dir = Path('build/jshat/view')
src_js_dir = Path('src_js')
src_scss_dir = Path('src_scss')
src_web_dir = Path('src_web')
node_modules_dir = Path('node_modules')


def task_jshat_view():
    """JsHat view - build all"""
    return {'actions': None,
            'task_dep': ['jshat_view_login']}


def task_jshat_view_login():
    """JsHat view - build login"""
    return _get_task_build('login',
                           src_js_dir / '@hat-core/gui/views/login/index.js')


def task_jshat_view_login_watch():
    """JsHat viewlication - build login on change"""
    return _get_task_watch('login',
                           src_js_dir / '@hat-core/gui/views/login/index.js')


def _get_task_build(name, entry, task_dep=[]):
    return {'actions': [(_build_view, [name, entry])],
            'task_dep': ['jshat_deps',
                         *task_dep]}


def _get_task_watch(name, entry, task_dep=[]):
    return {'actions': [(_build_view, [name, entry, '-w'])],
            'task_dep': ['jshat_deps',
                         *task_dep]}


def _build_view(name, entry, *args):
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


_webpack_conf = r"""
const path = require('path');
const CopyWebpackPlugin = require('{node_modules_dir}/copy-webpack-plugin');

module.exports = {{
    mode: 'none',
    entry: '{entry}',
    output: {{
        libraryTarget: 'commonjs',
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
            '{src_scss_dir}/view',
            '{node_modules_dir}'
        ]
    }},
    watchOptions: {{
        ignored: /node_modules/
    }},
    plugins: [
        new CopyWebpackPlugin({{
            patterns: [{{from: '{src_web_dir}/view/{name}'}}]
        }})
    ],
    devtool: 'eval-source-map',
    stats: 'errors-only'
}};
"""
