"""Common event server structures and functionality"""

import abc
import enum
import typing

from hat import aio
from hat import json
from hat.event.common import (EventId,
                              EventType,
                              Timestamp,
                              EventPayload,
                              Event,
                              QueryData,
                              Subscription)
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

    If module defines JSON schema repository and JSON schema id, JSON schema
    repository will be used for additional validation of backend configuration
    with JSON schema id.

    """

    @abc.abstractmethod
    async def get_last_event_id(self,
                                server_id: int
                                ) -> EventId:
        """Get last registered event id associated with server id"""

    @abc.abstractmethod
    async def register(self,
                       events: typing.List[Event]
                       ) -> typing.List[typing.Optional[Event]]:
        """Register events"""

    @abc.abstractmethod
    async def query(self,
                    data: QueryData
                    ) -> typing.List[Event]:
        """Query events"""


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

    If module defines JSON schema repository and JSON schema id, JSON schema
    repository will be used for additional validation of module configuration
    with JSON schema id.

    Module's `subscription` is constant during module's lifetime.

    """

    @property
    @abc.abstractmethod
    def subscription(self) -> Subscription:
        """Subscribed event types filter"""

    @abc.abstractmethod
    async def create_session(self) -> 'ModuleSession':
        """Create new module session"""


class ModuleSession(aio.Resource):

    @abc.abstractmethod
    async def process(self,
                      events: typing.List[ProcessEvent]
                      ) -> typing.Iterable[ProcessEvent]:
        """Process new session process events

        Provided process events include only those which are matched by modules
        subscription filter.

        Processing of session process events can result in registration of
        new process events.

        Single module session process is always called sequentially.

        """
