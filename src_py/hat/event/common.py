"""Common functionality shared between clients and event server"""

from pathlib import Path
import datetime
import enum
import struct
import typing

from hat import chatter
from hat import json
from hat import sbs
from hat import util
import hat.monitor.common


package_path = Path(__file__).parent

json_schema_repo = json.SchemaRepository(
    json.json_schema_repo,
    hat.monitor.common.json_schema_repo,
    json.SchemaRepository.from_json(package_path / 'json_schema_repo.json'))

sbs_repo = sbs.Repository(
    chatter.sbs_repo,
    sbs.Repository.from_json(package_path / 'sbs_repo.json'))


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


EventId = util.namedtuple(
    'EventId',
    ['server', 'int: server identifier'],
    ['instance', 'int: event instance identifier'])


EventType = typing.List[str]
"""Event type"""


EventPayload = util.namedtuple(
    'EventPayload',
    ['type', 'EventPayloadType: payload type'],
    ['data', 'Union[bytes,json.Data,SbsData]: data'])


SbsData = util.namedtuple(
    'SbsData',
    ['module', "Optional[str]: SBS module name"],
    ['type', "str: SBS type name"],
    ['data', "bytes: data"])


Event = util.namedtuple(
    'Event',
    ['event_id', 'EventId: event identifier'],
    ['event_type', 'EventType: event type'],
    ['timestamp', 'Timestamp: timestamp'],
    ['source_timestamp', 'Optional[Timestamp]: source timestamp'],
    ['payload', 'Optional[EventPayload]: payload'])


RegisterEvent = util.namedtuple(
    'RegisterEvent',
    ['event_type', 'EventType: event type'],
    ['source_timestamp', 'Optional[Timestamp]: source timestamp'],
    ['payload', 'Optional[EventPayload]: payload'])


QueryData = util.namedtuple(
    'QueryData',
    ['event_ids', 'Optional[List[EventId]]: event identifiers', None],
    ['event_types', 'Optional[List[EventType]]: event types', None],
    ['t_from', 'Optional[Timestamp]: timestamp from', None],
    ['t_to', 'Optional[Timestamp]: timestamp to', None],
    ['source_t_from', 'Optional[Timestamp]', None],
    ['source_t_to', 'Optional[Timestamp]', None],
    ['payload', 'Optional[EventPayload]: payload', None],
    ['order', 'Order: order', Order.DESCENDING],
    ['order_by', 'OrderBy: order by', OrderBy.TIMESTAMP],
    ['unique_type', 'bool: unique type flag', False],
    ['max_results', 'Optional[int]: maximum results', None])


