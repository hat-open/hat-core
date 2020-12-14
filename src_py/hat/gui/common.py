from pathlib import Path
import abc
import typing

from hat import aio
from hat import json
import hat.monitor.common


json_schema_repo = json.SchemaRepository(
    json.json_schema_repo,
    hat.monitor.common.json_schema_repo,
    json.SchemaRepository.from_json(Path(__file__).parent /
                                    'json_schema_repo.json'))


AdapterConf = json.Data

CreateAdapter = typing.Callable[[AdapterConf, 'AdapterEventClient'],
                                typing.Awaitable['Adapter']]


class Adapter(aio.Resource):
    """Adapter interface

    Adapters are implemented as python modules which are dynamically imported.
    Each adapter instance has configuration which must include `module` -
    python module identifier. It is expected that this module implements:

        * json_schema_id (Optional[str]): JSON schema id
        * json_schema_repo (Optional[json.SchemaRepository]): JSON schema repo
        * event_type_prefix (Optional[hat.event.common.EventType]):
            event type prefix
        * create (Callable[[json.Data,AdapterEventClient],Adapter]):
            coroutine responsible for creating adapter

    If module defines JSON schema repositoy and JSON schema id, JSON schema
    repository will be used for additional validation of adapter configuration
    with JSON schema id.

    Event type prefix is used for filtering events that can be obtained
    by calling :meth:`AdapterEventClient.receive`. It can not contain
    subscription wildchars. If it is None, adapter will not receive any
    event notifications.

    `create` coroutine is called with adapter instance configuration and
    adapter event client.

    """

    @abc.abstractmethod
    async def create_session(self, client):
        """Create new adapter session

        Args:
            client (AdapterSessionClient): adapter session client

        Returns:
            AdapterSession

        """


class AdapterSession(aio.Resource):
    """Adapter's single client session"""


class AdapterSessionClient(abc.ABC):
    """Adapter's session client represents single juggler connection"""

    @property
    def user(self):
        """str: user identifier"""

    @property
    def roles(self):
        """List[str]: user roles"""

    @property
    def local_data(self):
        """json.Data: json serializable local data"""

    @property
    def remote_data(self):
        """json.Data: json serializable remote data"""

    def register_change_cb(self, cb):
        """Register remote data change callback

        Args:
            cb (Callable[[],None]): change callback

        Returns:
            util.RegisterCallbackHandle

        """

    def set_local_data(self, data):
        """Set local data

        Args:
            data (json.Data): json serializable local data

        """

    async def send(self, msg):
        """Send message

        Args:
            msg (json.Data): json serializable message

        """

    async def receive(self):
        """Receive message

        Returns:
            json.Data: json serializable message

        """


class AdapterEventClient(abc.ABC):
    """Adapters interface to event client

    Received event notifications include only those that start with
    `event_type_prefix` as defined by adapter implementation.

    """

    async def receive(self):
        """See :meth:`hat.event.client.Client.receive`"""

    def register(self, events):
        """See :meth:`hat.event.client.Client.register`"""

    async def register_with_response(self, events):
        """See :meth:`hat.event.client.Client.register_with_response`"""

    async def query(self, data):
        """See :meth:`hat.event.client.Client.query`"""
