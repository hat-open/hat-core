"""Manufacturing Message Specification"""

from pathlib import Path
import asyncio
import logging
import typing

from hat import aio
from hat import asn1
from hat.drivers import acse
from hat.drivers.mms import common
from hat.drivers.mms import encoder


mlog = logging.getLogger(__name__)


Address = acse.Address
"""Address"""


IdentifiedEntity = acse.IdentifiedEntity
"""Identified entity"""


ConnectionInfo = acse.ConnectionInfo
"""Connection info"""


RequestCb = aio.AsyncCallable[['Connection', common.Request], common.Response]
"""Request callback"""


ConnectionCb = aio.AsyncCallable[['Connection'], None]
"""Connection callback"""


async def connect(request_cb: RequestCb,
                  addr: Address,
                  local_tsel: typing.Optional[int] = None,
                  remote_tsel: typing.Optional[int] = None,
                  local_ssel: typing.Optional[int] = None,
                  remote_ssel: typing.Optional[int] = None,
                  local_psel: typing.Optional[int] = None,
                  remote_psel: typing.Optional[int] = None,
                  local_ap_title: typing.Optional[asn1.ObjectIdentifier] = None,  # NOQA
                  remote_ap_title: typing.Optional[asn1.ObjectIdentifier] = None,  # NOQA
                  local_ae_qualifier: typing.Optional[int] = None,
                  remote_ae_qualifier: typing.Optional[int] = None,
                  user_data: typing.Optional[IdentifiedEntity] = None
                  ) -> 'Connection':
    """Connect to ACSE server"""
    initiate_req = 'initiate-RequestPDU', {
        'proposedMaxServOutstandingCalling': 5,
        'proposedMaxServOutstandingCalled': 5,
        'initRequestDetail': {
            'proposedVersionNumber': 1,
            'proposedParameterCBB': _parameter_cbb,
            'servicesSupportedCalling': _service_support}}
    req_user_data = _encode(initiate_req)
    acse_conn = await acse.connect(syntax_name_list=[_mms_syntax_name],
                                   app_context_name=_mms_app_context_name,
                                   addr=addr,
                                   local_tsel=local_tsel,
                                   remote_tsel=remote_tsel,
                                   local_ssel=local_ssel,
                                   remote_ssel=remote_ssel,
                                   local_psel=local_psel,
                                   remote_psel=remote_psel,
                                   local_ap_title=local_ap_title,
                                   remote_ap_title=remote_ap_title,
                                   local_ae_qualifier=local_ae_qualifier,
                                   remote_ae_qualifier=remote_ae_qualifier,
                                   user_data=(_mms_syntax_name, req_user_data))
    try:
        res_syntax_name, res_user_data = acse_conn.conn_res_user_data
        if not asn1.is_oid_eq(res_syntax_name, _mms_syntax_name):
            raise Exception("invalid syntax name")
        initiate_res = _decode(res_user_data)
        if initiate_res[0] != 'initiate-ResponsePDU':
            raise Exception("invalid initiate response")
        return _create_connection(request_cb, acse_conn)
    except Exception:
        await aio.uncancellable(acse_conn.async_close())
        raise


