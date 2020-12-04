"""Association Controll Service Element"""

from pathlib import Path
import logging
import typing

from hat import aio
from hat import asn1
from hat import util
from hat.drivers import copp


mlog = logging.getLogger(__name__)


IdentifiedEntity = copp.IdentifiedEntity
"""Identified entity"""


Address = copp.Address
"""Address"""


SyntaxNames = copp.SyntaxNames
"""Syntax names"""


ConnectionInfo = util.namedtuple(
    'ConnectionInfo',
    ['local_addr', "Address: local address"],
    ['local_tsel', "Optional[int]: local COTP selector"],
    ['local_ssel', "Optional[int]: local COSP selector"],
    ['local_psel', "Optional[int]: local COPP selector"],
    ['local_ap_title', "Optional[asn1.ObjectIdentifier]: local AP title"],
    ['local_ae_qualifier', "Optional[int]: local AE qualifier"],
    ['remote_addr', "Address: remote address"],
    ['remote_tsel', "Optional[int]: remote COTP selector"],
    ['remote_ssel', "Optional[int]: remote COSP selector"],
    ['remote_psel', "Optional[int]: remote COPP selector"],
    ['remote_ap_title', "Optional[asn1.ObjectIdentifier]: remote AP title"],
    ['remote_ae_qualifier', "Optional[int]: remote AE qualifier"])


ValidateResult = typing.Optional[IdentifiedEntity]
"""Validate result"""


ValidateCb = aio.AsyncCallable[[SyntaxNames, IdentifiedEntity], ValidateResult]
"""Validate callback"""


ConnectionCb = aio.AsyncCallable[['Connection'], None]
"""Connection callback"""


_acse_syntax_name = [('joint-iso-itu-t', 2),
                     ('association-control', 2),
                     ('abstract-syntax', 1),
                     ('apdus', 0),
                     ('version1', 1)]
_encoder = asn1.Encoder(asn1.Encoding.BER,
                        asn1.Repository.from_json(Path(__file__).parent /
                                                  'asn1_repo.json'))


async def connect(syntax_name_list, app_context_name, addr,
                  local_tsel=None, remote_tsel=None,
                  local_ssel=None, remote_ssel=None,
                  local_psel=None, remote_psel=None,
                  local_ap_title=None, remote_ap_title=None,
                  local_ae_qualifier=None, remote_ae_qualifier=None,
                  user_data=None):
    """Connect to ACSE server

    Args:
        syntax_name_list (List[asn1.ObjectIdentifier]): syntax names
        app_context_name (asn1.ObjectIdentifier): application context name
        addr (Address): remote address
        local_tsel (Optional[int]): local COTP selector
        remote_tsel (Optional[int]): remote COTP selector
        local_ssel (Optional[int]): local COSP selector
        remote_ssel (Optional[int]): remote COSP selector
        local_psel (Optional[int]): local COPP selector
        remote_psel (Optional[int]): remote COPP selector
        local_ap_title (Optional[asn1.ObjectIdentifier]): local AP title
        remote_ap_title (Optional[asn1.ObjectIdentifier]): remote AP title
        local_ae_qualifier (Optional[int]): local AE qualifier
        remote_ae_qualifier (Optional[int]): remote AE qualifier
        user_data (Optional[IdentifiedEntity]]): connect request user data

    Returns:
        Connection

    """
    syntax_names = SyntaxNames([_acse_syntax_name, *syntax_name_list])
    aarq_apdu = _aarq_apdu(syntax_names, app_context_name,
                           local_ap_title, remote_ap_title,
                           local_ae_qualifier, remote_ae_qualifier,
                           user_data)
    copp_user_data = _acse_syntax_name, _encode(aarq_apdu)
    copp_conn = await copp.connect(syntax_names=syntax_names,
                                   addr=addr,
                                   local_tsel=local_tsel,
                                   remote_tsel=remote_tsel,
                                   local_ssel=local_ssel,
                                   remote_ssel=remote_ssel,
                                   local_psel=local_psel,
                                   remote_psel=remote_psel,
                                   user_data=copp_user_data)
    try:
        aare_apdu_syntax_name, aare_apdu_entity = copp_conn.conn_res_user_data
        if not asn1.is_oid_eq(aare_apdu_syntax_name, _acse_syntax_name):
            raise Exception("invalid syntax name")
        aare_apdu = _decode(aare_apdu_entity)
        if aare_apdu[0] != 'aare' or aare_apdu[1]['result'] != 0:
            raise Exception("invalid apdu")
        calling_ap_title, called_ap_title = _get_ap_titles(aarq_apdu)
        calling_ae_qualifier, called_ae_qualifier = _get_ae_qualifiers(
            aarq_apdu)
        return _create_connection(copp_conn, aarq_apdu, aare_apdu,
                                  calling_ap_title, called_ap_title,
                                  calling_ae_qualifier, called_ae_qualifier)
    except Exception:
        await aio.uncancellable(
            _close_connection(copp_conn, _abrt_apdu(1)))
        raise


