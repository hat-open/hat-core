"""Implementations of interface to master monitor server

Attributes:
    mlog (logging.Logger): module logger
    connect_retry_delay (float): delay before retrying to connect to remote
        master in seconds
    connect_retry_count (int): number of trials for connecting to remote
        master until waiting for `connect_retry_delay`
    connected_timeout (float): timeout (in seconds) on initial trial for
        connecting to remote master. If connection is not established until
        the timeout, local master is run and trial for connection to remote
        master is restarted again.

"""

import abc
import asyncio
import contextlib
import logging

from hat import aio
from hat import chatter
from hat import util
from hat.monitor import common
from hat.monitor.server import blessing


mlog = logging.getLogger(__name__)

connect_retry_delay = 0.5

connect_retry_count = 3

connected_timeout = 2

_last_mid = 0


async def run(conf, master_change_cb):
    """Run connect to master loop

    This method runs indefinitely trying to establish connection with parent
    master monitor. Based on connection availability, `master_change_cb`
    is called when new instance of Master interface is created or existing
    is closed. Connection to remote master is considered established once
    first `MsgMaster` is received.

    Args:
        conf (hat.json.Data): configuration defined by
            ``hat://monitor/main.yaml#/definitions/master``
        master_change_cb (Callable[[Optional[Master]],None]):
            master change callback

    """
    local_master_group = None
    remote_master = None
    listener = await _create_listener(conf['address'])
    try:
        if not conf['parents']:
            await _run_local_master(conf, listener, master_change_cb)
            return
        while True:
            remote_master = await _connect_remote_with_timeout(
                conf['parents'], connected_timeout)
            if not remote_master:
                local_master_group = aio.Group()
                local_master_group.spawn(_run_local_master, conf,
                                         listener, master_change_cb)
                remote_master = await _connect_remote_loop(conf['parents'])
            if local_master_group:
                await local_master_group.async_close()
                local_master_group = None
            master_change_cb(remote_master)
            await remote_master.closed
            master_change_cb(None)
    finally:
        await listener.async_close()
        if local_master_group:
            await local_master_group.async_close()
        if remote_master:
            await remote_master.closed


async def _run_local_master(conf, listener, master_change_cb):
    master = _create_local_master(conf)
    master_change_cb(master)
    try:
        with listener.register(master._on_connection):
            await master.closed
    finally:
        await master.async_close()
        master_change_cb(None)


async def _connect_remote_loop(parents):
    loop_counter = 0
    while True:
        if loop_counter >= connect_retry_count:
            await asyncio.sleep(connect_retry_delay)
            loop_counter = 0
        for parent in parents:
            try:
                return await _create_remote_master(parent)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                mlog.debug("error on connection to parent monitor %s: "
                           "%s", parent, e, exc_info=e)
                continue
        loop_counter += 1


async def _connect_remote_with_timeout(parents, timeout):
    try:
        return await asyncio.wait_for(_connect_remote_loop(parents),
                                      connected_timeout)
    except asyncio.TimeoutError:
        return


async def _create_listener(address):
    listener = _Listener()
    listener._cbs = set()
    listener._connection_cbs = util.CallbackRegistry()
    listener._async_group = aio.Group(
        lambda e: mlog.error("error in listener: %s", e, exc_info=e))
    chatter_server = await chatter.listen(
        common.sbs_repo, address, listener._on_connection)
    listener._async_group.spawn(aio.call_on_cancel, chatter_server.async_close)
    return listener


class _Listener:

    @property
    def closed(self):
        return self._async_group.closed

    async def async_close(self):
        await self._async_group.async_close()

    def register(self, cb):
        return self._connection_cbs.register(cb)

    def _on_connection(self, conn):
        if not self._connection_cbs._cbs:
            self._async_group.spawn(self._close_connection, conn)
            return
        self._connection_cbs.notify(conn)

    async def _close_connection(self, conn):
        await aio.uncancellable(conn.async_close(), raise_cancel=False)


