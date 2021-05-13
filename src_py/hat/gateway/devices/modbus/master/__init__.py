"""Modbus master device"""

import asyncio

from hat import aio
from hat import json
from hat.gateway import common
from hat.gateway.devices.modbus.master.connection import connect


device_type: str = "modbus_master"

json_schema_id: str = "hat://gateway/modbus.yaml#/definitions/master"

json_schema_repo: json.SchemaRepository = common.json_schema_repo


async def create(conf: common.DeviceConf,
                 event_client: common.DeviceEventClient,
                 event_type_prefix: common.EventTypePrefix
                 ) -> 'ModbusMasterDevice':
    device = ModbusMasterDevice()
    device._conf = conf
    device._event_client = event_client
    device._event_type_prefix = event_type_prefix
    device._async_group = aio.Group()

    device._async_group.spawn(device._device_loop)
    return device


class ModbusMasterDevice(aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    async def _connection_loop(self):
        try:
            while True:
                try:
                    self._conn = await asyncio.wait_for(
                        connect(self._conf['connection']),
                        self._conf['connection']['connect_timeout'])
                except Exception:
                    await asyncio.sleep(
                        self._conf['connection']['connect_delay'])
                    continue

                await self._conn.wait_closing()

        finally:
            self.close()

    async def _event_client_loop(self):
        pass
