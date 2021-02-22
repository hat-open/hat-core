"""Common gateway interfaces"""

from pathlib import Path
import abc
import typing

from hat import aio
from hat import json
import hat.event.common
import hat.monitor.common


json_schema_repo: json.SchemaRepository = json.SchemaRepository(
    json.json_schema_repo,
    hat.monitor.common.json_schema_repo,
    json.SchemaRepository.from_json(Path(__file__).parent /
                                    'json_schema_repo.json'))
"""JSON schema repository"""

DeviceConf = json.Data
"""Device configuration"""

EventTypePrefix = hat.event.common.EventType
"""Event type prefix"""

CreateDevice = aio.AsyncCallable[
    [DeviceConf, 'DeviceEventClient', EventTypePrefix],
    'Device']
"""Create device callable"""


class Device(aio.Resource):
    """Device interface

    Device is implemented as python module which is dynamically imported.
    It is expected that this module implements:

        * device_type (str): device type identification
        * json_schema_id (Optional[str]): JSON schema id
        * json_schema_repo (Optional[json.SchemaRepository]): JSON schema repo
        * create (CreateDevice): creating new device instance

    If module defines JSON schema repositoy and JSON schema id, JSON schema
    repository will be used for additional validation of device configuration
    with JSON schema id.

    `create` is called with device configuration, appropriate instance of
    `DeviceEventClient` and event type prefix. Event type prefix is defined
    as [``gateway``, `<gateway_name>`, `<device_type>`, `<device_name>`].

    """


class DeviceEventClient(aio.Resource):
    """Device's event client interface"""

    @abc.abstractmethod
    async def receive(self) -> typing.List[hat.event.common.Event]:
        """Receive device events"""

    @abc.abstractmethod
    def register(self, events: typing.List[hat.event.common.RegisterEvent]):
        """Register device events"""

    @abc.abstractmethod
    async def register_with_response(self,
                                     events: typing.List[hat.event.common.RegisterEvent]  # NOQA
                                     ) -> typing.List[typing.Optional[hat.event.common.Event]]:  # NOQA
        """Register device events

        Each `RegisterEvent` from `events` is paired with results `Event` if
        new event was successfully created or `None` is new event could not be
        created.

        """

    @abc.abstractmethod
    async def query(self,
                    data: hat.event.common.QueryData
                    ) -> typing.List[hat.event.common.Event]:
        """Query device events from server"""
