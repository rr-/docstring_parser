"""Tests for parse_from_object function and attribute docstrings."""
from unittest.mock import patch

from docstring_parser import parse_from_object

module_attr: int = 1
"""Description for module_attr"""


def test_from_module_attribute_docstrings() -> None:
    """Test the parse of attribute docstrings from a module."""
    from . import test_parse_from_object  # pylint: disable=C0415,W0406

    docstring = parse_from_object(test_parse_from_object)

    assert "parse_from_object" in docstring.short_description
    assert len(docstring.params) == 1
    assert docstring.params[0].arg_name == "module_attr"
    assert docstring.params[0].type_name == "int"
    assert docstring.params[0].description == "Description for module_attr"


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
    assert docstring.description == "Short description\nLong description"
    assert len(docstring.params) == 2
    assert docstring.params[0].arg_name == "attr_one"
    assert docstring.params[0].type_name == "str"
    assert docstring.params[0].description == "Description for attr_one"
    assert docstring.params[1].arg_name == "attr_two"
    assert docstring.params[1].type_name == "bool"
    assert docstring.params[1].description == "Description for attr_two"


def test_from_class_attribute_docstrings_without_type() -> None:
    """Test the parse of untyped attribute docstrings."""

    class WithoutType:  # pylint: disable=missing-class-docstring
        attr_one = "value"
        """Description for attr_one"""

    docstring = parse_from_object(WithoutType)

    assert docstring.short_description is None
    assert docstring.long_description is None
    assert docstring.description is None
    assert len(docstring.params) == 1
    assert docstring.params[0].arg_name == "attr_one"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].description == "Description for attr_one"


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
