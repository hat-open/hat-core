Translator
==========

Translator is simple command line interface for configuration transformation.
It transforms single input configuration to single output configuration.
Configurations are represented by JSON data encoded in JSON or YAML format.
Each configuration structure is identified by unique identifier (configuration
type) and optional JSON schema. Translator reads input configuration from
`stdin` and outputs resulting configuration to `stdout`. If error during
transformation occurs, information is outputted to `stderr` and program
finishes with non zero return code. Translator comes with set of predefined
translations which can be extended with additional definitions
provided as command line arguments.


Running
-------

By installing Translator from `hat-translator` package, executable
`hat-translator` becomes available and can be used for starting this
component.

    .. program-output:: python -m hat.translator --help

    .. program-output:: python -m hat.translator list --help

    .. program-output:: python -m hat.translator translate --help

If multiple modules provide transformation for same
`(input-type, output-type)` pair, last transformation (from list of command
line module arguments) is used.

.. todo::

    * consider adding additional output subtype label instead of encoding
      specific translation identification as part of output type
      (example: "input: editor; output: event_primary" vs
      "input: editor; output: event; variant: primary")


Python implementation
---------------------

.. automodule:: hat.translator.common

.. automodule:: hat.translator.main
