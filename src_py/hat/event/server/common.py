"""Common event server structures and functionalty"""

import abc
import enum
import itertools
import typing

from hat import aio
from hat import json
from hat.event.common import (EventId,
                              EventType,
                              Timestamp,
                              EventPayload,
                              Event,
                              QueryData)
from hat.event.common import *  # NOQA


SourceType = enum.Enum('SourceType', [
    'COMMUNICATION',
    'MODULE'])


class Source(typing.NamedTuple):
    type: SourceType
    name: typing.Optional[str]
    id: int


class ProcessEvent(typing.NamedTuple):
    event_id: EventId
    source: Source
    event_type: EventType
    source_timestamp: typing.Optional[Timestamp]
    payload: typing.Optional[EventPayload]


class SessionChanges(typing.NamedTuple):
    new: typing.List[ProcessEvent]
    """new process events"""
    deleted: typing.List[ProcessEvent]
    """deleted process events"""


BackendConf = json.Data
"""Backend configuration"""

CreateBackend = typing.Callable[[BackendConf], typing.Awaitable['Backend']]
"""Create backend callable"""


class Backend(aio.Resource):
    """Backend ABC

    Backend is implemented as python module which is dynamically imported.
    It is expected that this module implements:

    * json_schema_id (typing.Optional[str]): JSON schema id
    * json_schema_repo (typing.Optional[json.SchemaRepository]):
        JSON schema repo
    * create (CreateBackend): create new backend instance

    If module defines JSON schema repositoy and JSON schema id, JSON schema
    repository will be used for additional validation of backend configuration
    with JSON schema id.

    """

    @abc.abstractmethod
    async def get_last_event_id(self,
                                server_id: int
                                ) -> EventId:
        """Get last registered event id associated with server id"""

    @abc.abstractmethod
    async def register(self, events: typing.List[Event]):
        """Register events

        .. todo::

            do we need list of success flags as result?

        """

    @abc.abstractmethod
    async def query(self,
                    data: QueryData
                    ) -> typing.List[Event]:
        """Query events"""


class EventTypeRegistryStorage(abc.ABC):
    """EventTypeRegistry storage ABC

    This interface specifies perzistent storage used by `EventTypeRegistry`.

    """

    @abc.abstractmethod
    async def get_event_type_mappings(self) -> typing.Dict[int, EventType]:
        """Get all event type mappings

        Returned dict has event type ids as keys and associated event types as
        values.

        """

    @abc.abstractmethod
    async def add_event_type_mappings(self,
                                      mappings: typing.Dict[int, EventType]):
        """Add new event type mappings

        `mappings` dict has event type ids as keys and associated event types
        as values. New mappings are appended to allready existing mappings.

        """


ModuleConf = json.Data

CreateModule = typing.Callable[
    [ModuleConf, 'hat.event.module_engine.ModuleEngine'],  # NOQA
    typing.Awaitable['Module']]


class Module(aio.Resource):
    """Module ABC

    Module is implemented as python module which is dynamically imported.
    It is expected that this module implements:

        * json_schema_id (typing.Optional[str]): JSON schema id
        * json_schema_repo (typing.Optional[json.SchemaRepository]):
            JSON schema repo
        * create (CreateModule): create new module instance

    If module defines JSON schema repositoy and JSON schema id, JSON schema
    repository will be used for additional validation of module configuration
    with JSON schema id.

    Module's `subscriptions` are constant during module's lifetime.

    """

    @property
    @abc.abstractmethod
    def subscriptions(self) -> typing.List[EventType]:
        """Subscribed event types filter"""

    @abc.abstractmethod
    async def create_session(self) -> 'ModuleSession':
        """Create new module session"""


class ModuleSession(aio.Resource):

    @abc.abstractmethod
    async def process(self,
                      changes: SessionChanges
                      ) -> SessionChanges:
        """Process session changes

        Changes include only process events which are matched by modules
        subscription filter.

        Single module session process is always called sequentially.

        """


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
    `hat.event.common.matches_query_type` function.

    When a value is removed from the registry, all its subscriptions are also
    removed.

    """

    def __init__(self):
        self._subscriptions = _SubscriptionTree(subtypes={}, values=set())

    def add(self,
            value: typing.Hashable,
            query_type: EventType):
        """Add and subscribe value

        Adds value to the registry and subscribes it to all event types that
        match query type. If value is already in the registry, new
        subscriptions will be added to previous.

        """

        def recursive_add(tree, query_type):
            if not query_type:
                tree.values.add(value)
                return
            if query_type[0] not in tree.subtypes:
                tree.subtypes[query_type[0]] = _SubscriptionTree(
                    subtypes={}, values=set())
            recursive_add(tree.subtypes[query_type[0]], query_type[1:])

        recursive_add(self._subscriptions, query_type)

    def remove(self, value: typing.Hashable):
        """Remove and unsubscribe value

        Removes value from the registry with all its subscriptions.

        """

        def recursive_remove(tree):
            if value in tree.values:
                tree.values.remove(value)
            for subtree in tree.subtypes.values():
                recursive_remove(subtree)

        recursive_remove(self._subscriptions)

    def find(self,
             event_type: EventType
             ) -> typing.Set[typing.Hashable]:
        """Find subscribed values

        Finds and returns all values that are subscribed to event type.

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


async def create_event_type_registry(storage: EventTypeRegistryStorage
                                     ) -> 'EventTypeRegistry':
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

    def get_event_type(self, identifier: int):
        """Get event types associated with identifier"""
        return self._mappings[identifier]

    async def get_identifiers(self,
                              event_types: typing.Iterable[EventType]
                              ) -> typing.List[int]:
        """Get identifiers associated with event types

        If event type doesn't have previously defined identifier, new one is
        created and stored in storage.

        """
        new_mappings = {}
        ids = [self._get_node(self._nodes, [], event_type, new_mappings).id
               for event_type in event_types]
        if new_mappings:
            await self._storage.add_event_type_mappings(new_mappings)
        return ids

    def query_identifiers(self,
                          event_types: EventType
                          ) -> typing.Set[int]:
        """Get identifiers matching event type queries"""
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


class _SubscriptionTree(typing.NamedTuple):
    subtypes: typing.Dict
    values: typing.Set[typing.Hashable]


class _EventTypeRegistryNode(typing.NamedTuple):
    id: int
    nodes: typing.Dict[str, '_EventTypeRegistryNode']
