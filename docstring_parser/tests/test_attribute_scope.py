"""Attribute docstrings belong to the selected module or class."""

import sys

from docstring_parser import parse_from_object

module_value = 1
"""The module value."""


class ModuleChild:
    module_value = 2
    """The child value."""


def test_module_does_not_inherit_class_attributes():
    doc = parse_from_object(sys.modules[__name__])
    assert list(doc.attrs_by_name) == ["module_value"]
    assert doc.attrs_by_name["module_value"].description == "The module value."


def test_class_does_not_inherit_nested_class_attributes():
    class Outer:
        value = 1
        """The outer value."""

        class Inner:
            value = 2
            """The inner value."""
            inner_only = 3
            """Inner only."""

        last = 4
        """The last outer attribute."""

    outer = parse_from_object(Outer)
    assert list(outer.attrs_by_name) == ["value", "last"]
    assert outer.attrs_by_name["value"].description == "The outer value."
    inner = parse_from_object(Outer.Inner)
    assert list(inner.attrs_by_name) == ["value", "inner_only"]
    assert inner.attrs_by_name["value"].description == "The inner value."
