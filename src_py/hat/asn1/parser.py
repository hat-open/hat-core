import itertools
import typing

from hat import util
from hat import peg
from hat.asn1 import common


def parse(asn1_def: str
          ) -> typing.Dict[common.TypeRef, common.Type]:
    """Parse ASN.1"""
    ast = _grammar.parse(asn1_def)
    refs = peg.walk_ast(ast, _actions)
    return refs


def _act_Root(n, c):
    return dict(itertools.chain.from_iterable(i.items() for i in c if i))


def _act_ModuleDefinition(n, c):
    name = c[0]
    default_implicit = c[4]
    imports = c[11]
    types = c[12]

    def sanitize(t):
        if isinstance(t, common.PrefixedType):
            return t._replace(type=sanitize(t.type),
                              implicit=(t.implicit if t.implicit is not None
                                        else default_implicit))
        if (isinstance(t, common.SetOfType) or
                isinstance(t, common.SequenceOfType)):
            return t._replace(type=sanitize(t.type))
        if isinstance(t, common.SetType) or isinstance(t, common.SequenceType):
            return t._replace(elements=[i._replace(type=sanitize(i.type))
                                        for i in t.elements])
        if isinstance(t, common.ChoiceType):
            return t._replace(choices=[i._replace(type=sanitize(i.type))
                                       for i in t.choices])
        if isinstance(t, common.TypeRef):
            if t == common.TypeRef('ABSTRACT-SYNTAX', 'Type'):
                return common.EntityType()
            if t.module:
                return t
            if t not in types:
                import_ref = util.first(imports, lambda i: i.name == t.name)
                if import_ref:
                    return t._replace(module=import_ref.module)
            return t._replace(module=name)
        return t

    return {ref._replace(module=name): sanitize(t)
            for ref, t in types.items()}


def _act_TagDefault(n, c):
    if not c:
        return False
    return {'EXPLICIT TAGS': False,
            'IMPLICIT TAGS': True,
            'AUTOMATIC TAGS': True}[c[0]]


def _act_Imports(n, c):
    return list(itertools.chain.from_iterable(i for i in c[2:-2]))


def _act_Type(n, c):
    if c[0] is None:
        return common.UnsupportedType()
    return c[0]


def _act_TypeWithConstraint(n, c):
    cls = {'SET': common.SetOfType,
           'SEQUENCE': common.SequenceOfType}[c[0]]
    t = c[-1].type if isinstance(c[-1], common.TypeProperty) else c[-1]
    return cls(t)


def _act_CharacterStringType(n, c):
    return {'BMPString': common.StringType.BMPString,
            'GeneralString': common.StringType.GeneralString,
            'GeneralizedTime': common.StringType.GeneralizedTime,
            'GraphicString': common.StringType.GraphicString,
            'IA5String': common.StringType.IA5String,
            'ISO646String': common.StringType.VisibleString,
            'NumericString': common.StringType.NumericString,
            'ObjectDescriptor': common.StringType.ObjectDescriptor,
            'PrintableString': common.StringType.PrintableString,
            'TeletexString': common.StringType.T61String,
            'T61String': common.StringType.T61String,
            'UniversalString': common.StringType.UniversalString,
            'UTF8String': common.StringType.UTF8String,
            'VideotexString': common.StringType.VideotexString,
            'VisibleString': common.StringType.VisibleString,
            'CHARACTER STRING': common.StringType.CHARACTER_STRING}.get(c[0])


def _act_ReferencedType(n, c):
    if n.value[0].name == 'modulereference':
        return common.TypeRef(c[0], c[3])
    elif n.value[0].name == 'typereference':
        return common.TypeRef(None, c[0])
    return common.UnsupportedType()


def _act_ChoiceElement(n, c):
    return c[0] if isinstance(c[0], common.TypeProperty) else None


def _act_SetOfType(n, c):
    t = c[-1] if n.value[-1].name == 'Type' else c[-1].type
    return common.SetOfType(t)


def _act_SequenceOfType(n, c):
    t = c[-1] if n.value[-1].name == 'Type' else c[-1].type
    return common.SequenceOfType(t)


def _act_ComponentTypeList(n, c):
    extension = False
    components = []
    for i in c:
        if i == '...':
            extension = True
        if not i or i == ',' or i == '...':
            continue
        if extension:
            i = i._replace(optional=True)
        components.append(i)
    return components


def _act_ComponentType(n, c):
    if c[0] == 'COMPONENTS OF':
        return
    if len(c) > 1:
        return c[0]._replace(optional=True)
    return c[0]


def _act_PrefixedType(n, c):
    if len(c) != 9:
        return
    tag_number = c[4]
    if tag_number is None:
        return
    return common.PrefixedType(type=c[8],
                               class_type=c[3],
                               tag_number=tag_number,
                               implicit=c[7])


