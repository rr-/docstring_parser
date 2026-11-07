"""Tests for parser objects, which hold the sections they were made with."""

import typing as T

import pytest

from docstring_parser import (
    BaseParser,
    DocstringStyle,
    ParseError,
    auto,
    compose,
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
    assert parser.name == style
    for text in INPUTS:
        assert _result(lambda: parser.parse(text)) == _result(
            lambda: parse(text, style, sections=sections)
        )


def test_auto_parser_parses_as_parse() -> None:
    """Test that AutoParser gives what parse() gives in auto mode."""
    parser = auto.Parser()
    assert parser.name == DocstringStyle.AUTO
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


def test_style_by_name_or_parser() -> None:
    """Test that parse() and compose() take a style's name or parser."""
    text = "Short.\n\n:param x: The x."
    assert DocstringStyle.REST == "rest"
    by_enum = dump(parse(text, DocstringStyle.REST))
    assert dump(parse(text, "rest")) == by_enum
    assert dump(parse(text, rest.Parser())) == by_enum
    docstring = parse(text)
    assert compose(docstring, "google") == compose(
        docstring, DocstringStyle.GOOGLE
    )
    assert compose(docstring, google.Parser()) == compose(docstring, "google")


def test_parser_has_its_sections() -> None:
    """Test that parse() takes no sections next to a parser."""
    with pytest.raises(ValueError, match="sections"):
        parse("Short.", rest.Parser(), sections=[])


def test_old_parser_names() -> None:
    """Test that the parsers keep the names they had."""
    assert google.GoogleParser is google.Parser
    assert numpydoc.NumpydocParser is numpydoc.Parser


_ESCAPED_NAMES = {
    "rest": ":param \\*\\*kwargs: d\n:param class\\_: d",
    "google": "Args:\n    \\*\\*kwargs: d\n    class\\_: d",
    "numpydoc": "Parameters\n----------\n\\*\\*kwargs\n    d\nclass\\_\n    d",
    "epydoc": "@param \\*\\*kwargs: d\n@param class\\_: d",
}


@pytest.mark.parametrize("style", sorted(_ESCAPED_NAMES))
def test_escaped_names_are_unescaped(style: str) -> None:
    """Test that every style drops the backslashes escaping ReST markup
    in a name."""
    docstring = parse("Short.\n\n" + _ESCAPED_NAMES[style], style)
    names = [param.arg_name for param in docstring.params]
    assert names == ["**kwargs", "class_"]


@pytest.mark.parametrize(
    "text, style",
    [
        ("Args:\n    arg1, arg2, ...: d", "google"),
        ("Parameters\n----------\narg1, arg2, ...\n    d", "numpydoc"),
    ],
)
def test_ellipsis_is_a_name(text: str, style: str) -> None:
    """Test that ``...`` is one of several names, as in napoleon."""
    docstring = parse("Short.\n\n" + text, style)
    names = [param.arg_name for param in docstring.params]
    assert names == ["arg1", "arg2", "..."]


def test_bare_names_line_gives_one_param_each() -> None:
    """Test that a Google line of bare names gives a param per name."""
    docstring = parse("Short.\n\nArgs:\n    x, y\n    z: d", "google")
    names = [param.arg_name for param in docstring.params]
    assert names == ["x", "y", "z"]


def test_rest_unescapes_types_and_attribute_directives() -> None:
    """Test that ReST unescapes type fields and attribute directives."""
    text = (
        "Short.\n\n:param x: d\n:type x: list\\_of\n\n"
        ".. attribute:: class\\_\n   :type: my\\_type\n\n   d"
    )
    docstring = parse(text, "rest")
    assert docstring.params[0].type_name == "list_of"
    assert docstring.attrs[0].arg_name == "class_"
    assert docstring.attrs[0].type_name == "my_type"


def test_rest_compose_escapes_trailing_underscore() -> None:
    """Test that ReST compose escapes an underscore ending a name, which
    docutils reads as a reference, and reads it back."""
    docstring = parse("Short.\n\nArgs:\n    class_: d\n    a_b: d", "google")
    text = compose(docstring, "rest")
    assert ":param class\\_: d" in text
    assert ":param a_b: d" in text
    names = [param.arg_name for param in parse(text, "rest").params]
    assert names == ["class_", "a_b"]