async def listen(validate_cb, connection_cb, addr=Address('0.0.0.0', 102)):
    """Create ACSE listening server

    Args:
        validate_cb (ValidateCb): callback function or coroutine called on new
            incomming connection request prior to creating connection object
        connection_cb (ConnectionCb): new connection callback
        addr (Address): local listening address

    Returns:
        Server

    """

    async def on_validate(syntax_names, user_data):
        aarq_apdu_syntax_name, aarq_apdu_entity = user_data
        if not asn1.is_oid_eq(aarq_apdu_syntax_name, _acse_syntax_name):
            raise Exception('invalid acse syntax name')
        aarq_apdu = _decode(aarq_apdu_entity)
        if aarq_apdu[0] != 'aarq':
            raise Exception('not aarq message')
        aarq_external = aarq_apdu[1]['user-information'][0]
        if aarq_external.direct_ref is not None:
            if not asn1.is_oid_eq(aarq_external.direct_ref,
                                  _encoder.syntax_name):
                raise Exception('invalid encoder identifier')
        _, called_ap_title = _get_ap_titles(aarq_apdu)
        _, called_ae_qualifier = _get_ae_qualifiers(aarq_apdu)
        _, called_ap_invocation_identifier = \
            _get_ap_invocation_identifiers(aarq_apdu)
        _, called_ae_invocation_identifier = \
            _get_ae_invocation_identifiers(aarq_apdu)

        aarq_user_data = (syntax_names.get_name(aarq_external.indirect_ref),
                          aarq_external.data)
        user_validate_result = await aio.call(
            validate_cb, syntax_names, aarq_user_data)
        aare_apdu = _aare_apdu(syntax_names,
                               user_validate_result,
                               called_ap_title, called_ae_qualifier,
                               called_ap_invocation_identifier,
                               called_ae_invocation_identifier)
        return _acse_syntax_name, _encode(aare_apdu)

    async def on_connection(copp_conn):
        try:
            aarq_apdu = _decode(copp_conn.conn_req_user_data[1])
            aare_apdu = _decode(copp_conn.conn_res_user_data[1])
            calling_ap_title, called_ap_title = _get_ap_titles(aarq_apdu)
            calling_ae_qualifier, called_ae_qualifier = _get_ae_qualifiers(
                aarq_apdu)
            conn = _create_connection(
                copp_conn, aarq_apdu, aare_apdu,
                called_ap_title, calling_ap_title,
                called_ae_qualifier, calling_ae_qualifier)
            await aio.call(connection_cb, conn)
        except BaseException as e:
            mlog.error("error creating new incomming connection: %s", e,
                       exc_info=e)
            await aio.uncancellable(
                _close_connection(copp_conn, _abrt_apdu(1)))

    async def wait_copp_server_closed():
        try:
            await copp_server.closed
        finally:
            group.close()

    group = aio.Group()
    copp_server = await copp.listen(on_validate, on_connection, addr)
    group.spawn(aio.call_on_cancel, copp_server.async_close)
    group.spawn(wait_copp_server_closed)

    srv = Server()
    srv._group = group
    srv._copp_server = copp_server
    return srv