class Master(abc.ABC):
    """Master interface

    Instances of this class should not be created outside of this module.
    Should not create instances of this class calling its constructor.

    """

    @property
    @abc.abstractmethod
    def closed(self):
        """asyncio.Future: closed future"""

    @property
    @abc.abstractmethod
    def mid(self):
        """int: local monitor id"""

    @property
    @abc.abstractmethod
    def components(self):
        """List[common.ComponentInfo]: global components state"""

    @abc.abstractmethod
    def register_change_cb(self, cb):
        """Register change callback

        Change callback is called once mid and/or components property changes.

        Args:
            cb (Callable[[],None]): change callback

        Returns:
            util.RegisterCallbackHandle

        """

    @abc.abstractmethod
    async def async_close(self):
        """Close server and all active connections"""

    @abc.abstractmethod
    def set_components(self, components):
        """Set local components info

        Args:
            components (List[common.ComponentInfo]): local components info

        """

    @abc.abstractmethod
    def set_rank(self, cid, mid, rank):
        """Set component's rank

        Args:
            cid (int): component id
            mid (int): component's local monitor id
            rank (int): component's rank

        """


def _create_local_master(conf):
    master = LocalMaster()
    master._async_group = aio.Group(exception_cb=master._on_exception)
    master._change_cbs = util.CallbackRegistry()
    master._mid = 0
    master._connections = {}
    master._global_components = []
    master._default_algorithm = blessing.Algorithm[conf['default_algorithm']]
    master._group_algorithms = {
        group: blessing.Algorithm[alg]
        for group, alg in conf['group_algorithms'].items()}
    return master


class LocalMaster(Master):
    """Local master implementation"""

    @property
    def closed(self):
        """See :meth:`hat.monitor.master.Master.closed`"""
        return self._async_group.closed

    @property
    def mid(self):
        """See :meth:`hat.monitor.master.Master.mid`"""
        return self._mid

    @property
    def components(self):
        """See :meth:`hat.monitor.master.Master.components`"""
        return self._global_components

    def register_change_cb(self, cb):
        """See :meth:`hat.monitor.master.Master.register_change_cb`"""
        return self._change_cbs.register(cb)

    async def async_close(self):
        """See :meth:`hat.monitor.master.Master.async_close`"""
        await self._async_group.async_close()

    def set_components(self, components):
        """See :meth:`hat.monitor.master.Master.set_components`"""
        self._update_global_on_local_components(components, self._mid)

    def set_rank(self, cid, mid, rank):
        """See :meth:`hat.monitor.master.Master.set_rank`"""
        self._calculate_global_components([
            i._replace(rank=rank) if i.cid == cid and i.mid == mid else i
            for i in self._global_components])

    def _send_msg_master(self, conn):
        conn.send(chatter.Data(
            module='HatMonitor',
            type='MsgMaster',
            data={'mid': self._connections[conn],
                  'components': [common.component_info_to_sbs(i)
                                 for i in self._global_components]}))

    def _calculate_global_components(self, new_components):
        new_global_components = blessing.calculate_blessing(
            group_algorithms=self._group_algorithms,
            components=new_components,
            default_algorithm=self._default_algorithm)
        if new_global_components == self._global_components:
            return
        self._global_components = new_global_components
        mlog.debug('blessing changed')
        for conn in self._connections:
            with contextlib.suppress(chatter.ConnectionClosedError):
                self._send_msg_master(conn)
        self._change_cbs.notify()

    def _on_connection(self, conn):
        self._async_group.spawn(self._connection_loop, conn)

    async def _connection_loop(self, conn):
        global _last_mid
        mid = _last_mid + 1
        _last_mid += 1
        self._connections[conn] = mid
        self._send_msg_master(conn)
        try:
            while True:
                msg = await conn.receive()
                if (msg.data.module != 'HatMonitor' or
                        not(msg.data.type == 'MsgSlave' or
                            msg.data.type == 'MsgSetRank')):
                    raise Exception('Message received from slave malformed: '
                                    'message MsgSlave or MsgSetRank from '
                                    'HatMonitor module expected')
                {'MsgSlave': self._process_msg_slave,
                 'MsgSetRank': self._process_msg_set_rank
                 }[msg.data.type](conn, msg)
        except chatter.ConnectionClosedError:
            mlog.debug("connection with mid=%s closed", mid)
        finally:
            await conn.async_close()
            del self._connections[conn]
            self._calculate_global_components(
                [i for i in self._global_components if i.mid != mid])

    def _process_msg_slave(self, conn, msg):
        slave_components = [common.component_info_from_sbs(i)
                            for i in msg.data.data['components']]
        slave_mid = self._connections[conn]
        self._update_global_on_local_components(slave_components, slave_mid)

    def _process_msg_set_rank(self, conn, msg):
        self.set_rank(msg.data.data['cid'],
                      msg.data.data['mid'],
                      msg.data.data['rank'])

    def _update_global_on_local_components(self, local_components, mid):
        new_global_components = [i for i in self._global_components
                                 if i.mid != mid]
        for c in local_components:
            old_c = util.first(self._global_components,
                               lambda i: i.cid == c.cid and i.mid == c.mid)
            if old_c:
                new_global_components.append(
                    c._replace(blessing=old_c.blessing))
            else:
                new_global_components.append(c)
        self._calculate_global_components(new_global_components)

    def _on_exception(self, e):
        mlog.error("exception in local master connection loop: %s",
                   e, exc_info=e)


