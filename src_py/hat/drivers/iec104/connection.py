"""IEC 60870-5-104 connection

Attributes:
    mlog (logging.Logger): module logger
    InterrogateCallback (Type[Callable]): interrogate callback
        This method is called when local peer receives interrogate request.
        Called with asdu address, returns list of data.
        Can be regular function or coroutine.
    CounterInterrogateCallback (Type[Callable]): counter interrogate callback
        This method is called when local peer receives counter interrogate
        request. Called with asdu address and freeze code, returns list of
        data. Can be regular function or coroutine.
    CommandCallback (Type[Callable]): command callback
        This method is called when local peer receives command request.
        Called with list of commands, returns if commands are successful.
        Can be regular function or coroutine.
"""

import typing
import asyncio
import contextlib
import logging
import enum

from hat import aio
from hat import util
from hat.drivers.iec104 import _common
from hat.drivers.iec104 import common


mlog = logging.getLogger(__name__)

InterrogateCallback = aio.AsyncCallable[
   ['Connection', int],
   typing.Optional[typing.List[common.Data]]]

CounterInterrogateCallback = aio.AsyncCallable[
   ['Connection', int, common.FreezeCode],
   typing.Optional[typing.List[common.Data]]]

CommandCallback = aio.AsyncCallable[
    ['Connection', typing.List[common.Command]],
    typing.Union[bool,
                 typing.Awaitable[bool]]]


class Address(typing.NamedTuple):
    host: str
    port: int = 2404


class ConnectionInfo(typing.NamedTuple):
    local_addr: Address
    remote_addr: Address


class _CmdId(typing.NamedTuple):
    type: '_CommandType'
    asdu: int
    io: int


class _DataType(enum.Enum):
    SINGLE = 1
    DOUBLE = 2
    STEP_POSITION = 3
    BITSTRING = 4
    NORMALIZED = 5
    SCALED = 6
    FLOATING = 7
    BINARY_COUNTER = 8


class _CommandType(enum.Enum):
    SINGLE = 1
    DOUBLE = 2
    REGULATING = 3
    NORMALIZED = 4
    SCALED = 5
    FLOATING = 6


async def connect(host, port=2404, interrogate_cb=None,
                  counter_interrogate_cb=None, command_cb=None,
                  response_timeout=15, supervisory_timeout=10,
                  test_timeout=20, send_window_size=12, receive_window_size=8):
    """Connect to remote device

    Args:
        host (str): remote server's hostname
        port (int): remote server's port
        interrogate_cb (Optional[InterrogateCallback]): interrogate callback
        counter_interrogate_cb (Optional[CounterInterrogateCallback]):
            counter interrogate callback
        command_cb (Optional[CommandCallback]): command callback
        response_timeout (float): response timeout (t1) in seconds
        supervisory_timeout (float): supervisory timeout (t2) in seconds
        test_timeout (float): test timeout (t3) in seconds
        send_window_size (int): send window size (k)
        receive_window_size (int): receive window size (w)

    Returns:
        Connection

    """

    async def read_startdt_con():
        while True:
            apdu = await _common.read_apdu(reader)
            if isinstance(apdu, _common.APDUU):
                if apdu.function == _common.ApduFunctionType.STARTDT_CON:
                    return
                if apdu.function == _common.ApduFunctionType.TESTFR_ACT:
                    _common.write_apdu(_common.APDUU(
                        function=_common.ApduFunctionType.TESTFR_CON))
                    continue
            mlog.warn('while waiting for STARTDT con, received %s', apdu)

    reader, writer = await asyncio.open_connection(host, port)
    _common.write_apdu(writer, _common.APDUU(
        function=_common.ApduFunctionType.STARTDT_ACT))
    try:
        await asyncio.wait_for(read_startdt_con(), response_timeout)
    except Exception:
        with contextlib.suppress(Exception):
            writer.close()
        raise

    transport = _common.Transport(
        reader, writer, True, response_timeout, supervisory_timeout,
        test_timeout, send_window_size, receive_window_size)
    return _create_connection(transport, interrogate_cb,
                              counter_interrogate_cb, command_cb)


