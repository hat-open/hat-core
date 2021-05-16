"""IEC 60870-5-104 connection"""

import asyncio
import collections
import logging
import typing

from hat import aio
from hat import util
from hat.drivers import tcp
from hat.drivers.iec104 import _iec104
from hat.drivers.iec104 import common


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""


InterrogateCb = aio.AsyncCallable[
    ['Connection', int],
    typing.Optional[typing.List[common.Data]]]
"""Interrogate callback

This method is called when local peer receives interrogate request.
Called with asdu address, returns list of data. If ``None`` is returned,
negative response is sent.

"""
util.register_type_alias('InterrogateCb')


CounterInterrogateCb = aio.AsyncCallable[
   ['Connection', int, common.FreezeCode],
   typing.Optional[typing.List[common.Data]]]
"""Counter interrogate callback

This method is called when local peer receives counter interrogate request.
Called with asdu address and freeze code, returns list of data. If ``None``
is returned, negative response is sent.

"""
util.register_type_alias('CounterInterrogateCb')


CommandCb = aio.AsyncCallable[
    ['Connection', typing.List[common.Command]],
    bool]
"""Command callback

This method is called when local peer receives command request.
Called with list of commands, returns if commands are successful.

"""
util.register_type_alias('CommandCb')


ConnectionCb = aio.AsyncCallable[['Connection'], None]
"""Connection callback"""
util.register_type_alias('ConnectionCb')


class Address(typing.NamedTuple):
    host: str
    port: int = 2404


class ConnectionInfo(typing.NamedTuple):
    local_addr: Address
    remote_addr: Address


async def connect(addr: Address,
                  interrogate_cb: typing.Optional[InterrogateCb] = None,
                  counter_interrogate_cb: typing.Optional[CounterInterrogateCb] = None,  # NOQA
                  command_cb: typing.Optional[CommandCb] = None,
                  response_timeout: float = 15,
                  supervisory_timeout: float = 10,
                  test_timeout: float = 20,
                  send_window_size: int = 12,
                  receive_window_size: int = 8
                  ) -> 'Connection':
    """Connect to remote device

    Args:
        addr: remote server's address
        interrogate_cb: interrogate callback
        counter_interrogate_cb: counter interrogate callback
        command_cb: command callback
        response_timeout: response timeout (t1) in seconds
        supervisory_timeout: supervisory timeout (t2) in seconds
        test_timeout: test timeout (t3) in seconds
        send_window_size: send window size (k)
        receive_window_size: receive window size (w)

    """

    def write_apdu(apdu):
        _iec104.write_apdu(conn, apdu)

    async def wait_startdt_con():
        while True:
            apdu = await _iec104.read_apdu(conn)

            if not isinstance(apdu, _iec104.APDUU):
                continue

            if apdu.function == _iec104.ApduFunction.STARTDT_CON:
                return

            if apdu.function == _iec104.ApduFunction.TESTFR_ACT:
                write_apdu(_iec104.APDUU(_iec104.ApduFunction.TESTFR_CON))

    conn = await tcp.connect(tcp.Address(*addr))

    try:
        write_apdu(_iec104.APDUU(_iec104.ApduFunction.STARTDT_ACT))
        await aio.wait_for(wait_startdt_con(), response_timeout)

    except Exception:
        await aio.uncancellable(conn.async_close())
        raise

    transport = _iec104.Transport(conn=conn,
                                  always_enabled=True,
                                  response_timeout=response_timeout,
                                  supervisory_timeout=supervisory_timeout,
                                  test_timeout=test_timeout,
                                  send_window_size=send_window_size,
                                  receive_window_size=receive_window_size)

    return _create_connection(transport=transport,
                              interrogate_cb=interrogate_cb,
                              counter_interrogate_cb=counter_interrogate_cb,
                              command_cb=command_cb)


