"""Tests for generic docstring routines."""

import typing as T

import pytest

from docstring_parser import epydoc, google, numpydoc
from docstring_parser.common import Docstring, DocstringStyle
from docstring_parser.parser import compose, parse


@pytest.mark.parametrize("style", list(DocstringStyle))
def test_no_docstring(style: DocstringStyle) -> None:
    """Test parsing an object with no __doc__."""
    docstring = parse(None, style)
    assert docstring.short_description is None
    assert docstring.long_description is None
    assert docstring.description is None
    assert not docstring.meta


@pytest.mark.parametrize(
    "blank, expected", [(True, "Short.\n\nLong."), (False, "Short.\nLong.")]
)
def test_description(blank: bool, expected: str) -> None:
    """Test that the description joins the short and long ones."""
    docstring = Docstring()
    docstring.short_description = "Short."
    docstring.long_description = "Long."
    docstring.blank_after_short_description = blank
    assert docstring.description == expected


def test_compose_without_style() -> None:
    """Test composing a docstring that has no style to fall back on."""
    with pytest.raises(ValueError):
        compose(Docstring())


def test_auto_skips_parsers_for_plain_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that text no style finds fields in is parsed as ReST only."""

    def fail(text: T.Optional[str]) -> Docstring:
        raise AssertionError("only ReST should parse this")

    for module in (google, numpydoc, epydoc):
        monkeypatch.setattr(module, "parse", fail)
    docstring = parse("Short.\n\nLong text, e.g. this - with dashes.")
    assert docstring.style == DocstringStyle.REST
    assert docstring.long_description == "Long text, e.g. this - with dashes."


@pytest.mark.parametrize(
    "line",
    [
        ":param a: x",
        "@param a: x",
        "Args:",
        "    Returns:  ",
        "----------",
        ".. deprecated:: 1.0",
        "----------\xa0",
        "\xa0@param a: x",
        "Returns:\u3000",
    ],
)
def test_auto_parses_every_style_for_field_lines(
    monkeypatch: pytest.MonkeyPatch, line: str
) -> None:
    """Test that a line that may start a field runs every style."""
    calls = []
    for module in (google, numpydoc, epydoc):
        monkeypatch.setattr(
            module,
            "parse",
            lambda text, parse=module.parse: calls.append(1) or parse(text),
        )
    parse(f"Short.\n\n{line}")
    assert len(calls) == 3