def _act_PrefixedImplicit(n, c):
    if not c:
        return
    return {'IMPLICIT': True,
            'EXPLICIT': False}[c[0]]


def _act_ClassNumber(n, c):
    return c[0] if n.value[0].name == 'number' else None


def _act_Class(n, c):
    if not c:
        return common.ClassType.CONTEXT_SPECIFIC
    return {'UNIVERSAL': common.ClassType.UNIVERSAL,
            'APPLICATION': common.ClassType.APPLICATION,
            'PRIVATE': common.ClassType.PRIVATE}[c[0]]


def _filter_None(x):
    return (i for i in x if i is not None)


_actions = {
    # Root
    'Root': _act_Root,

    # Module definition
    'ModuleDefinition': _act_ModuleDefinition,
    'ModuleIdentifier': lambda n, c: c[0],
    'TagDefault': _act_TagDefault,
    'Imports': _act_Imports,
    'SymbolsFromModule': lambda n, c: [common.TypeRef(c[3], i) for i in c[0]],
    'SymbolList': lambda n, c: [i for i in c if i and i != ','],
    'Symbol': lambda n, c: c[0],
    'Reference': lambda n, c: c[0],

    # Assignments
    'AssignmentList': lambda n, c: dict(_filter_None(c)),
    'Assignment': lambda n, c: c[0],
    'TypeAssignment': lambda n, c: (common.TypeRef(None, c[0]), c[-1]),

    # Types
    'Type': _act_Type,
    'TypeWithConstraint': _act_TypeWithConstraint,
    'ReferencedType': _act_ReferencedType,
    'NamedType': lambda n, c: common.TypeProperty(c[0], c[1]),
    'BuiltinType': lambda n, c: c[0],
    'BooleanType': lambda n, c: common.BooleanType(),
    'IntegerType': lambda n, c: common.IntegerType(),
    'BitStringType': lambda n, c: common.BitStringType(),
    'OctetStringType': lambda n, c: common.OctetStringType(),
    'NullType': lambda n, c: common.NullType(),
    'ObjectClassFieldType': lambda n, c: common.TypeRef(c[0], c[-1]),
    'ObjectIdentifierType': lambda n, c: common.ObjectIdentifierType(),
    'CharacterStringType': _act_CharacterStringType,
    'UnrestrictedCharacterStringType': lambda n, c: c[0],
    'RestrictedCharacterStringType': lambda n, c: c[0],
    'RealType': lambda n, c: common.RealType(),
    'EmbeddedPDVType': lambda n, c: common.EmbeddedPDVType(),
    'EnumeratedType': lambda n, c: common.EnumeratedType(),
    'ExternalType': lambda n, c: common.ExternalType(),
    'ChoiceType': lambda n, c: common.ChoiceType(c[4]),
    'ChoiceList': lambda n, c: [i for i in c if i and i != ','],
    'ChoiceElement': _act_ChoiceElement,
    'SetType': lambda n, c: common.SetType(c[4]),
    'SetOfType': _act_SetOfType,
    'SequenceType': lambda n, c: common.SequenceType(c[4]),
    'SequenceOfType': _act_SequenceOfType,
    'ComponentTypeList': _act_ComponentTypeList,
    'ComponentType': _act_ComponentType,
    'PrefixedType': _act_PrefixedType,
    'PrefixedImplicit': _act_PrefixedImplicit,
    'ClassNumber': _act_ClassNumber,
    'Class': _act_Class,

    # ObjectClass
    'DefinedObjectClass': lambda n, c: list(_filter_None(c))[-1],

    # Other
    'FieldName': lambda n, c: '.&'.join(i for i in c if i and i != '.'),
    'PrimitiveFieldName': lambda n, c: c[0],

    # Extended lexical items
    'valuereference': lambda n, c: c[0],
    'modulereference': lambda n, c: c[0],
    'xmlasn1typename': lambda n, c: c[0],
    'objectclassreference': lambda n, c: c[0],
    'objectreference': lambda n, c: c[0],
    'objectsetreference': lambda n, c: c[0],
    'word': lambda n, c: c[0],
    'typefieldreference': lambda n, c: c[1],
    'valuefieldreference': lambda n, c: c[1],
    'valuesetfieldreference': lambda n, c: c[1],
    'objectfieldreference': lambda n, c: c[1],
    'objectsetfieldreference': lambda n, c: c[1],

    # Lexical items
    'typereference': lambda n, c: ''.join(c[:-1]),
    'identifier': lambda n, c: ''.join(c[:-1]),
    'number': lambda n, c: int(''.join(c[:-1])),
    'realnumber': lambda n, c: float(''.join(c[:-1])),
    'bstring': lambda n, c: ''.join(_filter_None(c[1:-2])),
    'xmlbstring': lambda n, c: ''.join(_filter_None(c[:-1])),
    'hstring': lambda n, c: ''.join(_filter_None(c[1:-2])),
    'xmlhstring': lambda n, c: ''.join(_filter_None(c[:-1])),
    'cstring': lambda n, c: ''.join('"' if i == '""' else i for i in c[1:-2]),
    'xmlcstring': lambda n, c: ''.join(c[:-1]),
    'simplestring': lambda n, c: ''.join(c[1:-2]),
    'tstring': lambda n, c: ''.join(c[1:-2]),
    'xmltstring': lambda n, c: ''.join(c[:-1]),
    'psname': lambda n, c: ''.join(c[:-1]),
    'encodingreference': lambda n, c: ''.join(c[:-1]),
    'integerUnicodeLabel': lambda n, c: int(''.join(c[:-1])),
    'non_integerUnicodeLabel': lambda n, c: ''.join(c[:-1]),
    'extended_true': lambda n, c: True,
    'extended_false': lambda n, c: False

}


