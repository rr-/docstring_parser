"""Properties every style keeps by design, checked on every case file."""

import re
import typing as T

import pytest

from docstring_parser import (
    DocstringStyle,
    google,
    numpydoc,
    try_parse,
)
from docstring_parser.tests.cases import CASES_DIR, dump, read_case

CASES = sorted(CASES_DIR.rglob("*.txt"))
WORD = re.compile(r"\w+")


def _words(text: str) -> T.Set[str]:
    return set(WORD.findall(text))


# Words a style reads as syntax rather than keeping: section titles, the
# fields that only give a type, the parts of a ReST attribute directive, and
# the marks of an optional param's type.
TYPE_MARKS = {"optional", "default"}
SYNTAX = {
    DocstringStyle.REST: {"type", "rtype", "ytype", "vartype", "py", "value"}
    | TYPE_MARKS,
    DocstringStyle.GOOGLE: {
        word for s in google.DEFAULT_SECTIONS for word in _words(s.title)
    }
    | TYPE_MARKS,
    DocstringStyle.NUMPYDOC: {
        word for s in numpydoc.DEFAULT_SECTIONS for word in _words(s.title)
    }
    | TYPE_MARKS,
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


@pytest.mark.parametrize("style", list(SYNTAX), ids=lambda s: s.name.lower())
def test_no_text_is_dropped(style: DocstringStyle) -> None:
    """Test that every word of a docstring is somewhere in its parse,
    including the parts that cannot be read."""
    for path in CASES:
        text = read_case(path).input
        docstring = try_parse(text, style).docstring
        lost = _words(text) - _words(dump(docstring)) - SYNTAX[style]
        assert not lost, f"{path.relative_to(CASES_DIR)} loses {sorted(lost)}"
