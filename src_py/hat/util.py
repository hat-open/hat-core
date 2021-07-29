"""Common utility functions"""

import contextlib
import inspect
import socket
import typing


T = typing.TypeVar('T')


def register_type_alias(name: str):
    """Register type alias

    This function is temporary hack replacement for typing.TypeAlias.

    It is expected that calling location will have `name` in local namespace
    with type value. This function will wrap that type inside `typing.TypeVar`
    and update annotations.

    """
    frame = inspect.stack()[1][0]
    f_locals = frame.f_locals
    t = f_locals[name]
    f_locals[name] = typing.TypeVar(name, t, t)
    f_locals.setdefault('__annotations__', {})[name] = typing.Type[t]


def first(xs: typing.Iterable[T],
          fn: typing.Callable[[T], typing.Any] = lambda _: True,
          default: typing.Optional[T] = None
          ) -> typing.Optional[T]:
    """Return the first element from iterable that satisfies predicate `fn`,
    or `default` if no such element exists.

    Result of predicate `fn` can be of any type. Predicate is satisfied if it's
    return value is truthy.

    Args:
        xs: collection
        fn: predicate
        default: default value

    Example::

        assert first(range(3)) == 0
        assert first(range(3), lambda x: x > 1) == 2
        assert first(range(3), lambda x: x > 2) is None
        assert first(range(3), lambda x: x > 2, 123) == 123
        assert first({1: 'a', 2: 'b', 3: 'c'}) == 1
        assert first([], default=123) == 123

    """
    return next((i for i in xs if fn(i)), default)


class RegisterCallbackHandle(typing.NamedTuple):
    """Handle for canceling callback registration."""

    cancel: typing.Callable[[], None]
    """cancel callback registration"""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cancel()


ExceptionCb = typing.Callable[[Exception], None]
"""Exception callback"""
register_type_alias('ExceptionCb')


class CallbackRegistry:
    """Registry that enables callback registration and notification.

    Callbacks in the registry are notified sequentially with
    `CallbackRegistry.notify`. If a callback raises an exception, the
    exception is caught and `exception_cb` handler is called. Notification of
    subsequent callbacks is not interrupted. If handler is `None`, the
    exception is reraised and no subsequent callback is notified.

    Example::

        x = []
        y = []
        registry = CallbackRegistry()

        registry.register(x.append)
        registry.notify(1)

        with registry.register(y.append):
            registry.notify(2)

        registry.notify(3)

        assert x == [1, 2, 3]
        assert y == [2]

    """

    def __init__(self,
                 exception_cb: typing.Optional[ExceptionCb] = None):
        self._exception_cb = exception_cb
        self._cbs = []  # type: typing.List[typing.Callable]

    def register(self,
                 cb: typing.Callable
                 ) -> RegisterCallbackHandle:
        """Register a callback."""
        self._cbs.append(cb)
        return RegisterCallbackHandle(lambda: self._cbs.remove(cb))

    def notify(self, *args, **kwargs):
        """Notify all registered callbacks."""
        for cb in self._cbs:
            try:
                cb(*args, **kwargs)
            except Exception as e:
                if self._exception_cb:
                    self._exception_cb(e)
                else:
                    raise


def get_unused_tcp_port() -> int:
    """Search for unused TCP port"""
    with contextlib.closing(socket.socket()) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def get_unused_udp_port() -> int:
    """Search for unused UDP port"""
    with contextlib.closing(socket.socket(type=socket.SOCK_DGRAM)) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]
