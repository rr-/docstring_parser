"""Tests for the rule every style reads optional params and defaults by."""

import subprocess
import sys

import pytest

from docstring_parser import DocstringStyle, compose, parse

STYLES = [
    DocstringStyle.REST,
    DocstringStyle.GOOGLE,
    DocstringStyle.NUMPYDOC,
    DocstringStyle.EPYDOC,
]


def _parse(style: DocstringStyle, type_name: str, description: str):
    """Parse one param of a type and description, in a style."""
    if style == DocstringStyle.REST:
        text = f":param x: {description}"
        if type_name:
            text += f"\n:type x: {type_name}"
    elif style == DocstringStyle.GOOGLE:
        head = f"x ({type_name})" if type_name else "x"
        text = f"Args:\n    {head}: {description}"
    elif style == DocstringStyle.NUMPYDOC:
        head = f"x : {type_name}" if type_name else "x"
        text = f"Parameters\n----------\n{head}\n    {description}"
    else:
        text = f"@param x: {description}"
        if type_name:
            text += f"\n@type x: {type_name}"
    return parse(f"Short.\n\n{text}", style).params[0]


@pytest.mark.parametrize("style", STYLES, ids=lambda s: s.name.lower())
@pytest.mark.parametrize(
    ("type_name", "expected"),
    [
        ("int", ("int", False, None)),
        ("int, optional", ("int", True, None)),
        ("int, Optional", ("int", True, None)),
        ("int, *optional*", ("int", True, None)),
        ("int (optional)", ("int", True, None)),
        ("int?", ("int", True, None)),
        ("int, optional, default 3", ("int", True, "3")),
        ("int, default=3", ("int", True, "3")),
        ("int, default is 3", ("int", True, "3")),
        ("int, defaults to 3", ("int", True, "3")),
        ("int, default ``3``", ("int", True, "3")),
        ("List[int], default [1, 2]", ("List[int]", True, "[1, 2]")),
        ("str, default 'a, b'", ("str", True, "'a, b'")),
    ],
)
def test_type_marks(style: DocstringStyle, type_name: str, expected) -> None:
    """Test that every style splits the same marks off a type."""
    param = _parse(style, type_name, "X.")
    assert param.type_name == expected[0]
    assert param.is_optional is expected[1]
    assert param.default == expected[2]


@pytest.mark.parametrize("style", STYLES, ids=lambda s: s.name.lower())
@pytest.mark.parametrize(
    ("description", "default"),
    [
        ("Defaults to 3.", "3"),
        ("X. Defaults to 3.", "3"),
        ("Value (default: 3).", "3"),
        ("Defaults to ``None``, meaning all.", "None"),
        ("Defaults to os.getcwd().", "os.getcwd()"),
        ("Defaults to 3 if unset.", "3"),
        ("Defaults to 0 (no padding).", "0"),
        ("The default value is 'x'.", "'x'"),
        ("Defaults to [1, 2].", "[1, 2]"),
        ("The default is to use all of them.", None),
        ("By default, nothing.", None),
        ("Unlike the default :meth:`run`.", None),
        ("The default is 3 seconds.", None),
    ],
)
def test_default_in_description(
    style: DocstringStyle, description: str, default
) -> None:
    """Test that every style finds a default its description states."""
    param = _parse(style, "int", description)
    assert param.default == default
    assert param.is_optional is (default is not None)


@pytest.mark.parametrize("style", STYLES, ids=lambda s: s.name.lower())
def test_default_in_type_wins(style: DocstringStyle) -> None:
    """Test that a default in the type wins over one the description has."""
    param = _parse(style, "int, default 1", "Defaults to 2.")
    assert param.default == "1"


@pytest.mark.parametrize("style", STYLES, ids=lambda s: s.name.lower())
def test_is_optional_without_type(style: DocstringStyle) -> None:
    """Test that a param with no type is not optional, rather than None."""
    param = _parse(style, "", "X.")
    assert param.type_name is None
    assert param.is_optional is False


def test_numpydoc_optional_without_type_composes() -> None:
    """Test that an optional param with no type reads back by its name."""
    text = "Short.\n\nParameters\n----------\nx : optional\n    X."
    docstring = parse(text, DocstringStyle.NUMPYDOC)
    assert docstring.params[0].arg_name == "x"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].is_optional is True
    assert compose(docstring) == text


def test_long_defaults_finish_promptly() -> None:
    """Long near misses of a type or a default must parse in one pass."""
    code = """
from docstring_parser import parse
desc = 'default ' * 20000 + ' is (' + '(' * 20000
doc = 'Short.\\n\\nArgs:\\n    x (int' + ', [' * 20000 + '): ' + desc
assert parse(doc, 'google').params[0].default is None
"""
    subprocess.run([sys.executable, "-c", code], check=True, timeout=5)
