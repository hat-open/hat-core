import enum
import typing

import hat.asn1
import hat.asn1.ber
from hat import util


ObjectIdentifier = hat.asn1.ObjectIdentifier


@util.extend_enum_doc
class Version(enum.Enum):
    V1 = 0
    V2C = 1
    V3 = 3


Error = util.namedtuple(
    'Error',
    ['type', 'ErrorType'],
    ['index', 'int'])


@util.extend_enum_doc
class ErrorType(enum.Enum):
    NO_ERROR = 0
    TOO_BIG = 1
    NO_SUCH_NAME = 2
    BAD_VALUE = 3
    READ_ONLY = 4
    GEN_ERR = 5
    NO_ACCESS = 6
    WRONG_TYPE = 7
    WRONG_LENGTH = 8
    WRONG_ENCODING = 9
    WRONG_VALUE = 10
    NO_CREATION = 11
    INCONSISTENT_VALUE = 12
    RESOURCE_UNAVAILABLE = 13
    COMMIT_FAILED = 14
    UNDO_FAILED = 15
    AUTHORIZATION_ERROR = 16
    NOT_WRITABLE = 17
    INCONSISTENT_NAME = 18


Cause = util.namedtuple(
    'Cause',
    ['type', 'CouseType'],
    ['value', 'int'])


class CauseType(enum.Enum):
    COLD_START = 0
    WARM_START = 1
    LINK_DOWN = 2
    LINK_UP = 3
    AUTHENICATION_FAILURE = 4
    EGP_NEIGHBOR_LOSS = 5
    ENTERPRISE_SPECIFIC = 6


Data = util.namedtuple(
    ['Data', """Data

        Type of value is determined by value of data type:

            +------------------+------------------------+
            | type             | value                  |
            +==================+========================+
            | INTEGER          | int                    |
            +------------------+------------------------+
            | UNSIGNED         | int                    |
            +------------------+------------------------+
            | COUNTER          | int                    |
            +------------------+------------------------+
            | BIG_COUNTER      | int                    |
            +------------------+------------------------+
            | STRING           | str                    |
            +------------------+------------------------+
            | OBJECT_ID        | ObjectIdentifier       |
            +------------------+------------------------+
            | IP_ADDRESS       | Tuple[int,int,int,int] |
            +------------------+------------------------+
            | TIME_TICKS       | int                    |
            +------------------+------------------------+
            | ARBITRARY        | bytes                  |
            +------------------+------------------------+
            | EMPTY            | NoneType               |
            +------------------+------------------------+
            | UNSPECIFIED      | NoneType               |
            +------------------+------------------------+
            | NO_SUCH_OBJECT   | NoneType               |
            +------------------+------------------------+
            | NO_SUCH_INSTANCE | NoneType               |
            +------------------+------------------------+
            | END_OF_MIB_VIEW  | NoneType               |
            +------------------+------------------------+

    """],
    ['type', 'DataType'],
    ['name', 'ObjectIdentifier'],
    ['value', 'Any'])


DataType = util.extend_enum_doc(enum.Enum('DataType', [
    'INTEGER',
    'UNSIGNED',
    'COUNTER',
    'BIG_COUNTER',
    'STRING',
    'OBJECT_ID',
    'IP_ADDRESS',
    'TIME_TICKS',
    'ARBITRARY',
    'EMPTY',
    'UNSPECIFIED',
    'NO_SUCH_OBJECT',
    'NO_SUCH_INSTANCE',
    'END_OF_MIB_VIEW']))


Trap = util.namedtuple(
    'Trap',
    ['oid', 'ObjectIdentifier'],
    ['timestamp', 'int'],
    ['data', 'List[Data]'])


Context = util.namedtuple(
    'Context',
    ['engine_id', 'str'],
    ['name', 'str'])


MsgV1 = util.namedtuple(
    'MsgV1',
    ['type', 'MsgType'],
    ['community', 'str'],
    ['pdu', 'Pdu'])


MsgV2C = util.namedtuple(
    'MsgV2C',
    ['type', 'MsgType'],
    ['community', 'str'],
    ['pdu', 'Pdu'])


MsgV3 = util.namedtuple(
    'Msg',
    ['type', 'MsgType'],
    ['id', 'int'],
    ['reportable', 'bool'],
    ['context', 'Context'],
    ['pdu', 'Pdu'])


Msg = typing.Union[MsgV1, MsgV2C, MsgV3]


