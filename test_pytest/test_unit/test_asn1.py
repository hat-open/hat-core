import pytest
from pathlib import Path

from hat import asn1
from hat import json


def get_encoder(repository, encoding):
    return asn1.Encoder(encoding, repository)


def test_init_repo_file(tmpdir):
    directory = tmpdir.mkdir("schemas_asn1")
    file1 = directory.join("schema1.asn")
    file1.write("""
        Def1 DEFINITIONS ::= BEGIN
            T1 ::= BOOLEAN
        END
    """)
    file2 = directory.join("schema2.asn")
    file2.write("""
        Def2 DEFINITIONS ::= BEGIN
            T1 ::= BOOLEAN
        END
    """)

    repository = asn1.Repository(Path(directory))
    assert sorted(repository.to_json()) == [
        [['TypeRef', 'Def1', 'T1'], ['BooleanType']],
        [['TypeRef', 'Def2', 'T1'], ['BooleanType']]]


def test_init_repo_str():
    repository = asn1.Repository("""
        Def DEFINITIONS ::= BEGIN
            T1 ::= BOOLEAN
        END""")
    assert sorted(repository.to_json()) == [
        [['TypeRef', 'Def', 'T1'], ['BooleanType']]]


def test_init_repo_other_repo():
    repo_base = asn1.Repository("""
        Base DEFINITIONS ::= BEGIN
            T1 ::= BOOLEAN
        END""")
    repo_derived = asn1.Repository(repo_base, """
        Derived DEFINITIONS ::= BEGIN
            T1 ::= SEQUENCE OF Base.T1
        END
        """)
    assert sorted(repo_derived.to_json()) == [
        [['TypeRef', 'Base', 'T1'], ['BooleanType']],
        [['TypeRef', 'Derived', 'T1'], ['SequenceOfType',
                                        ['TypeRef', 'Base', 'T1']]]]


def test_init_repo_json(tmp_path):
    json_data = [[['TypeRef', 'Module', 'T1'], ['BooleanType']]]
    path = tmp_path / 'repo.json'
    json.encode_file(json_data, path)

    repo_file = asn1.Repository.from_json(path)
    repo_str = asn1.Repository.from_json(json_data)

    assert sorted(repo_file.to_json()) == sorted(repo_str.to_json())
    assert sorted(repo_file.to_json()) == sorted(json_data)


@pytest.mark.parametrize("asn1_def,refs_json", [(
    """
        Abc DEFINITIONS ::= BEGIN
        END""", []
    ), (
        """
        Abc DEFINITIONS ::= BEGIN
            T1 ::= BOOLEAN
        END
        """, [
            [['TypeRef', 'Abc', 'T1'], ['BooleanType']]]
    ), (
        """
        Abc DEFINITIONS ::= BEGIN
            T1 ::= ENUMERATED {
                red         (0),
                green       (1),
                blue        (2)
            }
        END
        """, [
            [['TypeRef', 'Abc', 'T1'], ['EnumeratedType']]]
    ), (
        """
        Module DEFINITIONS ::= BEGIN
            T1 ::= SET {
                item1 [0]                      INTEGER OPTIONAL,
                item2 [1]                      UTF8String,
                item3 [APPLICATION 1] IMPLICIT UTF8String
            }
        END
        """, [
            [['TypeRef', 'Module', 'T1'], ['SetType', [
                ['item1', ['PrefixedType', ['IntegerType'], 'CONTEXT_SPECIFIC',
                           0, False], True],
                ['item2', ['PrefixedType', ['StringType', 'UTF8String'],
                           'CONTEXT_SPECIFIC', 1, False], False],
                ['item3', ['PrefixedType', ['StringType', 'UTF8String'],
                           'APPLICATION', 1, True], False]]]]]
    )
])
def test_parse(asn1_def, refs_json):
    repo = asn1.Repository(asn1_def)
    assert sorted(repo.to_json()) == sorted(refs_json)


