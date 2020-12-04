"""Common event server structures and functionalty"""

import abc
import enum
import typing
import itertools

from hat import json
from hat import util
from hat.event.common import *  # NOQA


SourceType = enum.Enum('SourceType', [
    'COMMUNICATION',
    'MODULE'])


Source = util.namedtuple(
    'Source',
    ['type', 'SourceType: source type'],
    ['name', 'Optional[str]: source name (module name)'],
    ['id', 'int: identifier'])


ProcessEvent = util.namedtuple(
    'ProcessEvent',
    ['event_id', 'EventId: event identifier'],
    ['source', 'Source: source'],
    ['event_type', 'EventType: event type'],
    ['source_timestamp', 'Optional[Timestamp]: source timestamp'],
    ['payload', 'Optional[EventPayload]: payload'])


SessionChanges = util.namedtuple(
    'SessionChanges',
    ['new', 'List[ProcessEvent]: new register events'],
    ['deleted', 'List[ProcessEvent]: deleted register events'])


BackendConf = json.Data
"""Backend configuration"""

CreateBackend = typing.Callable[[BackendConf], typing.Awaitable['Backend']]
"""Create backend callable"""


class Backend(abc.ABC):
    """Backend ABC

    Backend is implemented as python module which is dynamically imported.
    It is expected that this module implements:

    * json_schema_id (Optional[str]): JSON schema id
    * create (CreateBackend): create new backend instance

    If module defines JSON schema id, it will be used for aditional
    validation of backend's configuration.

    """

    @property
    @abc.abstractmethod
    def closed(self):
        """asyncio.Future: closed future"""

    @abc.abstractmethod
    async def async_close(self):
        """Async close"""

    async def get_last_event_id(self, server_id):
        """Get last registered event id associated with server id

        Args:
            server_id (int): server identifier

        Returns:
            common.EventId

        """

    @abc.abstractmethod
    async def register(self, events):
        """Register events

        .. todo::

            do we need list of success flags as result?

        Args:
            events (List[Event]): events

        """

    @abc.abstractmethod
    async def query(self, data):
        """Query events

        Args:
            data (QueryData): query data

        Returns:
            List[Event]

        """


class EventTypeRegistryStorage(abc.ABC):
    """EventTypeRegistry storage ABC

    This interface specifies perzistent storage used by
    :class:`EventTypeRegistry`.

    """

    @abc.abstractmethod
    async def get_event_type_mappings(self):
        """Get all event type mappings

        Returned dict has event type ids as keys and associated event types as
        values.

        Returns:
            Dict[int,EventType]

        """

    @abc.abstractmethod
    async def add_event_type_mappings(self, mappings):
        """Add new event type mappings

        `mappings` dict has event type ids as keys and associated event types
        as values. New mappings are appended to allready existing mappings.

        Args:
            mappings (Dict[int,EventType]): event type mappings

        """


ModuleConf = json.Data

CreateModule = typing.Callable[
    [ModuleConf, 'hat.event.module_engine.ModuleEngine'],  # NOQA
    typing.Awaitable['Module']]


class Module(abc.ABC):
    """Module ABC

    Module is implemented as python module which is dynamically imported.
    It is expected that this module implements:

        * json_schema_id (Optional[str]): JSON schema id
        * create (CreateModule): create new module instance

    If module defines JSON schema id, it will be used for aditional
    validation of module's configuration.

    Module's `subscriptions` are constant during module's lifetime.

    """

    @property
    @abc.abstractmethod
    def subscriptions(self):
        """List[EventType]: subscribed event types filter"""

    @property
    @abc.abstractmethod
    def closed(self):
        """asyncio.Future: closed future"""

    @abc.abstractmethod
    async def async_close(self):
        """Async close"""

    @abc.abstractmethod
    async def create_session(self):
        """Create new module session

        Returns:
            ModuleSession

        """


class ModuleSession(abc.ABC):

    @property
    @abc.abstractmethod
    def closed(self):
        """asyncio.Future: closed future"""

    @abc.abstractmethod
    async def async_close(self, events):
        """Async close

        This method is called with all registered session events without
        applying subscription filter.

        .. todo::

            do we wan't to apply subscription filter

        Args:
            events (List[Event]): registered events

        """

    @abc.abstractmethod
    async def process(self, changes):
        """Process session changes

        Changes include only process events which are matched by modules
        subscription filter.

        Single module session process is always called sequentially.

        Args:
            changes (SessionChanges): session changes

        Returns:
            SessionChanges

        """