def matches_query_type(event_type, query_type):
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

    Args:
        event_type (EventType): event type
        query_type (EventType): query type

    Returns:
        bool: true if matches

    """
    if not event_type:
        if not query_type or query_type[0] == '*':
            return True
        else:
            return False
    if not query_type:
        return False
    if query_type[0] == '*':
        return True
    elif query_type[0] == '?' or query_type[0] == event_type[0]:
        return matches_query_type(event_type[1:], query_type[1:])
    return False


class SubscriptionRegistry:
    """Registry of event type subscriptions

    A tree-like collection that maps event types to hashable values. A map
    between an event type and a value is called a subscription. Registry
    enables finding all values that are subscribed to some event type. Each
    value can be subscribed to multiple event types.

    When adding a value to the registry, its subscriptions are specified by
    a query type. It can be the same as an event type, but also contain
    '?' and '*' wildcard subtypes. Value is subscribed to all event types that
    match the given query type. For more details on matching see
    :func:`matches_query_type`.

    When a value is removed from the registry, all its subscriptions are also
    removed.

    """
    _SubscriptionTree = util.namedtuple(
        '_SubscriptionTree', 'subtypes', 'values')

    def __init__(self):
        self._subscriptions = SubscriptionRegistry._SubscriptionTree(
            subtypes={}, values=set())

    def add(self, value, query_type):
        """Add and subscribe value

        Adds value to the registry and subscribes it to all event types that
        match query type. If value is already in the registry, new
        subscriptions will be added to previous.

        Args:
            value (Hashable): value
            query_type (EventType): query type
        """

        def recursive_add(tree, query_type):
            if not query_type:
                tree.values.add(value)
                return
            if query_type[0] not in tree.subtypes:
                tree.subtypes[query_type[0]] = \
                    SubscriptionRegistry._SubscriptionTree(
                        subtypes={}, values=set())
            recursive_add(tree.subtypes[query_type[0]], query_type[1:])

        recursive_add(self._subscriptions, query_type)

    def remove(self, value):
        """Remove and unsubscribe value

        Removes value from the registry with all its subscriptions.

        Args:
            value (Hashable): value
        """

        def recursive_remove(tree):
            if value in tree.values:
                tree.values.remove(value)
            for subtree in tree.subtypes.values():
                recursive_remove(subtree)

        recursive_remove(self._subscriptions)

    def find(self, event_type):
        """Find subscribed values

        Finds and returns all values that are subscribed to event type.

        Args:
            event_type (EventType): event type

        Returns:
            Set[Hashable]: values subscribed to event type
        """

        def recursive_find(tree, event_type):
            if not tree:
                return set()
            temp = tree.subtypes.get('*', None)
            values = set(temp.values) if temp else set()
            if event_type:
                values.update(recursive_find(
                    tree.subtypes.get('?'), event_type[1:]))
                values.update(recursive_find(
                    tree.subtypes.get(event_type[0]), event_type[1:]))
            else:
                values.update(tree.values)
            return values

        return recursive_find(self._subscriptions, event_type)


class Timestamp(util.namedtuple(
        'Timestamp',
        ['s', 'int: seconds since 1970-01-01'],
        ['us', 'int: microseconds added to timestamp defined by seconds'])):

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
        return hash(timestamp_to_bytes(self))


def timestamp_to_bytes(t):
    """Convert timestamp to 96 bit representation

    Bits 0 - 63 are big endian two's complement encoded :attr:`Timestamp.s` and
    bits 64 - 95 are big endian two's complement encoded :attr:`Timestamp.us`.

    Args:
        t (Timestamp): timestamp

    Returns:
        bytes

    """
    return struct.pack(">QI", t.s + (1 << 63), t.us)


def timestamp_from_bytes(data):
    """Create new timestamp from 96 bit representation

    Bytes representation is same as defined for :func:`timestamp_to_bytes`

    Args:
        data (bytes): 96 bit timestamp

    Returns:
        Timestamp: timestamp

    """
    s, us = struct.unpack(">QI", data)
    return Timestamp(int(s - (1 << 63)), int(us))


def timestamp_to_float(t):
    """Convert timestamp to floating number of seconds since 1970-01-01 UTC

    For precise serialization see :func:`timestamp_to_bytes` /
    :func:`timestamp_from_bytes`

    Args:
        t (Timestamp): timestamp

    Returns:
        float: timestamp

    """
    return t.s + t.us * 1E-6


def timestamp_from_float(ts):
    """Create new timestamp from floating number of seconds since 1970-01-01
    UTC

    For precise serialization see :func:`timestamp_to_bytes` /
    :func:`timestamp_from_bytes`

    Args:
        ts (float): seconds since 1970-01-01

    Returns:
        Timestamp: timestamp

    """
    s = int(ts)
    if ts < 0:
        s = s - 1
    us = round((ts - s) * 1E6)
    if us == 1000000:
        return Timestamp(s + 1, 0)
    else:
        return Timestamp(s, us)


def timestamp_to_datetime(t):
    """Convert timestamp to datetime

    For precise serialization see :func:`timestamp_to_bytes` /
    :func:`timestamp_from_bytes`

    Args:
        t (Timestamp): timestamp

    Returns:
        datetime.datetime: datetime (representing utc time)

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


def timestamp_from_datetime(dt):
    """Create new timestamp from datetime

    If `tzinfo` is not set, it is assumed that provided datetime represents
    utc time.

    For precise serialization see :func:`timestamp_to_bytes` /
    :func:`timestamp_from_bytes`

    Args:
        dt (datetime.datetime): datetime

    Returns:
        Timestamp: timestamp

    """
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    s = int(dt.timestamp())
    if dt.timestamp() < 0:
        s = s - 1
    return Timestamp(s=s, us=dt.microsecond)