@pytest.mark.parametrize("asn1_def", ["""
    Module DEFINITIONS ::= BEGIN
        T1 ::= BOOLEAN
        T2 ::= INTEGER
        T3 ::= BIT STRING
        T4 ::= OCTET STRING
        T5 ::= NULL
        T6 ::= OBJECT IDENTIFIER
        T7 ::= UTF8String
        T8 ::= ENUMERATED {
            red     (0),
            green   (1),
            blue    (2)
        }
        T9 ::= EMBEDDED PDV
    END
"""], ids=[''])
@pytest.mark.parametrize("encoding", list(asn1.Encoding))
@pytest.mark.parametrize("name,value", [
    ('T1', True),
    ('T2', 10),
    ('T3', [True, True, False, True]),
    ('T4', b'0123'),
    ('T5', None),
    ('T6', [1, 5, 3]),
    ('T6', [1, 5, 3, 7, 9, 2]),
    ('T6', [1, 0]),
    ('T6', [2, 3, 1]),
    ('T6', [0, 0]),
    ('T7', 'Foo bar'),
    ('T8', 1),
    ('T9', asn1.EmbeddedPDV(data=b'0123', abstract=None, transfer=None)),
])
def test_serialization(asn1_def, encoding, name, value):
    encoder = get_encoder(asn1.Repository(asn1_def), encoding)

    encoded_value = encoder.encode('Module', name, value)
    decoded_value, remainder = encoder.decode('Module', name, encoded_value)

    assert value == decoded_value
    assert len(remainder) == 0


@pytest.mark.parametrize("asn1_def", ["""
    Module DEFINITIONS ::= BEGIN
        T1 ::= CHOICE {
            item1   INTEGER,
            item2   BIT STRING,
            item3   NULL
        }
        T2 ::= SET {
            item1   BOOLEAN,
            item2   INTEGER,
            item3   BIT STRING
        }
        T3 ::= SET OF INTEGER
        T4 ::= SEQUENCE {
            item1   OCTET STRING,
            item2   NULL,
            item3   OBJECT IDENTIFIER
        }
        T5 ::= SEQUENCE OF INTEGER
        T6 ::= SET {
            item1   [APPLICATION 0] IMPLICIT UTF8String,
            item2   [APPLICATION 1] IMPLICIT ENUMERATED {
                red     (0),
                green   (1),
                blue    (2)
            },
            item3   [APPLICATION 2] IMPLICIT EMBEDDED PDV
        }
        T7 ::= SET {
            item1   [0] BOOLEAN,
            item2   [1] EXTERNAL,
            item3   [2] INTEGER
        }

        T8 ::= SET {
            item1   T4,
            item2   T6 OPTIONAL
        }
    END
"""])
@pytest.mark.parametrize("encoding", list(asn1.Encoding))
@pytest.mark.parametrize("name,value", [
    ('T1', ('item2', [True, False, True])),
    ('T2', {'item1': True, 'item2': 100, 'item3': [True, False, True]}),
    ('T3', [1, 2, 3, 4]),
    ('T4', {'item1': b'0123', 'item2': None, 'item3': [1, 2, 3]}),
    ('T5', [1, 2, 3, 4]),
    ('T6', {'item1': 'foo', 'item2': 0,
            'item3': asn1.EmbeddedPDV(None, None, b'0')}),
    ('T7', {'item1': True,
            'item2': asn1.External(b'0123', None, None),
            'item3': 12}),
    ('T8', {'item1': {'item1': b'0123', 'item2': None, 'item3': [1, 2, 3]},
            'item2': {'item1': 'foo', 'item2': 0,
                      'item3': asn1.EmbeddedPDV(None, None, b'0')}}),
    ('T8', {'item1': {'item1': b'0123', 'item2': None, 'item3': [1, 2, 3]}}),
])
def test_serialization_composite(asn1_def, encoding, name, value):
    encoder = get_encoder(asn1.Repository(asn1_def), encoding)

    encoded_value = encoder.encode('Module', name, value)
    decoded_value, remainder = encoder.decode('Module', name, encoded_value)

    assert value == decoded_value
    assert len(remainder) == 0