async def listen(connection_cb, host='0.0.0.0', port=2404, interrogate_cb=None,
                 counter_interrogate_cb=None, command_cb=None,
                 response_timeout=15, supervisory_timeout=10, test_timeout=20,
                 send_window_size=12, receive_window_size=8):
    """Create new IEC104 slave and listen for incoming connections

    Args:
        connection_cb (Callable[[Connection],None]): new connection callback
        host (str): listening socket hostname
        port (int): listening socket port
        interrogate_cb (Optional[InterrogateCallback]): interrogate callback
        counter_interrogate_cb (Optional[CounterInterrogateCallback]):
            counter interrogate callback
        command_cb (Optional[CommandCallback]): command callback
        response_timeout (float): response timeout (t1) in seconds
        supervisory_timeout (float): supervisory timeout (t2) in seconds
        test_timeout (float): test timeout (t3) in seconds
        send_window_size (int): send window size (k)
        receive_window_size (int): receive window size (w)

    Returns:
        Server

    """

    def on_client_connected(reader, writer):
        transport = _common.Transport(
            reader, writer, False, response_timeout, supervisory_timeout,
            test_timeout, send_window_size, receive_window_size)
        conn = _create_connection(transport, interrogate_cb,
                                  counter_interrogate_cb, command_cb)
        server._connections.append(conn)
        server._async_group.spawn(server._conn_life, conn)
        connection_cb(conn)

    group = aio.Group(
        lambda e: mlog.error('exception in server: %s', e, exc_info=e))
    tcp_server = await asyncio.start_server(on_client_connected, host, port)
    socknames = [socket.getsockname() for socket in tcp_server.sockets]
    addresses = [Address(*sockname[:2]) for sockname in socknames]

    server = Server()
    server._async_group = group
    server._srv = tcp_server
    server._addresses = addresses
    server._connections = []
    server._async_group.spawn(aio.call_on_cancel, server._on_close)
    return server


class Server(aio.Resource):
    """Server

    For creating new Server instances see :func:`listen`.

    Closing server closes all incoming connections.

    """

    @property
    def async_group(self):
        return self._async_group

    @property
    def addresses(self):
        """List[Address]: listening addresses"""
        return self._addresses

    async def _on_close(self):
        await self._ser.async_close()
        for conn in list(self._connections):
            await conn.async_close()

    async def _conn_life(self, conn):
        try:
            await conn.wait_closed()
        finally:
            if not conn.is_closed:
                await conn.async_close()
            self._connections.remove(conn)


def _create_connection(transport, interrogate_cb, counter_interrogate_cb,
                       command_cb):
    sockname = transport._writer.get_extra_info('sockname')
    peername = transport._writer.get_extra_info('peername')
    info = ConnectionInfo(local_addr=Address(sockname[0], sockname[1]),
                          remote_addr=Address(peername[0], peername[1]))

    conn = Connection()
    conn._transport = transport
    conn._info = info
    conn._interrogate_cb = interrogate_cb
    conn._counter_interrogate_cb = counter_interrogate_cb
    conn._command_cb = command_cb
    conn._interrogate_queue = aio.Queue()
    conn._interrogate_lock = asyncio.Lock()
    conn._counter_interrogate_queue = aio.Queue()
    conn._counter_interrogate_lock = asyncio.Lock()
    conn._data_queue = aio.Queue()
    conn._command_futures = {}
    conn._async_group = aio.Group(
        lambda e: mlog.error('exception in connection: %s', e, exc_info=e))
    conn._async_group.spawn(conn._read_loop)
    conn._async_group.spawn(aio.call_on_cancel, conn._transport.async_close)
    return conn


