import asyncio
import socket
import typing

import aiohttp

from hat import aio
from hat import json
from hat.drivers.hue import common
from hat.drivers.hue import encoder


async def create_user(addr: str,
                      app_name: str = 'hat',
                      dev_name: str = socket.gethostname()
                      ) -> str:
    """Create new user

    Register new user with bridge and return newly created username.

    """
    url = f'{addr}/api'
    req_data = {'devicetype': f'{app_name}#{dev_name}'}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=req_data) as res:
            res_data = await res.json()
    _parse_action_response(res_data)
    return res_data[0]['success']['username']


class Client:
    """High-level hue bridge client"""

    def __init__(self, addr: str, user: str):
        self._transport = ClientTransport(addr, user)

    @property
    def transport(self) -> 'ClientTransport':
        """Low-level transport"""
        return self._transport

    @property
    def closed(self) -> asyncio.Future:
        """Closed future"""
        return self._transport.closed

    async def async_close(self):
        """Async close"""
        await self._transport.async_close()

    async def touchlink(self):
        """Adds the closest light to the ZigBee network"""
        await self._transport.set_conf(None, None, {'touchlink': True})

    async def search(self):
        """Search for new devices"""
        await self._transport.search(common.DeviceType.LIGHT)
        await self._transport.search(common.DeviceType.SENSOR)

    async def rename(self,
                     device_id: common.DeviceId,
                     name: str):
        """Rename device"""
        await self._transport.rename(device_id, device_id, name)

    async def get_devices(self) -> typing.List[common.Device]:
        """Get all devices"""
        data = await self._transport.get(None)
        devices = []
        for device_type in common.DeviceType:
            devices.extend(
                encoder.device_from_json(
                    common.DeviceId(type=device_type, label=k), v)
                for k, v in data[device_type.value].items())
        return devices

    async def get_device(self, device_id: common.DeviceId) -> common.Device:
        """Get device"""
        data = await self._transport.get(device_id)
        return encoder.device_from_json(device_id, data)

    async def set_state(self,
                        device_id: common.DeviceId,
                        state: common.DeviceState):
        """Set device state"""
        data = encoder.state_to_json(state)
        await self._transport.set_state(device_id, data)


class ClientTransport:
    """Low-level bridge client communication"""

    def __init__(self, addr: str, user: str):
        self._addr = addr
        self._user = user
        self._session = aiohttp.ClientSession()
        self._async_group = aio.Group()
        self._async_group.spawn(aio.call_on_cancel, self._session.close)

    @property
    def closed(self) -> asyncio.Future:
        """Closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()

    async def get(self,
                  device_id: typing.Optional[common.DeviceId]
                  ) -> json.Data:
        """Get data

        If `device_id` is ``None``, global data is returned.

        """
        path = f'{device_id.type.value}/{device_id.label}' if device_id else ''
        return await self._get(path)

    async def search(self, device_type: common.DeviceType):
        """Search for new devices"""
        await self._post(device_type.value)

    async def rename(self,
                     device_id: common.DeviceId,
                     name: str):
        """Rename device"""
        path = f'{device_id.type.value}/{device_id.label}'
        await self._post(path, {'name': name})

    async def set_conf(self,
                       device_id: typing.Optional[common.DeviceId],
                       data: json.Data):
        """Set configuration

        If `device_id` is ``None``, global configuration is modified.

        Light devices are not supported.

        """
        if device_id and device_id.type == common.DeviceType.LIGHT:
            raise ValueError('light devices not supported')
        path = (f'{device_id.type}/{device_id}/config' if device_id
                else 'config')
        await self._put(path, data)

    async def set_state(self,
                        device_id: common.DeviceId,
                        data: json.Data):
        """Set device state"""
        path = f'{device_id.type.value}/{device_id.label}/state'
        await self._put(path, data)

    async def delete_user(self, user: str):
        """Delete existing user"""
        await self._delete(f'config/whitelist/{user}')

    async def _get(self, path):
        url = f'{self._addr}/api/{self._user}/{path}'
        async with self._session.get(url) as res:
            return await res.json()

    async def _post(self, path, data=None):
        url = f'{self._addr}/api/{self._user}/{path}'
        async with self._session.post(url, json=data) as res:
            _parse_action_response(await res.json())

    async def _put(self, path, data=None):
        url = f'{self._addr}/api/{self._user}/{path}'
        async with self._session.put(url, json=data) as res:
            _parse_action_response(await res.json())

    async def _delete(self, path):
        url = f'{self._addr}/api/{self._user}/{path}'
        async with self._session.delete(url) as res:
            _parse_action_response(await res.json())


def _parse_action_response(res):
    if not res:
        raise Exception('invalid response')
    errors = []
    for i in res:
        if 'error' in i:
            errors.append(i['error'])
        elif 'success' not in i:
            raise Exception('invalid response')
    if errors:
        raise Exception(f"hue error: {errors}")
