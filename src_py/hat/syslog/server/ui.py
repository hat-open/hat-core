"""Web server implementation

Attributes:
    mlog (logging.Logger): module logger
    max_results_limit (int): max results limit

"""

import functools
import logging
import urllib

from hat import juggler
from hat.syslog.server import common
from hat.util import aio


mlog = logging.getLogger(__name__)


max_results_limit = 200


async def create_web_server(conf, backend):
    """Create web server

    Args:
        conf (hat.syslog.server.conf.WebServerConf): configuration
        backend (hat.syslog.server.backend.Backend): backend

    Returns:
        WebServer

    """
    addr = urllib.parse.urlparse(conf.addr)
    if addr.scheme == 'http':
        addr = addr._replace(scheme='ws', path='ws')
    elif addr.scheme == 'https':
        addr = addr._replace(scheme='wss', path='ws')
    else:
        raise ValueError(f'invalid address {conf.address}')

    def on_connection(conn):
        async_group.spawn(_run_client, async_group, backend, conn)

    async_group = aio.Group()
    srv = await juggler.listen(addr.geturl(), on_connection,
                               static_path=conf.path)
    async_group.spawn(aio.call_on_cancel, srv.async_close)

    server = WebServer()
    server._async_group = async_group
    return server


class WebServer:

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._async_group.closed

    async def async_close(self):
        """Async close"""
        await self._async_group.async_close()


async def _run_client(async_group, backend, conn):
    change_queue = aio.Queue()
    async_group = async_group.create_subgroup()
    async_group.spawn(aio.call_on_cancel, conn.async_close)
    async_group.spawn(_change_loop, async_group, backend, conn, change_queue)
    try:
        with backend.register_change_cb(change_queue.put_nowait):
            with conn.register_change_cb(
                    functools.partial(change_queue.put_nowait, [])):
                await conn.closed
    finally:
        async_group.close()


async def _change_loop(async_group, backend, conn, change_queue):
    try:
        filter_json = common.filter_to_json(
            common.Filter(max_results=max_results_limit))
        first_id = backend.first_id
        last_id = backend.last_id
        filter_changed = True
        new_entries_json = []

        while True:
            if filter_changed:
                filter = common.filter_from_json(filter_json)
                entries = await backend.query(filter)
                entries_json = [common.entry_to_json(entry)
                                for entry in entries]
            elif new_entries_json:
                new_entries_json = [i for i in new_entries_json
                                    if _match_entry(filter_json, i)]
                entries_json = new_entries_json + entries_json
                entries_json = entries_json[:filter.max_results]

            conn.set_local_data({'filter': filter_json,
                                 'entries': entries_json,
                                 'first_id': first_id,
                                 'last_id': last_id})

            new_entries = await change_queue.get()
            new_entries_json = [common.entry_to_json(entry)
                                for entry in new_entries]

            first_id = backend.first_id
            last_id = backend.last_id
            new_filter_json = _sanitize_filter(conn.remote_data)
            filter_changed = new_filter_json != filter_json
            filter_json = new_filter_json
    finally:
        async_group.close()


def _sanitize_filter(filter_json):
    if not filter_json:
        filter_json = common.filter_to_json(
            common.Filter(max_results=max_results_limit))
    if (filter_json['max_results'] is None or
            filter_json['max_results'] > max_results_limit):
        filter_json = dict(filter_json, max_results=max_results_limit)
    return filter_json


def _match_entry(filter_json, entry_json):
    if (filter_json['last_id'] is not None
            and entry_json['id'] > filter_json['last_id']):
        return False
    if (filter_json['entry_timestamp_from'] is not None
            and entry_json['timestamp'] < filter_json['entry_timestamp_from']):
        return False
    if (filter_json['entry_timestamp_to'] is not None
            and entry_json['timestamp'] > filter_json['entry_timestamp_to']):
        return False
    if (filter_json['facility'] is not None and
            entry_json['msg']['facility'] != filter_json['facility']):
        return False
    if (filter_json['severity'] is not None and
            entry_json['msg']['severity'] != filter_json['severity']):
        return False
    if not _match_str_filter(filter_json['hostname'],
                             entry_json['msg']['hostname']):
        return False
    if not _match_str_filter(filter_json['app_name'],
                             entry_json['msg']['app_name']):
        return False
    if not _match_str_filter(filter_json['procid'],
                             entry_json['msg']['procid']):
        return False
    if not _match_str_filter(filter_json['msgid'],
                             entry_json['msg']['msgid']):
        return False
    if not _match_str_filter(filter_json['msg'],
                             entry_json['msg']['msg']):
        return False
    return True


def _match_str_filter(filter, value):
    return not filter or filter in value
