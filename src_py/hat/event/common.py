"""Common functionality shared between clients and event server"""

from pathlib import Path
import datetime
import enum
import struct
import typing

from hat import chatter
from hat import json
from hat import sbs
import hat.monitor.common


package_path: Path = Path(__file__).parent
"""Python package path"""

json_schema_repo: json.SchemaRepository = json.SchemaRepository(
    json.json_schema_repo,
    hat.monitor.common.json_schema_repo,
    json.SchemaRepository.from_json(package_path / 'json_schema_repo.json'))
"""JSON schema repository"""

sbs_repo = sbs.Repository(
    chatter.sbs_repo,
    sbs.Repository.from_json(package_path / 'sbs_repo.json'))
"""SBS schema repository"""

EventType: typing.Type = typing.List[str]
"""Event type"""


Order = enum.Enum('Order', [
    'DESCENDING',
    'ASCENDING'])


OrderBy = enum.Enum('OrderBy', [
    'TIMESTAMP',
    'SOURCE_TIMESTAMP'])


EventPayloadType = enum.Enum('EventPayloadType', [
    'BINARY',
    'JSON',
    'SBS'])


class EventId(typing.NamedTuple):
    server: int
    """server identifier"""
    instance: int
    """event instance identifier"""


class EventPayload(typing.NamedTuple):
    type: EventPayloadType
    data: typing.Union[bytes, json.Data, 'SbsData']


class SbsData(typing.NamedTuple):
    module: typing.Optional[str]
    """SBS module name"""
    type: str
    """SBS type name"""
    data: bytes


class Event(typing.NamedTuple):
    event_id: EventId
    event_type: EventType
    timestamp: 'Timestamp'
    source_timestamp: typing.Optional['Timestamp']
    payload: typing.Optional[EventPayload]


class RegisterEvent(typing.NamedTuple):
    event_type: EventType
    source_timestamp: typing.Optional['Timestamp']
    payload: typing.Optional[EventPayload]


class QueryData(typing.NamedTuple):
    event_ids: typing.Optional[typing.List[EventId]] = None
    event_types: typing.Optional[typing.List[EventType]] = None
    t_from: typing.Optional['Timestamp'] = None
    t_to: typing.Optional['Timestamp'] = None
    source_t_from: typing.Optional['Timestamp'] = None
    source_t_to: typing.Optional['Timestamp'] = None
    payload: typing.Optional[EventPayload] = None
    order: Order = Order.DESCENDING
    order_by: OrderBy = OrderBy.TIMESTAMP
    unique_type: bool = False
    max_results: typing.Optional[int] = None


def matches_query_type(event_type: EventType,
                       query_type: EventType
                       ) -> bool:
    """Determine if event type matches query type

    Event type is tested if it matches query type according to the following
    rules:

        * Matching is performed on subtypes in increasing order.
        * Event type is a match only if all its subtypes are matched by
          corresponding query subtypes.
        * Matching is finished when all query subtypes are exhausted.
        * Query subtype '?' matches exactly one event subtype of any value.
          The subtype must exist.
        * Query subtype '*' matches 0 or more event subtypes of any value. It
          must be the last query subtype.
        * All other values of query subtype match exactly one event subtype
          of the same value.
        * Query type without subtypes is matched only by event type with no
          subtypes.

    As a consequence of aforementioned matching rules, event subtypes '*' and
    '?' cannot be directly matched and it is advisable not to use them in event
    types.

    """
    is_variable = bool(query_type and query_type[-1] == '*')
    if is_variable:
        query_type = query_type[:-1]

    if len(event_type) < len(query_type):
        return False

    if len(event_type) > len(query_type) and not is_variable:
        return False

    for i, j in zip(event_type, query_type):
        if j != '?' and i != j:
            return False

    return True


class Subscription:
    """Subscription defined by query event types"""

    _Node = typing.Tuple[bool,                  # is_leaf
                         typing.Dict[str,       # subtype
                                     '_Node']]  # child

    def __init__(self, query_types: typing.Iterable[EventType]):
        self._root = False, {}
        for query_type in query_types:
            self._root = self._add_query_type(self._root, query_type)

    def get_query_types(self) -> typing.Iterable[EventType]:
        """Calculate sanitized query event types"""
        yield from self._get_query_types(self._root)

    def matches(self, event_type: EventType) -> bool:
        """Does `event_type` match subscription"""
        return self._matches(self._root, event_type)

    def _add_query_type(self, node, query_type):
        is_leaf, children = node

        if '*' in children:
            return node

        if not query_type:
            return True, children

        head, rest = query_type[0], query_type[1:]

        if head == '*':
            if rest:
                raise ValueError('invalid query event type')
            children.clear()
            children['*'] = True, {}

        else:
            child = children.get(head, (False, {}))
            child = self._add_query_type(child, rest)
            children[head] = child

        return node

    def _get_query_types(self, node):
        is_leaf, children = node

        if is_leaf and '*' not in children:
            yield []

        for head, child in children.items():
            for rest in self._get_query_types(child):
                yield [head, *rest]

    def _matches(self, node, event_type):
        is_leaf, children = node

        if '*' in children:
            return True

        if not event_type:
            return is_leaf

        head, rest = event_type[0], event_type[1:]

        for i in (head, '?'):
            child = children.get(i)
            if not child:
                continue
            if self._matches(child, rest):
                return True

        return False


