import pytest
import contextlib
import time
import datetime


measurements = []


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    terminalreporter.write('\nDuration report:\n')
    for i in measurements:
        identifier = i['module'].__name__
        if i['cls']:
            identifier += f"::{i['cls'].__name__}"
        if i['function']:
            identifier += f"::{i['function'].__name__}"
        duration = datetime.timedelta(seconds=i['duration'])
        description = i['description']
        terminalreporter.write(f"> {duration} [{identifier}] {description}\n")


@pytest.fixture
def duration(request):

    @contextlib.contextmanager
    def wrapper(description):
        start = time.monotonic()
        yield
        duration = time.monotonic() - start
        measurements.append({'module': request.module,
                             'cls': request.cls,
                             'function': request.function,
                             'description': description,
                             'duration': duration})

    return wrapper
