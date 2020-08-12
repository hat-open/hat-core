const path = require('path');
const CopyWebpackPlugin = require('copy-webpack-plugin');


function app(name, entry) {
    return {
        mode: 'none',
        entry: entry,
        output: {
            filename: name + '.js',
            path: path.join(__dirname, 'build', 'jshat', 'app', name)
        },
        module: {
            rules: [
                {
                    test: /\.scss$/,
                    use: ["style-loader", "css-loader", "resolve-url-loader", "sass-loader?sourceMap"]
                },
                {
                    test: /\.woff2$/,
                    use: "file-loader?name=fonts/[name].[ext]"
                }
            ]
        },
        resolve: {
            modules: [
                path.join(__dirname, 'src_js'),
                path.join(__dirname, 'src_scss', 'app'),
                path.join(__dirname, 'node_modules')
            ]
        },
        watchOptions: {
            ignored: /node_modules/
        },
        plugins: [
            new CopyWebpackPlugin({
                patterns: [{from: 'src_web/app/' + name}]
            })
        ],
        devtool: 'source-map',
        stats: 'errors-only'
    };
}


module.exports = [
    app('orchestrator', '.' + path.sep + path.join('src_js', '@hat-core', 'orchestrator', 'main')),
    app('monitor', '.' + path.sep + path.join('src_js', '@hat-core', 'monitor', 'main')),
    app('gui', '.' + path.sep + path.join('src_js', '@hat-core', 'gui', 'main')),
    app('syslog', '.' + path.sep + path.join('src_js', '@hat-core', 'syslog', 'main'))
];