MsgType = enum.Enum('MsgType', [
    'GET_REQUEST',
    'GET_NEXT_REQUEST',
    'GET_BULK_REQUEST',
    'RESPONSE',
    'SET_REQUEST',
    'TRAP',
    'INFORM_REQUEST',
    'SNMPV2_TRAP',
    'REPORT'])


BasicPdu = util.namedtuple(
    'BasicPdu',
    ['request_id', 'int'],
    ['error', 'Error'],
    ['data', 'List[Data]'])


TrapPdu = util.namedtuple(
    'TrapPdu',
    ['enterprise', 'ObjectIdentifier'],
    ['addr', 'Tuple[int,int,int,int]'],
    ['cause', 'Cause'],
    ['timestamp', 'int'],
    ['data', 'List[Data]'])


BulkPdu = util.namedtuple(
    'BulkPdu',
    ['request_id', 'int'],
    ['non_repeaters', 'int'],
    ['max_repetitions', 'int'],
    ['data', 'List[Data]'])


Pdu = typing.Union[BasicPdu, TrapPdu, BulkPdu]


def trap_to_pdu(version, trap):
    """Convert Trap to Pdu

    Args:
        version (Version): version
        trap (Trap): trap

    Returns:
        Pdu

    """
    raise NotImplementedError()


def trap_from_pdu(pdu):
    """Convert Pdu to Trap

    Args:
        pdu (Pdu): pdu

    Returns:
        Trap

    """
    raise NotImplementedError()


class Serializer:

    def __init__(self, encoder):
        self._encoder = encoder

    def encode(self, msg):
        """Encode message

        Args:
            msg (Msg): message

        Returns:
            bytes

        """
        if isinstance(msg, MsgV1):
            data = _encode_msg_v1(msg)
            name = 'MessageV1'
        elif isinstance(msg, MsgV2C):
            name = 'MessageV2C'
            data = _encode_msg_v2c(msg)
        elif isinstance(msg, MsgV3):
            name = 'MessageV3'
            data = _encode_msg_v3(msg)
        else:
            raise TypeError()
        msg_entity = self._encoder.encode('SNMP', name, data)
        msg_bytes = bytes(msg_entity)
        return msg_bytes

    def decode(self, msg_bytes):
        msg_entity = self._encoder.parser(msg_bytes)
        version = _get_version(msg_entity)
        name = f'Message{version.name}'
        msg = self._encoder.decode('SNMP', name, msg_entity)
        if version == Version.V1:
            return _decode_msg_v1(msg)
        if version == Version.V2C:
            return _decode_msg_v2c(msg)
        if version == Version.V3:
            return _decode_msg_v3(msg)
        raise Exception()


def _get_version(entity):
    if (entity.class_type != hat.asn1.ber.ClassType.UNIVERSAL or
            entity.tag_number != 16 or
            not entity.elements or
            entity.elements[0].class_type !=
            hat.asn1.ber.ClassType.UNIVERSAL or
            entity.elements[0].tag_number != 2):
        raise Exception()
    return Version(entity.elements[0].value)


def _encode_msg_v1(msg):
    version = Version.V1
    return {'version': version.value,
            'community': msg.community.encode('utf-8'),
            'data':  (_msg_type_to_pdu_name[msg.type],
                      _encode_pdu(version, msg.type, msg.pdu))}


def _decode_msg_v1(msg):
    msg_type = _pdu_name_to_msg_type[msg['data'][0]]
    pdu = _decode_pdu(Version.V1, msg_type, msg['data'][1])
    return MsgV1(type=msg_type,
                 community=msg['community'],
                 pdu=pdu)


def _encode_msg_v2c(msg):
    version = Version.V2C
    return {'version': version.value,
            'community': msg.community.encode('utf-8'),
            'data':  (_msg_type_to_pdu_name[msg.type],
                      _encode_pdu(version, msg.type, msg.pdu))}


def _decode_msg_v2c(msg):
    msg_type = _pdu_name_to_msg_type[msg['data'][0]]
    pdu = _decode_pdu(Version.V2C, msg_type, msg['data'][1])
    return MsgV2C(type=msg_type,
                  community=msg['community'],
                  pdu=pdu)


