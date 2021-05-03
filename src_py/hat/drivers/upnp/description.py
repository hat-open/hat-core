"""WIP UPnP description"""

import collections
import io
import typing
import xml.sax.handler

import aiohttp


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
