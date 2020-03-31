from pathlib import Path
import argparse
import contextlib
import io

import pytest

from hat import util


def test_first():
    x = [1, 2, 3]
    assert util.first(x) == 1
    assert util.first([]) is None
    assert util.first(x, lambda x: x > 1) == 2
    assert util.first(x, lambda x: x > 3) is None
    assert util.first([], default=4) == 4


def test_callback_registry():
    counter = 0

    def on_event():
        nonlocal counter
        counter = counter + 1

    registry = util.CallbackRegistry()

    assert counter == 0

    with registry.register(on_event):
        registry.notify()

    assert counter == 1

    registry.notify()

    assert counter == 1


@pytest.mark.parametrize('value_count', [1, 2, 10])
@pytest.mark.parametrize('cb_count', [0, 1, 2, 10])
def test_callback_registry_with_exception_cb(value_count, cb_count):

    def exception_cb(e):
        assert isinstance(e, Exception)
        raised.append(str(e))

    def cb(value):
        raise Exception(value)

    registry = util.CallbackRegistry(exception_cb)
    handlers = [registry.register(cb) for _ in range(cb_count)]

    raised = []
    expected = []
    for value in range(value_count):
        registry.notify(str(value))
        expected.extend(str(value) for _ in range(cb_count))
        assert raised == expected

    for handler in handlers:
        handler.cancel()

    raised = []
    expected = []
    for value in range(value_count):
        registry.notify(str(value))
        assert raised == expected


@pytest.mark.parametrize('cb_count', [1, 2, 10])
def test_callback_registry_without_exception_cb(cb_count):

    def cb():
        nonlocal call_count
        call_count += 1
        raise Exception()

    registry = util.CallbackRegistry()
    for _ in range(cb_count):
        registry.register(cb)

    call_count = 0
    with pytest.raises(Exception):
        registry.notify()
    assert call_count == 1


@pytest.mark.parametrize("query,params", [
    ('', {}),
    ('a=1&b=2', {'a': '1', 'b': '2'}),
    ('a&b=&&=2&c=1', {'a': None, 'b': '', 'c': '1'})
])
def test_parse_url_query(query, params):
    result = util.parse_url_query(query)
    assert result == params


def test_namedtuple():
    with pytest.raises(Exception):
        util.namedtuple('T', ('a', '', 0), 'b')


def test_parse_env_path(monkeypatch):
    path = Path('$A/$B/c')
    with monkeypatch.context() as ctx:
        ctx.setenv("A", "a")
        assert util.parse_env_path(path) == Path('a/./c')
        ctx.delenv("A")
        assert util.parse_env_path(path) == Path('././c')


def test_log_rotating_file_handler(tmp_path, monkeypatch):
    path = tmp_path / '$HATPATH/log.txt'
    with monkeypatch.context() as ctx:
        ctx.setenv('HATPATH', 'hatpath')
        util.parse_env_path(path).parent.mkdir()
        handler = util.LogRotatingFileHandler(path)
        assert handler.baseFilename == str(tmp_path / 'hatpath/log.txt')


def test_env_path_arg_parse_action(monkeypatch, capsys):
    with monkeypatch.context() as ctx:
        ctx.setenv('HATPATH', 'hatpath')
        parser = argparse.ArgumentParser()
        parser.add_argument('--x', action=util.EnvPathArgParseAction)
        args = parser.parse_args(['--x', '$HATPATH/a.txt'])
        assert args.x == Path('hatpath/a.txt')

        def invalid_parse_env_path(*args):
            raise Exception()

        ctx.setattr(util.common, 'parse_env_path', invalid_parse_env_path)
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                parser.parse_args(['--x', '$HATPATH/a.txt'])
