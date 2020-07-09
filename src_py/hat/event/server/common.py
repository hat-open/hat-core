"""Common event server structures and functionalty"""

import abc
import enum
import typing

from hat import util
from hat.event.common import *  # NOQA
from hat.util import json


BackendEvent = util.namedtuple(
    'BackendEvent',
    ['event_id', 'EventId: event identifier'],
    ['event_type_id', 'int: event type'],
    ['timestamp', 'Timestamp: timestamp'],
    ['source_timestamp', 'Optional[Timestamp]: source timestamp'],
    ['payload', 'Optional[EventPayload]: payload'])


BackendQueryData = util.namedtuple(
    'BackendQueryData',
    ['event_ids', 'Optional[List[EventId]]: event identifiers', None],
    ['event_type_ids', 'Optional[List[int]]: event types', None],
    ['t_from', 'Optional[Timestamp]: timestamp from', None],
    ['t_to', 'Optional[Timestamp]: timestamp to', None],
    ['source_t_from', 'Optional[Timestamp]', None],
    ['source_t_to', 'Optional[Timestamp]', None],
    ['payload', 'Optional[EventPayload]: payload', None],
    ['order', 'Order: order', Order.DESCENDING],  # NOQA
    ['order_by', 'OrderBy: order by', OrderBy.TIMESTAMP],  # NOQA
    ['unique_type', 'bool: unique type flag', False],
    ['max_results', 'Optional[int]: maximum results', None])


SourceType = util.extend_enum_doc(enum.Enum('SourceType', [
    'COMMUNICATION',
    'MODULE']))


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

    async def get_event_type_id_mappings(self):
        """Get all event type id mappings

        Returned dict has event type ids as keys and associated event types as
        values.

        Returns:
            Dict[int,EventType]

        """

    async def add_event_type_id_mappings(self, mappings):
        """Add new event type id mappings

        `mappings` dict has event type ids as keys and associated event types
        as values. New mappings are appended to allready existing mappings.

        Args:
            mappings (Dict[int,EventType]): event type id mappings

        """

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
            events (List[BackendEvent]): events

        """

    @abc.abstractmethod
    async def query(self, data):
        """Query events

        Args:
            data (BackendQueryData): query data

        Returns:
            List[BackendEvent]

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