async def listen(connection_cb: ConnectionCb,
                 addr: Address = Address('0.0.0.0'),
                 interrogate_cb: typing.Optional[InterrogateCb] = None,
                 counter_interrogate_cb: typing.Optional[CounterInterrogateCb] = None,  # NOQA
                 command_cb: typing.Optional[CommandCb] = None,
                 response_timeout: float = 15,
                 supervisory_timeout: float = 10,
                 test_timeout: float = 20,
                 send_window_size: int = 12,
                 receive_window_size: int = 8
                 ) -> 'Server':
    """Create new IEC104 slave and listen for incoming connections

    Args:
        connection_cb: new connection callback
        addr: listening socket address
        interrogate_cb: interrogate callback
        counter_interrogate_cb: counter interrogate callback
        command_cb: command callback
        response_timeout: response timeout (t1) in seconds
        supervisory_timeout: supervisory timeout (t2) in seconds
        test_timeout: test timeout (t3) in seconds
        send_window_size: send window size (k)
        receive_window_size: receive window size (w)

    """
    server = Server()
    server._connection_cb = connection_cb
    server._interrogate_cb = interrogate_cb
    server._counter_interrogate_cb = counter_interrogate_cb
    server._command_cb = command_cb
    server._response_timeout = response_timeout
    server._supervisory_timeout = supervisory_timeout
    server._test_timeout = test_timeout
    server._send_window_size = send_window_size
    server._receive_window_size = receive_window_size

    server._srv = await tcp.listen(server._on_connection, tcp.Address(*addr),
                                   bind_connections=True)
    server._addresses = [Address(*i) for i in server._srv.addresses]

    return server