@pytest.mark.parametrize("encoding", list(asn1.Encoding))
@pytest.mark.parametrize("sequence_size", [1, 20, 50])
def test_serialization_entity(encoding, sequence_size):
    sequence_items = ', '.join([f'item{n} [APPLICATION {n}] OCTET STRING'
                                for n in range(sequence_size)])
    sequence_items = '{' + sequence_items + '}'
    definition = f"""
    Module DEFINITIONS ::= BEGIN
        T1 ::= ABSTRACT-SYNTAX.&Type
        T2 ::= SEQUENCE {sequence_items}
    END"""
    encoder = get_encoder(asn1.Repository(definition), encoding)

    value = {f'item{n}': b'0123' for n in range(sequence_size)}
    entity = encoder.encode_value('Module', 'T2', value)

    encoded = encoder.encode('Module', 'T1', entity)
    decoded_entity, rest = encoder.decode('Module', 'T1', encoded)
    assert decoded_entity == entity
    assert len(rest) == 0
    decoded_value = encoder.decode_value('Module', 'T2', decoded_entity)
    assert decoded_value == value


@pytest.mark.parametrize("encoding", list(asn1.Encoding))
@pytest.mark.parametrize("data_type", ["entity", "bytes", "bitstring"])
@pytest.mark.parametrize("direct_ref", [None, [1, 5, 2, 3, 8]])
@pytest.mark.parametrize("indirect_ref", [None, 11])
def test_serialization_external(encoding, data_type, direct_ref, indirect_ref):
    encoder = get_encoder(asn1.Repository("""
    Module DEFINITIONS ::= BEGIN
        T1 ::= EXTERNAL
        T2 ::= BIT STRING
    END"""), encoding)

    bits = [True, False, False, True]
    data = {
        'entity': encoder.encode_value('Module', 'T2', bits),
        'bytes': encoder.encode('Module', 'T2', bits),
        'bitstring': bits
    }[data_type]

    external = asn1.External(data=data,
                             direct_ref=direct_ref,
                             indirect_ref=indirect_ref)
    encoded = encoder.encode('Module', 'T1', external)
    decoded, rest = encoder.decode('Module', 'T1', encoded)
    assert decoded == external
    assert len(rest) == 0


@pytest.mark.parametrize("encoding", list(asn1.Encoding))
@pytest.mark.parametrize("abstract", [None, 5, [1, 3, 8]])
@pytest.mark.parametrize("transfer", [None, [1, 6, 3]])
def test_serialization_embedded_pdv(encoding, abstract, transfer):
    if isinstance(abstract, list) and transfer is None:
        return

    encoder = get_encoder(asn1.Repository("""
    Module DEFINITIONS ::= BEGIN
        T1 ::= EMBEDDED PDV
        T2 ::= SEQUENCE OF INTEGER
    END"""), encoding)

    data = encoder.encode('Module', 'T2', [1, 2, 3, 9, 8, 7])

    embedded_pdv = asn1.EmbeddedPDV(data=data,
                                    abstract=abstract,
                                    transfer=transfer)
    encoded = encoder.encode('Module', 'T1', embedded_pdv)
    decoded, rest = encoder.decode('Module', 'T1', encoded)
    assert decoded == embedded_pdv
    assert len(rest) == 0


@pytest.mark.parametrize("asn1_def", ["""
    Module DEFINITIONS ::= BEGIN
        T1 ::= REAL
    END
"""])
@pytest.mark.parametrize("encoding", list(asn1.Encoding))
@pytest.mark.parametrize("name,value", [
    ('T1', 10.5)
])
def test_serialization_not_supported(asn1_def, encoding, name, value):
    encoder = get_encoder(asn1.Repository(asn1_def), encoding)

    with pytest.raises(NotImplementedError):
        encoder.encode('Module', name, value)


