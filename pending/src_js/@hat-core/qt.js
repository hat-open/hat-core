
export function init() {
    return new Promise(resolve => {
        const script = document.createElement('script');
        script.src = 'qrc:///qtwebchannel/qwebchannel.js';
        script.onload = () => {
            const {QWebChannel, qt} = window;
            new QWebChannel(qt.webChannelTransport, channel => {
                resolve(channel.objects);
            });
        };
        document.querySelector('head').appendChild(script);
    });
}
