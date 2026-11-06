"""Tests for parsing what can be parsed, and telling what cannot."""

import pytest

from docstring_parser import (
    DocstringStyle,
    ParseError,
    ParseResult,
    Problem,
    epydoc,
    google,
    numpydoc,
    parse,
    rest,
    try_parse,
)
from docstring_parser.tests.cases import CASES_DIR, dump, read_case

CASES = sorted(CASES_DIR.rglob("*.txt"))


@pytest.mark.parametrize("style", list(DocstringStyle), ids=lambda s: s.name)
def test_try_parse_agrees_with_parse(style: DocstringStyle) -> None:
    """Test that try_parse gives what parse gives, or what parse raises."""
    for path in CASES:
        text = read_case(path).input
        result = try_parse(text, style)
        try:
            docstring = parse(text, style)
        except ParseError as ex:
            assert result.problems, path
            assert ex.problems == result.problems, path
            assert str(ex).startswith(result.problems[0].message), path
        else:
            assert result.problems == [], path
            assert dump(result.docstring) == dump(docstring), path


def test_rest_problems() -> None:
    """Test that a field that cannot be read is kept as text."""
    result = try_parse(
        "\n\n    Short.\n\n    :param x: X.\n    :bad\n    :returns: R.\n",
        DocstringStyle.REST,
    )
    assert result.problems == [
        Problem(6, 'Error parsing meta information near ":bad\n".')
    ]
    assert result.docstring.params[0].arg_name == "x"
    assert result.docstring.returns is not None
    assert result.docstring.returns.description == "R."
    assert result.docstring.long_description == ":bad"


def test_google_problems() -> None:
    """Test that an item that cannot be read is kept as text."""
    result = google.try_parse(
        "Short.\n\nArgs:\n    x: X.\n    no colon here\n    y: Y.\n"
    )
    assert result.problems == [
        Problem(5, "Expected a colon in 'no colon here'.")
    ]
    assert result.docstring.params[0].arg_name == "x"
    assert result.docstring.params[1].arg_name == "y"
    assert result.docstring.long_description == "no colon here"


def test_google_problem_line_with_title_first() -> None:
    """Test the line of a problem in a docstring that opens with a title."""
    result = google.try_parse("Args:\n    x: X.\n    y\n")
    assert result.problems == [Problem(3, "Expected a colon in 'y'.")]


def test_epydoc_problems() -> None:
    """Test that fields that cannot be read are kept as text."""
    result = epydoc.try_parse(
        "Short.\n\n@param x: X.\n@param: nameless\n@return: R.\n@yield: Y.\n"
    )
    assert result.problems == [
        Problem(
            4, 'Error parsing meta information near "@param: nameless\n".'
        ),
        Problem(6, 'Error parsing meta information for "return".'),
    ]
    assert result.docstring.params[0].arg_name == "x"
    assert result.docstring.returns is not None
    assert result.docstring.returns.description == "R."
    assert (
        result.docstring.long_description == "@param: nameless\n\n@yield: Y."
    )


def test_numpydoc_has_no_problems() -> None:
    """Test that numpydoc reads any docstring."""
    text = "Short.\n\nParameters\n----------\nx\n"
    result = numpydoc.try_parse(text)
    assert isinstance(result, ParseResult)
    assert result.problems == []
    assert dump(result.docstring) == dump(numpydoc.parse(text))


def test_parse_error_carries_every_problem() -> None:
    """Test that parse raises one error with all problems and the result."""
    text = "Short.\n\n:param x: X.\n:bad\n:param: no name\n"
    with pytest.raises(ParseError) as info:
        rest.parse(text)
    assert str(info.value) == (
        'Error parsing meta information near ":bad\n". (and 1 more)'
    )
    assert info.value.problems == [
        Problem(4, 'Error parsing meta information near ":bad\n".'),
        Problem(5, "Expected one or two arguments for a param keyword."),
    ]
    assert info.value.result is not None
    assert info.value.result.docstring.params[0].arg_name == "x"


def test_parser_try_parse() -> None:
    """Test that a parser object parses leniently, as the functions do."""
    text = "Short.\n\n:param x: X.\n:bad\n"
    expected = try_parse(text, "rest")
    result = rest.Parser().try_parse(text)
    assert result.problems == expected.problems
    assert dump(result.docstring) == dump(expected.docstring)
    result = try_parse(text, rest.Parser())
    assert result.problems == expected.problems
    assert dump(result.docstring) == dump(expected.docstring)


def test_auto_prefers_style_with_no_problems() -> None:
    """Test that auto mode keeps a style that reads the text cleanly."""
    result = try_parse("Short.\n\n:param x: X.\n:bad\n")
    assert result.problems == []
    assert result.docstring.style == DocstringStyle.GOOGLE


def test_empty_text_has_no_problems() -> None:
    """Test that an empty docstring parses with no problems."""
    for style in DocstringStyle:
        assert try_parse("", style).problems == []
        assert try_parse(None, style).problems == []
