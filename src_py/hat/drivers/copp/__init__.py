"""Connection oriented presentation protocol

Attributes:
    mlog (logging.Logger): module logger

"""

from pathlib import Path
import logging
import typing

from hat import aio
from hat import asn1
from hat import util
from hat.drivers import cosp


mlog = logging.getLogger(__name__)


IdentifiedEntity = typing.Tuple[asn1.ObjectIdentifier, asn1.Entity]
"""Identified entity"""


Address = cosp.Address
"""Address"""


class ConnectionInfo(typing.NamedTuple):
    local_addr: Address
    local_tsel: typing.Optional[int]
    local_ssel: typing.Optional[int]
    local_psel: typing.Optional[int]
    remote_addr: Address
    remote_tsel: typing.Optional[int]
    remote_ssel: typing.Optional[int]
    remote_psel: typing.Optional[int]


ValidateResult = typing.Optional[IdentifiedEntity]
"""Validate result"""


ValidateCb = aio.AsyncCallable[['SyntaxNames', IdentifiedEntity],
                               ValidateResult]
"""Validate callback"""


ConnectionCb = aio.AsyncCallable[['Connection'], None]
"""Connection callback"""


_encoder = asn1.Encoder(asn1.Encoding.BER,
                        asn1.Repository.from_json(Path(__file__).parent /
                                                  'asn1_repo.json'))


class SyntaxNames:
    """Syntax name registry

    Args:
        syntax_names: list of ASN.1 ObjectIdentifiers representing syntax names

    """

    def __init__(self, syntax_names: typing.List[asn1.ObjectIdentifier]):
        self._syntax_names = {(i * 2 + 1): name
                              for i, name in enumerate(syntax_names)}

    def get_name(self, syntax_id: int) -> asn1.ObjectIdentifier:
        """Get syntax name associated with id"""
        return self._syntax_names[syntax_id]

    def get_id(self, syntax_name: asn1.ObjectIdentifier) -> int:
        """Get syntax id associated with name"""
        syntax_id, _ = util.first(self._syntax_names.items(),
                                  lambda i: asn1.is_oid_eq(i[1], syntax_name))
        return syntax_id


async def connect(syntax_names: SyntaxNames,
                  addr: Address,
                  local_tsel: typing.Optional[int] = None,
                  remote_tsel: typing.Optional[int] = None,
                  local_ssel: typing.Optional[int] = None,
                  remote_ssel: typing.Optional[int] = None,
                  local_psel: typing.Optional[int] = None,
                  remote_psel: typing.Optional[int] = None,
                  user_data: typing.Optional[IdentifiedEntity] = None
                  ) -> 'Connection':
    """Connect to COPP server"""
    cp_ppdu = _cp_ppdu(syntax_names, local_psel, remote_psel, user_data)
    cp_ppdu_data = _encode('CP-type', cp_ppdu)
    cosp_conn = await cosp.connect(addr=addr,
                                   local_tsel=local_tsel,
                                   remote_tsel=remote_tsel,
                                   local_ssel=local_ssel,
                                   remote_ssel=remote_ssel,
                                   user_data=cp_ppdu_data)
    try:
        cpa_ppdu = _decode('CPA-PPDU', cosp_conn.conn_res_user_data)
        _validate_connect_response(cp_ppdu, cpa_ppdu)
        calling_psel, called_psel = _get_psels(cp_ppdu)
        return _create_connection(syntax_names, cosp_conn, cp_ppdu, cpa_ppdu,
                                  calling_psel, called_psel)
    except Exception:
        await aio.uncancellable(_close_connection(cosp_conn, _arp_ppdu()))
        raise