class Connection(aio.Resource):
    """Single IEC104 connection

    For creating new Connection instances see :func:`connect`.

    """

    @property
    def async_group(self):
        return self._async_group

    @property
    def info(self):
        """ConnectionInfo: connection info"""
        return self._info

    def notify_data_change(self, data):
        """Notify local data change

        Args:
            data (List[common.Data]): data

        """
        for i in data:
            # TODO: implement bulk send data
            self._send_data(i, None)

    async def interrogate(self, asdu_address=0xFFFF):
        """Interrogate remote device

        Asdu broadcast address 0xFFFF is not supported by all devices

        Args:
            asdu_address (int): asdu address

        Returns:
            List[common.Data]: data

        """
        async with self._interrogate_lock:
            # is this necessary (no one closes it)
            if self._interrogate_queue.is_closed:
                raise aio.QueueClosedError()
            asdu = _common.ASDU(
                type=_common.AsduType.C_IC_NA,
                cause=common.Cause.ACTIVATION,
                is_negative_confirm=False,
                is_test=False,
                originator_address=None,
                address=asdu_address,
                ios=[_common.IO(
                    address=0,
                    time=None,
                    elements=[_common.create_io_element(
                                _common.AsduType.C_IC_NA, 20)])])
            self._transport.write(asdu)
            if not self._interrogate_queue.empty():
                self._interrogate_queue.get_nowait_until_empty()
            data = []
            async for asdu in self._interrogate_queue:
                if (asdu.type == _common.AsduType.C_IC_NA and
                        asdu.cause == common.Cause.ACTIVATION_CONFIRMATION):
                    continue
                if (asdu.type == _common.AsduType.C_IC_NA and
                        asdu.cause == common.Cause.ACTIVATION_TERMINATION):
                    return data
                data.extend(_asdu_to_data(asdu))

    async def counter_interrogate(self, asdu_address=0xFFFF,
                                  freeze=common.FreezeCode.READ):
        """Interrogate remote device counters

        Asdu broadcast address 0xFFFF is not supported by all devices

        Args:
            asdu_address (int): asdu address
            freeze (common.FreezeCode): freeze code

        Returns:
            List[common.Data]: data

        """
        async with self._counter_interrogate_lock:
            # is this necessary (no one closes it)
            if self._counter_interrogate_queue.is_closed:
                raise util.QueueClosedError()
            asdu = _common.ASDU(
                type=_common.AsduType.C_CI_NA,
                cause=common.Cause.ACTIVATION,
                is_negative_confirm=False,
                is_test=False,
                originator_address=None,
                address=asdu_address,
                ios=[_common.IO(
                    address=0,
                    time=None,
                    elements=[_common.create_io_element(
                                _common.AsduType.C_CI_NA, 5, freeze.value)])])
            self._transport.write(asdu)
            if not self._counter_interrogate_queue.empty():
                self._counter_interrogate_queue.get_nowait_until_empty()
            data = []
            async for asdu in self._counter_interrogate_queue:
                if (asdu.type == _common.AsduType.C_CI_NA and
                        asdu.cause == common.Cause.ACTIVATION_CONFIRMATION):
                    continue
                if (asdu.type == _common.AsduType.C_CI_NA and
                        asdu.cause == common.Cause.ACTIVATION_TERMINATION):
                    return data
                data.extend(_asdu_to_data(asdu))

    async def receive(self):
        """Receive remote data change

        Returns:
            List[common.Data]: data

        """
        async for asdu in self._data_queue:
            data = _asdu_to_data(asdu)
            if data:
                return data

    async def send_command(self, cmd):
        """Send command

        Args:
            cmd (common.Command): command

        Returns:
            bool: command's success

        """
        cmd_type = _command_type_from_value(cmd.value)
        if cmd.time:
            asdu_type = _command_type_to_asdu_type_with_time[cmd_type]
        else:
            asdu_type = _command_type_to_asdu_type_without_time[cmd_type]
        req = _common.ASDU(
            type=asdu_type,
            cause=(common.Cause.DEACTIVATION
                   if cmd.action == common.Action.CANCEL else
                   common.Cause.ACTIVATION),
            is_negative_confirm=False,
            is_test=False,
            originator_address=None,
            address=cmd.asdu_address,
            ios=[_common.IO(
                address=cmd.io_address,
                time=cmd.time,
                elements=[_common.create_io_element(
                            asdu_type,
                            value=cmd.value.value,
                            select=cmd.action == common.Action.SELECT,
                            qualifier=cmd.qualifier)])])
        cmd_id = _CmdId(type=cmd_type,
                        asdu=cmd.asdu_address,
                        io=cmd.io_address)
        if cmd_id in self._command_futures:
            return False
        self._transport.write(req)
        cmd_future = asyncio.Future()
        self._command_futures[cmd_id] = cmd_future
        try:
            resp = await cmd_future
            return not resp.is_negative_confirm
        finally:
            del self._command_futures[cmd_id]
        return False

    async def _read_loop(self):
        try:
            while True:
                asdu = await self._transport.read()
                if not asdu:
                    break
                if asdu.cause in _interrogate_causes:
                    self._interrogate_queue.put_nowait(asdu)
                elif asdu.cause in _counter_interrogate_causes:
                    self._counter_interrogate_queue.put_nowait(asdu)
                elif asdu.type == _common.AsduType.C_IC_NA:
                    if asdu.cause in _activate_causes:
                        self._interrogate_queue.put_nowait(asdu)
                    else:
                        await self._process_interrogate(asdu)
                elif asdu.type == _common.AsduType.C_CI_NA:
                    if asdu.cause in _activate_causes:
                        self._counter_interrogate_queue.put_nowait(asdu)
                    else:
                        await self._process_counter_interrogate(asdu)
                elif asdu.type in _command_asdu_types:
                    if asdu.cause in _activate_causes:
                        # TODO: handle properly ACTIVATION_TERMINATION in the
                        # command flow...
                        if asdu.cause == common.Cause.ACTIVATION_TERMINATION:
                            continue
                        for i in asdu.ios:
                            cmd_type = _asdu_type_to_command_type[asdu.type]
                            cmd_id = _CmdId(type=cmd_type,
                                            asdu=asdu.address,
                                            io=i.address)
                            cmd_future = self._command_futures.get(cmd_id)
                            if not cmd_future or cmd_future.done():
                                mlog.warning('received response for '
                                             ' non-waited command %s\n%s',
                                             cmd_id,
                                             self._command_futures)
                                continue
                            cmd_future.set_result(asdu)
                    else:
                        await self._process_command(asdu)
                elif asdu.type in _asdu_type_to_data_type.keys():
                    self._data_queue.put_nowait(asdu)
                else:
                    mlog.warn('discarding asdu %s', asdu)
        finally:
            mlog.debug("closing connection %s", self._info)
            self._async_group.close()

    async def _process_interrogate(self, asdu):
        data = await aio.call(self._interrogate_cb, self, asdu.address)
        if data is None:
            return
        self._transport.write(_common.ASDU(
            type=_common.AsduType.C_IC_NA,
            cause=common.Cause.ACTIVATION_CONFIRMATION,
            is_negative_confirm=False,
            is_test=False,
            originator_address=None,
            address=asdu.address,
            ios=[_common.IO(
                address=0,
                time=None,
                elements=[_common.create_io_element(
                            _common.AsduType.C_IC_NA, 20)])]))
        for i in data:
            self._send_data(i, common.Cause.INTERROGATED_STATION)
        self._transport.write(_common.ASDU(
            type=_common.AsduType.C_IC_NA,
            cause=common.Cause.ACTIVATION_TERMINATION,
            is_negative_confirm=False,
            is_test=False,
            originator_address=None,
            address=asdu.address,
            ios=[_common.IO(
                address=0,
                time=None,
                elements=[_common.create_io_element(
                            _common.AsduType.C_IC_NA, 20)])]))

    async def _process_counter_interrogate(self, asdu):
        freeze = asdu.ios[0].elements[0].freeze
        data = await aio.call(self._counter_interrogate_cb, self,
                              asdu.address, common.FreezeCode(freeze))
        self._transport.write(_common.ASDU(
            type=_common.AsduType.C_CI_NA,
            cause=common.Cause.ACTIVATION_CONFIRMATION,
            is_negative_confirm=False,
            is_test=False,
            originator_address=None,
            address=asdu.address,
            ios=[_common.IO(
                address=0,
                time=None,
                elements=[_common.create_io_element(
                            _common.AsduType.C_CI_NA, 5, freeze)])]))
        for i in data:
            self._send_data(i, common.Cause.INTERROGATED_COUNTER)
        self._transport.write(_common.ASDU(
            type=_common.AsduType.C_CI_NA,
            cause=common.Cause.ACTIVATION_TERMINATION,
            is_negative_confirm=False,
            is_test=False,
            originator_address=None,
            address=asdu.address,
            ios=[_common.IO(
                address=0,
                time=None,
                elements=[_common.create_io_element(
                            _common.AsduType.C_CI_NA, 5, freeze)])]))

    async def _process_command(self, asdu):
        cmd_type = _asdu_type_to_command_type[asdu.type]
        cmds = []
        for i, io in enumerate(asdu.ios):
            for ioe in io.elements:
                if asdu.cause == common.Cause.DEACTIVATION:
                    cmd_action = common.Action.CANCEL
                else:
                    cmd_action = (common.Action.SELECT if ioe.select else
                                  common.Action.EXECUTE)
                cmds.append(common.Command(
                    action=cmd_action,
                    value=_cmd_value_from_ioe(cmd_type, ioe),
                    asdu_address=asdu.address,
                    io_address=io.address + i,
                    time=io.time,
                    qualifier=ioe.qualifier))
        result = await aio.call(self._command_cb, self, cmds)
        self._transport.write(_common.ASDU(
            type=asdu.type,
            cause=common.Cause[asdu.cause.name + '_CONFIRMATION'],
            is_negative_confirm=not result,
            is_test=False,
            originator_address=None,
            address=asdu.address,
            ios=asdu.ios))

    def _send_data(self, data, cause):
        data_type = _data_type_from_value(data.value)
        if data_type == _DataType.NORMALIZED and data.quality is None:
            asdu_type = _common.AsduType.M_ME_ND
        elif data.time:
            asdu_type = _data_type_to_asdu_type_with_time[data_type]
        else:
            asdu_type = _data_type_to_asdu_type_without_time[data_type]
        ioe_args = {}
        if asdu_type in (_common.AsduType.M_ST_NA, _common.AsduType.M_ST_TB):
            ioe_args['value'] = data.value.value
            ioe_args['quality'] = data.quality
            ioe_args['t'] = data.value.transient
        elif asdu_type in (_common.AsduType.M_IT_NA, _common.AsduType.M_IT_TB):
            ioe_args['value'] = data.value.value
            ioe_args['invalid'] = data.value.invalid
            ioe_args['adjusted'] = data.value.adjusted
            ioe_args['overflow'] = data.value.overflow
            ioe_args['sequence'] = data.value.sequence
        elif asdu_type == _common.AsduType.M_ME_ND:
            ioe_args['value'] = data.value.value
        else:
            ioe_args['value'] = data.value.value
            ioe_args['quality'] = data.quality
        asdu = _common.ASDU(
            type=asdu_type,
            cause=cause if cause else data.cause,
            is_negative_confirm=False,
            is_test=data.is_test,
            originator_address=None,
            address=data.asdu_address,
            ios=[_common.IO(
                address=data.io_address,
                elements=[_common.create_io_element(asdu_type, **ioe_args)],
                time=data.time)])
        self._transport.write(asdu)