def timestamp_to_sbs(t):
    """Convert timestamp to SBS data

    Args:
        t (Timestamp): timestamp

    Returns:
        hat.sbs.Data: SBS data

    """
    return {'s': t.s, 'us': t.us}


def timestamp_from_sbs(data):
    """Create new timestamp from SBS data

    Args:
        data (hat.sbs.Data): SBS data

    Returns:
        Timestamp: timestamp

    """
    return Timestamp(s=data['s'], us=data['us'])


def now():
    """Create new timestamp representing current time

    Returns:
        Timestamp: timestamp

    """
    return timestamp_from_datetime(
        datetime.datetime.now(datetime.timezone.utc))


def event_to_sbs(event):
    """Convert Event to SBS data

    Args:
        event (Event): event

    Returns:
        hat.sbs.Data

    """
    return {
        'id': _event_id_to_sbs(event.event_id),
        'type': event.event_type,
        'timestamp': timestamp_to_sbs(event.timestamp),
        'sourceTimestamp': _optional_to_sbs(event.source_timestamp,
                                            timestamp_to_sbs),
        'payload': _optional_to_sbs(event.payload, event_payload_to_sbs)}


def event_from_sbs(data):
    """Create new Event based on SBS data

    Args:
        data (hat.sbs.Data): SBS data

    Returns:
        Event

    """
    return Event(
        event_id=_event_id_from_sbs(data['id']),
        event_type=data['type'],
        timestamp=timestamp_from_sbs(data['timestamp']),
        source_timestamp=_optional_from_sbs(data['sourceTimestamp'],
                                            timestamp_from_sbs),
        payload=_optional_from_sbs(data['payload'], event_payload_from_sbs))


def register_event_to_sbs(event):
    """Convert RegisterEvent to SBS data

    Args:
        event (RegisterEvent): register event

    Returns:
        hat.sbs.Data

    """
    return {
        'type': event.event_type,
        'sourceTimestamp': _optional_to_sbs(event.source_timestamp,
                                            timestamp_to_sbs),
        'payload': _optional_to_sbs(event.payload, event_payload_to_sbs)}


def register_event_from_sbs(data):
    """Create new RegisterEvent based on SBS data

    Args:
        data (hat.sbs.Data): SBS data

    Returns:
        RegisterEvent

    """
    return RegisterEvent(
        event_type=data['type'],
        source_timestamp=_optional_from_sbs(data['sourceTimestamp'],
                                            timestamp_from_sbs),
        payload=_optional_from_sbs(data['payload'], event_payload_from_sbs))


def query_to_sbs(query):
    """Convert QueryData to SBS data

    Args:
        query (QueryData): query data

    Returns:
        hat.sbs.Data

    """
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


def query_from_sbs(data):
    """Create new QueryData based on SBS data

    Args:
        data (hat.sbs.Data): SBS data

    Returns:
        QueryData

    """
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


def event_payload_to_sbs(payload):
    """Convert EventPayload to SBS data

    Args:
        payload (EventPayload): event payload

    Returns:
        hat.sbs.Data

    """
    return {
        EventPayloadType.BINARY: lambda: ('binary', payload.data),
        EventPayloadType.JSON: lambda: ('json', json.encode(payload.data)),
        EventPayloadType.SBS: lambda: ('sbs', _sbs_data_to_sbs(payload.data))
    }[payload.type]()


def event_payload_from_sbs(data):
    """Create new EventPayload based on SBS data

    Args:
        data (hat.sbs.Data): SBS data

    Returns:
        EventPayload

    """
    return {
        'binary': lambda: EventPayload(type=EventPayloadType.BINARY,
                                       data=data[1]),
        'json': lambda: EventPayload(type=EventPayloadType.JSON,
                                     data=json.decode(data[1])),
        'sbs': lambda: EventPayload(type=EventPayloadType.SBS,
                                    data=_sbs_data_from_sbs(data[1]))
    }[data[0]]()


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
