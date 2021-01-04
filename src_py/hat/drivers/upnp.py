import collections
import io
import typing
import xml.sax.handler

import aiohttp

from hat import aio
from hat.drivers import udp


class DeviceInfo(typing.NamedTuple):
    addr: udp.Address
    location: str
    server: str
    service: str


class Icon(typing.NamedTuple):
    mimetype: str
    width: int
    height: int
    depth: int
    url: str


class DeviceDescription(typing.NamedTuple):
    url: typing.Optional[str]
    dev_type: str
    dev_name: str
    manufacturer: str
    manufacturer_url: typing.Optional[str]
    model_desc: typing.Optional[str]
    model_name: str
    model_number: typing.Optional[str]
    model_url: typing.Optional[str]
    serial_number: typing.Optional[str]
    unique_dev_name: str
    icons: typing.List[Icon]


DeviceInfoCb = typing.Callable[[DeviceInfo], None]


default_multicast_addr = udp.Address('239.255.255.250', 1900)


async def discover(device_info_cb: DeviceInfoCb,
                   multicast_addr: udp.Address = default_multicast_addr,
                   local_name: str = 'hat'
                   ) -> 'DiscoveryServer':
    endpoint = await udp.create(udp.Address('0.0.0.0', multicast_addr.port))

    srv = DiscoveryServer()
    srv._endpoint = endpoint
    srv._device_info_cb = device_info_cb
    srv._multicast_addr = multicast_addr
    srv._local_name = local_name
    srv._async_group = aio.Group()
    srv._async_group.spawn(aio.call_on_cancel, endpoint.async_close)
    srv._async_group.spawn(srv._discovery_loop)
    return srv


async def get_description(location: str) -> DeviceDescription:
    async with aiohttp.ClientSession() as session:
        async with session.get(location) as res:
            text = await res.text()
        data = _decode_xml(text)
        version = data['root']['specVersion']
        if version['major'] != '1':
            raise Exception(f"unsupported version {version}")
        device = data['root']['device']
        device_icons = device.get('iconList', {}).get('icon', [])
        if not isinstance(device_icons, list):
            device_icons = [device_icons]
        icons = []
        for i in device_icons:
            icons.append(Icon(mimetype=i['mimetype'],
                              width=i['width'],
                              height=i['height'],
                              depth=i['depth'],
                              url=i['url']))
        return DeviceDescription(
            url=data['root'].get('URLBase'),
            dev_type=device['deviceType'],
            dev_name=device['friendlyName'],
            manufacturer=device['deviceType'],
            manufacturer_url=device.get('manufacturerURL'),
            model_desc=device.get('modelDescription'),
            model_name=device['modelName'],
            model_number=device.get('modelNumber'),
            model_url=device.get('modelURL'),
            serial_number=device.get('serialNumber'),
            unique_dev_name=device['UDN'],
            icons=icons)


class DiscoveryServer(aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    async def _discovery_loop(self):
        try:
            req = _encode_search_req(self._local_name)
            self._endpoint.send(req, self._multicast_addr)
            while True:
                res, addr = await self._endpoint.receive()
                try:
                    info = _decode_search_res(addr, res)
                except Exception:
                    continue
                await aio.call(self._device_info_cb, info)
        finally:
            self._async_group.close()


def _encode_search_req(local_name):
    return (f'M-SEARCH * HTTP/1.1\r\n'
            f'HOST: 239.255.255.250:1900\r\n'
            f'MAN: "ssdp:discover"\r\n'
            f'MX: 1\r\n'
            f'ST: ssdp:all\r\n'
            f'CPFN.UPNP.ORG: {local_name}\r\n').encode('utf-8')


def _decode_search_res(addr, data):
    lines = str(data, encoding='utf-8').strip().split('\r\n')
    if lines[0].strip() != 'HTTP/1.1 200 OK':
        raise Exception('invalid response')
    entries = {}
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        segments = [i.strip() for i in line.split(':', 1)]
        entries[segments[0].upper()] = segments[1]
    return DeviceInfo(addr=addr,
                      location=entries['LOCATION'],
                      server=entries['SERVER'],
                      service=entries['USN'])


def _decode_xml(text):
    handler = _XmlContentHandler()
    parser = xml.sax.make_parser()
    parser.setContentHandler(handler)
    parser.setFeature(xml.sax.handler.feature_external_ges, False)
    parser.setFeature(xml.sax.handler.feature_external_pes, False)
    parser.parse(io.StringIO(text))
    return handler.root


class _XmlContentHandler(xml.sax.ContentHandler):

    def __init__(self):
        self._root = {}
        self._stack = collections.deque([self._root])

    @property
    def root(self):
        return self._root

    def startElement(self, name, attrs):
        self._stack.append({})

    def endElement(self, name):
        el = self._stack.pop()
        text = el.get('', '')
        children = {k: v for k, v in el.items() if k}
        top = self._stack[-1]
        if name in top:
            if not isinstance(top[name], list):
                top[name] = [top[name]]
            top[name].append(children or text)
        else:
            top[name] = children or text

    def characters(self, content):
        el = self._stack[-1]
        el[''] = el.get('', '') + content
