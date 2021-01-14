"""Slave communication implementation"""

import asyncio
import contextlib
import itertools
import logging
import typing

from hat import aio
from hat import chatter
from hat import json
from hat.monitor.server import common
import hat.monitor.server.master
import hat.monitor.server.server


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

connect_timeout: float = 5
"""Connect timeout in seconds"""

connect_retry_count: int = 3
"""Connect retry count before local master is activated"""

connect_retry_delay: float = 1
"""Connect retry delay in seconds"""


async def run(conf: json.Data,
              server: hat.monitor.server.server.Server,
              master: hat.monitor.server.master.Master):
    """Run slave/master loop

    Args:
        conf: configuration defined by
            ``hat://monitor/main.yaml#/definitions/slave``
        server: local server
        master: local master

    """
    conn = None

    async def cleanup():
        await master.set_server(None)
        server.update(0, [])
        if conn:
            await conn.async_close()

    try:
        if not conf['parents']:
            mlog.debug('no parents - activating local master')
            await master.set_server(server)
            await master.wait_closed()
            return

        while True:
            server.update(0, [])

            if not conn or not conn.is_open:
                conn = await connect(conf['parents'], connect_retry_count)

            if conn and conn.is_open:
                mlog.debug('master detected - activating local slave')
                slave = Slave(server, conn)
                await slave.wait_closed()

            elif conn:
                await conn.async_close()

            else:
                mlog.debug('no master detected - activating local master')
                await master.set_server(server)
                conn = await connect(conf['parents'], None)
                await master.set_server(None)

    except Exception as e:
        mlog.warning('run error: %s', e, exc_info=e)

    finally:
        mlog.debug('stopping run')
        await aio.uncancellable(cleanup())


async def connect(addresses: str,
                  retry_count: typing.Optional[int]
                  ) -> typing.Optional[chatter.Connection]:
    """Establish connection with remote master"""
    counter = range(retry_count) if retry_count else itertools.repeat(None)
    for _ in counter:
        for address in addresses:
            with contextlib.suppress(Exception):
                conn = await asyncio.wait_for(
                    chatter.connect(common.sbs_repo, address),
                    connect_timeout)
                return conn
        await asyncio.sleep(connect_retry_delay)


class Slave(aio.Resource):
    """Slave"""

    def __init__(self,
                 server: hat.monitor.server.server.Server,
                 conn: chatter.Connection):
        self._server = server
        self._conn = conn
        self._components = []
        self.async_group.spawn(self._slave_loop)
        self.async_group.spawn(aio.call_on_done, server.wait_closing(),
                               self.close)

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._conn.async_group

    async def _slave_loop(self):
        try:
            mlog.debug('connected to master')
            await self._receive()

            with self._server.register_change_cb(self._on_server_change):
                self._components = self._server.local_components
                self._send_msg_slave()

                while True:
                    await self._receive()

        except ConnectionError:
            pass

        except Exception as e:
            mlog.warning('slave loop error: %s', e, exc_info=e)

        finally:
            self.async_group.close()
            self._server.update(0, [])
            mlog.debug('connection to master closed')

    async def _receive(self):
        msg = await self._conn.receive()
        msg_type = msg.data.module, msg.data.type

        if msg_type == ('HatMonitor', 'MsgMaster'):
            msg_master = common.msg_master_from_sbs(msg.data.data)
            self._process_msg_master(msg_master)

        else:
            raise Exception('unsupported message type')

    def _on_server_change(self):
        if self._components == self._server.local_components:
            return

        self._components = self._server.local_components
        self._send_msg_slave()

    def _send_msg_slave(self):
        msg = common.MsgSlave(components=self._components)
        with contextlib.suppress(ConnectionError):
            self._conn.send(chatter.Data(
                module='HatMonitor',
                type='MsgSlave',
                data=common.msg_slave_to_sbs(msg)))

    def _process_msg_master(self, msg_master):
        self._server.update(msg_master.mid, msg_master.components)
