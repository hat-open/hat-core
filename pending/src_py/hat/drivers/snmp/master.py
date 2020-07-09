import asyncio

from hat import util
import hat.asn1.ber
import hat.drivers.udp
from hat.drivers.snmp.serializer import (Version,
                                         Error,
                                         ErrorType,
                                         Data,
                                         DataType,
                                         MsgV1,
                                         MsgV2C,
                                         MsgV3,
                                         MsgType,
                                         BasicPdu,
                                         BulkPdu,
                                         Serializer)
from hat.drivers.snmp.serializer import (ObjectIdentifier,  # NOQA
                                         Context)


async def create_master(asn1_repo, context, remote_host,
                        remote_port=161, version=Version.V2C):
    """Create master

    For v1 and v2c, context's name is used as community name.

    Args:
        asn1_repo (hat.asn1.Repository): asn1 repository
        context (Context): context
        remote_host (str): remote host name
        remote_port (int): remote udp port
        version (Version): version

    Returns:
        Master

    """
    master = Master()
    master._version = version
    master._context = context
    master._response_cbs = util.CallbackRegistry()
    master._request_id = 1
    master._serializer = Serializer(hat.asn1.ber.BerEncoder(asn1_repo))
    master._async_group = util.AsyncGroup()
    master._udp = await hat.drivers.udp.create(
        local_addr=None,
        remote_addr=(remote_host, remote_port))
    master._async_group.spawn(master._read_loop)
    return master


class Master:

    @property
    def closed(self):
        """asyncio.Future: closed future"""

        return self._async_group.closed

    async def async_close(self):
        """Async close"""

        await self._async_group.async_close()

    async def get(self, names):
        """Get data

        Args:
            names (Iterable[ObjectIdentifier]): names

        Returns:
            Union[Error,List[Data]]

        """
        data = [self._name_to_data(name) for name in names]
        return await self._async_group.spawn(self._send, MsgType.GET_REQUEST,
                                             data)

    async def get_next(self, names):
        """Get next data

        Args:
            names (Iterable[ObjectIdentifier]): names

        Returns:
            Union[Error,List[Data]]

        """
        data = [self._name_to_data(name) for name in names]
        return await self._async_group.spawn(self._send,
                                             MsgType.GET_NEXT_REQUEST, data)

    async def get_bulk(self, names):
        """Get bulk data

        Args:
            names (Iterable[ObjectIdentifier]): names

        Returns:
            Union[Error,List[Data]]

        """
        data = [self._name_to_data(name) for name in names]
        return await self._async_group.spawn(self._send,
                                             MsgType.GET_BULK_REQUEST, data)

    async def set(self, data):
        """Set data

        Args:
            data (List[data]): data

        Returns:
            Union[Error,List[Data]]

        """
        return await self._async_group.spawn(self._send, MsgType.SET_REQUEST,
                                             data)

    async def inform(self, data):
        """Inform

        Args:
            data (List[data]): data

        Returns:
            Union[Error,List[Data]]

        """
        return await self._async_group.spawn(self._send,
                                             MsgType.INFORM_REQUEST, data)

    async def _read_loop(self):
        while True:
            try:
                msg_bytes, addr = await self._udp.receive()
                msg = self._serializer.decode(msg_bytes)
                self._response_cbs.notify((msg, addr))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print('>>>>>', e)
                import pdb; pdb.post_mortem()
                _ = 1
        await self._udp.async_close()

    async def _send(self, msg_type, data):
        if msg_type == MsgType.GET_BULK_REQUEST:
            req_pdu = BulkPdu(request_id=self._request_id,
                              non_repeaters=0,
                              max_repetitions=0,
                              data=data)
        else:
            req_pdu = BasicPdu(request_id=self._request_id,
                               error=Error(ErrorType.NO_ERROR, 0),
                               data=data)
        req_msg = self._create_msg(msg_type, req_pdu)
        req_msg_bytes = self._serializer.encode(req_msg)
        self._request_id += 1

        # TODO: resend, timeout, check request_id, ...
        queue = util.Queue()
        with self._response_cbs.register(queue.put_nowait):
            self._udp.send(req_msg_bytes)
            res_msg, _ = await queue.get()
            if res_msg.pdu.error.type != ErrorType.NO_ERROR:
                return res_msg.pdu.error
            return res_msg.pdu.data

    def _create_msg(self, msg_type, pdu):
        if self._version == Version.V1:
            return MsgV1(type=msg_type,
                         community=self._context.name,
                         pdu=pdu)
        if self._version == Version.V2C:
            return MsgV2C(type=msg_type,
                          community=self._context.name,
                          pdu=pdu)
        if self._version == Version.V3:
            return MsgV3(type=msg_type,
                         id=self._request_id,
                         reportable=False,
                         context=self._context,
                         pdu=pdu)
        raise Exception()

    def _name_to_data(self, name):
        if self._version == Version.V1:
            return Data(type=DataType.EMPTY,
                        name=name,
                        value=None)
        if self._version == Version.V2C:
            return Data(type=DataType.UNSPECIFIED,
                        name=name,
                        value=None)
        if self._version == Version.V3:
            return Data(type=DataType.UNSPECIFIED,
                        name=name,
                        value=None)
        raise Exception()
