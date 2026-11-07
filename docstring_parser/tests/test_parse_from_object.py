"""Tests for parse_from_object function and attribute docstrings."""

import sys
from unittest.mock import patch

from docstring_parser import parse_from_object

module_attr: int = 1
"""Description for module_attr"""


def test_from_module_attribute_docstrings() -> None:
    """Test the parse of attribute docstrings from a module."""
    docstring = parse_from_object(sys.modules[__name__])

    assert docstring.short_description is not None
    assert "parse_from_object" in docstring.short_description
    assert len(docstring.attrs) == 1
    assert docstring.params == []
    assert docstring.attrs[0].arg_name == "module_attr"
    assert docstring.attrs[0].type_name == "int"
    assert docstring.attrs[0].description == "Description for module_attr"


def test_from_class_attribute_docstrings() -> None:
    """Test the parse of attribute docstrings from a class."""

    class StandardCase:
        """Short description

        Long description
        """

        attr_one: str
        """Description for attr_one"""
        attr_two: bool = False
        """Description for attr_two"""

    docstring = parse_from_object(StandardCase)

    assert docstring.short_description == "Short description"
    assert docstring.long_description == "Long description"
    assert docstring.description == "Short description\n\nLong description"
    assert len(docstring.attrs) == 2
    assert docstring.params == []
    assert docstring.attrs[0].arg_name == "attr_one"
    assert docstring.attrs[0].type_name == "str"
    assert docstring.attrs[0].description == "Description for attr_one"
    assert docstring.attrs[1].arg_name == "attr_two"
    assert docstring.attrs[1].type_name == "bool"
    assert docstring.attrs[1].description == "Description for attr_two"


def test_from_class_attribute_named_like_param() -> None:
    """Test that an attribute named like a documented param is kept."""

    class WithParam:
        """Short description

        :param x: The param x.
        """

        x: int = 1
        """The attribute x."""

    docstring = parse_from_object(WithParam)

    assert len(docstring.params) == 1
    assert docstring.params[0].arg_name == "x"
    assert docstring.params[0].description == "The param x."
    assert len(docstring.attrs) == 1
    assert docstring.attrs[0].arg_name == "x"
    assert docstring.attrs[0].description == "The attribute x."


def test_from_class_documented_attribute_wins() -> None:
    """Test that an attribute the docstring documents is not added twice."""

    class WithAttribute:
        """Short description

        :attribute x: From the docstring.
        """

        x: int = 1
        """From the source."""

    docstring = parse_from_object(WithAttribute)

    assert len(docstring.attrs) == 1
    assert docstring.attrs[0].description == "From the docstring."


def test_from_class_attribute_docstrings_without_type() -> None:
    """Test the parse of untyped attribute docstrings."""

    class WithoutType:
        attr_one = "value"
        """Description for attr_one"""

    docstring = parse_from_object(WithoutType)

    assert docstring.short_description is None
    assert docstring.long_description is None
    assert docstring.description is None
    assert len(docstring.attrs) == 1
    assert docstring.params == []
    assert docstring.attrs[0].arg_name == "attr_one"
    assert docstring.attrs[0].type_name is None
    assert docstring.attrs[0].description == "Description for attr_one"


def test_from_class_without_source() -> None:
    """Test the parse of class when source is unavailable."""

    class WithoutSource:
        """Short description"""

        attr_one: str
        """Description for attr_one"""

    with patch(
        "inspect.getsource", side_effect=OSError("could not get source code")
    ):
        docstring = parse_from_object(WithoutSource)

    assert docstring.short_description == "Short description"
    assert docstring.long_description is None
    assert docstring.description == "Short description"
    assert len(docstring.params) == 0
    assert len(docstring.attrs) == 0


def test_from_function() -> None:
    """Test the parse of a function docstring."""

    def a_function(param1: str, param2: int = 2):
        """Short description
        Args:
            param1: Description for param1
            param2: Description for param2
        """
        return f"{param1} {param2}"

    docstring = parse_from_object(a_function)

    assert docstring.short_description == "Short description"
    assert docstring.description == "Short description"
    assert len(docstring.params) == 2
    assert docstring.params[0].arg_name == "param1"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].description == "Description for param1"
    assert docstring.params[1].arg_name == "param2"
    assert docstring.params[1].type_name is None
    assert docstring.params[1].description == "Description for param2"


def test_from_builtin_class() -> None:
    """Test the parse of a class that has no source, being built in."""
    docstring = parse_from_object(int)

    assert docstring.short_description is not None
    assert len(docstring.params) == 0


def test_from_builtin_module() -> None:
    """Test the parse of a module that has no source, being built in."""
    docstring = parse_from_object(sys)

    assert docstring.short_description is not None


def test_from_object_with_descriptor_doc() -> None:
    """Test the parse of an object whose __doc__ is not a string."""
    descriptor = type(
        "Descriptor", (), {"__doc__": property(lambda self: "Short.")}
    )

    docstring = parse_from_object(descriptor)

    assert docstring.short_description is None
    assert len(docstring.meta) == 0


def test_attribute_docstring_is_cleaned() -> None:
    """Test that an attribute's docstring is cleaned as a docstring is."""

    class WithAttr:
        """Class docstring."""

        value: int = 1
        """
            Indented
              attribute doc.
        """

    docstring = parse_from_object(WithAttr)
    assert docstring.attrs[0].description == "Indented\n  attribute doc."
