"""Tests for the type of a param as it is written."""

import pytest

from docstring_parser import DocstringStyle, parse

STYLES = {
    DocstringStyle.REST: "Short.\n\n:param x: X.\n:type x: int, optional",
    DocstringStyle.GOOGLE: "Short.\n\nArgs:\n    x (int, optional): X.",
    DocstringStyle.NUMPYDOC: (
        "Short.\n\nParameters\n----------\nx : int, optional\n    X."
    ),
    DocstringStyle.EPYDOC: "Short.\n\n@param x: X.\n@type x: int, optional",
}


@pytest.mark.parametrize("style", list(STYLES), ids=lambda s: s.name.lower())
def test_raw_type_keeps_optional_mark(style: DocstringStyle) -> None:
    """Test that the raw type keeps what the type has split off."""
    param = parse(STYLES[style], style).params[0]
    assert param.type_name == "int"
    assert param.is_optional is True
    assert param.raw_type_name == "int, optional"


def test_raw_type_keeps_default() -> None:
    """Test that the raw type keeps a default written in the type."""
    param = parse(
        "Short.\n\nParameters\n----------\nx : int, default 1\n    X.",
        DocstringStyle.NUMPYDOC,
    ).params[0]
    assert param.type_name == "int"
    assert param.default == "1"
    assert param.raw_type_name == "int, default 1"


def test_raw_type_of_rest_inline_type() -> None:
    """Test that a type in a ``:param`` field is its raw type."""
    param = parse("Short.\n\n:param str? x: X.", DocstringStyle.REST).params[0]
    assert param.type_name == "str"
    assert param.raw_type_name == "str?"


def test_raw_type_of_type_field_alone() -> None:
    """Test that a type field with no param field keeps its raw type."""
    param = parse("Short.\n\n:type x: int, optional", DocstringStyle.REST)
    assert param.params[0].type_name == "int"
    assert param.params[0].raw_type_name == "int, optional"


def test_raw_type_of_attribute_directive() -> None:
    """Test that an attribute directive's type option is its raw type."""
    docstring = parse(
        "Short.\n\n.. attribute:: x\n   :type: int, optional\n\n   The x.",
        DocstringStyle.REST,
    )
    assert docstring.attrs[0].type_name == "int"
    assert docstring.attrs[0].raw_type_name == "int, optional"


@pytest.mark.parametrize(
    ("style", "text"),
    [
        (DocstringStyle.REST, "Short.\n\n:param x: X."),
        (DocstringStyle.GOOGLE, "Short.\n\nArgs:\n    x: X."),
        (
            DocstringStyle.NUMPYDOC,
            "Short.\n\nParameters\n----------\nx\n    X.",
        ),
        (DocstringStyle.EPYDOC, "Short.\n\n@param x: X."),
    ],
    ids=lambda v: v.name.lower() if isinstance(v, DocstringStyle) else "",
)
def test_no_raw_type_without_type(style: DocstringStyle, text: str) -> None:
    """Test that a param written with no type has no raw type."""
    param = parse(text, style).params[0]
    assert param.type_name is None
    assert param.raw_type_name is None
