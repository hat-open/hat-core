Hat Core - Python utility library
=================================

This library is part of Hat Open project - open-source framework of tools and
libraries for developing applications used for remote monitoring, control and
management of intelligent electronic devices such as IoT devices, PLCs,
industrial automation or home automation systems.

Development of Hat Open and associated repositories is sponsored by
Končar - Power Plant and Electric Traction Engineering Inc.
(Končar KET - `<https://www.koncar-ket.hr>`_).

For more information see:

    * `hat-util` documentation - `<https://core.hat-open.com/docs/libraries/util/python.html>`_
    * Hat Core homepage - `<https://core.hat-open.com>`_
    * Hat Core git repository - `<https://github.com/hat-open/hat-core.git>`_

.. warning::

    This project is currently in state of active development. Features,
    functionality and API are unstable.


About
-----

Common utility functions not available as part of standard library.

* `hat.util.first`::

    def first(xs: typing.Iterable[T],
              fn: typing.Callable[[T], bool] = lambda _: True,
              default: typing.Optional[T] = None
              ) -> typing.Optional[T]:
        """Return the first element from iterable that satisfies predicate
           `fn`, or `default` if no such element exists.

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


* `hat.util.CallbackRegistry`::

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
        :meth:`CallbackRegistry.notify`. If a callback raises an exception, the
        exception is caught and `exception_cb` handler is called. Notification
        of subsequent callbacks is not interrupted. If handler is `None`, the
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
                     exception_cb: typing.Optional[ExceptionCb] = None): ...

        def register(self,
                     cb: typing.Callable
                     ) -> RegisterCallbackHandle:
            """Register a callback."""

        def notify(self, *args, **kwargs):
            """Notify all registered callbacks."""


* `hat.util.parse_url_query`::

    def parse_url_query(query: str) -> typing.Dict[str, str]:
        """Parse url query string.

        Returns a dictionary of field names and their values.

        Args:
            query: url query string

        Example::

            url = urllib.parse.urlparse('https://pypi.org/search/?q=hat-util')
            args = parse_url_query(url.query)
            assert args == {'q': 'hat-util'}

        """


* `hat.util.get_unused_tcp_port` and `hat.util.get_unused_udp_port`::

    def get_unused_tcp_port() -> int:
        """Search for unused TCP port"""

    def get_unused_udp_port() -> int:
        """Search for unused UDP port"""
