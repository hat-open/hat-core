"""Process control"""

import asyncio
import contextlib
import ctypes
import signal
import subprocess
import sys
import typing

from hat import aio


async def create_process(args: typing.List[str],
                         sigint_timeout: float = 5,
                         sigkill_timeout: float = 2
                         ) -> 'Process':
    """Create process"""
    process = Process()
    process._sigint_timeout = sigint_timeout
    process._sigkill_timeout = sigkill_timeout
    process._async_group = aio.Group()
    process._read_queue = aio.Queue()

    process._process = await asyncio.create_subprocess_exec(
        *args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        preexec_fn=preexec_fn)

    process._async_group.spawn(process._read_loop)

    return process


class Process(aio.Resource):
    """Process"""

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def pid(self) -> int:
        """Process ID"""
        return self._process.pid

    @property
    def returncode(self) -> typing.Optional[int]:
        """Return code"""
        return self._process.returncode

    async def readline(self) -> str:
        """Read line from stdout"""
        try:
            return await self._read_queue.get()

        except aio.QueueClosedError:
            raise ConnectionError()

    async def _read_loop(self):
        try:
            try:
                while True:
                    line = await self._process.stdout.readline()
                    if not line:
                        break
                    line = line.decode('utf-8', 'ignore').rstrip()
                    self._read_queue.put_nowait(line)

            finally:
                self._read_queue.close()

            await self._process.wait()

        finally:
            self.close()
            await aio.uncancellable(self._close())

    async def _close(self):
        if self._process.returncode is not None:
            return

        with contextlib.suppress(Exception):
            self._process.send_signal(SIGINT)

        with contextlib.suppress(asyncio.TimeoutError):
            await aio.wait_for(self._process.wait(), self._sigint_timeout)

        if self._process.returncode is not None:
            return

        with contextlib.suppress(Exception):
            self._process.kill()

        with contextlib.suppress(asyncio.TimeoutError):
            await aio.wait_for(self._process.wait(), self._sigkill_timeout)


class Win32Job(aio.Resource):
    """Win32 Job Object"""

    def __init__(self):
        self._async_group = aio.Group()
        self._job = kernel32.CreateJobObjectA(None, None)

        JobObjectExtendedLimitInformation = 9
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION(
            BasicLimitInformation=JOBOBJECT_BASIC_LIMIT_INFORMATIONRECT(
                LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE))
        kernel32.SetInformationJobObject(self._job,
                                         JobObjectExtendedLimitInformation,
                                         ctypes.byref(info),
                                         ctypes.sizeof(info))

        self._async_group.spawn(aio.call_on_cancel, kernel32.CloseHandle,
                                self._job)

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    def add_process(self, process: Process):
        """Add process"""
        PROCESS_TERMINATE = 1
        PROCESS_SET_QUOTA = 0x100
        access = PROCESS_TERMINATE | PROCESS_SET_QUOTA

        handle = kernel32.OpenProcess(access, False, process.pid)
        kernel32.AssignProcessToJobObject(self._job, handle)
        kernel32.CloseHandle(handle)


if sys.platform == 'linux':

    class LibC:

        def __init__(self, path):
            self._lib = ctypes.cdll.LoadLibrary(path)

            self._lib.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong,
                                        ctypes.c_ulong, ctypes.c_ulong,
                                        ctypes.c_ulong]
            self._lib.prctl.restype = ctypes.c_int

            self.PR_SET_PDEATHSIG = 1
            self.SIGKILL = 9

        def prctl(self, option, arg2=0, arg3=0, arg4=0, arg5=0):
            return self._lib.prctl(option, arg2, arg3, arg4, arg5)

    libc = LibC('libc.so.6')

    def preexec_fn():
        libc.prctl(libc.PR_SET_PDEATHSIG, libc.SIGKILL)

    creationflags = 0

    SIGINT = signal.SIGINT

elif sys.platform == 'win32':

    import ctypes.wintypes

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("nLength", ctypes.wintypes.DWORD),
                    ("lpSecurityDescriptor", ctypes.wintypes.LPVOID),
                    ("bInheritHandle", ctypes.wintypes.BOOL)]

    class JOBOBJECT_BASIC_LIMIT_INFORMATIONRECT(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.wintypes.LARGE_INTEGER),
                    ("PerJobUserTimeLimit", ctypes.wintypes.LARGE_INTEGER),
                    ("LimitFlags", ctypes.wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", ctypes.wintypes.DWORD),
                    ("Affinity", ctypes.wintypes.PULONG),
                    ("PriorityClass", ctypes.wintypes.DWORD),
                    ("SchedulingClass", ctypes.wintypes.DWORD)]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                    ("WriteOperationCount", ctypes.c_ulonglong),
                    ("OtherOperationCount", ctypes.c_ulonglong),
                    ("ReadTransferCount", ctypes.c_ulonglong),
                    ("WriteTransferCount", ctypes.c_ulonglong),
                    ("OtherTransferCount", ctypes.c_ulonglong)]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [("BasicLimitInformation",
                     JOBOBJECT_BASIC_LIMIT_INFORMATIONRECT),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class Kernel32:

        def __init__(self, path):
            self._lib = ctypes.windll.LoadLibrary(path)

            self._lib.CreateJobObjectA.argtypes = [
                ctypes.POINTER(SECURITY_ATTRIBUTES),
                ctypes.wintypes.LPCSTR]
            self._lib.CreateJobObjectA.restype = ctypes.wintypes.HANDLE

            self._lib.SetInformationJobObject.argtypes = [
                ctypes.wintypes.HANDLE,
                ctypes.wintypes.UINT,  # TODO: enum size
                ctypes.wintypes.LPVOID,
                ctypes.wintypes.DWORD]
            self._lib.SetInformationJobObject.restype = ctypes.wintypes.BOOL

            self._lib.AssignProcessToJobObject.argtypes = [
                ctypes.wintypes.HANDLE,
                ctypes.wintypes.HANDLE]
            self._lib.AssignProcessToJobObject.restype = ctypes.wintypes.BOOL

            self._lib.OpenProcess.argtypes = [ctypes.wintypes.DWORD,
                                              ctypes.wintypes.BOOL,
                                              ctypes.wintypes.DWORD]
            self._lib.OpenProcess.restype = ctypes.wintypes.HANDLE

            self._lib.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
            self._lib.CloseHandle.restype = ctypes.wintypes.BOOL

            self.CreateJobObjectA = self._lib.CreateJobObjectA
            self.SetInformationJobObject = self._lib.SetInformationJobObject
            self.AssignProcessToJobObject = self._lib.AssignProcessToJobObject
            self.OpenProcess = self._lib.OpenProcess
            self.CloseHandle = self._lib.CloseHandle

    kernel32 = Kernel32('Kernel32.dll')

    preexec_fn = None

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    SIGINT = signal.CTRL_BREAK_EVENT

else:

    raise Exception('unsupported platform')
