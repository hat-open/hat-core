Simple binary serialization
===========================

Simple binary serialization (SBS) features:

    * schema based
    * small schema language optimized for human readability
    * schema re-usability and organization into modules
    * small number of built in types
    * polymorphic data types
    * binary serialization
    * designed to enable simple and efficient implementation
    * optimized for small encoded data size

Example of SBS schema::

    module Module

    Entry(K, V) = Tuple {
        key: K
        value: V
    }

    Collection(K) = Union {
        null: None
        bool: Entry(K, Boolean)
        int: Entry(K, Integer)
        float: Entry(K, Float)
        str: Entry(K, String)
        bytes: Entry(K, Bytes)
    }

    IntKeyCollection = Collection(Integer)

    StrKeyCollection = Collection(String)


Schema definition
-----------------

SBS shemas are written as UTF-8 encoded files with `.sbs` file extension.
Characters ``,``, space, ``\t``, ``\r`` and ``\n`` are considered white-space
characters and are ignored. Characters ``(``, ``)``, ``{``, ``}``, ``:``, ``=``
and white-space characters are used as delimiters between other identifiers.
All other valid identifiers are defined by regex ``r'[A-Za-z][A-Za-z0-9_]*'``.
Character ``#`` is used as start of comment that spans to the end of line.

Each file represents single SBS schema module. Name of SBS module is defined
by ``module <name>`` directive where ``<name>`` represents user-defined
module name. This directive is only mandatory part of each SBS schema and
should be placed at the beginning of each .sbs file. Example of minimal valid
SBS schema::

    module ModuleName

Rest of .sbs files contains arbitrary number of user-defined types. Each type
definition is written as ``<new_type>(<t1> <t2> ...) = <other_type>`` where:

    * ``<new_type>``

        Name of new user-defined type.

    * ``<t1>``, ``<t2>``, ...

        Identifiers representing parametric data type arguments used in
        ``<other_type>`` definition. If these arguments are not used,
        parenthesis can be omitted.

    * ``<other_type>``

        Other user defined or built in type which encoding should be used
        for encoding of ``<new_type>``. User defined types are specified
        as ``<module_name>.<type_name>(<t1> <t2> ...)``. If ``<type_name>``
        refers to type defined in same module, ``<module_name>.`` can be
        omitted. If user defined type is not parametric data type, parenthesis
        should be omitted.

Builtin data types include:

    * simple data types

        * ``Boolean``

            Data type with two possible values representing true and false.

        * ``Integer``

            Unconstrained signed integer value.

        * ``Float``

            Floating point value that can be encoded with 8 bytes according to
            `IEEE 754`.

        * ``String``

            UTF-8 encoded string value.

        * ``Bytes``

            Array of byte values of arbitrary length.

    * composite data types

        * ``Array(<t>)``

            Parametric data type that defines arbitrary length Array where all
            elements are of type defined by ``<t>``.

        * ``Tuple { <entry1>: <t1>, <entry2>: <t2>, ... }``

            Collection of user-defined entries where each entry has entry
            identifier (``<entry1>``, ``<entry2>``, ...) and entry type
            (``<t1>``, ``<t2>``, ...). Encoded data must contain all entries
            specified by type definition.

        * ``Union { <entry1>: <t1>, <entry2>: <t2>, ... }``

            Type that can represent one of types defined by ``<t1>``, ``<t2>``,
            ... Encoded data must contain only single entry identified by
            entry identifier (``<entry1>``, ``<entry2>``, ...).

    * derived data types

        These include predefined types that can be expressed as::

            None = Tuple {}

            Maybe(a) = Union {
                Nothing: None
                Just: a
            }


Data encoding
-------------

Boolean
'''''''

Boolean value is encoded as single byte with value ``0x01`` as true and
``0x00`` as false.


Integer
'''''''

Signed integer values are encoded as variable length byte array. Most
significant bit in all bytes, except last one, is set to ``0`` (last bytes most
significant bit is ``1``). Concatenation of other bits represent big-endian
encoded two's complement binary representation of integer value.

::

    +-----------------+-------+-----------------+
    |        0        |       |        m        |
    | 7 6 5 4 3 2 1 0 |       | 7 6 5 4 3 2 1 0 |
    +-----------------+  ...  +-----------------+
    | 0 xn ... x(n-7) |       | 1   x6 ... x0   |
    +-----------------+-------+-----------------+


Float
'''''

Floating point values are encoded according to IEEE 754 binary64 (double
precision) format.


Bytes
'''''

Bytes array is encoded "as is" and prefixed with bytes count encoded as
``Integer``.


String
''''''

String value is encoded as UTF-8 encoded ``Bytes``.


Array
'''''

Array is encoded as sequential concatenation of each element encoding. This
concatenated bytes are prefixed with array's element count encoded as
``Integer``.


Tuple
'''''

Tuple is encoded as sequential concatenation of tuple's elements encoding
according to elements order defined by schema.


Union
'''''

Union encodes single element prefixed with encoded element's zero-based index
as ``Integer``.


Python implementation
---------------------

.. automodule:: hat.sbs
