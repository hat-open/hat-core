import pytest

from hat import duktape


def test_eval():
    inter = duktape.Interpreter()
    result = inter.eval("1 + 2")
    assert result == 1 + 2


@pytest.mark.parametrize("val", [
    None,
    0, 1, -1, 12345, -12345,
    0.001, 123.456,
    "", "1", "abc",
    True, False,
    [], [1, 2, 3], [[], [1, 2, ['a', 'b', True]]],
    {}, {'a': 1}, {'b': {'c': {}}}
])
def test_set_get_value(val):
    inter = duktape.Interpreter()
    inter.set('val', val)

    result = inter.get('val')
    assert val == result

    result = inter.eval('val')
    assert val == result


@pytest.mark.parametrize("val", [
    {1: 2}
])
def test_invalid_set_value(val):
    inter = duktape.Interpreter()
    with pytest.raises(Exception):
        inter.set('val', val)


def test_set_function():
    inter = duktape.Interpreter()
    inter.set('f', lambda x: x)
    f = inter.get('f')
    assert f(123) == 123


def test_call_function():
    inter = duktape.Interpreter()
    inter.set('f', lambda x, y: [x, y])

    assert inter.eval('f(1, 2)') == [1, 2]


@pytest.mark.skip("duktape fatal error closes process")
def test_invalid_call_function():
    inter = duktape.Interpreter()
    inter.set('f', lambda x, y: [x, y])

    assert inter.eval('f(1)') == [1, None]