class Server(aio.Resource):
    """Server

    For creating new Server instances see `listen` coroutine.

    Closing server closes all incoming connections.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._srv.async_group

    @property
    def addresses(self) -> typing.List[Address]:
        """Listening addresses"""
        return self._addresses

    async def _on_connection(self, conn):
        transport = _iec104.Transport(
            conn=conn,
            always_enabled=False,
            response_timeout=self._response_timeout,
            supervisory_timeout=self._supervisory_timeout,
            test_timeout=self._test_timeout,
            send_window_size=self._send_window_size,
            receive_window_size=self._receive_window_size)

        conn = _create_connection(
            transport=transport,
            interrogate_cb=self._interrogate_cb,
            counter_interrogate_cb=self._counter_interrogate_cb,
            command_cb=self._command_cb)

        await aio.call(self._connection_cb, conn)


def _create_connection(transport, interrogate_cb,
                       counter_interrogate_cb, command_cb,):

    info = ConnectionInfo(
        local_addr=Address(*transport.conn.info.local_addr),
        remote_addr=Address(*transport.conn.info.remote_addr))

    conn = Connection()
    conn._transport = transport
    conn._interrogate_cb = interrogate_cb
    conn._counter_interrogate_cb = counter_interrogate_cb
    conn._command_cb = command_cb
    conn._info = info
    conn._interrogate_queue = None
    conn._interrogate_lock = asyncio.Lock()
    conn._counter_interrogate_queue = None
    conn._counter_interrogate_lock = asyncio.Lock()
    conn._data_queue = aio.Queue()
    conn._command_futures = {}
    conn.async_group.spawn(conn._read_loop)
    return conn


class Connection(aio.Resource):
    """Single IEC104 connection

    For creating new Connection instances see `connect` coroutine.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._transport.async_group

    @property
    def info(self) -> ConnectionInfo:
        """Connection info"""
        return self._info

    def notify_data_change(self, data: typing.List[common.Data]):
        """Notify local data change"""
        if not self.is_open:
            raise ConnectionError()

        for i in data:
            asdu = _asdu_from_data(i)
            self._transport.write(asdu)

    async def interrogate(self,
                          asdu_address: int = 0xFFFF
                          ) -> typing.List[common.Data]:
        """Interrogate remote device

        Asdu broadcast address 0xFFFF is not supported by all devices

        """
        element = _iec104.IOElement_C_IC_NA(qualifier=20)
        io = _iec104.IO(address=0,
                        elements=[element],
                        time=None)
        asdu = _iec104.ASDU(type=_iec104.AsduType.C_IC_NA,
                            cause=common.Cause.ACTIVATION,
                            is_negative_confirm=False,
                            is_test=False,
                            originator_address=None,
                            address=asdu_address,
                            ios=[io])

        async with self._interrogate_lock:
            if not self.is_open:
                raise ConnectionError()

            self._transport.write(asdu)
            self._interrogate_queue = aio.Queue()

            try:
                data = collections.deque()
                async for i in self._interrogate_queue:
                    data.extend(i)

            finally:
                self._interrogate_queue = None

            if not self.is_open:
                raise ConnectionError()

            return list(data)

    async def counter_interrogate(self,
                                  asdu_address: int = 0xFFFF,
                                  freeze: common.FreezeCode = common.FreezeCode.READ  # NOQA
                                  ) -> typing.List[common.Data]:
        """Interrogate remote device counters

        Asdu broadcast address 0xFFFF is not supported by all devices

        """
        element = _iec104.IOElement_C_CI_NA(request=5,
                                            freeze=freeze)
        io = _iec104.IO(address=0,
                        elements=[element],
                        time=None)
        asdu = _iec104.ASDU(type=_iec104.AsduType.C_CI_NA,
                            cause=common.Cause.ACTIVATION,
                            is_negative_confirm=False,
                            is_test=False,
                            originator_address=None,
                            address=asdu_address,
                            ios=[io])

        async with self._counter_interrogate_lock:
            if not self.is_open:
                raise ConnectionError()

            self._transport.write(asdu)
            self._counter_interrogate_queue = aio.Queue()

            try:
                data = collections.deque()
                async for i in self._counter_interrogate_queue:
                    data.extend(i)

            finally:
                self._counter_interrogate_queue = None

            if not self.is_open:
                raise ConnectionError()

            return list(data)

    async def receive(self) -> typing.List[common.Data]:
        """Receive remote data change"""
        try:
            return await self._data_queue.get()

        except aio.QueueClosedError:
            raise ConnectionError()

    async def send_command(self,
                           cmd: common.Command
                           ) -> bool:
        """Send command

        Returns command success result

        """
        if not self.is_open:
            raise ConnectionError()

        asdu = _asdu_from_command(cmd)
        key = asdu.type, cmd.asdu_address, cmd.io_address
        if key in self._command_futures:
            return False

        self._transport.write(asdu)

        future = asyncio.Future()
        try:
            self._command_futures[key] = future
            return await future

        finally:
            del self._command_futures[key]

        return False

    async def _read_loop(self):
        try:
            mlog.debug("connection active: %s", self._info)

            while True:
                asdu = await self._transport.read()

                if asdu.type in _interrogate_asdu_types:
                    await self._process_interrogate(asdu)

                elif asdu.type in _data_asdu_types:
                    await self._process_data(asdu)

                elif asdu.type in _command_asdu_types:
                    await self._process_command(asdu)

                else:
                    mlog.warning("unsupported ASDU type: %s", asdu.type)

        except ConnectionError:
            pass

        except Exception as e:
            mlog.warning("read loop error: %s", e, exc_info=e)

        finally:
            mlog.debug("closing connection: %s", self._info)
            self.close()

            self._data_queue.close()
            if self._interrogate_queue is not None:
                self._interrogate_queue.close()
            if self._counter_interrogate_queue is not None:
                self._counter_interrogate_queue.close()

            for future in self._command_futures.values():
                if not future.done():
                    future.set_exception(ConnectionError())

    async def _process_interrogate(self, asdu):
        if asdu.cause == common.Cause.ACTIVATION:
            await self._process_interrogate_activation(asdu)

        elif asdu.cause == common.Cause.DEACTIVATION:
            await self._process_interrogate_deactivation(asdu)

        elif asdu.cause == common.Cause.ACTIVATION_CONFIRMATION:
            await self._process_interrogate_activation_confirmation(asdu)

        elif asdu.cause == common.Cause.ACTIVATION_TERMINATION:
            await self._process_interrogate_activation_termination(asdu)

    async def _process_interrogate_activation(self, asdu):
        is_counter_interrogate = (asdu.type == _iec104.AsduType.C_CI_NA)

        try:
            if is_counter_interrogate:
                freeze = common.FreezeCode.READ
                freeze = asdu.ios[0].elements[0].freeze
                data = await aio.call(self._counter_interrogate_cb, self,
                                      asdu.address, freeze)

            else:
                data = await aio.call(self._interrogate_cb, self,
                                      asdu.address)

        except Exception as e:
            mlog.warning('interrogate error: %s', e, exc_info=e)
            data = None

        # TODO should check requested qualifier
        element = (_iec104.IOElement_C_CI_NA(5, freeze)
                   if is_counter_interrogate
                   else _iec104.IOElement_C_IC_NA(20))
        io = _iec104.IO(address=0,
                        time=None,
                        elements=[element])

        self._transport.write(_iec104.ASDU(
            type=asdu.type,
            cause=common.Cause.ACTIVATION_CONFIRMATION,
            is_negative_confirm=data is None,
            is_test=False,
            originator_address=None,
            address=asdu.address,
            ios=[io]))

        if data is None:
            return

        data_cause = (common.Cause.INTERROGATED_COUNTER
                      if is_counter_interrogate
                      else common.Cause.INTERROGATED_STATION)
        for i in data:
            data_asdu = _asdu_from_data(i)
            data_asdu = data_asdu._replace(cause=data_cause)
            self._transport.write(data_asdu)

        self._transport.write(_iec104.ASDU(
            type=asdu.type,
            cause=common.Cause.ACTIVATION_TERMINATION,
            is_negative_confirm=False,
            is_test=False,
            originator_address=None,
            address=asdu.address,
            ios=[io]))

    async def _process_interrogate_deactivation(self, asdu):
        self._transport.write(_iec104.ASDU(
            type=asdu.type,
            cause=common.Cause.DEACTIVATION_CONFIRMATION,
            is_negative_confirm=True,
            is_test=False,
            originator_address=None,
            address=asdu.address,
            ios=asdu.ios))

    async def _process_interrogate_activation_confirmation(self, asdu):
        if not asdu.is_negative_confirm:
            return

        queue = (self._counter_interrogate_queue
                 if asdu.type == _iec104.AsduType.C_CI_NA
                 else self._interrogate_queue)
        if queue is not None:
            queue.close()

    async def _process_interrogate_activation_termination(self, asdu):
        queue = (self._counter_interrogate_queue
                 if asdu.type == _iec104.AsduType.C_CI_NA
                 else self._interrogate_queue)
        if queue is not None:
            queue.close()

    async def _process_data(self, asdu):
        data = _asdu_to_data(asdu)

        if asdu.cause in _interrogate_causes:
            if (self._interrogate_queue is not None and
                    not self._interrogate_queue.is_closed):
                self._interrogate_queue.put_nowait(data)

        elif asdu.cause in _counter_interrogate_causes:
            if (self._counter_interrogate_queue is not None and
                    not self._counter_interrogate_queue.is_closed):
                self._counter_interrogate_queue.put_nowait(data)

        else:
            self._data_queue.put_nowait(data)

    async def _process_command(self, asdu):
        if asdu.cause == common.Cause.ACTIVATION:
            await self._process_command_activation(asdu)

        elif asdu.cause == common.Cause.DEACTIVATION:
            await self._process_command_deactivation(asdu)

        elif asdu.cause == common.Cause.ACTIVATION_CONFIRMATION:
            await self._process_command_activation_confirmation(asdu)

        elif asdu.cause == common.Cause.DEACTIVATION_CONFIRMATION:
            await self._process_command_deactivation_confirmation(asdu)

        elif asdu.cause == common.Cause.ACTIVATION_TERMINATION:
            await self._process_command_activation_termination(asdu)

    async def _process_command_activation(self, asdu):
        cmds = _asdu_to_commands(asdu)

        try:
            result = await aio.call(self._command_cb, self, cmds)

        except Exception as e:
            mlog.warning('command activation error: %s', e, exc_info=e)
            result = False

        self._transport.write(_iec104.ASDU(
            type=asdu.type,
            cause=common.Cause.ACTIVATION_CONFIRMATION,
            is_negative_confirm=not result,
            is_test=False,
            originator_address=None,
            address=asdu.address,
            ios=asdu.ios))

    async def _process_command_deactivation(self, asdu):
        cmds = _asdu_to_commands(asdu)

        try:
            result = await aio.call(self._command_cb, self, cmds)

        except Exception as e:
            mlog.warning('command deactivation error: %s', e, exc_info=e)
            result = False

        self._transport.write(_iec104.ASDU(
            type=asdu.type,
            cause=common.Cause.DEACTIVATION_CONFIRMATION,
            is_negative_confirm=not result,
            is_test=False,
            originator_address=None,
            address=asdu.address,
            ios=asdu.ios))

    async def _process_command_activation_confirmation(self, asdu):
        for io in asdu.ios:
            key = asdu.type, asdu.address, io.address
            future = self._command_futures.get(key)
            if not future or future.done():
                continue
            future.set_result(not asdu.is_negative_confirm)

    async def _process_command_deactivation_confirmation(self, asdu):
        for io in asdu.ios:
            key = asdu.type, asdu.address, io.address
            future = self._command_futures.get(key)
            if not future or future.done():
                continue
            future.set_result(not asdu.is_negative_confirm)

    async def _process_command_activation_termination(self, asdu):
        pass