class Server:
    """ACSE listening server

    For creating new server see :func:`listen`

    """

    @property
    def addresses(self):
        """List[Address]: listening addresses"""
        return self._copp_server.addresses

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._group.closed

    async def async_close(self):
        """Close listening socket

        Calling this method doesn't close active incomming connections

        """
        await self._group.async_close()


def _create_connection(copp_conn, aarq_apdu, aare_apdu,
                       local_ap_title, remote_ap_title,
                       local_ae_qualifier, remote_ae_qualifier):
    aarq_external = aarq_apdu[1]['user-information'][0]
    aare_external = aare_apdu[1]['user-information'][0]
    conn_req_user_data = (
        copp_conn.syntax_names.get_name(aarq_external.indirect_ref),
        aarq_external.data)
    conn_res_user_data = (
        copp_conn.syntax_names.get_name(aare_external.indirect_ref),
        aare_external.data)

    conn = Connection()
    conn._copp_conn = copp_conn
    conn._conn_req_user_data = conn_req_user_data
    conn._conn_res_user_data = conn_res_user_data
    conn._info = ConnectionInfo(local_ap_title=local_ap_title,
                                local_ae_qualifier=local_ae_qualifier,
                                remote_ap_title=remote_ap_title,
                                remote_ae_qualifier=remote_ae_qualifier,
                                **copp_conn.info._asdict())
    conn._read_queue = aio.Queue()
    conn._group = aio.Group()
    conn._group.spawn(conn._read_loop)
    return conn


class Connection:
    """ACSE connection

    For creating new connection see :func:`connect`

    """

    @property
    def info(self):
        """ConnectionInfo: connection info"""
        return self._info

    @property
    def conn_req_user_data(self):
        """IdentifiedEntity: connect request's user data"""
        return self._conn_req_user_data

    @property
    def conn_res_user_data(self):
        """IdentifiedEntity: connect response's user data"""
        return self._conn_res_user_data

    @property
    def closed(self):
        """asyncio.Future: closed future"""
        return self._group.closed

    async def async_close(self):
        """Async close"""
        await self._group.async_close()

    async def read(self):
        """Read data

        Returns:
            IdentifiedEntity

        """
        return await self._read_queue.get()

    def write(self, data):
        """Write data

        Args:
            data (IdentifiedEntity): data

        """
        self._copp_conn.write(data)

    async def _read_loop(self):
        close_apdu = _abrt_apdu(0)
        try:
            while True:
                syntax_name, entity = await self._copp_conn.read()
                if asn1.is_oid_eq(syntax_name, _acse_syntax_name):
                    if entity[0] == 'abrt':
                        close_apdu = None
                    elif entity[0] == 'rlrq':
                        close_apdu = _rlre_apdu()
                    else:
                        close_apdu = _abrt_apdu(1)
                    break
                await self._read_queue.put((syntax_name, entity))
        finally:
            self._group.close()
            self._read_queue.close()
            await aio.uncancellable(
                _close_connection(self._copp_conn, close_apdu))


async def _close_connection(copp_conn, apdu):
    data = (_acse_syntax_name, _encode(apdu)) if apdu else None
    await copp_conn.async_close(data)


def _get_ap_titles(aarq_apdu):
    calling = None
    called = None
    if 'calling-AP-title' in aarq_apdu[1]:
        if aarq_apdu[1]['calling-AP-title'][0] == 'ap-title-form2':
            calling = aarq_apdu[1]['calling-AP-title'][1]
    if 'called-AP-title' in aarq_apdu[1]:
        if aarq_apdu[1]['called-AP-title'][0] == 'ap-title-form2':
            called = aarq_apdu[1]['called-AP-title'][1]
    return calling, called


