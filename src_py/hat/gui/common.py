"""Common GUI interfaces"""

from pathlib import Path
import abc
import typing

from hat import aio
from hat import json
from hat import util
import hat.event.common
import hat.monitor.common


json_schema_repo: json.SchemaRepository = json.SchemaRepository(
    json.json_schema_repo,
    hat.monitor.common.json_schema_repo,
    json.SchemaRepository.from_json(Path(__file__).parent /
                                    'json_schema_repo.json'))
"""JSON schema repository"""

AdapterConf = json.Data
"""Adapter configuration"""

CreateSubscription = aio.AsyncCallable[
    [AdapterConf],
    hat.event.common.Subscription]
"""Create subscription callable"""

CreateAdapter = aio.AsyncCallable[
    [AdapterConf, 'AdapterEventClient'],
    'Adapter']
"""Create adapter callable"""


class Adapter(aio.Resource):
    """Adapter interface

    Adapters are implemented as python modules which are dynamically imported.
    Each adapter instance has configuration which must include `module` -
    python module identifier. It is expected that this module implements:

        * json_schema_id (Optional[str]): JSON schema id
        * json_schema_repo (Optional[json.SchemaRepository]): JSON schema repo
        * create_subscription (CreateSubscription): create subscription
        * create_adapter (CreateAdapter): create new adapter instance

    If module defines JSON schema repositoy and JSON schema id, JSON schema
    repository will be used for additional validation of adapter configuration
    with JSON schema id.

    Subscription is used for filtering events that can be obtained
    by calling `AdapterEventClient.receive` method.

    `create_adapter` is called with adapter instance configuration and adapter
    event client.

    """

    @abc.abstractmethod
    async def create_session(self,
                             client: 'AdapterSessionClient'
                             ) -> 'AdapterSession':
        """Create new adapter session"""


class AdapterSession(aio.Resource):
    """Adapter's single client session"""


class AdapterSessionClient(aio.Resource):
    """Adapter's session client represents single juggler connection"""

    @property
    def user(self) -> str:
        """User identifier"""

    @property
    def roles(self) -> typing.List[str]:
        """User roles"""

    @property
    def local_data(self) -> json.Data:
        """JSON serializable local data"""

    @property
    def remote_data(self) -> json.Data:
        """JSON serializable remote data"""

    def register_change_cb(self,
                           cb: typing.Callable[[], None]
                           ) -> util.RegisterCallbackHandle:
        """Register remote data change callback"""

    def set_local_data(self, data: json.Data):
        """Set local data"""

    async def send(self, msg: json.Data):
        """Send message"""

    async def receive(self) -> json.Data:
        """Receive message"""


class AdapterEventClient(aio.Resource):
    """Adapters interface to event client"""

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
