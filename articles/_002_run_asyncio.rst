`asyncio` application lifetime
==============================

:author: Bozo Kopic

This article explores different lifetime problems associated with running
long-living Python applications.


Classic application lifetime
----------------------------

Most of Python applications are implemented with simple pattern:

.. code:: python

    import sys

    def main():
        ...

    if __name__ == '__main__':
        sys.exit(main())

If this pattern is applied, execution of application is confined into execution
of single function `main`. This means that start of `main` execution is
considered application startup and end of `main` execution is considered
end of application execution.

For applications that are used for processing previously available data,
structure and execution plan for `main` function is mostly linear. Example of
such `main` is:

.. code:: python

    def main():
        read_input()
        validate_data()
        process_data()
        generate_output()

In this example, actions are executed sequentially and are dependent on previous
actions execution. For such actions, their lifetime is dependent on data they
are processing. This means that lifetime of `main` function (and thus lifetime
of application) is directly dependent of processed data. If this data is
available previous to application execution or if it is limited in quantity,
lifetime of application is also limited. Examples of this kind of applications
are command line utilities such as `tar`, `git`, `cp`, etc.

For applications that do not operate on previously available data or if
quantity of processed data is directly determined by previously processed data,
more complex and non-deterministic execution logic is required. Example of this
kind of applications `main` can be written as:

.. code:: python

    def main():
        initialize()
        while not done:
            read_data()
            validate_data()
            process_data()
            generate_output_part()
        generate_output_end()

Application that depend on data that is not previously available, are also
dependent on the structure and time when required data will be available.
Because of this, applications execution lifetime is often less deterministic
and can spawn indefinite execution time. Example of this kind of applications
are different kind of server applications (`apache`, `xorg`, ...).


`asyncio` application lifetime
------------------------------

Architecture and organization of long-running "server" applications is complex
problem for which multiple design patters exist. One of widely used is usage
of event loop. By using event loop, application functionality is split into
multiple loosely connected parts which execution is triggered by occurrence of
specific event. During execution os specific application logic, multiple events
can be queued as result of application logic or from external sources. These
events can be used as triggers for execution of other parts of application
logic. Usual implementations of event loop are closely related and therefore
usable as basic structural organization for previous long-running example
application.

.. code:: python

    def main():
        register_event_subscriptions()
        queue_initial_events()
        while not done:
            wait_while_queue_empty()
            deque_event()
            process_event()
        cleanup()

`asyncio` is library distributed with CPython distribution that provides
cross-platform implementation of event loop. Together with event loop
implemetation and appropriate nonblocking IO function implementations,
this library provides possibility to organize application logic by usage of
coroutines. Coroutines provide synchronization points which are used for
temporary delegation of execution flow to event loop engine. By using this
concept, application logic can be described in sequential manner while
execution will be split into multiple concurrent parts. Example of usual
structure for `asyncio` applications is:

.. code:: python

    import asyncio
    import sys

    async def main():
        ...

    if __name__ == '__main__':
        sys.exit(asyncio.run(main()))

Lifetime of `asyncio` applications is therefore similar to other "server"
and long-running application. Same problems, regarding controlling of
application execution and lifetime, are associated with applications based
on `asyncio`.


Signals
-------

One of main requirement which processes data is usage of some kind input/output
mechanism for obtaining input data and providing processing result. Usual means
for communication between application and "outside world" are writing/reading
of files, communication based on pipes or shared memory, communication based
on sockets, etc. Usage of this kind of communication media provides application
with possibility to actively communicate and synchronize with "outside world".
This communication is not only responsible for providing input data that
should be processed but is also directly responsible for controlling of
application's execution lifetime.

Posix signals are asynchronous communication mechanism that is most commonly
used for controlling of application execution. Main difference between signals
and other previously mentioned communication methods is availability of signals
without existence of additional explicit application logic for negotiating
communication. This mechanism is provided by operating system and is enabled
prior to delegation of execution control to application defined logic.

Most of predefined signals have conventional semantics associated with them.
For example, once application receives SIGINT or SIGTERM, it should finish
execution of application logic and stop its running process. This behavior is
even implemented as default one and assigned to each application by operating
system kernel. Although this is the default behavior, application can
override it by providing custom signal handling routines (even ignore request
for application termination). Prior to execution of scripts code, Python
interpreter overrides default behavior associated with these signals. New
routines associated with these signals are responsible for raising
`KeyboardInterrupt` exception from function that is currently being executed.
This means that most of Python functions can raise this exception if
application receives SIGINT or SIGTERM signal. By handling this exception,
application can provide additional cleanup logic or ignore termination request
according to its current state of execution.

Together with signals which behavior can be overridden, some signals can not
be overridden and are strongly enforced by operating system kernel. Example of
such signal is SIGKILL which signals unconditional termination of application
process. Stopping application by sending SIGKILL is therfore considered
last resort for terminating application which is without sufficient reason
ignoring signals SIGINT or SIGTERM.