_activate_causes = {common.Cause.ACTIVATION_CONFIRMATION,
                    common.Cause.ACTIVATION_TERMINATION,
                    common.Cause.DEACTIVATION_CONFIRMATION}

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

_command_asdu_types = {_common.AsduType.C_SC_NA,
                       _common.AsduType.C_DC_NA,
                       _common.AsduType.C_RC_NA,
                       _common.AsduType.C_SE_NA,
                       _common.AsduType.C_SE_NB,
                       _common.AsduType.C_SE_NC,
                       _common.AsduType.C_SC_TA,
                       _common.AsduType.C_DC_TA,
                       _common.AsduType.C_RC_TA,
                       _common.AsduType.C_SE_TA,
                       _common.AsduType.C_SE_TB,
                       _common.AsduType.C_SE_TC}

_asdu_type_to_command_type = {
    _common.AsduType.C_SC_NA: _CommandType.SINGLE,
    _common.AsduType.C_DC_NA: _CommandType.DOUBLE,
    _common.AsduType.C_RC_NA: _CommandType.REGULATING,
    _common.AsduType.C_SE_NA: _CommandType.NORMALIZED,
    _common.AsduType.C_SE_NB: _CommandType.SCALED,
    _common.AsduType.C_SE_NC: _CommandType.FLOATING,
    _common.AsduType.C_SC_TA: _CommandType.SINGLE,
    _common.AsduType.C_DC_TA: _CommandType.DOUBLE,
    _common.AsduType.C_RC_TA: _CommandType.REGULATING,
    _common.AsduType.C_SE_TA: _CommandType.NORMALIZED,
    _common.AsduType.C_SE_TB: _CommandType.SCALED,
    _common.AsduType.C_SE_TC: _CommandType.FLOATING}

