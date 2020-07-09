import sys
import functools

import hat.syslog.server.main
import hat.syslog.server.backend as sqlite_backend
from hat.util import aio

from test_perf.test_syslog import memory_backend


def main():
    message_count = int(get_last_sys_arg())
    backend_type = get_last_sys_arg()
    create_fn = {"memory": memory_backend.create_backend,
                 "sqlite": sqlite_backend.create_backend}[backend_type]
    create_backend, backend_queue = get_create_backend_queue(create_fn)
    group = aio.Group()
    group.spawn(until_all_messages, backend_queue, group, message_count)
    hat.syslog.server.main.create_backend = create_backend
    hat.syslog.server.main.main()


def get_last_sys_arg():
    ret = sys.argv[-1]
    sys.argv.remove(ret)
    return ret


def get_create_backend_queue(create_fn):

    async def create_wrapper(create_fn, *args, **kwargs):
        backend = await create_fn(*args, **kwargs)
        queue.put_nowait(backend)
        return backend

    queue = aio.Queue()
    create_backend = functools.partial(create_wrapper, create_fn)
    return create_backend, queue


async def until_all_messages(backend_queue, group, message_count):
    backend = await backend_queue.get()
    entry_queue = aio.Queue()
    backend.register_change_cb(lambda i: entry_queue.put_nowait(i))
    while True:
        entries = await entry_queue.get()
        for e in entries:
            if e.id == message_count:
                await backend.async_close()
                group.close()


if __name__ == '__main__':
    sys.exit(main())