_interrogate_asdu_types = {_iec104.AsduType.C_IC_NA,
                           _iec104.AsduType.C_CI_NA}

_data_asdu_types_without_time = {_iec104.AsduType.M_SP_NA,
                                 _iec104.AsduType.M_DP_NA,
                                 _iec104.AsduType.M_ST_NA,
                                 _iec104.AsduType.M_BO_NA,
                                 _iec104.AsduType.M_ME_NA,
                                 _iec104.AsduType.M_ME_NB,
                                 _iec104.AsduType.M_ME_NC,
                                 _iec104.AsduType.M_IT_NA}

_data_asdu_types_with_time = {_iec104.AsduType.M_SP_TB,
                              _iec104.AsduType.M_DP_TB,
                              _iec104.AsduType.M_ST_TB,
                              _iec104.AsduType.M_BO_TB,
                              _iec104.AsduType.M_ME_TD,
                              _iec104.AsduType.M_ME_TE,
                              _iec104.AsduType.M_ME_TF,
                              _iec104.AsduType.M_IT_TB}

_data_asdu_types = {*_data_asdu_types_without_time,
                    *_data_asdu_types_with_time}

_command_asdu_types_without_time = {_iec104.AsduType.C_SC_NA,
                                    _iec104.AsduType.C_DC_NA,
                                    _iec104.AsduType.C_RC_NA,
                                    _iec104.AsduType.C_SE_NA,
                                    _iec104.AsduType.C_SE_NB,
                                    _iec104.AsduType.C_SE_NC}