class Timestamp(typing.NamedTuple):
    s: int
    """seconds since 1970-01-01 (can be negative)"""
    us: int
    """microseconds added to timestamp seconds in range (-1e6, 1e6)"""

    def __lt__(self, other):
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.s * 1000000 + self.us < other.s * 1000000 + other.us

    def __gt__(self, other):
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.s * 1000000 + self.us > other.s * 1000000 + other.us

    def __eq__(self, other):
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.s * 1000000 + self.us == other.s * 1000000 + other.us

    def __ne__(self, other):
        return not self == other

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def __hash__(self):
        return self.s * 1000000 + self.us


def timestamp_to_bytes(t: Timestamp) -> bytes:
    """Convert timestamp to 12 byte representation

    Bytes [0, 8] are big endian two's complement encoded `Timestamp.s` and
    bytes [9, 12] are big endian two's complement encoded `Timestamp.us`.

    """
    return struct.pack(">qi", t.s, t.us)


def timestamp_from_bytes(data: bytes) -> Timestamp:
    """Create new timestamp from 12 byte representation

    Bytes representation is same as defined for `timestamp_to_bytes` function.

    """
    s, us = struct.unpack(">qi", data)
    return Timestamp(s, us)


def timestamp_to_float(t: Timestamp) -> float:
    """Convert timestamp to floating number of seconds since 1970-01-01 UTC

    For precise serialization see `timestamp_to_bytes`/`timestamp_from_bytes`.

    """
    return t.s + t.us * 1E-6


def timestamp_from_float(ts: float) -> Timestamp:
    """Create timestamp from floating number of seconds since 1970-01-01 UTC

    For precise serialization see `timestamp_to_bytes`/`timestamp_from_bytes`.

    """
    s = int(ts)
    if ts < 0:
        s = s - 1
    us = round((ts - s) * 1E6)
    if us == 1000000:
        return Timestamp(s + 1, 0)
    else:
        return Timestamp(s, us)


def timestamp_to_datetime(t: Timestamp) -> datetime.datetime:
    """Convert timestamp to datetime (representing utc time)

    For precise serialization see `timestamp_to_bytes`/`timestamp_from_bytes`.

    """
    try:
        dt_from_s = datetime.datetime.fromtimestamp(t.s, datetime.timezone.utc)
    except OSError:
        dt_from_s = (
            datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) +
            datetime.timedelta(seconds=t.s))
    return datetime.datetime(
        year=dt_from_s.year,
        month=dt_from_s.month,
        day=dt_from_s.day,
        hour=dt_from_s.hour,
        minute=dt_from_s.minute,
        second=dt_from_s.second,
        microsecond=t.us,
        tzinfo=datetime.timezone.utc)


def timestamp_from_datetime(dt: datetime.datetime) -> Timestamp:
    """Create new timestamp from datetime

    If `tzinfo` is not set, it is assumed that provided datetime represents
    utc time.

    For precise serialization see `timestamp_to_bytes`/`timestamp_from_bytes`.

    """
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    s = int(dt.timestamp())
    if dt.timestamp() < 0:
        s = s - 1
    return Timestamp(s=s, us=dt.microsecond)


def timestamp_to_sbs(t: Timestamp) -> sbs.Data:
    """Convert timestamp to SBS data"""
    return {'s': t.s, 'us': t.us}


def timestamp_from_sbs(data: sbs.Data) -> Timestamp:
    """Create new timestamp from SBS data"""
    return Timestamp(s=data['s'], us=data['us'])


def now() -> Timestamp:
    """Create new timestamp representing current time"""
    return timestamp_from_datetime(
        datetime.datetime.now(datetime.timezone.utc))


def event_to_sbs(event: Event) -> sbs.Data:
    """Convert Event to SBS data"""
    return {
        'id': _event_id_to_sbs(event.event_id),
        'type': event.event_type,
        'timestamp': timestamp_to_sbs(event.timestamp),
        'sourceTimestamp': _optional_to_sbs(event.source_timestamp,
                                            timestamp_to_sbs),
        'payload': _optional_to_sbs(event.payload, event_payload_to_sbs)}


def event_from_sbs(data: sbs.Data) -> Event:
    """Create new Event based on SBS data"""
    return Event(
        event_id=_event_id_from_sbs(data['id']),
        event_type=data['type'],
        timestamp=timestamp_from_sbs(data['timestamp']),
        source_timestamp=_optional_from_sbs(data['sourceTimestamp'],
                                            timestamp_from_sbs),
        payload=_optional_from_sbs(data['payload'], event_payload_from_sbs))