_command_type_to_asdu_type_without_time = {
    _CommandType.SINGLE: _common.AsduType.C_SC_NA,
    _CommandType.DOUBLE: _common.AsduType.C_DC_NA,
    _CommandType.REGULATING: _common.AsduType.C_RC_NA,
    _CommandType.NORMALIZED: _common.AsduType.C_SE_NA,
    _CommandType.SCALED: _common.AsduType.C_SE_NB,
    _CommandType.FLOATING: _common.AsduType.C_SE_NC}

_command_type_to_asdu_type_with_time = {
    _CommandType.SINGLE: _common.AsduType.C_SC_TA,
    _CommandType.DOUBLE: _common.AsduType.C_DC_TA,
    _CommandType.REGULATING: _common.AsduType.C_RC_TA,
    _CommandType.NORMALIZED: _common.AsduType.C_SE_TA,
    _CommandType.SCALED: _common.AsduType.C_SE_TB,
    _CommandType.FLOATING: _common.AsduType.C_SE_TC}

_asdu_type_to_data_type = {
    _common.AsduType.M_SP_NA: _DataType.SINGLE,
    _common.AsduType.M_DP_NA: _DataType.DOUBLE,
    _common.AsduType.M_ST_NA: _DataType.STEP_POSITION,
    _common.AsduType.M_BO_NA: _DataType.BITSTRING,
    _common.AsduType.M_ME_NA: _DataType.NORMALIZED,
    _common.AsduType.M_ME_NB: _DataType.SCALED,
    _common.AsduType.M_ME_NC: _DataType.FLOATING,
    _common.AsduType.M_IT_NA: _DataType.BINARY_COUNTER,
    _common.AsduType.M_ME_ND: _DataType.NORMALIZED,
    _common.AsduType.M_SP_TB: _DataType.SINGLE,
    _common.AsduType.M_DP_TB: _DataType.DOUBLE,
    _common.AsduType.M_ST_TB: _DataType.STEP_POSITION,
    _common.AsduType.M_BO_TB: _DataType.BITSTRING,
    _common.AsduType.M_ME_TD: _DataType.NORMALIZED,
    _common.AsduType.M_ME_TE: _DataType.SCALED,
    _common.AsduType.M_ME_TF: _DataType.FLOATING,
    _common.AsduType.M_IT_TB: _DataType.BINARY_COUNTER}

