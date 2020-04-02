import pytest

from hat import sbs


def test_example():
    repo = sbs.Repository('''
        module Module

        Entry(K, V) = Tuple {
            key: K
            value: V
        }

        T = Array(Maybe(Entry(String, Integer)))
    ''')
    data = [
        ('Nothing', None),
        ('Just', {
            'key': 'abc',
            'value': 123
        })
    ]
    encoded_data = repo.encode('Module', 'T', data)
    decoded_data = repo.decode('Module', 'T', encoded_data)
    assert data == decoded_data


@pytest.mark.parametrize("schema", ["""
    module Module

    T1 = Boolean
    T2 = Integer
    T3 = Float
    T4 = String
    T5 = Bytes

    T6 = Array(Integer)
    T7 = Array(Array(Boolean))
    T8 = Tuple { x: Integer, y: String }
    T9 = Union { x: Integer, y: String }

    T10 = Tuple {}
    T11 = Union {}
    T12 = None
    T13 = Maybe(Integer)

    T14(x) = x
    T15 = T14(Integer)
    T16 = T14(String)

    T17(x) = Array(x)
    T18(y) = T17(y)
    T19 = T18(Maybe(Integer))

    T20 = Array(Float)
"""])
@pytest.mark.parametrize("t,v", [
    ('T1', True),
    ('T1', False),
    ('T2', 0),
    ('T2', 1),
    ('T2', -1),
    ('T2', 128),
    ('T2', -128),
    ('T2', 256),
    ('T2', -256),
    ('T2', 123456789123456789123456789),
    ('T2', -123456789123456789123456789),
    ('T3', 0),
    ('T3', -1),
    ('T3', 1),
    ('T3', 0.5),
    ('T3', -0.5),
    ('T3', 123.456),
    ('T3', -123.456),
    ('T3', 1e25),
    ('T3', -1e25),
    ('T4', ''),
    ('T4', '0'),
    ('T4', 'abcdefg'),
    ('T4', ' \n\'\"\\'),
    ('T5', b''),
    ('T5', b'0'),
    ('T5', b'abcdefg'),
    ('T5', b' \n\'\"\\'),
    ('T6', []),
    ('T6', [1]),
    ('T6', [1, 2, 3, 4, 5]),
    ('T6', list(range(100))),
    ('T7', []),
    ('T7', [[]]),
    ('T7', [[], [], []]),
    ('T7', [[True]]),
    ('T7', [[], [False]]),
    ('T7', [[True], [False], [True, False]]),
    ('T8', {'x': 1, 'y': '1'}),
    ('T9', ('x', 1)),
    ('T9', ('y', '1')),
    ('T10', None),
    ('T11', None),
    ('T12', None),
    ('T13', ('Nothing', None)),
    ('T13', ('Just', 1234)),
    ('T15', 1234),
    ('T16', 'abcd'),
    ('T19', [('Nothing', None), ('Just', 1234)]),
    ('T20', [0, 1.5, -1, 0.005, 1000.1])
])
def test_serialization(schema, t, v):
    repo = sbs.Repository(schema)

    encoded_v = repo.encode('Module', t, v)
    decoded_v = repo.decode('Module', t, encoded_v)

    assert decoded_v == v


def test_loading_schema_file(tmp_path):

    path = tmp_path / 'schema.sbs'
    with open(path, 'w', encoding='utf-8') as f:
        f.write("module M T = Integer")

    repo = sbs.Repository(path)
    value = 123
    encoded_value = repo.encode('M', 'T', value)
    decoded_value = repo.decode('M', 'T', encoded_value)
    assert value == decoded_value


def test_parametrized_types():
    repo = sbs.Repository("""
        module M

        T1(x) = Integer
    """)

    encoded = repo.encode(None, 'Integer', 1)

    with pytest.raises(Exception):
        repo.encode('M', 'T1', 1)

    with pytest.raises(Exception):
        repo.decode('M', 'T1', encoded)


def test_multiple_modules():
    repo = sbs.Repository("""
        module M1

        T = Integer
    """, """
        module M2

        T = M1.T
    """)
    value = 1
    encoded_value = repo.encode('M2', 'T', value)
    decoded_value = repo.decode('M2', 'T', encoded_value)
    assert value == decoded_value


@pytest.mark.parametrize("schema", ["""
    module Module

    T1 = Union { a: Integer }
"""])
@pytest.mark.parametrize("t,v", [
    ('T1', ('b', 1))
])
def test_invalid_serialization(schema, t, v):
    repo = sbs.Repository(schema)
    with pytest.raises(Exception):
        encoded_v = repo.encode('Module', t, v)
        decoded_v = repo.decode('Module', t, encoded_v)
        if v == decoded_v:
            raise Exception()


@pytest.mark.parametrize("schema", ["""
    module Module

    T1(t) = t
    T = T1(Integer, String)
""", """
    module Module

    T1(t) = t(Integer)
    T = T1(Integer)
""", """
    module Module

    T = None(String)
""", """
    module Module

    T = Array
"""])
def test_invalid_schema(schema):
    with pytest.raises(Exception):
        sbs.Repository(schema)


def test_repository_initialization_with_repository():
    repo1 = sbs.Repository("""
        module M

        T = Integer
    """)
    repo2 = sbs.Repository(repo1)

    assert repo1.encode('M', 'T', 1) == repo2.encode('M', 'T', 1)


def test_invalid_repository_initialization_argument_type():
    with pytest.raises(Exception):
        sbs.Repository(None)
