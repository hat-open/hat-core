.. _hat-stc:

`hat.stc` - Python statechart library
=====================================

This library provides basic implementation of
`hierarchical state machine <https://en.wikipedia.org/wiki/UML_state_machine>`_
engine. Statechart definition can be provided as structures defined by API or
by `SCXML definition <https://www.w3.org/TR/scxml/>`_. Additionally,
`Graphviz <https://graphviz.org/>`_ DOT graph can be generated based on state
definition together with Sphinx extension `hat.sphinx.scxml`.

Notable differences between `hat.stc` and SCXML standard:

    * initial child state (in `scxml` and `state` tag) should be defined
      only by setting parent's `initial` attribute

    * transitions without associated event name are not supported

    * parallel substates are not supported

    * history pseudo-state is not supported

    * data model is not supported

    * external communications is not supported

    * all actions and conditions are identified by name - arbitrary expressions
      or executable contents are not supported

    * transition event identifiers are used as exact event names without
      support for substring segmentation matching


Tutorial
--------

.. todo::

    ...


API
---

API reference is available as part of generated documentation:

    * `Python hat.stc module <../../pyhat/hat/stc.html>`_
