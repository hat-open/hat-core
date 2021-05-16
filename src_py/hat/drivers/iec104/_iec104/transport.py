import asyncio
import itertools
import logging

from hat import aio
from hat.drivers import tcp
from hat.drivers.iec104._iec104 import common
from hat.drivers.iec104._iec104 import encoder


mlog = logging.getLogger(__name__)


class Transport(aio.Resource):

    def __init__(self,
                 conn: tcp.Connection,
                 always_enabled: bool,
                 response_timeout: float,
                 supervisory_timeout: float,
                 test_timeout: float,
                 send_window_size: int,
                 receive_window_size: int):
        self._conn = conn
        self._always_enabled = always_enabled
        self._is_enabled = always_enabled
        self._response_timeout = response_timeout
        self._supervisory_timeout = supervisory_timeout
        self._test_timeout = test_timeout
        self._send_window_size = send_window_size
        self._receive_window_size = receive_window_size
        self._read_queue = aio.Queue()
        self._write_queue = aio.Queue()
        self._test_event = asyncio.Event()
        self._ssn = 0
        self._rsn = 0
        self._ack = 0
        self._w = 0
        self._write_supervisory_handle = None
        self._waiting_ack_handles = {}
        self._waiting_ack_cv = asyncio.Condition()
        self.async_group.spawn(self._read_loop)
        self.async_group.spawn(self._write_loop)
        self.async_group.spawn(self._test_loop)
        self.async_group.spawn(aio.call_on_cancel, self._on_close)

    @property
    def async_group(self) -> aio.Group:
        return self._conn.async_group

    @property
    def conn(self):
        return self._conn

    def write(self, asdu: common.ASDU):
        try:
            self._write_queue.put_nowait(asdu)

        except aio.QueueClosedError:
            raise ConnectionError()

    async def read(self) -> common.ASDU:
        try:
            return await self._read_queue.get()

        except aio.QueueClosedError:
            raise ConnectionError()

    async def _on_close(self):
        self._read_queue.close()
        self._write_queue.close()

        for f in self._waiting_ack_handles.values():
            f.cancel()

        self._stop_supervisory_timeout()

    def _on_response_timeout(self):
        mlog.warning("response timeout occured - closing connection")
        self.close()

    def _on_supervisory_timeout(self):
        self._write_supervisory_handle = None

        try:
            self._write_apdu(common.APDUS(self._rsn))
            self._w = 0

        except Exception as e:
            mlog.warning('supervisory timeout error: %s', e, exc_info=e)

    async def _read_loop(self):
        try:
            while True:
                apdu = await encoder.read_apdu(self._conn)

                if isinstance(apdu, common.APDUU):
                    await self._process_apduu(apdu)

                elif isinstance(apdu, common.APDUS):
                    await self._process_apdus(apdu)

                elif isinstance(apdu, common.APDUI):
                    await self._process_apdui(apdu)

                else:
                    raise ValueError("unsupported APDU")

        except (ConnectionError, aio.QueueClosedError):
            pass

        except Exception as e:
            mlog.warning('read loop error: %s', e, exc_info=e)

        finally:
            self.close()

    async def _write_loop(self):
        try:
            while True:
                asdu = await self._write_queue.get()

                if self._ssn in self._waiting_ack_handles:
                    raise Exception("can not reuse already registered ssn")

                async with self._waiting_ack_cv:
                    await self._waiting_ack_cv.wait_for(
                        lambda: (len(self._waiting_ack_handles) <
                                 self._send_window_size))

                if not self._is_enabled:
                    continue

                self._write_apdu(common.APDUI(ssn=self._ssn,
                                              rsn=self._rsn,
                                              asdu=asdu))
                self._w = 0
                self._stop_supervisory_timeout()

                self._waiting_ack_handles[self._ssn] = (
                    asyncio.get_event_loop().call_later(
                        self._response_timeout, self._on_response_timeout))
                self._ssn = (self._ssn + 1) % 0x8000

        except (ConnectionError, aio.QueueClosedError):
            pass

        except Exception as e:
            mlog.warning('write loop error: %s', e, exc_info=e)

        finally:
            self.close()

    async def _test_loop(self):
        try:
            while True:
                await asyncio.sleep(self._test_timeout)

                self._test_event.clear()
                self._write_apdu(common.APDUU(common.ApduFunction.TESTFR_ACT))

                await aio.wait_for(self._test_event.wait(),
                                   self._response_timeout)

        except Exception as e:
            mlog.warning('test loop error: %s', e, exc_info=e)

        finally:
            self.close()

    def _write_apdu(self, apdu):
        encoder.write_apdu(self._conn, apdu)

    async def _process_apduu(self, apdu):
        if apdu.function == common.ApduFunction.STARTDT_ACT:
            if not self._always_enabled:
                self._is_enabled = True
                self._write_apdu(common.APDUU(common.ApduFunction.STARTDT_CON))

        elif apdu.function == common.ApduFunction.STOPDT_ACT:
            if not self._always_enabled:
                self._is_enabled = False
                self._write_apdu(common.APDUU(common.ApduFunction.STOPDT_CON))

        elif apdu.function == common.ApduFunction.TESTFR_ACT:
            self._write_apdu(common.APDUU(common.ApduFunction.TESTFR_CON))

        elif apdu.function == common.ApduFunction.TESTFR_CON:
            self._test_event.set()

    async def _process_apdus(self, apdu):
        await self._set_ack(apdu.rsn)

    async def _process_apdui(self, apdu):
        await self._set_ack(apdu.rsn)

        self._rsn = (apdu.ssn + 1) % 0x8000
        self._start_supervisory_timeout()

        if apdu.asdu:
            self._read_queue.put_nowait(apdu.asdu)

        self._w += 1
        if self._w >= self._receive_window_size:
            self._write_apdu(common.APDUS(self._rsn))
            self._w = 0
            self._stop_supervisory_timeout()

    async def _set_ack(self, ack):
        if ack >= self._ack:
            ssns = range(self._ack, ack)
        else:
            ssns = itertools.chain(range(self._ack, 0x8000), range(ack))

        for ssn in ssns:
            handle = self._waiting_ack_handles.pop(ssn, None)
            if not handle:
                raise Exception("received ack for unsent sequence number")
            handle.cancel()

        self._ack = ack
        async with self._waiting_ack_cv:
            self._waiting_ack_cv.notify_all()

    def _start_supervisory_timeout(self):
        if self._write_supervisory_handle:
            return

        self._write_supervisory_handle = asyncio.get_event_loop().call_later(
            self._supervisory_timeout, self._on_supervisory_timeout)

    def _stop_supervisory_timeout(self):
        if not self._write_supervisory_handle:
            return

        self._write_supervisory_handle.cancel()
        self._write_supervisory_handle = None