_command_asdu_types_with_time = {_iec104.AsduType.C_SC_TA,
                                 _iec104.AsduType.C_DC_TA,
                                 _iec104.AsduType.C_RC_TA,
                                 _iec104.AsduType.C_SE_TA,
                                 _iec104.AsduType.C_SE_TB,
                                 _iec104.AsduType.C_SE_TC}

_command_asdu_types = {*_command_asdu_types_without_time,
                       *_command_asdu_types_with_time}

_interrogate_causes = {common.Cause.INTERROGATED_STATION,
                       common.Cause.INTERROGATED_GROUP01,
                       common.Cause.INTERROGATED_GROUP02,
                       common.Cause.INTERROGATED_GROUP03,
                       common.Cause.INTERROGATED_GROUP04,
                       common.Cause.INTERROGATED_GROUP05,
                       common.Cause.INTERROGATED_GROUP06,
                       common.Cause.INTERROGATED_GROUP07,
                       common.Cause.INTERROGATED_GROUP08,
                       common.Cause.INTERROGATED_GROUP09,
                       common.Cause.INTERROGATED_GROUP10,
                       common.Cause.INTERROGATED_GROUP11,
                       common.Cause.INTERROGATED_GROUP12,
                       common.Cause.INTERROGATED_GROUP13,
                       common.Cause.INTERROGATED_GROUP14,
                       common.Cause.INTERROGATED_GROUP15,
                       common.Cause.INTERROGATED_GROUP16}

