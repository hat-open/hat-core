.. _hat-util:

`hat.util` - Python utility library
===================================

This module includes few simple function/mechanics not available as part of
Python standard library.


.. _hat-util-first:

`hat.util.first`
----------------

This is simple function with signature::

    def first(xs: typing.Iterable[T],
              fn: typing.Callable[[T], bool] = lambda _: True,
              default: typing.Optional[T] = None
              ) -> typing.Optional[T]:
        """Return the first element from iterable that satisfies predicate `fn`,
        or `default` if no such element exists.

        Args:
            xs: collection
            fn: predicate
            default: default value

        """

Some of possible application of this function include:

    * accessing first element of arbitrary iterable

        If collection doesn't implement sequence protocol, accessing
        first (or any other) element can be done by creating iterator and
        calling `next` function. `first` provides convenient wrapper for this
        operation::

            assert first({1: 'a', 2: 'b', 3: 'c'}) == 1

        Additionally, event in case of sequences (e.g. `list`, `tuple`,
        `range`), calling `first` with default value can be more convenient
        than additional 'length greater than zero' check::

            assert first([], default=123) == 123

    * find first element that satisfies predicate

        By providing predicate function, any iterable can be searched for
        first element that satisfies required condition::

            assert first(range(3), lambda x: x > 1) == 2

        Default value is returned if there is no elements that satisfy
        predicate::

            assert first(range(3), lambda x: x > 2) is None
            assert first(range(3), lambda x: x > 2, 123) == 123


.. _hat-util-CallbackRegistry:

`hat.util.CallbackRegistry`
---------------------------

`CallbackRegistry` provides facility for registering/unregistering functions
and their invocation. It is usually used as simple event handling
infrastructure where additional component decoupling is required.

::

    class RegisterCallbackHandle(typing.NamedTuple):
        """Handle for canceling callback registration."""

        cancel: typing.Callable[[], None]
        """cancel callback registration"""

        def __enter__(self): ...

        def __exit__(self, *args): ...

    ExceptionCb: typing.Type = typing.Callable[[Exception], None]
    """Exception callback"""

    class CallbackRegistry:
        """Registry that enables callback registration and notification.

        Callbacks in the registry are notified sequentially with
        `CallbackRegistry.notify`. If a callback raises an exception, the
        exception is caught and `exception_cb` handler is called. Notification of
        subsequent callbacks is not interrupted. If handler is `None`, the
        exception is reraised and no subsequent callback is notified.

        """

        def __init__(self,
                     exception_cb: typing.Optional[ExceptionCb] = None): ...

        def register(self,
                     cb: typing.Callable
                     ) -> RegisterCallbackHandle:
            """Register a callback."""

        def notify(self, *args, **kwargs):
            """Notify all registered callbacks."""

Usage example::

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


.. _hat-util-parse_url_query:

`hat.util.parse_url_query`
--------------------------

URL query string parser::

    def parse_url_query(query: str) -> typing.Dict[str, str]:
        """Parse url query string.

        Returns a dictionary of field names and their values.

        Args:
            query: url query string

        """

Usage example::

    url = urllib.parse.urlparse('https://pypi.org/search/?q=hat-util')
    args = parse_url_query(url.query)
    assert args == {'q': 'hat-util'}


.. _hat-util-get_unused_tcp_port:
.. _hat-util-get_unused_udp_port:

`hat.util.get_unused_tcp_port` and `hat.util.get_unused_udp_port`
-----------------------------------------------------------------

Helper functions for obtaining `unused` TCP/UDP port. This functions create
new socket and bind them to arbitrary port. After binding is completed,
sockets are immediately closed and bounded port is returned as one of available
`unused` port.

There is no guarantee that this port will stay `unused` after temporary socket
is closed.

There is no guarantee that consecutive invocation of these functions will
return different results.

::

    def get_unused_tcp_port() -> int:
        """Search for unused TCP port"""

    def get_unused_udp_port() -> int:
        """Search for unused UDP port"""


.. _hat-util-api:

API
---

API reference is available as part of generated documentation:

    * `hat.util module <../../pyhat/hat/util.html>`_
