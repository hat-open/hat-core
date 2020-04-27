"""Common gateway interfaces"""

import abc
import typing

from hat.util import json
import hat.event.common


DeviceConf = json.Data

EventTypePrefix = hat.event.common.EventType

CreateDevice = typing.Callable[
    [DeviceConf, 'DeviceEventClient', EventTypePrefix],
    typing.Awaitable['Device']]


class Device(abc.ABC):
    """Device interface

    Device is implemented as python module which is dynamically imported.
    It is expected that this module implements:

        * device_type (str): device type identification
        * json_schema_id (Optional[str]): JSON schema id
        * create (CreateDevice): creating new device instance

    If module defines JSON schema id, it will be used for aditional
    validation of device configuration.

    """

    @property
    @abc.abstractmethod
    def closed(self):
        """asyncio.Future: closed future"""

    @abc.abstractmethod
    async def async_close(self):
        """Async close"""


class DeviceEventClient(abc.ABC):
    """Device's event client interface"""

    @abc.abstractmethod
    async def receive(self):
        """Receive device events

        Returns:
            List[hat.event.common.Event]

        """

    @abc.abstractmethod
    def register(self, events):
        """Register device events

        Args:
            events (List[hat.event.common.RegisterEvent]): register events

        """

    @abc.abstractmethod
    async def register_with_response(self, events):
        """Register device events

        Each `DeviceRegisterEvent` from `events` is paired with results
        `DeviceEvent` if new event was successfuly created or `None` is new
        event could not be created.

        Args:
            events (List[hat.event.common.RegisterEvent]): register events

        Returns:
            List[Optional[hat.event.common.Event]]

        """

    @abc.abstractmethod
    async def query(self, data):
        """Query device events from server

        Args:
            data (hat.event.common.QueryData): query data

        Returns:
            List[hat.event.common.Event]

        """