_data_type_to_asdu_type_without_time = {
    _DataType.SINGLE: _common.AsduType.M_SP_NA,
    _DataType.DOUBLE: _common.AsduType.M_DP_NA,
    _DataType.STEP_POSITION: _common.AsduType.M_ST_NA,
    _DataType.BITSTRING: _common.AsduType.M_BO_NA,
    _DataType.NORMALIZED: _common.AsduType.M_ME_NA,
    _DataType.SCALED: _common.AsduType.M_ME_NB,
    _DataType.FLOATING: _common.AsduType.M_ME_NC,
    _DataType.BINARY_COUNTER: _common.AsduType.M_IT_NA}

_data_type_to_asdu_type_with_time = {
    _DataType.SINGLE: _common.AsduType.M_SP_TB,
    _DataType.DOUBLE: _common.AsduType.M_DP_TB,
    _DataType.STEP_POSITION: _common.AsduType.M_ST_TB,
    _DataType.BITSTRING: _common.AsduType.M_BO_TB,
    _DataType.NORMALIZED: _common.AsduType.M_ME_TD,
    _DataType.SCALED: _common.AsduType.M_ME_TE,
    _DataType.FLOATING: _common.AsduType.M_ME_TF,
    _DataType.BINARY_COUNTER: _common.AsduType.M_IT_TB}


