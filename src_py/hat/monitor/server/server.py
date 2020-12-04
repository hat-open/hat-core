"""Implementation of local monitor server

Attributes:
    mlog (logging.Logger): module logger

"""

import contextlib
import logging

from hat import aio
from hat import chatter
from hat import util
from hat.monitor import common


mlog = logging.getLogger(__name__)

_last_cid = 0


async def create(conf):
    """Create local monitor server

    Args:
        conf (hat.json.Data): configuration defined by
            ``hat://monitor/main.yaml#/definitions/server``

    Returns:
        Server

    """
    server = Server()
    server._default_rank = conf['default_rank']
    server._rank_cache = {}
    server._master = None
    server._mid = 0
    server._components = []
    server._async_group = aio.Group(server._on_exception)
    server._change_cbs = util.CallbackRegistry()
    server._master_change_handler = None
    server._connections = {}
    server._local_components = []
    chatter_server = await chatter.listen(
        sbs_repo=common.sbs_repo,
        address=conf['address'],
        on_connection_cb=lambda conn: server._async_group.spawn(
            server._connection_loop, conn))
    server._async_group.spawn(aio.call_on_cancel, chatter_server.async_close)
    mlog.debug('monitor server listens clients on %s', conf['address'])
    return server


class Server:
    """Local monitor server

    For creating new instance of this class see :func:`create`

    """

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    @property
    def components(self):
        """List[common.ComponentInfo]: global components state

        If connection to monitor is not established, this propertry provides
        list of local components state.

        """
        return self._components

    @property
    def mid(self):
        """int: monitor id"""
        return self._mid

    def register_change_cb(self, cb):
        """Register change callback

        Change callback is called once mid and/or components property changes.

        Args:
            cb (Callable[[],None]): change callback

        Returns:
            util.RegisterCallbackHandle

        """
        return self._change_cbs.register(cb)

    async def async_close(self):
        """Close server and all active connections"""
        await self._async_group.async_close()

    def set_master(self, master):
        """Set master

        Args:
            master (Optional[hat.monitor.master.Master]): master

        """
        if self._master is master:
            return
        if self._master_change_handler:
            self._master_change_handler.cancel()
            self._master_change_handler = None
        self._master = master
        if self._master:
            self._on_master_change()
            self._master_change_handler = master.register_change_cb(
                self._on_master_change)
            self._master.set_components(self._local_components)
        else:
            if self._mid == 0:
                return
            self._mid = 0
            self._local_components = [i._replace(mid=0)
                                      for i in self._local_components]
            self._handle_local_changes()

    def set_rank(self, cid, mid, rank):
        """Set component's rank

        Args:
            cid (int): component id
            mid (int): component's local monitor id
            rank (int): component's rank

        """
        if self._master:
            self._master.set_rank(cid, mid, rank)
        if mid != self.mid:
            return
        self._change_local_component(cid, rank=rank)
        if not self._master:
            self._handle_local_changes()
        info = util.first(self._local_components, lambda i: i.cid == cid)
        if info is None:
            return
        self._rank_cache[info.name, info.group] = info.rank

    def _handle_local_changes(self):
        if self._master:
            self._master.set_components(self._local_components)
        else:
            if self._components == self._local_components:
                return
            self._components = list(self._local_components)
            self._send_msg_server_to_clients()
            self._change_cbs.notify()

    async def _connection_loop(self, conn):
        global _last_cid
        cid = _last_cid + 1
        _last_cid += 1
        self._connections[conn] = cid
        try:
            self._send_msg_server(conn)
            while True:
                msg_client = await conn.receive()
                if (msg_client.data.module != 'HatMonitor' or
                        msg_client.data.type != 'MsgClient'):
                    raise Exception('Message received from client malformed: '
                                    'message MsgClient from HatMonitor module '
                                    'expected')
                self._process_msg_client(msg_client, cid)
                self._handle_local_changes()
        except chatter.ConnectionClosedError:
            mlog.debug('connection %s closed', cid)
        finally:
            await conn.async_close()
            del self._connections[conn]
            self._local_components = [i for i in self._local_components
                                      if i.cid != cid]
            self._handle_local_changes()

    def _send_msg_server_to_clients(self):
        for conn in self._connections.keys():
            with contextlib.suppress(chatter.ConnectionClosedError):
                self._send_msg_server(conn)

    def _send_msg_server(self, conn):
        conn.send(chatter.Data(
            module='HatMonitor',
            type='MsgServer',
            data={'cid': self._connections[conn],
                  'mid': self.mid,
                  'components': [common.component_info_to_sbs(info)
                                 for info in self.components]}))

    def _on_master_change(self):
        if (self._mid == self._master.mid and
                self._components == self._master.components):
            return
        for i in self._master.components:
            if i.mid == self._master.mid:
                self._rank_cache[i.name, i.group] = i.rank
        self._local_components = [
            i._replace(mid=self._master.mid,
                       rank=self._rank_cache.get((i.name, i.group),
                                                 self._default_rank))
            for i in self._local_components]
        self._mid = self._master.mid
        self._components = list(self._master.components)
        self._send_msg_server_to_clients()
        self._change_cbs.notify()

    def _process_msg_client(self, msg_client, cid):
        if util.first(self._local_components, lambda i: i.cid == cid):
            self._change_local_component(
                cid,
                name=msg_client.data.data['name'],
                group=msg_client.data.data['group'],
                address=msg_client.data.data['address'][1],
                ready=msg_client.data.data['ready'][1])
        else:
            self._local_components.append(
                common.ComponentInfo(
                    cid=cid,
                    mid=self.mid,
                    name=msg_client.data.data['name'],
                    group=msg_client.data.data['group'],
                    address=msg_client.data.data['address'][1],
                    rank=self._rank_cache.get((msg_client.data.data['name'],
                                               msg_client.data.data['group']),
                                              self._default_rank),
                    blessing=None,
                    ready=msg_client.data.data['ready'][1]))

    def _change_local_component(self, cid, **kwargs):
        self._local_components = [i._replace(**kwargs) if i.cid == cid else i
                                  for i in self._local_components]

    def _on_exception(self, e):
        mlog.error('error in server receive loop: %s', e, exc_info=e)