async def listen(validate_cb: ValidateCb,
                 connection_cb: ConnectionCb,
                 addr: Address = Address('0.0.0.0', 102)
                 ) -> 'Server':
    """Create COPP listening server

    Args:
        validate_cb: callback function or coroutine called on new
            incomming connection request prior to creating connection object
        connection_cb: new connection callback
        addr: local listening address

    """

    async def on_validate(user_data):
        cp_ppdu = _decode('CP-type', user_data)
        cp_params = cp_ppdu['normal-mode-parameters']
        called_psel_data = cp_params.get('called-presentation-selector')
        called_psel = (int.from_bytes(called_psel_data, 'big')
                       if called_psel_data else None)
        cp_pdv_list = cp_params['user-data'][1][0]
        syntax_names = _sytax_names_from_cp_ppdu(cp_ppdu)
        cp_user_data = (
            syntax_names.get_name(
                cp_pdv_list['presentation-context-identifier']),
            cp_pdv_list['presentation-data-values'][1])
        cpa_user_data = await aio.call(
            validate_cb, syntax_names, cp_user_data)
        cpa_ppdu = _cpa_ppdu(syntax_names, called_psel, cpa_user_data)
        cpa_ppdu_data = _encode('CPA-PPDU', cpa_ppdu)
        return cpa_ppdu_data

    async def on_connection(cosp_conn):
        try:
            cp_ppdu = _decode('CP-type', cosp_conn.conn_req_user_data)
            cpa_ppdu = _decode('CPA-PPDU', cosp_conn.conn_res_user_data)
            syntax_names = _sytax_names_from_cp_ppdu(cp_ppdu)
            calling_psel, called_psel = _get_psels(cp_ppdu)
            conn = _create_connection(syntax_names, cosp_conn,
                                      cp_ppdu, cpa_ppdu,
                                      called_psel, calling_psel)
            await aio.call(connection_cb, conn)
        except BaseException as e:
            mlog.error("error creating new incomming connection: %s", e,
                       exc_info=e)
            await aio.uncancellable(_close_connection(cosp_conn, _arp_ppdu()))

    async def wait_cosp_server_closed():
        try:
            await cosp_server.wait_closed()
        finally:
            async_group.close()

    async_group = aio.Group()
    cosp_server = await cosp.listen(on_validate, on_connection, addr)
    async_group.spawn(aio.call_on_cancel, cosp_server.async_close)
    async_group.spawn(wait_cosp_server_closed)

    srv = Server()
    srv._async_group = async_group
    srv._cosp_server = cosp_server
    return srv


class Server(aio.Resource):
    """COPP listening server

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
        return self._cosp_server.addresses


def _create_connection(syntax_names, cosp_conn, cp_ppdu, cpa_ppdu,
                       local_psel, remote_psel):
    cp_user_data = cp_ppdu['normal-mode-parameters']['user-data']
    cpa_user_data = cpa_ppdu['normal-mode-parameters']['user-data']

    conn_req_user_data = (
        syntax_names.get_name(
            cp_user_data[1][0]['presentation-context-identifier']),
        cp_user_data[1][0]['presentation-data-values'][1])
    conn_res_user_data = (
        syntax_names.get_name(
            cpa_user_data[1][0]['presentation-context-identifier']),
        cpa_user_data[1][0]['presentation-data-values'][1])

    conn = Connection()
    conn._cosp_conn = cosp_conn
    conn._syntax_names = syntax_names
    conn._conn_req_user_data = conn_req_user_data
    conn._conn_res_user_data = conn_res_user_data
    conn._info = ConnectionInfo(local_psel=local_psel,
                                remote_psel=remote_psel,
                                **cosp_conn.info._asdict())
    conn._close_ppdu = _arp_ppdu()
    conn._read_queue = aio.Queue()
    conn._async_group = aio.Group()
    conn._async_group.spawn(conn._read_loop)
    return conn


class Connection(aio.Resource):
    """COPP connection

    For creating new connection see :func:`connect`

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def info(self) -> ConnectionInfo:
        """Connection info"""
        return self._info

    @property
    def syntax_names(self) -> SyntaxNames:
        """Syntax names"""
        return self._syntax_names

    @property
    def conn_req_user_data(self) -> IdentifiedEntity:
        """Connect request's user data"""
        return self._conn_req_user_data

    @property
    def conn_res_user_data(self) -> IdentifiedEntity:
        """Connect response's user data"""
        return self._conn_res_user_data

    def close(self, user_data: typing.Optional[IdentifiedEntity] = None):
        """Close connection"""
        self._close_ppdu = _aru_ppdu(self._syntax_names, user_data)
        self._async_group.close()

    async def async_close(self,
                          user_data: typing.Optional[IdentifiedEntity] = None):
        """Async close"""
        self.close(user_data)
        await self.wait_closed()

    async def read(self) -> IdentifiedEntity:
        """Read data"""
        return await self._read_queue.get()

    def write(self, data: IdentifiedEntity):
        """Write data"""
        ppdu_data = _encode('User-data', _user_data(self._syntax_names, data))
        self._cosp_conn.write(ppdu_data)

    async def _read_loop(self):
        try:
            while True:
                cosp_data = await self._cosp_conn.read()
                user_data = _decode('User-data', cosp_data)
                pdv_list = user_data[1][0]
                syntax_name = self._syntax_names.get_name(
                    pdv_list['presentation-context-identifier'])
                data = pdv_list['presentation-data-values'][1]
                await self._read_queue.put((syntax_name, data))
        finally:
            self._async_group.close()
            self._read_queue.close()
            await aio.uncancellable(
                _close_connection(self._cosp_conn, self._close_ppdu))


