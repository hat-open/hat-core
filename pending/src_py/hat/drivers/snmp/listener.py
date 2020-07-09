import asyncio

from hat import util
import hat.asn1.ber
import hat.drivers.udp
from hat.drivers.snmp.serializer import (MsgV1,
                                         MsgV2C,
                                         MsgV3,
                                         trap_from_pdu,
                                         Serializer)
from hat.drivers.snmp.serializer import (ObjectIdentifier,  # NOQA
                                         Context)


async def create_listener(asn1_repo, local_host='0.0.0.0', local_port=162):
    """Create listener

    Args:
        asn1_repo (hat.asn1.Repository): asn1 repository
        local_host (str): local host name
        local_port (int): local udp port

    Returns:
        Listener

    """
    listener = Listener()
    listener._queue = util.Queue()
    listener._async_group = util.AsyncGroup()
    listener._serializer = Serializer(hat.asn1.ber.BerEncoder(asn1_repo))
    listener._udp = await hat.drivers.udp.create(
        local_addr=(local_host, local_port),
        remote_addr=None)
    listener._async_group.spawn(listener._read_loop)
    return listener


class Listener:

    @property
    def closed(self):
        """asyncio.Future: closed future"""

        return self._async_group.closed

    async def async_close(self):
        """Async close"""

        await self._async_group.async_close()

    async def receive(self):
        """Receive trap

        For v1 and v2c, context's name is used as community name.

        Returns:
            Tuple[Context,Trap]

        """
        return await self._queue.get()

    async def _read_loop(self):
        while True:
            try:
                msg_bytes, addr = await self._udp.receive()
                msg = self._serializer.decode_msg(msg_bytes)
                if isinstance(msg, MsgV1):
                    context = Context(None, msg.community)
                elif isinstance(msg, MsgV2C):
                    context = Context(None, msg.community)
                elif isinstance(msg, MsgV3):
                    context = msg.context
                else:
                    raise Exception()
                trap = trap_from_pdu(msg.pdu)
                self._queue.put_nowait((context, trap))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print('>>>>>', e)
                # import pdb; pdb.post_mortem()
                _ = 1
        await self._udp.async_close()
        self._queue.close()