async def create_event_type_registry(storage):
    """Create EventTypeRegistry instance

    This class can be used for simple mapping between event types and unique
    numerical event type identifiers.

    """
    registry = EventTypeRegistry()
    registry._storage = storage
    registry._mappings = await storage.get_event_type_mappings()
    registry._last_id = max(registry._mappings.keys(), default=1)
    registry._nodes = {}

    new_mappings = {}
    reverse_mappings = {tuple(v): k for k, v in registry._mappings.items()}
    for event_type in list(registry._mappings.values()):
        registry._init_node(reverse_mappings, registry._nodes, [], event_type,
                            new_mappings)
    if new_mappings:
        await storage.add_event_type_mappings(new_mappings)

    return registry


class EventTypeRegistry:

    def get_event_type(self, identifier):
        """Get event types associated with identifier"""
        return self._mappings[identifier]

    async def get_identifiers(self, event_types):
        """Get identifiers associated with event types

        If event type doesn't have previously defined identifier, new one is
        created and stored in storage.

        Args:
            event_types (Iterable[EventType]): event types

        Returns:
            List[int]

        """
        new_mappings = {}
        ids = [self._get_node(self._nodes, [], event_type, new_mappings).id
               for event_type in event_types]
        if new_mappings:
            await self._storage.add_event_type_mappings(new_mappings)
        return ids

    def query_identifiers(self, event_types):
        """Get identifiers matching event type queries

        Args:
            event_types (EventType): event type queries

        Returns:
            Set[int]

        """
        nodes = itertools.chain.from_iterable(
            self._query_nodes(self._nodes, event_type)
            for event_type in event_types)
        return {node.id for node in nodes}

    def _init_node(self, reverse_mappings, nodes, event_type_prefix,
                   event_type_suffix, new_mappings):
        segment = event_type_suffix[0]
        node = nodes.get(segment)
        next_event_type_prefix = [*event_type_prefix, segment]
        next_event_type_suffix = event_type_suffix[1:]
        if not node:
            node_id = reverse_mappings.get(tuple(next_event_type_prefix))
            if node_id is None:
                self._last_id += 1
                node = _EventTypeRegistryNode(id=self._last_id, nodes={})
                nodes[segment] = node
                self._mappings[node.id] = next_event_type_prefix
                new_mappings[node.id] = next_event_type_prefix
            else:
                node = _EventTypeRegistryNode(id=node_id, nodes={})
                nodes[segment] = node
        if not next_event_type_suffix:
            return node
        return self._init_node(reverse_mappings, node.nodes,
                               next_event_type_prefix, next_event_type_suffix,
                               new_mappings)

    def _get_node(self, nodes, event_type_prefix, event_type_suffix,
                  new_mappings):
        segment = event_type_suffix[0]
        node = nodes.get(segment)
        next_event_type_prefix = [*event_type_prefix, segment]
        next_event_type_suffix = event_type_suffix[1:]
        if not node:
            self._last_id += 1
            node = _EventTypeRegistryNode(id=self._last_id, nodes={})
            nodes[segment] = node
            self._mappings[node.id] = next_event_type_prefix
            new_mappings[node.id] = next_event_type_prefix
        if not next_event_type_suffix:
            return node
        return self._get_node(node.nodes, next_event_type_prefix,
                              next_event_type_suffix, new_mappings)

    def _query_nodes(self, nodes, event_type):
        if not event_type:
            return
        segment, event_subtype = event_type[0], event_type[1:]
        if not event_subtype:
            if segment == '*':
                for subnode in nodes.values():
                    yield subnode
                    yield from self._query_nodes(subnode.nodes, ['*'])
            elif segment == '?':
                for subnode in nodes.values():
                    yield subnode
            else:
                subnode = nodes.get(segment)
                if subnode:
                    yield subnode
        else:
            if segment == '?':
                for subnode in nodes.values():
                    if event_subtype == ['*']:
                        yield subnode
                    yield from self._query_nodes(subnode.nodes, event_subtype)
            else:
                subnode = nodes.get(segment)
                if subnode:
                    if event_subtype == ['*']:
                        yield subnode
                    yield from self._query_nodes(subnode.nodes, event_subtype)


_EventTypeRegistryNode = util.namedtuple(
    '_EventTypeRegistryNode',
    ['id', 'int'],
    ['nodes', 'Dict[str,_EventTypeRegistryNode]'])
