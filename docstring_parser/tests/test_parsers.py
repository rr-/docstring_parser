"""Tests for parser objects, which hold the sections they were made with."""

import typing as T

import pytest

from docstring_parser import (
    BaseParser,
    DocstringStyle,
    ParseError,
    auto,
    epydoc,
    google,
    numpydoc,
    parse,
    rest,
)
from docstring_parser.sections import Kind, SectionSpec, default_sections
from docstring_parser.tests.cases import CASES_DIR, dump, read_case

INPUTS = [read_case(p).input for p in sorted(CASES_DIR.rglob("*.txt"))]
PARSERS = {
    DocstringStyle.REST: rest.Parser,
    DocstringStyle.GOOGLE: google.Parser,
    DocstringStyle.NUMPYDOC: numpydoc.Parser,
    DocstringStyle.EPYDOC: epydoc.Parser,
}


def _result(call: T.Callable[[], T.Any]) -> str:
    try:
        return dump(call())
    except ParseError as ex:
        return f"ParseError: {ex}"


@pytest.mark.parametrize("style", list(PARSERS), ids=lambda s: s.name.lower())
@pytest.mark.parametrize("given", [False, True], ids=["none", "default"])
def test_parser_parses_as_parse(style: DocstringStyle, given: bool) -> None:
    """Test that a style's parser gives what parse() gives in that style."""
    sections = default_sections(style) if given else None
    parser = PARSERS[style](sections)
    assert isinstance(parser, BaseParser)
    assert parser.name == style.name.lower()
    for text in INPUTS:
        assert _result(lambda: parser.parse(text)) == _result(
            lambda: parse(text, style, sections=sections)
        )


def test_auto_parser_parses_as_parse() -> None:
    """Test that AutoParser gives what parse() gives in auto mode."""
    parser = auto.Parser()
    assert parser.name == "auto"
    for text in INPUTS:
        assert _result(lambda: parser.parse(text)) == _result(
            lambda: parse(text)
        )


def test_auto_parser_with_sections() -> None:
    """Test that AutoParser hands its sections to every style."""
    sections = [SectionSpec("Inputs", Kind.PARAM, bare=True)]
    docstring = auto.Parser(sections).parse(
        "Short.\n\nInputs\n    x: The x.\n"
    )
    assert docstring.style is DocstringStyle.GOOGLE
    assert [p.arg_name for p in docstring.params] == ["x"]


def test_parse_reuses_parsers_for_sections() -> None:
    """Test that parse() builds one parser for the same sections."""
    sections = default_sections(DocstringStyle.REST)
    parse("Short.", DocstringStyle.REST, sections=sections)
    parsers = rest._parsers.parsers()
    parse(":param x: X.", DocstringStyle.REST, sections=sections)
    assert rest._parsers.parsers() == parsers


def test_old_parser_names() -> None:
    """Test that the parsers keep the names they had."""
    assert google.GoogleParser is google.Parser
    assert numpydoc.NumpydocParser is numpydoc.Parser
