"""Simple Service Discovery Protocol"""

import logging
import typing

from hat import aio
from hat import udp
from hat import util


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


class DeviceInfo(typing.NamedTuple):
    addr: udp.Address
    location: str
    server: str
    service: str


DeviceInfoCb = aio.AsyncCallable[[DeviceInfo], None]
"""Device info callback"""
util.register_type_alias('DeviceInfoCb')


default_multicast_addr = udp.Address('239.255.255.250', 1900)


async def discover(device_info_cb: DeviceInfoCb,
                   multicast_addr: udp.Address = default_multicast_addr,
                   local_name: str = 'hat'
                   ) -> 'DiscoveryServer':
    """Create discovery server"""
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


class DiscoveryServer(aio.Resource):
    """Discovery server"""

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
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