def _encode_msg_v3(msg):
    version = Version.V3
    return {'version': version.value,
            'msgGlobalData': {'msgID': msg.id,
                              'msgMaxSize': 2147483647,
                              'msgFlags': bytes([4 if msg.reportable else 0]),
                              'msgSecurityModel': 1},
            'msgSecurityParameters': b'',
            'msgData': ('plaintext', {
                'contextEngineID': msg.context.engine_id.encode('utf-8'),
                'contextName': msg.context.name.encode('utf-8'),
                'data': (_msg_type_to_pdu_name[msg.type],
                         _encode_pdu(version, msg.type, msg.pdu))})}


def _decode_msg_v3(msg):
    msg_type = _pdu_name_to_msg_type[msg['msgData'][1]['data'][0]]
    pdu = _decode_pdu(Version.V3, msg_type, msg['msgData'][1]['data'][1])
    return MsgV3(
        msg_type=msg_type,
        id=msg['msgGlobalData']['msgID'],
        reportable=bool(msg['msgGlobalData']['msgFlags'][0] & 4),
        context=Context(
            engine_id=msg['msgData'][1]['contextEngineID'].decode('utf-8'),
            name=msg['msgData'][1]['contextName'].decode('utf-8')),
        pdu=pdu)


def _encode_pdu(version, msg_type, pdu):
    if msg_type == MsgType.GET_BULK_REQUEST:
        return _encode_bulk_pdu(version, pdu)
    if msg_type == MsgType.TRAP:
        return _encode_trap_pdu(version, pdu)
    if msg_type in {MsgType.GET_REQUEST,
                    MsgType.GET_NEXT_REQUEST,
                    MsgType.RESPONSE,
                    MsgType.SET_REQUEST,
                    MsgType.INFORM_REQUEST,
                    MsgType.SNMPV2_TRAP,
                    MsgType.REPORT}:
        return _encode_basic_pdu(version, pdu)
    raise Exception()


def _decode_pdu(version, msg_type, pdu):
    if msg_type == MsgType.GET_BULK_REQUEST:
        return _decode_bulk_pdu(version, pdu)
    if msg_type == MsgType.TRAP:
        return _decode_trap_pdu(version, pdu)
    if msg_type in {MsgType.GET_REQUEST,
                    MsgType.GET_NEXT_REQUEST,
                    MsgType.RESPONSE,
                    MsgType.SET_REQUEST,
                    MsgType.INFORM_REQUEST,
                    MsgType.SNMPV2_TRAP,
                    MsgType.REPORT}:
        return _decode_basic_pdu(version, pdu)
    raise Exception()


def _encode_basic_pdu(version, pdu):
    return {'request-id': pdu.request_id,
            'error-status': pdu.error.type.value,
            'error-index': pdu.error.index,
            'variable-bindings': [_encode_data(version, data)
                                  for data in pdu.data]}


def _decode_basic_pdu(version, pdu):
    return BasicPdu(request_id=pdu['request-id'],
                    error=Error(type=ErrorType(pdu['error-status']),
                                index=pdu['error-index']),
                    data=[_decode_data(version, data)
                          for data in pdu['variable-bindings']])


def _encode_bulk_pdu(version, pdu):
    return {'request-id': pdu.request_id,
            'non-repeaters': pdu.non_repeaters,
            'max-repetitions': pdu.max_repetitions,
            'variable-bindings': [_encode_data(version, data)
                                  for data in pdu.data]}


def _decode_bulk_pdu(version, pdu):
    return BulkPdu(request_id=pdu['request-id'],
                   non_repeaters=pdu['non-repeaters'],
                   max_repetitions=pdu['max-repetitions'],
                   data=[_decode_data(version, data)
                         for data in pdu['variable-bindings']])


def _encode_trap_pdu(version, pdu):
    return {'enterprise': pdu.enterprise,
            'agent-addr': pdu.addr,
            'generic-trap': pdu.cause.type.value,
            'specific-trap': pdu.cause.value,
            'time-stamp': pdu.timestamp,
            'variable-bindings': [_encode_data(version, data)
                                  for data in pdu.data]}


def _decode_trap_pdu(version, pdu):
    return TrapPdu(enterprise=pdu['enterprise'],
                   addr=tuple(pdu['agent-addr']),
                   cause=Cause(type=CauseType(pdu['generic-trap']),
                               value=pdu['specific-trap']),
                   timestamp=pdu['time-stamp'],
                   data=[_decode_data(version, data)
                         for data in pdu['variable-bindings']])


