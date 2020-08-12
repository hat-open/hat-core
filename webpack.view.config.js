const path = require('path');
const CopyWebpackPlugin = require('copy-webpack-plugin');


function view(name, entry) {
    return {
        mode: 'none',
        entry: entry,
        output: {
            libraryTarget: 'commonjs',
            filename: 'index.js',
            path: path.join(__dirname, 'build', 'jshat', 'view', name)
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
                path.join(__dirname, 'src_scss', 'view'),
                path.join(__dirname, 'node_modules')
            ]
        },
        watchOptions: {
            ignored: /node_modules/
        },
        plugins: [
            new CopyWebpackPlugin({
                patterns: [{from: 'src_web/view/' + name}]
            })
        ],
        devtool: 'eval-source-map',
        stats: 'errors-only'
    };
}


module.exports = [
    view('login', '.' + path.sep + path.join('src_js', '@hat-core', 'gui', 'views', 'login', 'index'))
];