async def _close_connection(cosp_conn, ppdu):
    try:
        data = _encode('Abort-type', ppdu) if ppdu else None
    except Exception as e:
        mlog.error("error encoding ppdu: %s", e, exc_info=e)
        data = None
    finally:
        await cosp_conn.async_close(data)


def _get_psels(cp_ppdu):
    cp_params = cp_ppdu['normal-mode-parameters']
    calling_psel_data = cp_params.get('calling-presentation-selector')
    calling_psel = (int.from_bytes(calling_psel_data, 'big')
                    if calling_psel_data else None)
    called_psel_data = cp_params.get('called-presentation-selector')
    called_psel = (int.from_bytes(called_psel_data, 'big')
                   if called_psel_data else None)
    return calling_psel, called_psel


def _validate_connect_response(cp_ppdu, cpa_ppdu):
    cp_params = cp_ppdu['normal-mode-parameters']
    cpa_params = cpa_ppdu['normal-mode-parameters']
    called_psel_data = cp_params.get('called-presentation-selector')
    responding_psel_data = cpa_params.get('responding-presentation-selector')
    if called_psel_data and responding_psel_data:
        called_psel = int.from_bytes(called_psel_data, 'big')
        responding_psel = int.from_bytes(responding_psel_data, 'big')
        if called_psel != responding_psel:
            raise Exception('presentation selectors not matching')
    result_list = cpa_params['presentation-context-definition-result-list']
    if any(i['result'] != 0 for i in result_list):
        raise Exception('presentation context not accepted')


def _cp_ppdu(syntax_names, calling_psel, called_psel, user_data):
    cp_params = {
        'presentation-context-definition-list': [
            {'presentation-context-identifier': i,
             'abstract-syntax-name': name,
             'transfer-syntax-name-list': [_encoder.syntax_name]}
            for i, name in syntax_names._syntax_names.items()]}
    if calling_psel is not None:
        cp_params['calling-presentation-selector'] = \
            calling_psel.to_bytes(4, 'big')
    if called_psel is not None:
        cp_params['called-presentation-selector'] = \
            called_psel.to_bytes(4, 'big')
    if user_data:
        cp_params['user-data'] = _user_data(syntax_names, user_data)
    return {
        'mode-selector': {
            'mode-value': 1},
        'normal-mode-parameters': cp_params}


def _cpa_ppdu(syntax_names, responding_psel, user_data):
    cpa_params = {
        'presentation-context-definition-result-list': [
            {'result': 0,
             'transfer-syntax-name': _encoder.syntax_name}
            for _ in syntax_names._syntax_names.keys()]}
    if responding_psel is not None:
        cpa_params['responding-presentation-selector'] = \
            responding_psel.to_bytes(4, 'big')
    if user_data:
        cpa_params['user-data'] = _user_data(syntax_names, user_data)
    return {
        'mode-selector': {
            'mode-value': 1},
        'normal-mode-parameters': cpa_params}


def _aru_ppdu(syntax_names, user_data):
    aru_params = {}
    if user_data:
        aru_params['user-data'] = _user_data(syntax_names, user_data)
    return 'aru-ppdu', ('normal-mode-parameters', aru_params)


def _arp_ppdu():
    return 'arp-ppdu', {}


def _user_data(syntax_names, user_data):
    return 'fully-encoded-data', [{
        'presentation-context-identifier': syntax_names.get_id(user_data[0]),
        'presentation-data-values': (
            'single-ASN1-type', user_data[1])}]


def _sytax_names_from_cp_ppdu(cp_ppdu):
    cp_params = cp_ppdu['normal-mode-parameters']
    syntax_names = SyntaxNames([])
    syntax_names._syntax_names = {
        i['presentation-context-identifier']: i['abstract-syntax-name']
        for i in cp_params['presentation-context-definition-list']}
    return syntax_names


def _encode(name, value):
    return _encoder.encode('ISO8823-PRESENTATION', name, value)


def _decode(name, data):
    res, _ = _encoder.decode('ISO8823-PRESENTATION', name, memoryview(data))
    return res