def register_event_to_sbs(event: RegisterEvent) -> sbs.Data:
    """Convert RegisterEvent to SBS data"""
    return {
        'type': event.event_type,
        'sourceTimestamp': _optional_to_sbs(event.source_timestamp,
                                            timestamp_to_sbs),
        'payload': _optional_to_sbs(event.payload, event_payload_to_sbs)}


def register_event_from_sbs(data: sbs.Data) -> RegisterEvent:
    """Create new RegisterEvent based on SBS data"""
    return RegisterEvent(
        event_type=data['type'],
        source_timestamp=_optional_from_sbs(data['sourceTimestamp'],
                                            timestamp_from_sbs),
        payload=_optional_from_sbs(data['payload'], event_payload_from_sbs))


def query_to_sbs(query: QueryData) -> sbs.Data:
    """Convert QueryData to SBS data"""
    return {
        'ids': _optional_to_sbs(query.event_ids, lambda ids: [
            _event_id_to_sbs(i) for i in ids]),
        'types': _optional_to_sbs(query.event_types),
        'tFrom': _optional_to_sbs(query.t_from, timestamp_to_sbs),
        'tTo': _optional_to_sbs(query.t_to, timestamp_to_sbs),
        'sourceTFrom': _optional_to_sbs(query.source_t_from, timestamp_to_sbs),
        'sourceTTo': _optional_to_sbs(query.source_t_to, timestamp_to_sbs),
        'payload': _optional_to_sbs(query.payload, event_payload_to_sbs),
        'order': {Order.DESCENDING: ('descending', None),
                  Order.ASCENDING: ('ascending', None)}[query.order],
        'orderBy': {OrderBy.TIMESTAMP: ('timestamp', None),
                    OrderBy.SOURCE_TIMESTAMP: ('sourceTimestamp', None)
                    }[query.order_by],
        'uniqueType': query.unique_type,
        'maxResults': _optional_to_sbs(query.max_results)}


def query_from_sbs(data: sbs.Data) -> QueryData:
    """Create new QueryData based on SBS data"""
    return QueryData(
        event_ids=_optional_from_sbs(data['ids'], lambda ids: [
            _event_id_from_sbs(i) for i in ids]),
        event_types=_optional_from_sbs(data['types']),
        t_from=_optional_from_sbs(data['tFrom'], timestamp_from_sbs),
        t_to=_optional_from_sbs(data['tTo'], timestamp_from_sbs),
        source_t_from=_optional_from_sbs(data['sourceTFrom'],
                                         timestamp_from_sbs),
        source_t_to=_optional_from_sbs(data['sourceTTo'], timestamp_from_sbs),
        payload=_optional_from_sbs(data['payload'], event_payload_from_sbs),
        order={'descending': Order.DESCENDING,
               'ascending': Order.ASCENDING}[data['order'][0]],
        order_by={'timestamp': OrderBy.TIMESTAMP,
                  'sourceTimestamp': OrderBy.SOURCE_TIMESTAMP
                  }[data['orderBy'][0]],
        unique_type=data['uniqueType'],
        max_results=_optional_from_sbs(data['maxResults']))


def event_payload_to_sbs(payload: EventPayload) -> sbs.Data:
    """Convert EventPayload to SBS data"""
    if payload.type == EventPayloadType.BINARY:
        return 'binary', payload.data

    if payload.type == EventPayloadType.JSON:
        return 'json', json.encode(payload.data)

    if payload.type == EventPayloadType.SBS:
        return 'sbs', _sbs_data_to_sbs(payload.data)

    raise ValueError('unsupported payload type')


def event_payload_from_sbs(data: sbs.Data) -> EventPayload:
    """Create new EventPayload based on SBS data"""
    data_type, data_data = data

    if data_type == 'binary':
        return EventPayload(type=EventPayloadType.BINARY,
                            data=data_data)

    if data_type == 'json':
        return EventPayload(type=EventPayloadType.JSON,
                            data=json.decode(data_data))

    if data_type == 'sbs':
        return EventPayload(type=EventPayloadType.SBS,
                            data=_sbs_data_from_sbs(data_data))

    raise ValueError('unsupported payload type')


def _event_id_to_sbs(event_id):
    return {'server': event_id.server,
            'instance': event_id.instance}


def _event_id_from_sbs(data):
    return EventId(server=data['server'],
                   instance=data['instance'])


def _sbs_data_to_sbs(data):
    return {'module': _optional_to_sbs(data.module),
            'type': data.type,
            'data': data.data}


def _sbs_data_from_sbs(data):
    return SbsData(module=_optional_from_sbs(data['module']),
                   type=data['type'],
                   data=data['data'])


def _optional_to_sbs(value, fn=lambda i: i):
    return ('Just', fn(value)) if value is not None else ('Nothing', None)


def _optional_from_sbs(data, fn=lambda i: i):
    return fn(data[1]) if data[0] == 'Just' else None
