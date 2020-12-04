"""Common utility functions"""

import collections
import contextlib
import enum
import socket
import sys
import typing
import warnings


T = typing.TypeVar('T')


def first(xs: typing.Iterable[T],
          fn: typing.Callable[[T], bool] = lambda _: True,
          default: typing.Optional[T] = None) -> typing.Optional[T]:
    """Return the first element from iterable that satisfies predicate `fn`,
    or `default` if no such element exists.

    Args:
        xs: collection
        fn: predicate
        default: default value

    """
    return next((i for i in xs if fn(i)), default)


def namedtuple(name: typing.Union[str, typing.Tuple[str, str]],
               *field_props: typing.Iterable[typing.Union[
                    str,
                    typing.Tuple[str, str],
                    typing.Tuple[str, str, typing.Any]
               ]]) -> typing.Type[collections.namedtuple]:
    """Create a documented Type[collections.namedtuple]`.

    The `name` can be a string; or a tuple containing name and documentation.

    The `field_props` are an iterable of tuple field properties. A property
    can be a field name; a tuple of field name and documentation; or a tuple
    of field name, documentation and default value.

    Args:
        name: tuple name with optional documentation
        field_props: tuple field properties

    """
    field_props = [(i, None) if isinstance(i, str) else list(i)
                   for i in field_props]
    cls = collections.namedtuple(name if isinstance(name, str) else name[0],
                                 [i[0] for i in field_props])
    default_values = []
    for i in field_props:
        if default_values and len(i) < 3:
            raise Exception("property with default value not at end")
        if len(i) > 2:
            default_values.append(i[2])
    if default_values:
        cls.__new__.__defaults__ = tuple(default_values)
    if not isinstance(name, str):
        cls.__doc__ = name[1]
    for i in field_props:
        if i[1]:
            getattr(cls, i[0]).__doc__ = i[1]
    with contextlib.suppress(AttributeError, ValueError):
        cls.__module__ = sys._getframe(1).f_globals.get('__name__', '__main__')
    return cls


def extend_enum_doc(cls: enum.EnumMeta,
                    description: str = None) -> enum.EnumMeta:
    """Extend enumeration documentation with a list of all members."""
    warnings.warn("extend_enum_doc is deprecated", DeprecationWarning)
    doc = description or cls.__doc__
    cls.__doc__ = doc + "\n\n" + "\n".join("* " + i.name for i in cls)
    return cls


class RegisterCallbackHandle(typing.NamedTuple):
    """Handle for canceling callback registration.

    Args:
        cancel: cancel callback registration

    """
    cancel: typing.Callable[[], None]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cancel()


class CallbackRegistry:
    """Registry that enables callback registration and notification.

    Callbacks in the registry are notified sequentially with
    :meth:`CallbackRegistry.notify`. If a callback raises an exception, the
    exception is caught and `exception_cb` handler is called. Notification of
    subsequent callbacks is not interrupted. If handler is `None`, the
    exception is reraised and no subsequent callback is notified.

    Args:
        exception_cb: exception handler

    """

    def __init__(self,
                 exception_cb: typing.Optional[typing.Callable[[Exception], None]] = None):  # NOQA
        self._exception_cb = exception_cb
        self._cbs = []

    def register(self, cb: typing.Callable) -> RegisterCallbackHandle:
        """Register a callback. A handle for registration canceling is
        returned.

        Args:
            cb: callback

        """
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


def parse_url_query(query: str) -> typing.Dict[str, str]:
    """Parse url query string.

    Returns a dictionary of field names and their values.

    Args:
        query: url query string

    """
    ret = {}
    for i in query.split('&'):
        if not i:
            continue
        temp = i.split('=')
        if not temp[0]:
            continue
        ret[temp[0]] = temp[1] if len(temp) > 1 else None
    return ret


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
