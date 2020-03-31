"""Common utility functions"""

import argparse
import collections
import contextlib
import logging.handlers
import os
import pathlib
import sys


def first(xs, fn=lambda _: True, default=None):
    """Return the first element from iterable that satisfies predicate `fn`,
    or `default` if no such element exists.

    Args:
        xs (Iterable[Any]): collection
        fn (Callable[[Any],bool]): predicate
        default (Any): default

    Returns:
        Any

    """
    return next((i for i in xs if fn(i)), default)


def namedtuple(name, *field_props):
    """Create a documented Type[collections.namedtuple]`.

    The `name` can be a string; or a tuple containing name and documentation.

    The `field_props` are an iterable of tuple field properties. A property
    can be a field name; a tuple of field name and documentation; or a tuple
    of field name, documentation and default value.

    Args:
        name (Union[str,Tuple[str,str]]):
            tuple name with optional documentation
        field_props (Iterable[Union[str,Tuple[str,str],Tuple[str,str,Any]]]):
            tuple field properties

    Returns:
        Type[collections.namedtuple]

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


def extend_enum_doc(cls, description=None):
    """Extend enumeration documentation with a list of all members.

    Args:
        cls (enum.EnumMeta): enumeration class

    Returns:
        enum.EnumMeta

    """
    doc = description or cls.__doc__
    cls.__doc__ = doc + "\n\n" + "\n".join("* " + i.name for i in cls)
    return cls


class RegisterCallbackHandle(namedtuple('RegisterCallbackHandle', 'cancel')):
    """Handle for canceling callback registration.

    Args:
        cancel (Callable[[],None]): cancel callback registration

    """

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
        exception_cb (Optional[Callable[[Exception],None]]): exception handler

    """

    def __init__(self, exception_cb=None):
        self._exception_cb = exception_cb
        self._cbs = []

    def register(self, cb):
        """Register a callback. A handle for registration canceling is
        returned.

        Args:
            cb (Callable): callback

        Returns:
            RegisterCallbackHandle

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


def parse_url_query(query):
    """Parse url query string.

    Returns a dictionary of field names and their values.

    Args:
        query (str): url query string

    Returns:
        Dict[str,str]

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


def parse_env_path(path):
    """Parse path with environment variables.

    Parse file path and replace all file path segments equal to ``$<name>``
    with value of ``<name>`` environment variable. If environment variable is
    not set, segments are replaced with ``.``.

    Args:
        path (os.PathLike): file path

    Returns:
        pathlib.Path

    """
    path = pathlib.Path(path)
    segments = []
    for segment in path.parts:
        if segment.startswith('$'):
            segment = os.environ.get(segment[1:], '.')
        segments.append(segment)
    return pathlib.Path(*segments)


class LogRotatingFileHandler(logging.handlers.RotatingFileHandler):

    def __init__(self, filename, *vargs, **kwargs):
        """Filename is parsed with :func:`parse_env_path`.

        For other arguments, see:
        :class:`logging.handlers.RotatingFileHandler`.

        """
        super().__init__(parse_env_path(filename), *vargs, **kwargs)


class EnvPathArgParseAction(argparse.Action):
    """Argparse action for parsing file paths with environment variables.

    Each path is parsed with :func:`parse_env_path`.

    """

    def __call__(self, parser, namespace, values, option_string=None):
        ret = []
        for value in (values if self.nargs else [values]):
            try:
                ret.append(parse_env_path(value))
            except Exception as e:
                parser.error(str(e))
        setattr(namespace, self.dest, ret if self.nargs else ret[0])