_grammar = peg.Grammar(r"""

## Root #######################################################################

Root  <- OS ModuleDefinition* EOF


## Module definition ##########################################################

ModuleDefinition              <- ModuleIdentifier
                                'DEFINITIONS' OS
                                 EncodingReferenceDefault
                                 TagDefault
                                 ExtensionDefault
                                 '::=' OS 'BEGIN' OS
                                 Exports
                                 Imports
                                 AssignmentList
                                 EncodingControlSectionList
                                 'END' OS
ModuleIdentifier              <- modulereference DefinitiveIdentification?
DefinitiveIdentification      <- DefinitiveOID IRIValue?
DefinitiveOID                 <- '{' OS DefinitiveObjIdComponent+ '}' OS
DefinitiveObjIdComponent      <- identifier ("(" OS number ")" OS)?
                               / number
EncodingReferenceDefault      <- (encodingreference 'INSTRUCTIONS' OS)?
TagDefault                    <- ( 'EXPLICIT TAGS' OS
                                 / 'IMPLICIT TAGS' OS
                                 / 'AUTOMATIC TAGS' OS)?
ExtensionDefault              <- ('EXTENSIBILITY IMPLIED' OS)?
Exports                       <- ( 'EXPORTS ALL' OS ';' OS
                                 / 'EXPORTS' OS SymbolList? ';' OS)?
SymbolList                    <- Symbol (',' OS Symbol)*
Symbol                        <- Reference ('{' OS '}' OS)?
Reference                     <- typereference
                               / valuereference
                               / objectclassreference
                               / objectreference
                               / objectsetreference
Imports                       <- ('IMPORTS' OS SymbolsFromModule* ';' OS)?
SymbolsFromModule             <- SymbolList 'FROM' OS modulereference
                                 (ObjectIdentifierValue / DefinedValue)?
EncodingControlSectionList    <- EncodingControlSection*
EncodingControlSection        <- 'ENCODING-CONTROL' OS
                                 encodingreference encodingreference+


## Assignments ################################################################

AssignmentList          <- Assignment*
Assignment              <- TypeAssignment
                         / ValueAssignment
                         / XMLValueAssignment
                         / ValueSetTypeAssignment
                         / ObjectClassAssignment
                         / ObjectAssignment
                         / ObjectSetAssignment
TypeAssignment          <- typereference
                           ParameterList?
                           '::=' OS Type
ValueAssignment         <- valuereference
                           ParameterList?
                           Type
                           '::=' OS Value
XMLValueAssignment      <- valuereference
                           '::=' OS XMLTypedValue
ValueSetTypeAssignment  <- typereference
                           ParameterList?
                           Type
                           '::=' OS ValueSet
ObjectClassAssignment   <- objectclassreference
                           ParameterList?
                           '::=' OS
                           ObjectClass
ObjectAssignment        <- objectreference
                           ParameterList?
                           DefinedObjectClass
                           '::=' OS Object
ObjectSetAssignment     <- objectsetreference
                           ParameterList?
                           DefinedObjectClass
                           '::=' OS ObjectSet
ParameterList           <- '{' OS Parameter (',' OS Parameter)* '}' OS
Parameter               <- (( Reference
                            / Type
                            / DefinedObjectClass) ':' OS)?
                           Reference
Reference               <- typereference
                         / valuereference
                         / objectclassreference
                         / objectreference
                         / objectsetreference


## Types ######################################################################

Type                 <- TypeWithConstraint
                      / BuiltinType Constraint?
                      / !('CLASS' OS '{' OS) ReferencedType Constraint?
TypeWithConstraint   <- 'SET' OS
                        SizeConstraint
                        'OF' OS
                        (NamedType / Type)
                      / 'SET' OS
                        Constraint
                        'OF' OS
                        (NamedType / Type)
                      / 'SEQUENCE' OS
                        SizeConstraint
                        'OF' OS
                        (NamedType / Type)
                      / 'SEQUENCE' OS
                        Constraint
                        'OF' OS
                        (NamedType / Type)
NamedType            <- identifier Type
BuiltinType          <- BitStringType
                      / BooleanType
                      / CharacterStringType
                      / ChoiceType
                      / DateType
                      / DateTimeType
                      / DurationType
                      / EmbeddedPDVType
                      / EnumeratedType
                      / ExternalType
                      / InstanceOfType
                      / IntegerType
                      / IRIType
                      / NullType
                      / ObjectClassFieldType
                      / ObjectIdentifierType
                      / OctetStringType
                      / RealType
                      / RelativeIRIType
                      / RelativeOIDType
                      / SequenceType
                      / SequenceOfType
                      / SetType
                      / SetOfType
                      / PrefixedType
                      / TimeType
                      / TimeOfDayType
ReferencedType       <- modulereference '.' OS typereference
                        ActualParameterList?
                      / typereference ActualParameterList?
                      / identifier '<' OS Type
                      / ReferencedObjects '.' OS FieldName
ActualParameterList  <- '{' OS ActualParameter (',' OS ActualParameter)* '}' OS
ActualParameter      <- Type
                      / Value
                      / ValueSet
                      / DefinedObjectClass
                      / Object
                      / ObjectSet
VersionNumber        <- number

## BitString
BitStringType  <- 'BIT STRING' OS '{' OS NamedBitList '}' OS
                / 'BIT STRING' OS
NamedBitList   <- NamedBit (',' OS NamedBit)*
NamedBit       <- identifier '(' OS number ')' OS
                / identifier '(' OS DefinedValue ')' OS

## Boolean
BooleanType  <- 'BOOLEAN' OS

## CharacterString
CharacterStringType              <- RestrictedCharacterStringType
                                  / UnrestrictedCharacterStringType
RestrictedCharacterStringType    <- 'BMPString' OS
                                  / 'GeneralString' OS
                                  / 'GeneralizedTime' OS
                                  / 'GraphicString' OS
                                  / 'IA5String' OS
                                  / 'ISO646String' OS
                                  / 'NumericString' OS
                                  / 'ObjectDescriptor' OS
                                  / 'PrintableString' OS
                                  / 'TeletexString' OS
                                  / 'T61String' OS
                                  / 'UniversalString' OS
                                  / 'UTF8String' OS
                                  / 'VideotexString' OS
                                  / 'VisibleString' OS
UnrestrictedCharacterStringType  <- 'CHARACTER STRING' OS

## Choice
ChoiceType                         <- 'CHOICE' OS '{' OS ChoiceList '}' OS
ChoiceList                         <- ChoiceElement (',' OS ChoiceElement)*
ChoiceElement                      <- NamedType
                                    / '...' OS
                                      ('!' OS ExceptionIdentification)?
                                    / '[[' OS
                                      (VersionNumber ':' OS)?
                                      NamedType (',' OS NamedType)*
                                      ']]' OS


## Date
DateType  <- 'DATE' OS

## DateTime
DateTimeType  <- 'DATE-TIME' OS

## Duration
DurationType  <- 'DURATION' OS

## EmbeddedPDV
EmbeddedPDVType  <- 'EMBEDDED PDV' OS

## Enumerated
EnumeratedType   <- 'ENUMERATED' OS '{' OS Enumeration
                    (',' OS '...' OS
                     ('!' OS ExceptionIdentification)?
                     (',' OS Enumeration)?)? '}' OS
Enumeration      <- EnumerationItem (',' OS EnumerationItem)*
EnumerationItem  <- NamedNumber
                  / identifier

## External
ExternalType  <- 'EXTERNAL' OS

## InstanceOf
InstanceOfType  <- 'INSTANCE OF' OS DefinedObjectClass

## Integer
IntegerType      <- 'INTEGER' OS ('{' OS NamedNumberList '}' OS)?
NamedNumberList  <- NamedNumber (',' OS NamedNumber)*
NamedNumber      <- identifier '(' OS SignedNumber ')' OS
                  / identifier '(' OS DefinedValue ')' OS

## IRI
IRIType  <- 'OID-IRI' OS

## Null
NullType  <- 'NULL' OS

## ObjectClassField
ObjectClassFieldType  <- DefinedObjectClass '.' OS FieldName

## ObjectIdentifier
ObjectIdentifierType  <- 'OBJECT IDENTIFIER' OS

## OctetString
OctetStringType  <- 'OCTET STRING' OS

## Real
RealType  <- 'REAL' OS

## RelativeIRI
RelativeIRIType  <- 'RELATIVE-OID-IRI' OS

## RelativeOID
RelativeOIDType  <- 'RELATIVE-OID' OS

## Sequence
SequenceType       <- 'SEQUENCE' OS '{' OS ComponentTypeList '}' OS
ComponentTypeList  <- (ComponentType / '...' OS)
                      (',' OS (ComponentType / '...' OS))*
ComponentType      <- 'COMPONENTS OF' OS Type
                    / NamedType 'OPTIONAL' OS
                    / NamedType 'DEFAULT' OS Value
                    / NamedType

## SequenceOf
SequenceOfType  <- 'SEQUENCE OF' OS (NamedType / Type)

## Set
SetType  <- 'SET' OS '{' OS ComponentTypeList '}' OS

## SetOf
SetOfType  <- 'SET OF' OS (NamedType / Type)

## Prefixed
PrefixedType       <- '[' OS PrefixedReference Class ClassNumber ']' OS
                      PrefixedImplicit Type
                    / '[' OS PrefixedReference PrefixedReference ']' OS
                      Type
PrefixedReference  <- (encodingreference ':' OS)?
PrefixedImplicit   <- ( 'IMPLICIT' OS
                      / 'EXPLICIT' OS)?
ClassNumber        <- number
                    / DefinedValue
Class              <- ( 'UNIVERSAL' OS
                      / 'APPLICATION' OS
                      / 'PRIVATE' OS)?

## Time
TimeType  <- 'TIME' OS

## TimeOfDay
TimeOfDayType  <- 'TIME-OF-DAY' OS


## Values #####################################################################

Value                  <- BuiltinValue
                        / ReferencedValue
                        / OpenTypeFieldVal
BuiltinValue           <- NullValue
                        / BooleanValue
                        / 'CONTAINING' OS Value
                        / bstring
                        / hstring
                        / SignedNumber
                        / RealValue
                        / identifier ':' OS Value
                        / identifier
                        / cstring
                        / '{' OS (identifier (',' OS identifier)*)? '}' OS
                        / '{' OS CharsDefn (',' OS CharsDefn)* '}' OS
                        / '{' OS number ',' OS number ',' OS
                          number ',' OS number '}' OS
                        / '{' OS number ',' OS number '}' OS
                        / '{' OS (NamedValue (',' OS NamedValue)*)? '}' OS
                        / '{' OS NamedValue* '}' OS
                        / '{' OS (Value (',' OS Value)*)? '}' OS
                        / IRIValue
                        / RelativeIRIValue
                        / ObjectIdentifierValue
                        / RelativeOIDValue
                        / tstring
ReferencedValue        <- DefinedValue
                        / ValueFromObject
DefinedValue           <- (modulereference '.' OS)?
                          valuereference ActualParameterList?
ValueFromObject        <- ReferencedObjects '.' OS FieldName
OpenTypeFieldVal       <- Type ':' OS Value
BooleanValue           <- ('TRUE' / 'FALSE') OS
NullValue              <- 'NULL' OS
NamedValue             <- identifier Value
CharsDefn              <- cstring
                        / '{' OS number ',' OS number ',' OS
                          number ',' OS number '}' OS
                        / '{' OS number ',' OS number '}' OS
                        / DefinedValue
SignedNumber           <- ('-' OS)? number
RealValue              <- 'PLUS-INFINITY' OS
                        / 'MINUS-INFINITY' OS
                        / 'NOT-A-NUMBER' OS
                        / ('-' OS)? realnumber
IRIValue               <- '"' OS
                          ('/' OS
                           (integerUnicodeLabel / non_integerUnicodeLabel))+
                          '"' OS
RelativeIRIValue       <- '"' OS
                          (integerUnicodeLabel / non_integerUnicodeLabel)
                          ('/' OS
                           (integerUnicodeLabel / non_integerUnicodeLabel))*
                          '"' OS
ObjectIdentifierValue  <- '{' OS ObjIdComponents+ '}' OS
                        / '{' OS DefinedValue ObjIdComponents+ '}' OS
ObjIdComponents        <- identifier ('(' OS (number / DefinedValue) ')' OS)?
                        / number
                        / DefinedValue
RelativeOIDValue       <- '{' OS RelativeOIDComponents+ '}' OS
RelativeOIDComponents  <- identifier '(' OS (number / DefinedValue) ')' OS
                        / number
                        / DefinedValue


## XMLValue ###################################################################

XMLValue                    <- XMLBuiltinValue
                             / XMLObjectClassFieldValue
XMLBuiltinValue             <- XMLBitStringValue
                             / XMLBooleanValue
                             / XMLCharacterStringValue
                             / XMLChoiceValue
                             / XMLEmbeddedPDVValue
                             / XMLEnumeratedValue
                             / XMLExternalValue
                             / XMLIntegerValue
                             / XMLIRIValue
                             / XMLNullValue
                             / XMLObjectIdentifierValue
                             / XMLOctetStringValue
                             / XMLRealValue
                             / XMLRelativeIRIValue
                             / XMLRelativeOIDValue
                             / XMLSequenceValue
                             / XMLSequenceOfValue
                             / XMLSetValue
                             / XMLSetOfValue
                             / XMLTimeValue
XMLObjectClassFieldValue    <- XMLOpenTypeFieldVal
                             / XMLFixedTypeFieldVal
XMLOpenTypeFieldVal         <- XMLTypedValue
XMLFixedTypeFieldVal        <- XMLBuiltinValue
XMLTypedValue               <- '<' NonParameterizedTypeName '>' OS
                               XMLValue
                               '</' NonParameterizedTypeName '>' OS
                             / '<' NonParameterizedTypeName '/>' OS
XMLBitStringValue           <- ( XMLTypedValue
                             / xmlbstring
                             / XMLIdentifierList)?
XMLIdentifierList           <- EmptyElementList
                             / TextList
EmptyElementList            <- ('<' identifier '/>' OS)+
TextList                    <- identifier+
XMLBooleanValue             <- EmptyElementBoolean
                             / TextBoolean
EmptyElementBoolean         <- '<' 'true' '/>' OS
                             / '<' 'false' '/>' OS
TextBoolean                 <- extended_true
                             / extended_false
XMLCharacterStringValue     <- XMLRestrictedCharacterStringValue
                             / XMLUnrestrictedCharacterStringValue
XMLRestrictedCharacterStringValue    <- xmlcstring
XMLUnrestrictedCharacterStringValue  <- XMLSequenceValue
XMLSequenceValue            <- XMLComponentValueList?
XMLComponentValueList       <- XMLNamedValue+
XMLNamedValue               <- '<' identifier '>' OS
                               XMLValue
                               '</' identifier '>' OS
XMLChoiceValue              <- '<' identifier '>' OS
                               XMLValue
                               '</' identifier '>' OS
XMLEmbeddedPDVValue         <- XMLSequenceValue
XMLEnumeratedValue          <- EmptyElementEnumerated
                             / TextEnumerated
XMLExternalValue            <- XMLSequenceValue
EmptyElementEnumerated      <- '<' identifier '/>' OS
TextEnumerated              <- identifier
XMLIntegerValue             <- XMLSignedNumber
                             / EmptyElementInteger
                             / TextInteger
XMLSignedNumber             <- ('-' OS)? number
EmptyElementInteger         <- '<' identifier '>' OS
TextInteger                 <- identifier
XMLIRIValue                 <- ('/' OS
                                ( integerUnicodeLabel
                                / non_integerUnicodeLabel))+
XMLNullValue                <- ()
XMLObjectIdentifierValue    <- XMLObjIdComponentList
XMLObjIdComponentList       <- XMLObjIdComponent ('.' OS XMLObjIdComponent)*
XMLObjIdComponent           <- identifier
                             / XMLNumberForm
                             / XMLNameAndNumberForm
XMLNumberForm               <- number
XMLNameAndNumberForm        <- identifier '(' OS XMLNumberForm ')' OS
XMLOctetStringValue         <- XMLTypedValue
                             / xmlhstring
XMLRealValue                <- XMLNumericRealValue
                             / XMLSpecialRealValue
XMLNumericRealValue         <- ('-' OS)? realnumber
XMLSpecialRealValue         <- EmptyElementReal
                             / TextReal
EmptyElementReal            <- '<' 'PLUS-INFINITY' '/>' OS
                             / '<' 'MINUS-INFINITY' '/>' OS
                             / '<' 'NOT-A-NUMBER' '/>' OS
TextReal                    <- 'INF' OS
                             / '-' OS 'INF' OS
                             / 'NaN' OS
XMLRelativeIRIValue         <- (integerUnicodeLabel / non_integerUnicodeLabel)
                               ('/' OS
                                ( integerUnicodeLabel
                                / non_integerUnicodeLabel))*
XMLRelativeOIDValue         <- XMLRelativeOIDComponentList
XMLRelativeOIDComponentList <- XMLRelativeOIDComponent
                               ('.' OS XMLRelativeOIDComponentList)*
XMLRelativeOIDComponent     <- XMLNumberForm
                             / XMLNameAndNumberForm
XMLSequenceOfValue          <- ( XMLValueList
                               / XMLDelimitedItemList)?
XMLValueList                <- XMLValueOrEmpty+
XMLValueOrEmpty             <- XMLValue
                             / '<' NonParameterizedTypeName '/>' OS
XMLDelimitedItemList        <- XMLDelimitedItem+
XMLDelimitedItem            <- '<' NonParameterizedTypeName '>' OS
                               XMLValue
                               '</' NonParameterizedTypeName '>' OS
                             / '<' identifier '>' OS
                               XMLValue
                               '</' identifier '>' OS
NonParameterizedTypeName    <- (modulereference '.' OS)? typereference
                             / xmlasn1typename
XMLSetValue                 <- XMLComponentValueList?
XMLSetOfValue               <- ( XMLValueList
                               / XMLDelimitedItemList)?
XMLTimeValue                <- xmltstring


## ValueSet ###################################################################

ValueSet                       <- '{' OS ElementSetSpecs '}' OS
ElementSetSpecs                <- '...' OS
                                  (',' OS '...' OS (',' OS ElementSetSpec)?)?
                                / ElementSetSpec
                                  (',' OS '...' OS (',' OS ElementSetSpec)?)?
ElementSetSpec                 <- 'ALL' OS 'EXCEPT' OS Elements
                                / Unions
Unions                         <- Intersections
                                  (('|' OS / 'UNION' OS) Intersections)*
Intersections                  <- IntersectionElements
                                  (('^' OS / 'INTERSECTION' OS)
                                   IntersectionElements)*
IntersectionElements           <- Elements ('EXCEPT' OS Elements)?
Elements                       <- SubtypeElements
                                / ObjectSetElements
                                / '(' OS ElementSetSpec ')' OS
SubtypeElements                <- SizeConstraint
                                / 'FROM' OS Constraint
                                / 'WITH COMPONENT' OS Constraint
                                / 'WITH COMPONENTS' OS '{' OS
                                  ('...' OS ',' OS)?
                                  NamedConstraint
                                  (',' OS NamedConstraint)* '}' OS
                                / 'PATTERN' OS Value
                                / 'SETTINGS' OS (psname '=' OS psname)+
                                / ('MIN' OS / Value)
                                  ('<' OS)? '..' OS ('<' OS)?
                                  ('MAX' OS / Value)
                                / Value
                                / ('INCLUDES' OS)? Type
Constraint                     <- '(' OS (GeneralConstraint / ElementSetSpecs)
                                  ('!' OS ExceptionIdentification)? ')' OS
SizeConstraint                 <- 'SIZE' OS Constraint
NamedConstraint                <- identifier Constraint?
                                  ( 'PRESENT' OS
                                  / 'ABSENT' OS
                                  / 'OPTIONAL' OS)?
GeneralConstraint              <- 'CONSTRAINED BY' OS '{' OS
                                  (UserDefinedConstraintParameter
                                   (',' OS UserDefinedConstraintParameter)*)?
                                  '}' OS
                                / 'CONTAINING' OS Type ('ENCODED BY' OS Value)?
                                / 'ENCODED BY' OS Value
                                / '{' OS DefinedObjectSet '}' OS
                                  '{' OS AtNotation (',' OS AtNotation)* '}' OS
                                / ObjectSet
UserDefinedConstraintParameter <- (DefinedObjectClass / Type) ':' OS Value
                                / (DefinedObjectClass / Type) ':' OS ValueSet
                                / (DefinedObjectClass / Type) ':' OS Object
                                / (DefinedObjectClass / Type) ':' OS ObjectSet
                                / Type
                                / DefinedObjectClass
ExceptionIdentification        <- SignedNumber
                                / DefinedValue
                                / Type ':' OS Value
AtNotation                     <- '@' OS ('.' OS)*
                                  identifier ('.' OS identifier)*


## ObjectClass ################################################################

ObjectClass                   <- ObjectClassDefn
                               / DefinedObjectClass ActualParameterList?
DefinedObjectClass            <- 'TYPE-IDENTIFIER' OS
                               / 'ABSTRACT-SYNTAX' OS
                               / (modulereference '.' OS objectclassreference)?
                                 objectclassreference
ObjectClassDefn               <- 'CLASS' OS '{' OS
                                 FieldSpec (',' OS FieldSpec)* '}' OS
                                 WithSyntaxSpec?
FieldSpec                     <- FixedTypeValueFieldSpec
                               / VariableTypeValueFieldSpec
                               / FixedTypeValueSetFieldSpec
                               / VariableTypeValueSetFieldSpec
                               / ObjectFieldSpec
                               / ObjectSetFieldSpec
                               / TypeFieldSpec
WithSyntaxSpec                <- 'WITH SYNTAX' OS
                                 '{' OS TokenOrGroupSpec+ '}' OS
TypeFieldSpec                 <- typefieldreference TypeOptionalitySpec?
FixedTypeValueFieldSpec       <- valuefieldreference Type ('UNIQUE' OS)?
                                 ValueOptionalitySpec?
VariableTypeValueFieldSpec    <- valuefieldreference FieldName
                                 ValueOptionalitySpec?
FixedTypeValueSetFieldSpec    <- valuesetfieldreference Type
                                 ValueSetOptionalitySpec?
VariableTypeValueSetFieldSpec <- valuesetfieldreference FieldName
                                 ValueSetOptionalitySpec?
ObjectFieldSpec               <- objectfieldreference DefinedObjectClass
                                 ObjectOptionalitySpec?
ObjectSetFieldSpec            <- objectsetfieldreference DefinedObjectClass
                                 ObjectSetOptionalitySpec?
TokenOrGroupSpec              <- Literal
                               / PrimitiveFieldName
                               / '[' OS TokenOrGroupSpec+ ']' OS
TypeOptionalitySpec           <- 'OPTIONAL' OS
                               / 'DEFAULT' OS Type
ValueOptionalitySpec          <- 'OPTIONAL' OS
                               / 'DEFAULT' OS Value
ValueSetOptionalitySpec       <- 'OPTIONAL' OS
                               / 'DEFAULT' OS ValueSet
ObjectOptionalitySpec         <- 'OPTIONAL' OS
                               / 'DEFAULT' OS Object
ObjectSetOptionalitySpec      <- 'OPTIONAL' OS
                               / 'DEFAULT' OS ObjectSet


## Object #####################################################################

Object              <- DefinedObject ActualParameterList?
                     / ObjectDefn
                     / ReferencedObjects '.' OS FieldName
ObjectDefn          <- '{' OS
                       ( FieldSetting (',' OS FieldSetting)*
                       / DefinedSyntaxToken*)
                       '}' OS
DefinedSyntaxToken  <- Literal
                     / Setting


## ObjectSet ##################################################################

ObjectSet          <- '{' OS ObjectSetSpec '}' OS
ObjectSetSpec      <- '...' OS (',' OS ElementSetSpec)?
                    / ElementSetSpec
                      (',' OS '...' OS (',' OS ElementSetSpec)?)?
ObjectSetElements  <- Object
                    / DefinedObjectSet ActualParameterList?
                    / ReferencedObjects '.' OS FieldName


## Other ######################################################################

FieldName           <- PrimitiveFieldName ('.' OS PrimitiveFieldName)*
PrimitiveFieldName  <- typefieldreference
                     / valuefieldreference
                     / valuesetfieldreference
                     / objectfieldreference
                     / objectsetfieldreference
Literal             <- ',' OS / word
AbsoluteReference   <- '@' OS ModuleIdentifier
                       '.' OS typereference ('.' OS ComponentId)*
ComponentId         <- identifier
                     / number
                     / '*' OS
FieldSetting        <- PrimitiveFieldName Setting
Setting             <- Type
                     / Value
                     / ValueSet
                     / Object
                     / ObjectSet
ReferencedObjects   <- DefinedObject ActualParameterList?
                     / DefinedObjectSet ActualParameterList?
DefinedObject       <- (modulereference '.' OS objectsetreference)?
                       objectreference
DefinedObjectSet    <- (modulereference '.' OS objectsetreference)?
                       objectsetreference


## Extended lexical items #####################################################

valuereference           <- identifier
modulereference          <- typereference
xmlasn1typename          <- typereference
objectclassreference     <- encodingreference
objectreference          <- valuereference
objectsetreference       <- typereference
word                     <- encodingreference
typefieldreference       <- '&' typereference
valuefieldreference      <- '&' valuereference
valuesetfieldreference   <- '&' typereference
objectfieldreference     <- '&' objectreference
objectsetfieldreference  <- '&' objectsetreference


## Lexical items ##############################################################

typereference            <- [A-Z] ('-' [A-Za-z0-9] / [A-Za-z0-9])* OS
identifier               <- [a-z] ('-' [A-Za-z0-9] / [A-Za-z0-9])* OS
number                   <- ('0' / [1-9] [0-9]*) OS
realnumber               <- [0-9]+ ('.' [0-9]*)?
                            ([eE] ('-' / '+')? ('0' / [1-9] [0-9]*))? OS
bstring                  <- "'" ('0' / '1' / WS)* "'B" OS
xmlbstring               <- ('0' / '1' / WS)* OS
hstring                  <- "'" ([A-F0-9] / WS)* "'H" OS
xmlhstring               <- ([A-Fa-f0-9] / WS)* OS
cstring                  <- '"' ('""' / !'"' .)* '"' OS
xmlcstring               <- (![<>] .)* OS                                # TODO
simplestring             <- '"' (!'"' .)* '"' OS                         # SKIP
tstring                  <- '"' [0-9+:.,/CDHMRPSTWYZ-]+ '"' OS
xmltstring               <- [0-9+:.,/CDHMRPSTWYZ-]+ OS
psname                   <- [A-Z] ('-' [A-Za-z0-9] / [A-Za-z0-9])* OS
encodingreference        <- [A-Z] ('-' [A-Z0-9] / [A-Z0-9])* OS
integerUnicodeLabel      <- ('0' / [1-9] [0-9]*) OS
non_integerUnicodeLabel  <- !integerUnicodeLabel [a-zA-Z0-9_]* OS        # TODO
extended_true            <- ('true' / '1') OS
extended_false           <- ('false' / '0') OS


## Spacing ####################################################################

MS       <- Spacing+  # mandatory spacing
OS       <- Spacing*  # optional spacing
Spacing  <- WS / Comment
Comment  <- '--' (!(EOL / '--') .)* (EOL / '--')
WS       <- ' ' / '\t' / EOL
EOL      <- '\r\n' / '\n' / '\r'
EOF      <- !.


""", 'Root')