Most of programs communicate with other unknown programs through signals
relaying on their proposed semantics. Example is command line shells which
associate users Ctrl+C command with routines that send SIGINT to currently
running program.

If we analyze prior example of applications that are used for processing
previously available data (applications with predefined lifetime), once user
presses Ctrl+C, any of the currently running functions could stop execution,
raise `KeyboardInterrupt` exception and propagate it to the `main`. In this
case execution of `main` function is terminated and application process
finishes. Due to sequential nature of data processing, this behavior is desired
in majority of cases. Because of this, `KeyboardInterrupt` isn't event part
of `Exception` children hierarchy so that it would not be caught by mistake
during handling of other exceptions.

For long-running applications, handling of SIGINT signal is often more complex
and dependent of current execution state running application. This kind of
applications rely on communication channels and protocols for communicating with
"outside world". This resources and protocols are usually statefull and should
be properly released prior to application termination. Many of these
applications can even postpone termination request if current processing of
data is critical for well behaved system operation.


`asyncio` and signals
---------------------

For determining behavior of `asyncio` application once it receives SIGINT,
we will run applications and examen console output when we press Ctrl+C 5
seconds after application is run and 15 seconds after application is run.

Code of test application (`test.py`) is:

.. code:: python

    import asyncio
    import time

    async def main():
        time.sleep(10)
        await asyncio.sleep(10)

    if __name__ == '__main__':
        asyncio.run(main())

When Ctrl+C is pressed 5 second after application is started, application
exits with console output::

    Traceback (most recent call last):
      File "test.py", line 11, in <module>
        asyncio.run(main())
      File "/usr/lib/python3.7/asyncio/runners.py", line 43, in run
        return loop.run_until_complete(main)
      File "/usr/lib/python3.7/asyncio/base_events.py", line 566, in run_until_complete
        self.run_forever()
      File "/usr/lib/python3.7/asyncio/base_events.py", line 534, in run_forever
        self._run_once()
      File "/usr/lib/python3.7/asyncio/base_events.py", line 1771, in _run_once
        handle._run()
      File "/usr/lib/python3.7/asyncio/events.py", line 88, in _run
        self._context.run(self._callback, *self._args)
      File "test.py", line 6, in main
        time.sleep(10)
    KeyboardInterrupt

From this call stack trace, we can notice that `KeyboardInterrupt` was raised
from `time.sleep` function and was propagated to `main` coroutine which
propagates exception to `ayncio.run` and stops program execution.

If we run the same program and press Ctrl+C 15 seconds after application is
started, application also exits but this time with following console
output::

    Traceback (most recent call last):
      File "test.py", line 11, in <module>
        asyncio.run(main())
      File "/usr/lib/python3.7/asyncio/runners.py", line 43, in run
        return loop.run_until_complete(main)
      File "/usr/lib/python3.7/asyncio/base_events.py", line 566, in run_until_complete
        self.run_forever()
      File "/usr/lib/python3.7/asyncio/base_events.py", line 534, in run_forever
        self._run_once()
      File "/usr/lib/python3.7/asyncio/base_events.py", line 1735, in _run_once
        event_list = self._selector.select(timeout)
      File "/usr/lib/python3.7/selectors.py", line 468, in select
        fd_event_list = self._selector.poll(timeout, max_ev)
    KeyboardInterrupt

From this call stack trace we can observe that `KeyboardInterrupt` is raised
from method which is part of internal `asyncio` implementation and is
propagated directly to `asyncio.run` bypassing `main` coroutine.

We can clearly demonstrate this behavior with little modification of above
script:

.. code:: python

    import asyncio
    import time

    async def main():
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            print('>> time.sleep')
            raise
        try:
            await asyncio.sleep(10)
        except KeyboardInterrupt:
            print('>> asyncio.sleep')
            raise

    if __name__ == '__main__':
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print('>> asyncio.run')

When we press Ctrl+C 5 seconds after startup, output is::

    >> time.sleep
    >> asyncio.run

But when we press Ctrl+C 15 seconds after startup, we get::

    >> asyncio.run

This example shows us that although coroutine code seems to be executed
sequentially, on every synchronization point (in this case
`await asyncio.sleep(10)`) application execution is transferred from coroutine
to `asyncio` event loop. This observation is specially important when
handling of signals is necessary, because application can receive lifetime
controlling signals at any time.


`hat.util.run_asyncio`
----------------------

`hat-util` package provides function `hat.util.run_asyncio` which can be used
instead of `asyncio.run`. This function overrides default handlers associated
with signals SIGINT and SIGTERM and replaces them with routine which cancels
initially run task (task created based on execution of `main` coroutine).
Once this method finishes, all signal handlers are restored to previous state.

Cancellation of `asyncio` task is implemented as raising of
`asyncio.CancelledError` exception at most nested currently waiting
synchronization point.

By suppressing `KeyboardInterrupt` and raising `asyncio.CancelledError`
exceptions we have better reasoning where and when this exception will occur.
This allows us easier handling of termination requests and better organization
and control of cleanup code execution.

