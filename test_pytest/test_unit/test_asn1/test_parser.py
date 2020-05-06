from hat.asn1 import common
from hat.asn1 import parser


def test_minimal_modules():
    refs = parser.parse(r"""
        Abc DEFINITIONS ::= BEGIN
            T1 ::= BOOLEAN
            T2 ::= INTEGER
            T3 ::= BIT STRING
            T4 ::= OCTET STRING
            T5 ::= NULL
            T6 ::= OBJECT IDENTIFIER
            T7 ::= UTF8String
            T8 ::= VisibleString
            T9 ::= EXTERNAL
            T10 ::= CHOICE {
                a INTEGER,
                b NULL,
                c T1,
                d Abc.T2
            }
            T11 ::= SET {
                abc [0] INTEGER,
                xyz     NULL
            }
            T12 ::= SET OF T3
        END
        Xyz DEFINITIONS ::= BEGIN
            IMPORTS T1 FROM Abc;
        END
    """)
    assert refs == {
        common.TypeRef('Abc', 'T1'): common.BooleanType(),
        common.TypeRef('Abc', 'T2'): common.IntegerType(),
        common.TypeRef('Abc', 'T3'): common.BitStringType(),
        common.TypeRef('Abc', 'T4'): common.OctetStringType(),
        common.TypeRef('Abc', 'T5'): common.NullType(),
        common.TypeRef('Abc', 'T6'): common.ObjectIdentifierType(),
        common.TypeRef('Abc', 'T7'): common.StringType.UTF8String,
        common.TypeRef('Abc', 'T8'): common.StringType.VisibleString,
        common.TypeRef('Abc', 'T9'): common.ExternalType(),
        common.TypeRef('Abc', 'T10'): common.ChoiceType([
            common.TypeProperty('a', common.IntegerType()),
            common.TypeProperty('b', common.NullType()),
            common.TypeProperty('c', common.TypeRef('Abc', 'T1')),
            common.TypeProperty('d', common.TypeRef('Abc', 'T2'))]),
        common.TypeRef('Abc', 'T11'): common.SetType([
            common.TypeProperty(
                'abc', common.PrefixedType(common.IntegerType(),
                                           common.ClassType.CONTEXT_SPECIFIC,
                                           0,
                                           False)),
            common.TypeProperty('xyz', common.NullType())]),
        common.TypeRef('Abc', 'T12'): common.SetOfType(
            common.TypeRef('Abc', 'T3'))
    }
