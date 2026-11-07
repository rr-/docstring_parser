"""Tests for what kind of item each meta says it documents."""

import pytest

from docstring_parser import (
    DocstringDeprecated,
    DocstringMeta,
    DocstringMethod,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
    ParseError,
    parse,
)
from docstring_parser.common import (
    PARAM_KINDS,
    RAISES_KINDS,
    DocstringExample,
    Kind,
)
from docstring_parser.tests.cases import CASES_DIR, read_case

STYLES = [
    DocstringStyle.REST,
    DocstringStyle.GOOGLE,
    DocstringStyle.NUMPYDOC,
    DocstringStyle.EPYDOC,
]


def _family(meta: DocstringMeta) -> frozenset:
    if isinstance(meta, DocstringParam):
        return PARAM_KINDS
    if isinstance(meta, DocstringReturns):
        return frozenset({Kind.YIELDS if meta.is_generator else Kind.RETURNS})
    if isinstance(meta, DocstringRaises):
        return RAISES_KINDS
    if isinstance(meta, DocstringExample):
        return frozenset({Kind.EXAMPLES})
    if isinstance(meta, DocstringDeprecated):
        return frozenset({Kind.DEPRECATION})
    if isinstance(meta, DocstringMethod):
        return frozenset({Kind.METHOD})
    return frozenset({Kind.TEXT})


@pytest.mark.parametrize("style", STYLES, ids=lambda s: s.name.lower())
def test_kind_matches_class(style: DocstringStyle) -> None:
    """Test that every parsed meta's kind is one its class allows."""
    for path in sorted(CASES_DIR.rglob("*.txt")):
        try:
            docstring = parse(read_case(path).input, style)
        except ParseError:
            continue
        for meta in docstring.meta:
            assert meta.kind in _family(meta), path


def test_kind_must_fit_class() -> None:
    """Test that a param or raises cannot get a kind of another class."""
    with pytest.raises(ValueError, match="param"):
        DocstringParam(None, "x", None, None, None, Kind.RAISES)
    with pytest.raises(ValueError, match="raises"):
        DocstringRaises(None, None, Kind.PARAM)


@pytest.mark.parametrize(
    ("style", "text", "kinds"),
    [
        (
            DocstringStyle.REST,
            ":param x: X.\n:keyword y: Y.\n:attribute z: Z.\n:ivar w: W.",
            [Kind.PARAM, Kind.KEYWORD, Kind.ATTRIBUTE, Kind.ATTRIBUTE],
        ),
        (
            DocstringStyle.EPYDOC,
            "@param x: X.\n@keyword y: Y.\n@ivar z: Z.\n@cvar w: W.",
            [Kind.PARAM, Kind.KEYWORD, Kind.ATTRIBUTE, Kind.ATTRIBUTE],
        ),
        (
            DocstringStyle.GOOGLE,
            "S.\n\nArgs:\n    x: X.\n\nAttributes:\n    y: Y.\n\n"
            "Yields:\n    int: Z.",
            [Kind.PARAM, Kind.ATTRIBUTE, Kind.YIELDS],
        ),
        (
            DocstringStyle.NUMPYDOC,
            "S.\n\nOther Parameters\n----------------\nx\n    X.\n\n"
            "Receives\n--------\ny\n    Y.\n\n"
            "Warns\n-----\nUserWarning\n    W.",
            [Kind.OTHER_PARAM, Kind.RECEIVES, Kind.WARNS],
        ),
    ],
    ids=lambda v: v.name.lower() if isinstance(v, DocstringStyle) else "",
)
def test_sub_kinds(style: DocstringStyle, text: str, kinds: list) -> None:
    """Test that each style tells the kinds of params and raises apart."""
    assert [m.kind for m in parse(text, style).meta] == kinds


@pytest.mark.parametrize(
    ("style", "text"),
    [
        (DocstringStyle.REST, ":param x: X.\n:attribute y: Y."),
        (DocstringStyle.REST, ":param x: X.\n:ivar y: Y."),
        (DocstringStyle.EPYDOC, "@param x: X.\n@ivar y: Y."),
        (
            DocstringStyle.GOOGLE,
            "S.\n\nArgs:\n    x: X.\n\nAttributes:\n    y: Y.",
        ),
        (
            DocstringStyle.NUMPYDOC,
            "S.\n\nParameters\n----------\nx\n    X.\n\n"
            "Attributes\n----------\ny\n    Y.",
        ),
    ],
    ids=lambda v: v.name.lower() if isinstance(v, DocstringStyle) else "",
)
def test_params_leave_out_attributes(style: DocstringStyle, text: str) -> None:
    """Test that params and attrs each list their own items."""
    docstring = parse(text, style)
    assert [p.arg_name for p in docstring.params] == ["x"]
    assert [a.arg_name for a in docstring.attrs] == ["y"]


@pytest.mark.parametrize(
    ("style", "text"),
    [
        (DocstringStyle.REST, "S.\n\n:returns: R.\n:yields: Y."),
        (DocstringStyle.GOOGLE, "S.\n\nReturns:\n    R.\n\nYields:\n    Y."),
        (
            DocstringStyle.NUMPYDOC,
            "S.\n\nReturns\n-------\nint\n    R.\n\n"
            "Yields\n------\nint\n    Y.",
        ),
    ],
    ids=lambda v: v.name.lower() if isinstance(v, DocstringStyle) else "",
)
def test_returns_and_yields_apart(style: DocstringStyle, text: str) -> None:
    """Test that returns and yields each list only their own kind."""
    docstring = parse(text, style)
    assert docstring.returns is not None
    assert docstring.returns.description == "R."
    assert docstring.yields is not None
    assert docstring.yields.description == "Y."
    assert [m.description for m in docstring.many_returns] == ["R."]
    assert [m.description for m in docstring.many_yields] == ["Y."]


def test_yields_only() -> None:
    """Test that a generator's docstring has no returns."""
    docstring = parse("S.\n\n@yield: Y.", DocstringStyle.EPYDOC)
    assert docstring.returns is None
    assert docstring.many_returns == []
    assert docstring.yields is not None
    assert docstring.yields.description == "Y."
