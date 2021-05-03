"""WIP Chrome DevTools Protocol"""

import asyncio
import logging
import typing

import aiohttp

from hat import aio
from hat import json
from hat import util


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


async def connect(host: str,
                  port: int
                  ) -> 'Connection':
    session = aiohttp.ClientSession()

    try:
        res = await session.get(f'http://{host}:{port}/json/version')
        res = await res.json()
        addr = res['webSocketDebuggerUrl']
        ws = await session.ws_connect(addr, max_msg_size=0)

    except BaseException:
        await aio.uncancellable(session.close())
        raise

    conn = Connection()
    conn._ws = ws
    conn._session = session
    conn._async_group = aio.Group()
    conn._event_cbs = util.CallbackRegistry()
    conn._last_id = 0
    conn._result_futures = {}

    conn._async_group.spawn(aio.call_on_cancel, conn._on_close)
    conn._async_group.spawn(conn._receive_loop)

    return conn


EventCb = typing.Callable[['str', json.Data], None]


class Connection(aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    def register_event_cb(self,
                          cb: EventCb
                          ) -> util.RegisterCallbackHandle:
        """Register remote data change callback"""
        return self._event_cbs.register(cb)

    async def call(self,
                   method: str,
                   params: json.Data = {},
                   session_id=None
                   ) -> json.Data:
        if not self.is_open:
            raise ConnectionError()

        self._last_id += 1
        msg = {'id': self._last_id,
               'method': method,
               'params': params}
        if session_id is not None:
            msg['sessionId'] = session_id

        future = asyncio.Future()
        self._result_futures[msg['id']] = future

        try:
            await self._ws.send_json(msg)
            return await future

        finally:
            del self._result_futures[msg['id']]

    async def _on_close(self):
        for future in self._result_futures.values():
            if not future.done():
                future.set_exception(ConnectionError())

        await self._ws.close()
        await self._session.close()

    async def _receive_loop(self):
        try:
            while True:
                msg_ws = await self._ws.receive()
                if self._ws.closed or msg_ws.type == aiohttp.WSMsgType.CLOSING:
                    break
                if msg_ws.type != aiohttp.WSMsgType.TEXT:
                    raise Exception('unsupported message type')

                msg = json.decode(msg_ws.data)

                if 'id' in msg:
                    future = self._result_futures.get(msg['id'])
                    if future and not future.done():
                        future.set_result(msg['result'])

                else:
                    self._event_cbs.notify(msg['method'], msg['params'])

        except Exception as e:
            mlog.error("receive loop error: %s", e, exc_info=e)

        finally:
            self.close()