def _encode_data(version, data):
    if data.type == DataType.INTEGER:
        data_type = 'value'
        value = ('simple', ('integer', data.value))
    elif data.type == DataType.UNSIGNED:
        data_type = 'value'
        value = ('application-wide', ('unsigned', data.value))
    elif data.type == DataType.COUNTER:
        data_type = 'value'
        value = ('application-wide', ('counter', data.value))
    elif data.type == DataType.BIG_COUNTER:
        data_type = 'value'
        value = ('application-wide', ('bigCounter', data.value))
    elif data.type == DataType.STRING:
        data_type = 'value'
        value = ('simple', ('string', data.value.encode('utf-8')))
    elif data.type == DataType.OBJECT_ID:
        data_type = 'value'
        value = ('simple', ('objectId', data.value))
    elif data.type == DataType.IP_ADDRESS:
        data_type = 'value'
        value = ('application-wide', ('ipAddress', bytes(data.value)))
    elif data.type == DataType.TIME_TICKS:
        data_type = 'value'
        value = ('application-wide', ('timeTicks', data.value))
    elif data.type == DataType.ARBITRARY:
        data_type = 'value'
        value = ('application-wide', ('arbitrary', data.value))
    elif data.type == DataType.EMPTY:
        data_type = 'value'
        value = ('simple', ('empty', None))
    elif data.type == DataType.UNSPECIFIED:
        data_type = 'unSpecified'
        value = None
    elif data.type == DataType.NO_SUCH_OBJECT:
        data_type = 'noSuchObject'
        value = None
    elif data.type == DataType.NO_SUCH_INSTANCE:
        data_type = 'noSuchInstance'
        value = None
    elif data.type == DataType.END_OF_MIB_VIEW:
        data_type = 'endOfMibView'
        value = None
    else:
        raise TypeError()
    return {'name': data.name,
            'data': (data_type, value)}


def _decode_data(version, data):
    t1, v1 = data['data']
    if t1 == 'value':
        t2, (t3, v2) = v1
        if t2 == 'simple':
            if t3 == 'integer':
                data_type = DataType.INTEGER
                value = v2
            elif t3 == 'string':
                data_type = DataType.STRING
                value = v2.decode('utf-8')
            elif t3 == 'objectId':
                data_type = DataType.OBJECT_ID
                value = tuple(v2)
            elif t3 == 'empty':
                data_type = DataType.EMPTY
                value = None
            else:
                raise Exception()
        elif t2 == 'application-wide':
            if t3 == 'ipAddress':
                data_type = DataType.IP_ADDRESS
                value = tuple(v2)
            elif t3 == 'counter':
                data_type = DataType.COUNTER
                value = v2
            elif t3 == 'unsigned':
                data_type = DataType.UNSIGNED
                value = v2
            elif t3 == 'timeTicks':
                data_type = DataType.TIME_TICKS
                value = v2
            elif t3 == 'arbitrary':
                data_type = DataType.ARBITRARY
                value = v2
            elif t3 == 'bigCounter':
                data_type = DataType.BIG_COUNTER
                value = v2
            else:
                raise Exception()
        else:
            raise Exception()
    elif t1 == 'unSpecified':
        data_type = DataType.UNSPECIFIED
        value = None
    elif t1 == 'noSuchObject':
        data_type = DataType.NO_SUCH_OBJECT
        value = None
    elif t1 == 'noSuchInstance':
        data_type = DataType.NO_SUCH_INSTANCE
        value = None
    elif t1 == 'endOfMibView':
        data_type = DataType.END_OF_MIB_VIEW
        value = None
    else:
        raise Exception()
    return Data(type=data_type,
                name=tuple(data['name']),
                value=value)


_msg_type_to_pdu_name, _pdu_name_to_msg_type = (
    lambda x: ({k: v for k, v in x},
               {k: v for v, k in x})
)([(MsgType.GET_REQUEST, 'get-request'),
   (MsgType.GET_NEXT_REQUEST, 'get-next-request'),
   (MsgType.GET_BULK_REQUEST, 'get-bulk-request'),
   (MsgType.RESPONSE, 'response'),
   (MsgType.SET_REQUEST, 'set-request'),
   (MsgType.TRAP, 'trap'),
   (MsgType.INFORM_REQUEST, 'inform-request'),
   (MsgType.SNMPV2_TRAP, 'nmpV2-trap'),
   (MsgType.REPORT, 'report')])
