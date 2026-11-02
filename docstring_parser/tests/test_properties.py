"""Property-based tests on generated docstring-like text.

The text is built from fragments that are meaningful in some style, so that
generated docstrings exercise the parsers rather than being plain text. Runs
are derandomized to keep them reproducible; set the ``HYPOTHESIS_PROFILE``
environment variable to ``thorough`` for a longer randomized search.
"""

import inspect
import os

import hypothesis
import hypothesis.strategies as st

from docstring_parser import (
    DocstringStyle,
    ParseError,
    RenderingStyle,
    compose,
    parse,
)
from docstring_parser._core import google
from docstring_parser.tests._serialize import docstring_to_dict

hypothesis.settings.register_profile(
    "default",
    max_examples=500,
    derandomize=True,
    deadline=None,
    suppress_health_check=list(hypothesis.HealthCheck),
)
hypothesis.settings.register_profile(
    "thorough",
    max_examples=50_000,
    deadline=None,
    suppress_health_check=list(hypothesis.HealthCheck),
)
hypothesis.settings.load_profile(
    os.environ.get("HYPOTHESIS_PROFILE", "default")
)

FRAGMENTS = [
    "\n",
    "\n    ",
    "\n        ",
    "    ",
    " ",
    ":",
    "x",
    "y",
    "a b",
    "int",
    "(int)",
    "(int, optional)",
    ", optional",
    "?",
    "*",
    "-",
    ",",
    "[",
    "]",
    "(",
    ")",
    "'",
    '"',
    "`",
    ":param ",
    ":type ",
    ":returns:",
    ":rtype:",
    ":raises ",
    "@param ",
    "@type ",
    "@return:",
    "@rtype:",
    "@raise ",
    "Args:",
    "Returns:",
    "Raises:",
    "Yields:",
    "Example:",
    "Attributes:",
    "Note:",
    "\nParameters\n----------\n",
    "\nReturns\n-------\n",
    "\nExamples\n--------\n",
    "\nNotes\n-----\n",
    ".. deprecated:: 1.0",
    "Defaults to 3.",
    "default=",
    "default: 3",
    ">>> ",
    "... ",
]

STYLES = [
    DocstringStyle.REST,
    DocstringStyle.GOOGLE,
    DocstringStyle.NUMPYDOC,
    DocstringStyle.EPYDOC,
]

docstrings = st.lists(st.sampled_from(FRAGMENTS), max_size=25).map("".join)


@hypothesis.given(docstrings, st.sampled_from(STYLES + [DocstringStyle.AUTO]))
def test_only_parse_errors(text: str, style: DocstringStyle) -> None:
    """Parsing either succeeds or raises ParseError, in both modes."""
    for legacy in (True, False):
        try:
            parse(text, style, legacy=legacy)
        except ParseError:
            pass


@hypothesis.given(
    docstrings.filter(lambda text: not inspect.cleandoc(text)[:1].isspace()),
    st.sampled_from(STYLES),
    st.sampled_from(list(RenderingStyle)),
)
def test_compose_round_trip(
    text: str, style: DocstringStyle, rendering_style: RenderingStyle
) -> None:
    """Parsing composed text gives back the same docstring.

    Excluded are docstrings whose first line is indented more than the
    following ones, since PEP 257 cleaning can not keep that indentation
    once composed, and Google docstrings whose description starts with a
    section title, which can not be told apart from a section once composed.
    """
    docstring = parse(text, style, legacy=False)
    if style == DocstringStyle.GOOGLE and docstring.short_description:
        first = docstring.short_description.splitlines()[0]
        title = first[:-1].rstrip().lower() if first.endswith(":") else ""
        hypothesis.assume(title not in google.default_sections())
    composed = compose(docstring, rendering_style=rendering_style)
    again = parse(composed, style, legacy=False)
    assert docstring_to_dict(again) == docstring_to_dict(docstring)
