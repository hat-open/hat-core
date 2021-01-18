"""Master communication implementation"""

import contextlib
import itertools
import logging
import typing

from hat import aio
from hat import chatter
from hat import json
from hat import util
from hat.monitor.server import blessing
from hat.monitor.server import common
import hat.monitor.server.server


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


async def create(conf: json.Data
                 ) -> 'Master':
    """Create master

    Args:
        conf: configuration defined by
            ``hat://monitor/main.yaml#/definitions/master``

    """
    master = Master()
    master._last_mid = 0
    master._group_algorithms = {
        group: blessing.Algorithm[algorithm]
        for group, algorithm in conf['group_algorithms'].items()}
    master._default_algorithm = blessing.Algorithm[conf['default_algorithm']]
    master._components = []
    master._mid_components = {}
    master._change_cbs = util.CallbackRegistry()
    master._active_subgroup = aio.Group()
    master._active_subgroup.close()

    master._srv = await chatter.listen(
        sbs_repo=common.sbs_repo,
        address=conf['address'],
        connection_cb=master._create_slave)

    mlog.debug('master listens slaves on %s', conf['address'])
    return master


class Master(aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._srv.async_group

    @property
    def active(self) -> bool:
        """Is active"""
        return self._active_subgroup.is_open

    @property
    def components(self) -> typing.List[common.ComponentInfo]:
        """Global components"""
        return self._components

    def register_change_cb(self,
                           cb: typing.Callable[[], None]
                           ) -> util.RegisterCallbackHandle:
        """Register change callback

        Change callback is called once active and/or components property
        changes.

        """
        return self._change_cbs.register(cb)

    async def set_server(self, server: hat.monitor.server.server.Server):
        """Set server

        If `server` is not ``None``, master is activated. Otherwise master is
        deactivated.

        """
        await self._active_subgroup.async_close()
        if not server:
            return

        self._active_subgroup = self.async_group.create_subgroup()
        self._active_subgroup.spawn(self._active_loop, server)
        self._components = []
        self._mid_components[0] = []
        self._change_cbs.notify()

    async def _active_loop(self, server):

        def on_server_change():
            self._set_components(0, server.local_components)

        def on_master_change():
            server.update(0, self._components)

        try:
            mlog.debug('master activated')

            with server.register_change_cb(on_server_change):
                with self.register_change_cb(on_master_change):
                    on_master_change()
                    on_server_change()
                    await server.wait_closing()

        except Exception as e:
            mlog.warning('active loop error: %s', e, exc_info=e)

        finally:
            self._active_subgroup.close()
            self._components = []
            self._mid_components = {}
            self._change_cbs.notify()
            on_master_change()
            mlog.debug('master deactivated')

    def _create_slave(self, conn):
        if not self.active:
            conn.close()
            return

        self._last_mid += 1
        mid = self._last_mid

        slave = _Slave(self, conn, mid)
        self._active_subgroup.spawn(slave.slave_loop)
        self._mid_components[mid] = []

    def _remove_slave(self, mid):
        components = self._mid_components.pop(mid, [])
        if not components:
            return
        self._update_components()

    def _set_components(self, mid, components):
        components = [i._replace(mid=mid) for i in components
                      if i.name is not None and i.group is not None]
        if self._mid_components.get(mid, []) == components:
            return

        self._mid_components[mid] = components
        self._update_components()

    def _update_components(self):
        blessings = {(i.mid, i.cid): i.blessing
                     for i in self._components}
        components = itertools.chain.from_iterable(
            self._mid_components.values())
        components = [i._replace(blessing=blessings.get((i.mid, i.cid)))
                      for i in components]
        components = blessing.calculate(components, self._group_algorithms,
                                        self._default_algorithm)
        if components == self._components:
            return

        self._components = components
        self._change_cbs.notify()


class _Slave:

    def __init__(self, master, conn, mid):
        self._master = master
        self._conn = conn
        self._mid = mid
        self._components = master.components

    async def slave_loop(self):
        try:
            mlog.debug('connection %s established', self._mid)

            self._components = self._master.components
            self._send_msg_master()

            with self._master.register_change_cb(self._on_change):
                while True:
                    msg = await self._conn.receive()
                    msg_type = msg.data.module, msg.data.type

                    if msg_type == ('HatMonitor', 'MsgSlave'):
                        msg = common.msg_slave_from_sbs(msg.data.data)
                        self._process_msg_slave(msg)

                    else:
                        raise Exception('unsupported message type')

        except ConnectionError:
            pass

        except Exception as e:
            mlog.warning('connection loop error: %s', e, exc_info=e)

        finally:
            self._conn.close()
            self._master._remove_slave(self._mid)
            mlog.debug('connection %s closed', self._mid)

    def _on_change(self):
        if self._master.components == self._components:
            return

        self._components = self._master.components
        self._send_msg_master()

    def _send_msg_master(self):
        msg = common.MsgMaster(mid=self._mid,
                               components=self._components)

        with contextlib.suppress(ConnectionError):
            self._conn.send(chatter.Data(
                module='HatMonitor',
                type='MsgMaster',
                data=common.msg_master_to_sbs(msg)))

    def _process_msg_slave(self, msg_slave):
        self._master._set_components(self._mid, msg_slave.components)