def _asdu_to_data(asdu):
    data_type = _asdu_type_to_data_type[asdu.type]
    data = []
    for io in asdu.ios:
        for i, ioe in enumerate(io.elements):
            try:
                data.append(_io_element_to_data(
                    ioe, data_type, io.time, asdu.address, io.address + i,
                    asdu.cause, asdu.is_test))
            except Exception as e:
                mlog.warn("Could not convert IO element to data: %s", e,
                          exc_info=True)
    return data


def _io_element_to_data(ioe, data_type, time, asdu_address, io_address, cause,
                        is_test):
    return common.Data(
        value=_data_value_from_ioe(data_type, ioe),
        quality=ioe.quality if hasattr(ioe, 'quality') else None,
        time=time,
        asdu_address=asdu_address,
        io_address=io_address,
        cause=cause,
        is_test=is_test)


def _data_value_from_ioe(data_type, ioe):
    if data_type == _DataType.SINGLE:
        return common.SingleValue(ioe.value)
    elif data_type == _DataType.DOUBLE:
        return common.DoubleValue(ioe.value)
    elif data_type == _DataType.STEP_POSITION:
        return common.StepPositionValue(
            value=ioe.value,
            transient=ioe.t)
    elif data_type == _DataType.BITSTRING:
        return common.BitstringValue(value=ioe.value)
    elif data_type == _DataType.NORMALIZED:
        return common.NormalizedValue(value=ioe.value)
    elif data_type == _DataType.SCALED:
        return common.ScaledValue(value=ioe.value)
    elif data_type == _DataType.FLOATING:
        return common.FloatingValue(value=ioe.value)
    elif data_type == _DataType.BINARY_COUNTER:
        return common.BinaryCounterValue(
            value=ioe.value,
            sequence=ioe.sequence,
            overflow=ioe.overflow,
            adjusted=ioe.adjusted,
            invalid=ioe.invalid)


def _cmd_value_from_ioe(cmd_type, ioe):
    if cmd_type == _CommandType.SINGLE:
        return common.SingleValue(ioe.value)
    elif cmd_type == _CommandType.DOUBLE:
        return common.DoubleValue(ioe.value)
    elif cmd_type == _CommandType.REGULATING:
        return common.RegulatingValue(ioe.value)
    elif cmd_type == _CommandType.NORMALIZED:
        return common.NormalizedValue(value=ioe.value)
    elif cmd_type == _CommandType.SCALED:
        return common.ScaledValue(value=ioe.value)
    elif cmd_type == _CommandType.FLOATING:
        return common.FloatingValue(value=ioe.value)


def _data_type_from_value(data_value):
    return {
        common.SingleValue: _DataType.SINGLE,
        common.DoubleValue: _DataType.DOUBLE,
        common.StepPositionValue: _DataType.STEP_POSITION,
        common.BitstringValue: _DataType.BITSTRING,
        common.NormalizedValue: _DataType.NORMALIZED,
        common.ScaledValue: _DataType.SCALED,
        common.FloatingValue: _DataType.FLOATING,
        common.BinaryCounterValue: _DataType.BINARY_COUNTER}[type(data_value)]


def _command_type_from_value(command_value):
    return {common.SingleValue: _CommandType.SINGLE,
            common.DoubleValue: _CommandType.DOUBLE,
            common.RegulatingValue: _CommandType.REGULATING,
            common.NormalizedValue: _CommandType.NORMALIZED,
            common.ScaledValue: _CommandType.SCALED,
            common.FloatingValue: _CommandType.FLOATING}[type(command_value)]