async def listen(connection_cb: ConnectionCb,
                 request_cb: RequestCb,
                 addr: Address = Address('0.0.0.0', 102)
                 ) -> 'Server':
    """Create MMS listening server

    Args:
        connection_cb: new connection callback
        request_cb: received request callback
        addr: local listening address

    """

    async def on_validate(syntax_names, user_data):
        syntax_name, req_user_data = user_data
        if not asn1.is_oid_eq(syntax_name, _mms_syntax_name):
            raise Exception('invalid mms syntax name')
        initiate_req = _decode(req_user_data)
        if initiate_req[0] != 'initiate-RequestPDU':
            raise Exception('invalid initiate request')
        initiate_res = 'initiate-ResponsePDU', {
            'negotiatedMaxServOutstandingCalling': 5,
            'negotiatedMaxServOutstandingCalled': 5,
            'negotiatedDataStructureNestingLevel': 4,  # TODO compatibility
            'initResponseDetail': {
                'negotiatedVersionNumber': 1,
                'negotiatedParameterCBB': _parameter_cbb,
                'servicesSupportedCalled': _service_support}}
        if 'localDetailCalling' in initiate_req[1]:
            initiate_res[1]['localDetailCalled'] = \
                initiate_req[1]['localDetailCalling']
        res_user_data = _encode(initiate_res)
        return _mms_syntax_name, res_user_data

    async def on_connection(acse_conn):
        try:
            try:
                conn = _create_connection(request_cb, acse_conn)
            except Exception:
                await aio.uncancellable(acse_conn.async_close())
                raise
            try:
                await aio.call(connection_cb, conn)
            except BaseException:
                await aio.uncancellable(conn.async_close())
                raise
        except Exception as e:
            mlog.error("error creating new incomming connection: %s",
                       e, exc_info=e)

    async def wait_acse_server_closed():
        try:
            await acse_server.wait_closed()
        finally:
            async_group.close()

    async_group = aio.Group()
    acse_server = await acse.listen(on_validate, on_connection, addr)
    async_group.spawn(aio.call_on_cancel, acse_server.async_close)
    async_group.spawn(wait_acse_server_closed)

    srv = Server()
    srv._async_group = async_group
    srv._acse_server = acse_server
    return srv


class Server(aio.Resource):
    """MMS listening server

    For creating new server see :func:`listen`

    Closing server doesn't close active incomming connections

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def addresses(self) -> typing.List[Address]:
        """Listening addresses"""
        return self._acse_server.addresses


def _create_connection(request_cb, acse_conn):
    conn = Connection()
    conn._request_cb = request_cb
    conn._acse_conn = acse_conn
    conn._last_invoke_id = 0
    conn._unconfirmed_queue = aio.Queue()
    conn._response_futures = {}
    conn._async_group = aio.Group()
    conn._async_group.spawn(conn._read_loop)
    return conn


class Connection(aio.Resource):
    """MMS connection

    For creating new connection see :func:`connect`

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def info(self) -> ConnectionInfo:
        """Connection info"""
        return self._acse_conn.info

    async def receive_unconfirmed(self) -> common.Unconfirmed:
        """Receive unconfirmed message

        Raises:
            ConnectionError: in case connection is not open

        """
        try:
            return await self._unconfirmed_queue.get()
        except aio.QueueClosedError:
            raise ConnectionError('connection is not open')

    def send_unconfirmed(self, unconfirmed: common.Unconfirmed):
        """Send unconfirmed message"""
        pdu = 'unconfirmed-PDU', {
            'service': encoder.encode_unconfirmed(unconfirmed)}
        data = _mms_syntax_name, _encode(pdu)
        self._acse_conn.write(data)

    async def send_confirmed(self,
                             req: common.Request
                             ) -> common.Response:
        """Send confirmed request and wait for response

        Raises:
            ConnectionError: in case connection is not open

        """
        if self._async_group.is_closing:
            raise ConnectionError('connection is not open')
        invoke_id = self._last_invoke_id + 1
        pdu = 'confirmed-RequestPDU', {
            'invokeID': invoke_id,
            'service': encoder.encode_request(req)}
        data = _mms_syntax_name, _encode(pdu)
        self._acse_conn.write(data)
        self._last_invoke_id = invoke_id
        self._response_futures[invoke_id] = asyncio.Future()
        try:
            return await self._response_futures[invoke_id]
        finally:
            del self._response_futures[invoke_id]

    async def _read_loop(self):
        running = True
        try:
            while running:
                syntax_name, entity = await self._acse_conn.read()
                if not asn1.is_oid_eq(syntax_name, _mms_syntax_name):
                    continue
                pdu = _decode(entity)
                running = await self._process_pdu(pdu)
        except asyncio.CancelledError:
            pdu = 'conclude-RequestPDU', None
            data = _mms_syntax_name, _encode(pdu)
            self._acse_conn.write(data)
            # TODO: wait for response
            raise
        finally:
            self._async_group.close()
            self._unconfirmed_queue.close()
            for response_future in self._response_futures.values():
                if not response_future.done():
                    response_future.set_exception(
                        ConnectionError('connection is not open'))
            await aio.uncancellable(self._acse_conn.async_close())

    async def _process_pdu(self, pdu):
        name, data = pdu

        if name == 'unconfirmed-PDU':
            unconfirmed = encoder.decode_unconfirmed(data['service'])
            await self._unconfirmed_queue.put(unconfirmed)
            return True

        elif name == 'confirmed-RequestPDU':
            invoke_id = data['invokeID']
            req = encoder.decode_request(data['service'])
            res = await aio.call(self._request_cb, self, req)
            if isinstance(res, common.ErrorResponse):
                res_pdu = 'confirmed-ErrorPDU', {
                    'invokeID': invoke_id,
                    'serviceError': {
                        'errorClass': (res.error_class.value, res.value)}}
            else:
                res_pdu = 'confirmed-ResponsePDU', {
                    'invokeID': invoke_id,
                    'service': encoder.encode_response(res)}
            res_data = _mms_syntax_name, _encode(res_pdu)
            self._acse_conn.write(res_data)
            return True

        elif name == 'confirmed-ResponsePDU':
            invoke_id = data['invokeID']
            res = encoder.decode_response(data['service'])
            future = self._response_futures.get(invoke_id)
            if future and not future.done():
                future.set_result(res)
            else:
                mlog.warn(f"dropping confirmed response "
                          f"(invoke_id: {invoke_id})")
            return True

        elif name == 'confirmed-ErrorPDU':
            invoke_id = data['invokeID']
            error_class_name, value = data['serviceError']['errorClass']
            error_class = common.ErrorClass(error_class_name)
            res = common.ErrorResponse(error_class, value)
            future = self._response_futures.get(invoke_id)
            if future and not future.done():
                future.set_result(res)
            else:
                mlog.warn(f"dropping confirmed error "
                          f"(invoke_id: {invoke_id})")
            return True

        elif name == 'conclude-RequestPDU':
            res_pdu = 'conclude-ResponsePDU', None
            res_data = _mms_syntax_name, _encode(res_pdu)
            self._acse_conn.write(res_data)
            return False

        return False