_counter_interrogate_causes = {common.Cause.INTERROGATED_COUNTER,
                               common.Cause.INTERROGATED_COUNTER01,
                               common.Cause.INTERROGATED_COUNTER02,
                               common.Cause.INTERROGATED_COUNTER03,
                               common.Cause.INTERROGATED_COUNTER04}


def _asdu_to_data(asdu):
    data = collections.deque()
    for io in asdu.ios:
        for element in io.elements:
            quality = (element.quality if hasattr(element, 'quality')
                       else None)

            data.append(common.Data(value=element.value,
                                    quality=quality,
                                    time=io.time,
                                    asdu_address=asdu.address,
                                    io_address=io.address,
                                    cause=asdu.cause,
                                    is_test=asdu.is_test))

    return list(data)


def _asdu_from_data(data):
    if isinstance(data.value, common.SingleValue):
        if data.time is None:
            asdu_type = _iec104.AsduType.M_SP_NA
            element = _iec104.IOElement_M_SP_NA(data.value, data.quality)
        else:
            asdu_type = _iec104.AsduType.M_SP_TB
            element = _iec104.IOElement_M_SP_TB(data.value, data.quality)

    elif isinstance(data.value, common.DoubleValue):
        if data.time is None:
            asdu_type = _iec104.AsduType.M_DP_NA
            element = _iec104.IOElement_M_DP_NA(data.value, data.quality)
        else:
            asdu_type = _iec104.AsduType.M_DP_TB
            element = _iec104.IOElement_M_DP_TB(data.value, data.quality)

    elif isinstance(data.value, common.StepPositionValue):
        if data.time is None:
            asdu_type = _iec104.AsduType.M_ST_NA
            element = _iec104.IOElement_M_ST_NA(data.value, data.quality)
        else:
            asdu_type = _iec104.AsduType.M_ST_TB
            element = _iec104.IOElement_M_ST_TB(data.value, data.quality)

    elif isinstance(data.value, common.BitstringValue):
        if data.time is None:
            asdu_type = _iec104.AsduType.M_BO_NA
            element = _iec104.IOElement_M_BO_NA(data.value, data.quality)
        else:
            asdu_type = _iec104.AsduType.M_BO_TB
            element = _iec104.IOElement_M_BO_TB(data.value, data.quality)

    elif isinstance(data.value, common.NormalizedValue):
        if data.time is None:
            asdu_type = _iec104.AsduType.M_ME_NA
            element = _iec104.IOElement_M_ME_NA(data.value, data.quality)
        else:
            asdu_type = _iec104.AsduType.M_ME_TD
            element = _iec104.IOElement_M_ME_TD(data.value, data.quality)

    elif isinstance(data.value, common.ScaledValue):
        if data.time is None:
            asdu_type = _iec104.AsduType.M_ME_NB
            element = _iec104.IOElement_M_ME_NB(data.value, data.quality)
        else:
            asdu_type = _iec104.AsduType.M_ME_TE
            element = _iec104.IOElement_M_ME_TE(data.value, data.quality)

    elif isinstance(data.value, common.FloatingValue):
        if data.time is None:
            asdu_type = _iec104.AsduType.M_ME_NC
            element = _iec104.IOElement_M_ME_NC(data.value, data.quality)
        else:
            asdu_type = _iec104.AsduType.M_ME_TF
            element = _iec104.IOElement_M_ME_TF(data.value, data.quality)

    elif isinstance(data.value, common.BinaryCounterValue):
        if data.time is None:
            asdu_type = _iec104.AsduType.M_IT_NA
            element = _iec104.IOElement_M_IT_NA(data.value)
        else:
            asdu_type = _iec104.AsduType.M_IT_TB
            element = _iec104.IOElement_M_IT_TB(data.value)

    else:
        raise ValueError('unsupported command value type')

    io = _iec104.IO(address=data.io_address,
                    time=data.time,
                    elements=[element])
    asdu = _iec104.ASDU(type=asdu_type,
                        cause=data.cause,
                        is_negative_confirm=False,
                        is_test=data.is_test,
                        originator_address=None,
                        address=data.asdu_address,
                        ios=[io])
    return asdu


