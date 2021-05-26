import logging
import typing

from hat import aio
from hat.gateway import common
import hat.event.common


mlog = logging.getLogger(__name__)


class RemoteDeviceEnableReq(typing.NamedTuple):
    device_id: int
    enable: bool


class RemoteDeviceWriteReq(typing.NamedTuple):
    device_id: int
    data_name: str
    request_id: str
    value: int


Request = typing.Union[RemoteDeviceEnableReq,
                       RemoteDeviceWriteReq]


class StatusRes(typing.NamedTuple):
    status: str


class RemoteDeviceStatusRes(typing.NamedTuple):
    device_id: int
    status: str


class RemoteDeviceReadRes(typing.NamedTuple):
    device_id: int
    data_name: str
    result: str
    value: typing.Optional[int]
    cause: typing.Optional[str]


class RemoteDeviceWriteRes(typing.NamedTuple):
    device_id: int
    data_name: str
    request_id: str
    result: str


Response = typing.Union[StatusRes,
                        RemoteDeviceStatusRes,
                        RemoteDeviceReadRes,
                        RemoteDeviceWriteRes]


class EventClientProxy(aio.Resource):

    def __init__(self,
                 event_client: common.DeviceEventClient,
                 event_type_prefix: common.EventTypePrefix):
        self._event_client = event_client
        self._event_type_prefix = event_type_prefix
        self._async_group = event_client.async_group.create_subgroup()
        self._read_queue = aio.Queue()
        self.async_group.spawn(self._read_loop)

    @property
    def async_group(self) -> aio.Group:
        return self._async_group

    def write(self, responses: typing.List[Response]):
        register_events = [
            _response_to_register_event(self._event_type_prefix, i)
            for i in responses]
        self._event_client.register(register_events)

    async def read(self) -> Request:
        try:
            return await self._read_queue.get()

        except aio.QueueClosedError:
            raise ConnectionError()

    async def _read_loop(self):
        try:
            mlog.debug('starting read loop')
            while True:
                events = await self._event_client.receive()
                mlog.debug('received %s events', len(events))

                for event in events:
                    try:
                        req = _request_from_event(event)
                        self._read_queue.put_nowait(req)

                    except Exception as e:
                        mlog.info('received invalid event: %s', e, exc_info=e)

        except ConnectionError:
            mlog.debug('connection closed')

        except Exception as e:
            mlog.error('read loop error: %s', e, exc_info=e)

        finally:
            mlog.debug('closing read loop')
            self.close()
            self._read_queue.close()


def _request_from_event(event):
    event_type_suffix = event.event_type[5:]

    if event_type_suffix[0] != 'remote_device':
        raise Exception('unsupported event type')

    device_id = int(event_type_suffix[1])

    if event_type_suffix[2] == 'enable':
        enable = bool(event.payload.data)
        return RemoteDeviceEnableReq(device_id=device_id,
                                     enable=enable)

    if event_type_suffix[2] == 'write':
        data_name = event_type_suffix[3]
        request_id = event.payload.data['request_id']
        value = event.payload.data['value']
        return RemoteDeviceWriteReq(device_id=device_id,
                                    data_name=data_name,
                                    request_id=request_id,
                                    value=value)

    raise Exception('unsupported event type')


def _response_to_register_event(event_type_prefix, res):
    if isinstance(res, StatusRes):
        event_type = (*event_type_prefix, 'gateway', 'status')
        payload = res.status

    elif isinstance(res, RemoteDeviceStatusRes):
        event_type = (*event_type_prefix, 'gateway', 'remote_device',
                      str(res.device_id), 'status')
        payload = res.status

    elif isinstance(res, RemoteDeviceReadRes):
        event_type = (*event_type_prefix, 'gateway', 'remote_device',
                      str(res.device_id), 'read', res.data_name)
        payload = {'result': res.result}
        if res.value is not None:
            payload['value'] = res.value
        if res.cause is not None:
            payload['cause'] = res.cause

    elif isinstance(res, RemoteDeviceWriteRes):
        event_type = (*event_type_prefix, 'gateway', 'remote_device',
                      str(res.device_id), 'write', res.data_name)
        payload = {'request_id': res.request_id,
                   'result': res.result}

    else:
        raise ValueError('invalid response type')

    return hat.event.common.RegisterEvent(
        event_type=event_type,
        source_timestamp=None,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=payload))
