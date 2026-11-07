"""Properties every style keeps by design, checked on every case file."""

import re
import typing as T

import pytest

from docstring_parser import (
    DocstringStyle,
    ParseError,
    RenderingStyle,
    compose,
    google,
    numpydoc,
    parse,
    try_parse,
)
from docstring_parser.tests.cases import CASES_DIR, dump, read_case
from docstring_parser.tests.generated import generated_inputs

CASES = sorted(CASES_DIR.rglob("*.txt"))
WORD = re.compile(r"\w+")


def _words(text: str) -> T.Set[str]:
    return set(WORD.findall(text))


# Words a style reads as syntax rather than keeping: section titles, the
# fields that only give a type, the parts of the attribute and deprecated
# directives, and the marks of an optional param's type.
TYPE_MARKS = {"optional", "default"}
SYNTAX = {
    DocstringStyle.REST: {
        "type",
        "rtype",
        "ytype",
        "vartype",
        "py",
        "value",
        "deprecated",
    }
    | TYPE_MARKS,
    DocstringStyle.GOOGLE: {"deprecated"} | TYPE_MARKS,
    DocstringStyle.NUMPYDOC: TYPE_MARKS,
    DocstringStyle.EPYDOC: {
        "type",
        "rtype",
        "returntype",
        "ytype",
        "return",
        "yield",
    }
    | TYPE_MARKS,
}

# The words of section titles, in lowercase, since titles match in any case.
TITLE_WORDS = {
    DocstringStyle.GOOGLE: {
        word.lower()
        for s in google.DEFAULT_SECTIONS
        for word in _words(s.title)
    },
    DocstringStyle.NUMPYDOC: {
        word.lower()
        for s in numpydoc.DEFAULT_SECTIONS
        for word in _words(s.title)
    },
}


@pytest.mark.parametrize("style", list(SYNTAX), ids=lambda s: s.name.lower())
def test_no_text_is_dropped(style: DocstringStyle) -> None:
    """Test that every word of a docstring is somewhere in its parse,
    including the parts that cannot be read."""
    for path in CASES:
        text = read_case(path).input
        docstring = try_parse(text, style).docstring
        titles = TITLE_WORDS.get(style, set())
        lost = {
            word
            for word in _words(text) - _words(dump(docstring)) - SYNTAX[style]
            if word.lower() not in titles
        }
        assert not lost, f"{path.relative_to(CASES_DIR)} loses {sorted(lost)}"


STYLES = list(SYNTAX)


def _round_trips(text: str, style: DocstringStyle) -> T.List[str]:
    """Return the renderings in which a docstring parsed with no problems
    does not read back as it was parsed."""
    result = try_parse(text, style)
    if result.problems:
        return []
    expected = dump(result.docstring)
    failed = []
    for rendering in RenderingStyle:
        composed = compose(result.docstring, style, rendering)
        try:
            actual = dump(parse(composed, style))
        except ParseError as ex:
            actual = str(ex)
        if actual != expected:
            failed.append(rendering.name.lower())
    return failed


def _blank_lines_empty(text: str) -> bool:
    """Return whether no line of a text is spaces alone."""
    return all(line.strip() or not line for line in text.split("\n"))


@pytest.mark.parametrize("style", STYLES, ids=lambda s: s.name.lower())
def test_compose_writes_no_blank_line_with_indent(
    style: DocstringStyle,
) -> None:
    """Test that every case input with no blank line holding spaces,
    composed in every style and rendering, writes none either."""
    for path in CASES:
        name = path.relative_to(CASES_DIR).as_posix()
        text = read_case(path).input
        if not _blank_lines_empty(text):
            continue
        docstring = try_parse(text, style).docstring
        for target in STYLES:
            for rendering in RenderingStyle:
                composed = compose(docstring, target, rendering)
                assert _blank_lines_empty(composed), (
                    f"{name} as {target.name.lower()} {rendering.name.lower()}"
                )


# Case inputs that cannot read back the same, and why.
SEVERAL_TYPES = "several type fields name one param, so another one types it"
NAMED_TYPE = "a named type alone right after a return names that return"
CASE_EXCLUSIONS = {
    ("fork/rest_parser_attributes_03.txt", DocstringStyle.REST): SEVERAL_TYPES,
    ("rest/type_only_01.txt", DocstringStyle.REST): NAMED_TYPE,
}


@pytest.mark.parametrize("style", STYLES, ids=lambda s: s.name.lower())
def test_compose_round_trips(style: DocstringStyle) -> None:
    """Test that every case input parsed with no problems composes, in
    every rendering, to text that parses back the same."""
    for path in CASES:
        name = path.relative_to(CASES_DIR).as_posix()
        if (name, style) in CASE_EXCLUSIONS:
            continue
        failed = _round_trips(read_case(path).input, style)
        assert not failed, f"{name} changes in {failed}"


def test_compose_round_trip_exclusions_still_fail() -> None:
    """Test that every excluded case input still fails to round trip, so
    that one fixed leaves the list."""
    for name, style in CASE_EXCLUSIONS:
        text = read_case(CASES_DIR / name).input
        assert _round_trips(text, style), f"{name} round trips now"


# Generated docstrings that cannot read back the same, and why, by their
# index among the first GENERATED.
SUMMARY = "an indented first line reads as a field or title once flush"
BODY = "a body's first line is dedented apart from its other lines"
DIRECTIVE = "a directive's body holds the directive itself"
GENERATED = 2000
GENERATED_EXCLUSIONS = {
    (555, DocstringStyle.REST): SUMMARY,
    (637, DocstringStyle.REST): SUMMARY,
    (672, DocstringStyle.REST): SUMMARY,
    (764, DocstringStyle.NUMPYDOC): SUMMARY,
    (835, DocstringStyle.EPYDOC): SUMMARY,
    (852, DocstringStyle.REST): SUMMARY,
    (1253, DocstringStyle.NUMPYDOC): BODY,
    (1408, DocstringStyle.NUMPYDOC): SUMMARY,
    (1507, DocstringStyle.GOOGLE): BODY,
    (1541, DocstringStyle.REST): SUMMARY,
    (1572, DocstringStyle.EPYDOC): SUMMARY,
    (1733, DocstringStyle.EPYDOC): SUMMARY,
    (1774, DocstringStyle.REST): SUMMARY,
    (1943, DocstringStyle.NUMPYDOC): DIRECTIVE,
}


def test_generated_round_trips() -> None:
    """Test that generated docstrings parsed with no problems compose to
    text that parses back the same, but for the known exclusions, which
    must still fail."""
    failing = set()
    for index, text in enumerate(generated_inputs(GENERATED)):
        for style in STYLES:
            if _round_trips(text, style):
                failing.add((index, style))
    assert failing - set(GENERATED_EXCLUSIONS) == set()
    assert set(GENERATED_EXCLUSIONS) - failing == set()