_parameter_cbb = [False] * 10  # 18
_parameter_cbb[0] = True  # str1
_parameter_cbb[1] = True  # str2
_parameter_cbb[2] = True  # vnam
_parameter_cbb[3] = True  # valt
_parameter_cbb[4] = True  # vadr
_parameter_cbb[6] = True  # tpy
_parameter_cbb[7] = True  # vlis

_service_support = [False] * 85  # 93
_service_support[0] = True  # status
_service_support[1] = True  # getNameList
_service_support[2] = True  # identify
_service_support[4] = True  # read
_service_support[5] = True  # write
_service_support[6] = True  # getVariableAccessAttributes
_service_support[11] = True  # defineNamedVariableList
_service_support[12] = True  # getNamedVariableListAttributes
_service_support[13] = True  # deleteNamedVariableList
_service_support[79] = True  # informationReport

# not supported - compatibility flags
_service_support[18] = True  # output
_service_support[83] = True  # conclude


_mms_syntax_name = [('iso', 1),
                    ('standard', 0),
                    ('iso9506', 9506),
                    ('part', 2),
                    ('mms-abstract-syntax-version1', 1)]
_mms_app_context_name = [('iso', 1),
                         ('standard', 0),
                         ('iso9506', 9506),
                         ('part', 2),
                         ('mms-annex-version1', 3)]
_encoder = asn1.Encoder(asn1.Encoding.BER,
                        asn1.Repository.from_json(Path(__file__).parent /
                                                  'asn1_repo.json'))


def _encode(value):
    return _encoder.encode_value('ISO-9506-MMS-1', 'MMSpdu', value)


def _decode(entity):
    return _encoder.decode_value('ISO-9506-MMS-1', 'MMSpdu', entity)