def _get_ae_qualifiers(aarq_apdu):
    calling = None
    called = None
    if 'calling-AE-qualifier' in aarq_apdu[1]:
        if aarq_apdu[1]['calling-AE-qualifier'][0] == 'ap-qualifier-form2':
            calling = aarq_apdu[1]['calling-AE-qualifier'][1]
    if 'called-AE-qualifier' in aarq_apdu[1]:
        if aarq_apdu[1]['called-AE-qualifier'][0] == 'ap-qualifier-form2':
            called = aarq_apdu[1]['called-AE-qualifier'][1]
    return calling, called


def _get_ap_invocation_identifiers(aarq_apdu):
    calling = aarq_apdu[1].get('calling-AP-invocation-identifier')
    called = aarq_apdu[1].get('called-AP-invocation-identifier')
    return calling, called


def _get_ae_invocation_identifiers(aarq_apdu):
    calling = aarq_apdu[1].get('calling-AE-invocation-identifier')
    called = aarq_apdu[1].get('called-AE-invocation-identifier')
    return calling, called


def _aarq_apdu(syntax_names, app_context_name,
               calling_ap_title, called_ap_title,
               calling_ae_qualifier, called_ae_qualifier,
               user_data):
    aarq_apdu = 'aarq', {'application-context-name': app_context_name}
    if calling_ap_title is not None:
        aarq_apdu[1]['calling-AP-title'] = 'ap-title-form2', calling_ap_title
    if called_ap_title is not None:
        aarq_apdu[1]['called-AP-title'] = 'ap-title-form2', called_ap_title
    if calling_ae_qualifier is not None:
        aarq_apdu[1]['calling-AE-qualifier'] = ('ae-qualifier-form2',
                                                calling_ae_qualifier)
    if called_ae_qualifier is not None:
        aarq_apdu[1]['called-AE-qualifier'] = ('ae-qualifier-form2',
                                               called_ae_qualifier)
    if user_data:
        aarq_apdu[1]['user-information'] = [
            asn1.External(direct_ref=_encoder.syntax_name,
                          indirect_ref=syntax_names.get_id(user_data[0]),
                          data=user_data[1])]
    return aarq_apdu


def _aare_apdu(syntax_names, user_data,
               responding_ap_title, responding_ae_qualifier,
               responding_ap_invocation_identifier,
               responding_ae_invocation_identifier):
    aare_apdu = 'aare', {
        'application-context-name': user_data[0],
        'result': 0,
        'result-source-diagnostic': ('acse-service-user', 0),
        'user-information': [
            asn1.External(direct_ref=_encoder.syntax_name,
                          indirect_ref=syntax_names.get_id(user_data[0]),
                          data=user_data[1])]}
    if responding_ap_title is not None:
        aare_apdu[1]['responding-AP-title'] = ('ap-title-form2',
                                               responding_ap_title)
    if responding_ae_qualifier is not None:
        aare_apdu[1]['responding-AE-qualifier'] = ('ae-qualifier-form2',
                                                   responding_ae_qualifier)
    if responding_ap_invocation_identifier is not None:
        aare_apdu[1]['responding-AP-invocation-identifier'] = \
            responding_ap_invocation_identifier
    if responding_ae_invocation_identifier is not None:
        aare_apdu[1]['responding-AE-invocation-identifier'] = \
            responding_ae_invocation_identifier
    return aare_apdu


def _abrt_apdu(source):
    return 'abrt', {'abort-source': source}


def _rlre_apdu():
    return 'rlre', {}


def _encode(value):
    return _encoder.encode_value('ACSE-1', 'ACSE-apdu', value)


def _decode(entity):
    return _encoder.decode_value('ACSE-1', 'ACSE-apdu', entity)