Because `asyncio.CancelledError` exceptions are raised only on synchronization
points (where `await` is used), additional care must be used that coroutines
do not use long lasting blocking code and thus support promp reaction to
received signals.

Additionally, `hat.util.run_asyncio` cancels running task only once no matter
how many signals are sent to application. This provides easier cleanup
implementation because cleanup procedure won't be interrupter with another
termination request.

We can run test script by replacing `asyncio.run` with `hat.util.run_asyncio`
and `KeyboardInterrupt` with `asyncio.CancelledError`:

.. code:: python

    import asyncio
    import time
    import hat.util

    async def main():
        try:
            time.sleep(10)
        except asyncio.CancelledError:
            print('>> time.sleep')
            raise
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            print('>> asyncio.sleep')
            raise

    if __name__ == '__main__':
        try:
            hat.util.run_asyncio(main())
        except asyncio.CancelledError:
            print('>> hat.util.run_asyncio')

If we press Ctrl+C after 5 seconds, application will continue running for
another 5 seconds and then terminate with console output::

    >> asyncio.sleep
    >> hat.util.run_asyncio

If we press Ctrl+C after 15 seconds, application will terminate instantly
with console output::

    >> asyncio.sleep
    >> hat.util.run_asyncio


Signals in Windows
------------------

Unfortunately, Windows doesn't have full support for Posix signals. Most of
the signal handling procedures, as defined by C standard library, operate only
inside scope of single process and can not be used for communication between
processes.

For Windows application process, request for process termination is usually done
by calling `TerminateProcess` (`kernel32.dll` function). This request is
unconditional and with its semantics it is closest to the usage of SIGKILL
signal.

For console applications, asynchronous request for process termination can be
triggered by calling `GenerateConsoleCtrlEvent` (`kernel32.dll` function).
Default behavior for all console applications is to stop application execution
once either of this two events are received. This default behavior can be
overridden by calling `SetConsoleCtrlHandler` and providing alternative
event handlers. Alternative method for raising CTRL_C_EVENT is associated
with user Ctrl+C key press when application is running in active command
prompt. This behavior resembles behavior associated with Posix SIGINT and
SIGTERM signals.

Main difference between events raised with `GenerateConsoleCtrlEvent` and Posix
signals is that raising of CTRL_C_EVENT and CTRL_BREAK_EVENT can only target
process group instead of single process (or even thread in case of `pthread`
implementation). This means that once we raise CTRL_C_EVENT or
CTRL_BREAK_EVENT, all processes in target process group will receive and handle
sent event. Further restriction is put on CTRL_C_EVENT which can only be raised
from process which is part of the target process group. Because of this
restriction, every process raising CTRL_C_EVENT must also handle event that
itself raised.


Controlling Python applications lifetime on Windows
---------------------------------------------------

Python tries to provide uniform API for different platforms. Because of this,
external control of application lifetime for Python applications running on
Windows is possible with same interface used for sending and handling of
Posix signals. But because of previously mentioned restrictions, additional
care should be used.

Most significant restrictions and rules for using Python signal mapping to
Windows events:

    * Children processes which are to be controlled by events should be
      created with `subprocess.Popen` 's `CREATE_NEW_PROCESS_GROUP` flag.
      Creation of new group is mandatory if calling process doesn't
      want to handle sent event.

    * `os.kill` and `subprocess.Process.send_signal` doesn't receive process
      identification. Instead, process group identification is expected. Process
      group identification is the same as process identification for which new
      group was created. Process group identification `0` identifies process
      group to which current process belongs.

    * Raising of SIGKILL is implemented as calling `subprocess.Popen.terminate`
      which calls `TerminateProcess`.

    * `os.kill` and `subprocess.Process.send_signal` support only
      SIGKILL, CTRL_C_EVENT and CTRL_BREAK_EVENT.

    * When writing signal handlers in Python, CTRL_C_EVENT is notified as
      SIGINT signal and CTRL_BREAK_EVENT is notified as SIGBREAK signal.

    * CTRL_C_EVENT and CTRL_BREAK_EVENT are dispatched to all processes in
      process group.

    * Only CTRL_BREAK_EVENT can be raised from one process group targeting
      other process group.


`hat.util.run_asyncio` on Windows
---------------------------------

Implementation of `run_asyncio` takes into account previously mentioned
restrictions. This means that signals for which default behavior is temporary
overridden include SIGBREAK.

Depending on used implementation of `asyncio` event loop, there exist
possibility that signal handlers will not be triggered while event loop is in
state of waiting for IO associated events. This problem is currently addressed
by providing periodical "wakeup" of event loop every 0.5 seconds. This period
is responsible for latency between raising events and notification of their
occurrence which can last up to 0.5 second.

Because of these addition logic implemented inside `run_asyncio`, same code
provided as example of running `asyncio` application with
`hat.util.run_asyncio` can be run on Windows with same behavior as on other
systems.