@pytest.mark.parametrize("asn1_def", ["""
    Module DEFINITIONS ::= BEGIN
        T1 ::= CHOICE {
            item1   INTEGER,
            item2   BOOLEAN,
            item3   BIT STRING
        }
        T2 ::= CHOICE {
            item1   INTEGER,
            item2   BOOLEAN
        }
        T3 ::= SET {
            item1   INTEGER,
            item2   BOOLEAN
        }
        T4 ::= SET {
            item1   INTEGER,
            item2   BOOLEAN,
            item3   BIT STRING
        }
        T5 ::= SEQUENCE {
            item1   INTEGER,
            item2   BOOLEAN
        }
        T6 ::= SEQUENCE {
            item1   INTEGER,
            item2   BOOLEAN,
            item3   BIT STRING
        }
        T7 ::= SEQUENCE {
            item1   INTEGER,
            item2   BOOLEAN,
            xyz     UTF8String
        }
        T8 ::= SEQUENCE {
            item1   INTEGER,
            item2   BOOLEAN,
            item3   BIT STRING
        }
    END
"""], ids=[""])
@pytest.mark.parametrize("encoding", list(asn1.Encoding))
@pytest.mark.parametrize("value,serialize_name,deserialize_name", [
    (('item3', [True, False]), 'T1', 'T2'),
    ({'item1': 1, 'item2': True}, 'T3', 'T4'),
    ({'item1': 1, 'item2': True}, 'T5', 'T6'),
    ({'item1': 1, 'item2': True, 'xyz': 'abc'}, 'T7', 'T8'),
])
def test_invalid_serialization(asn1_def, encoding, value, serialize_name,
                               deserialize_name):
    encoder = get_encoder(asn1.Repository(asn1_def), encoding)
    encoded_value = encoder.encode('Module', serialize_name, value)
    with pytest.raises(Exception):
        encoder.decode('Module', deserialize_name, encoded_value)


@pytest.mark.parametrize("encoding", list(asn1.Encoding))
def test_constructed_as_octet_and_utf8_string(encoding):
    encoder = get_encoder(asn1.Repository("""
    Module DEFINITIONS ::= BEGIN
        T1 ::= SEQUENCE OF OCTET STRING
        T2 ::= OCTET STRING
        T3 ::= UTF8String
    END"""), encoding)

    entity = encoder.encode_value('Module', 'T1', [b'foo', b'bar'])
    assert encoder.decode_value('Module', 'T2', entity) == b'foobar'
    assert encoder.decode_value('Module', 'T3', entity) == 'foobar'


@pytest.mark.parametrize("encoding", list(asn1.Encoding))
def test_constructed_as_bit_string(encoding):
    encoder = get_encoder(asn1.Repository("""
    Module DEFINITIONS ::= BEGIN
        T1 ::= SEQUENCE OF OCTET STRING
        T2 ::= BIT STRING
    END"""), encoding)

    entity = encoder.encode_value(
        'Module', 'T1', [bytes([0, 5]), bytes([0, 15])])
    assert encoder.decode_value('Module', 'T2', entity) == (
        [False, False, False, False, False, True, False, True] +
        [False, False, False, False, True, True, True, True])


@pytest.mark.parametrize("oid1,oid2,expected", [
    ([1, 2, 3], [1, 2, 3], True),
    ([1, ('a', 2), 3], [1, 2, 3], True),
    ([1, 2, 3], [1, 2, ('b', 3)], True),
    ([('c', 1), 2, 3], [1, 2, ('d', 3)], True),
    ([('e', 1), 2, 3], [('f', 1), 2, 3], True),
    ([1, 2, 3], [1, 2], False),
    ([1, 2, 3], [1, 4, 3], False),
])
def test_is_oid_eq(oid1, oid2, expected):
    assert asn1.is_oid_eq(oid1, oid2) is expected


def test_example_docs():
    repo = asn1.Repository(r"""
        Example DEFINITIONS ::= BEGIN
            T ::= SEQUENCE OF CHOICE {
                a BOOLEAN,
                b INTEGER,
                c UTF8String
            }
        END
    """)

    encoder = asn1.Encoder(asn1.Encoding.BER, repo)

    value = [('c', '123'), ('a', True), ('a', False), ('b', 123)]

    encoded = encoder.encode('Example', 'T', value)
    decoded, rest = encoder.decode('Example', 'T', encoded)

    assert value == decoded
    assert len(rest) == 0