async def _create_remote_master(parent_address):
    master = RemoteMaster()
    master._async_group = aio.Group(exception_cb=master._on_exception)
    master._change_cbs = util.CallbackRegistry()
    master._local_components = []
    master._mid = None
    master._components = []
    master._parent_address = parent_address
    master._conn = await chatter.connect(common.sbs_repo, parent_address)
    msg_master = await master._conn.receive()
    master._process_msg_master(msg_master)
    master._async_group.spawn(aio.call_on_cancel, master._conn.async_close)
    master._async_group.spawn(master._receive_loop)
    return master


class RemoteMaster(Master):
    """Remote master interface"""

    @property
    def closed(self):
        """See :meth:`hat.monitor.master.Master.closed`"""
        return self._async_group.closed

    @property
    def mid(self):
        """See :meth:`hat.monitor.master.Master.mid`"""
        return self._mid

    @property
    def components(self):
        """See :meth:`hat.monitor.master.Master.components`"""
        return self._components

    def register_change_cb(self, cb):
        """See :meth:`hat.monitor.master.Master.register_change_cb`"""
        return self._change_cbs.register(cb)

    async def async_close(self):
        """Close connection and master listening socket"""
        await self._async_group.async_close()

    def set_components(self, components):
        """See :meth:`hat.monitor.master.Master.set_components`"""
        self._local_components = components
        self._send_msg_slave()

    def set_rank(self, cid, mid, rank):
        """See :meth:`hat.monitor.master.Master.set_rank`"""
        self._send_msg_set_rank(cid, mid, rank)

    def _send_msg_slave(self):
        self._conn.send(chatter.Data(
            module='HatMonitor',
            type='MsgSlave',
            data={'components': [common.component_info_to_sbs(i)
                                 for i in self._local_components]}))

    def _send_msg_set_rank(self, cid, mid, rank):
        self._conn.send(chatter.Data(
            module='HatMonitor',
            type='MsgSetRank',
            data={'cid': cid,
                  'mid': mid,
                  'rank': rank}))

    def _process_msg_master(self, msg_master):
        if (msg_master.data.module != 'HatMonitor' or
                msg_master.data.type != 'MsgMaster'):
            raise Exception('Message received from master malformed: '
                            'message MsgMaster from HatMonitor module '
                            'expected')
        self._mid = msg_master.data.data['mid']
        self._components = [common.component_info_from_sbs(i)
                            for i in msg_master.data.data['components']]
        self._change_cbs.notify()

    async def _receive_loop(self):
        try:
            while True:
                msg = await self._conn.receive()
                self._process_msg_master(msg)
        except chatter.ConnectionClosedError:
            mlog.debug("connection to %s closed", self._parent_address)
        finally:
            self._async_group.close()

    def _on_exception(self, e):
        mlog.error("exception in remote master receive loop: %s",
                   e, exc_info=e)
