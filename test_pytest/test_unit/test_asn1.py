import pytest
from pathlib import Path

from hat import asn1
from hat.util import json


def get_encoder(repository):
    return asn1.Encoder(asn1.Encoding.BER, repository)


@pytest.mark.parametrize("asn1_def,refs_json", [("""
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
    """, [
        [['TypeRef', 'Abc', 'T1'], ['EnumeratedType']]]
)])
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
        T7 ::= STRING
        T8 ::= EXTERNAL
        T9 ::= EMBEDDEDPDV
        T10 ::= CHOICE {
            item1   INTEGER,
            item2   BIT STRING,
            item3   NULL
        }
        T11 ::= SET {
            item1   INTEGER,
            item2   BIT STRING,
            item3   NULL
        }
        T12 ::= SET OF INTEGER
        T13 ::= SEQUENCE {
            item1   INTEGER,
            item2   INTEGER,
            item3   BIT STRING
        }
        T14 ::= SEQUENCE OF INTEGER
        T15 ::= SET {
            item1   [APPLICATION 0] IMPLICIT INTEGER,
            item2   [APPLICATION 1] IMPLICIT INTEGER,
            item3   [APPLICATION 2] IMPLICIT INTEGER
        }
        T16 ::= SET {
            item1   [0] INTEGER,
            item2   [1] INTEGER,
            item3   [2] INTEGER
        }
    END
"""], ids=[''])
@pytest.mark.parametrize("name,value", [
    ('T1', True),
    ('T2', 10),
    ('T3', [True, True, False, True]),
    ('T4', b'0123'),
    ('T5', None),
    ('T6', [1, 5, 3]),
    ('T7', 'Foo bar'),
    ('T8', asn1.External(data=b'0123', direct_ref=None, indirect_ref=None)),
    ('T9', asn1.EmbeddedPDV(abstract=None, data=b'0123', transfer=None)),
    ('T10', ('item2', [True, False, True])),
    ('T11', {'item1': 10, 'item2': [True, False, True], 'item3': None}),
    ('T12', [1, 2, 3, 4]),
    ('T13', {'item1': 10, 'item2': 11, 'item3': [True, False, True]}),
    ('T14', [1, 2, 3, 4]),
    ('T15', {'item1': 10, 'item2': 11, 'item3': 12}),
    ('T16', {'item1': 10, 'item2': 11, 'item3': 12})
])
def test_serialization(asn1_def, name, value):
    encoder = get_encoder(asn1.Repository(asn1_def))

    encoded_value = encoder.encode('Module', name, value)
    decoded_value, remainder = encoder.decode('Module', name, encoded_value)

    assert value == decoded_value
    assert len(remainder) == 0


@pytest.mark.parametrize("asn1_def", ["""
    Module DEFINITIONS ::= BEGIN
        T1 ::= REAL
    END
"""])
@pytest.mark.parametrize("name,value", [
    ('T1', 10.5)
])
def test_serialization_not_supported(asn1_def, name, value):
    encoder = get_encoder(asn1.Repository(asn1_def))

    with pytest.raises(NotImplementedError):
        encoder.encode('Module', name, value)


@pytest.mark.parametrize("oid1,oid2,expected", [
    ([1, 2, 3], [1, 2, 3], True),
])
def test_is_oid_eq(oid1, oid2, expected):
    assert asn1.is_oid_eq(oid1, oid2) is expected


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