def _asdu_to_commands(asdu):
    cmds = collections.deque()
    for io in asdu.ios:
        for element in io.elements:
            if asdu.cause == common.Cause.DEACTIVATION:
                action = common.Action.CANCEL
            elif element.select:
                action = common.Action.SELECT
            else:
                action = common.Action.EXECUTE

            cmds.append(common.Command(action=action,
                                       value=element.value,
                                       asdu_address=asdu.address,
                                       io_address=io.address,
                                       time=io.time,
                                       qualifier=element.qualifier))

    return list(cmds)


def _asdu_from_command(cmd):
    if isinstance(cmd.value, common.SingleValue):
        if cmd.time is None:
            asdu_type = _iec104.AsduType.C_SC_NA
            element_cls = _iec104.IOElement_C_SC_NA
        else:
            asdu_type = _iec104.AsduType.C_SC_TA
            element_cls = _iec104.IOElement_C_SC_TA

    elif isinstance(cmd.value, common.DoubleValue):
        if cmd.time is None:
            asdu_type = _iec104.AsduType.C_DC_NA
            element_cls = _iec104.IOElement_C_DC_NA
        else:
            asdu_type = _iec104.AsduType.C_DC_TA
            element_cls = _iec104.IOElement_C_DC_TA

    elif isinstance(cmd.value, common.RegulatingValue):
        if cmd.time is None:
            asdu_type = _iec104.AsduType.C_RC_NA
            element_cls = _iec104.IOElement_C_RC_NA
        else:
            asdu_type = _iec104.AsduType.C_RC_TA
            element_cls = _iec104.IOElement_C_RC_TA

    elif isinstance(cmd.value, common.NormalizedValue):
        if cmd.time is None:
            asdu_type = _iec104.AsduType.C_SE_NA
            element_cls = _iec104.IOElement_C_SE_NA
        else:
            asdu_type = _iec104.AsduType.C_SE_TA
            element_cls = _iec104.IOElement_C_SE_TA

    elif isinstance(cmd.value, common.ScaledValue):
        if cmd.time is None:
            asdu_type = _iec104.AsduType.C_SE_NB
            element_cls = _iec104.IOElement_C_SE_NB
        else:
            asdu_type = _iec104.AsduType.C_SE_TB
            element_cls = _iec104.IOElement_C_SE_TB

    elif isinstance(cmd.value, common.FloatingValue):
        if cmd.time is None:
            asdu_type = _iec104.AsduType.C_SE_NC
            element_cls = _iec104.IOElement_C_SE_NC
        else:
            asdu_type = _iec104.AsduType.C_SE_TC
            element_cls = _iec104.IOElement_C_SE_TC

    else:
        raise ValueError('unsupported command value type')

    if cmd.action == common.Action.EXECUTE:
        select = False
        cause = common.Cause.ACTIVATION

    elif cmd.action == common.Action.SELECT:
        select = True
        cause = common.Cause.ACTIVATION

    elif cmd.action == common.Action.CANCEL:
        select = False
        cause = common.Cause.DEACTIVATION

    else:
        raise ValueError('unsupported command action')

    element = element_cls(value=cmd.value,
                          select=select,
                          qualifier=cmd.qualifier)
    io = _iec104.IO(address=cmd.io_address,
                    time=cmd.time,
                    elements=[element])
    asdu = _iec104.ASDU(type=asdu_type,
                        cause=cause,
                        is_negative_confirm=False,
                        is_test=False,
                        originator_address=None,
                        address=cmd.asdu_address,
                        ios=[io])
    return asdu
