"""Run the text case files in the cases directory.

Set UPDATE_CASES=1 to write the actual output into the files instead.
"""

import os
import typing as T
from pathlib import Path

import pytest

from docstring_parser.common import DocstringStyle, ParseError
from docstring_parser.parser import compose, parse

from .cases import CASES_DIR, Case, read_case, run, write_case

CASE_PATHS = sorted(CASES_DIR.rglob("*.txt"))

# Cases whose composed docstring does not come back the same after another
# parse and compose, and why.
UNSTABLE_COMPOSE = {
    "corpus/pandas/pandas.core.computation.eval.eval.txt": (
        "numpydoc: an optional type with a default repeats 'optional'"
    ),
    "corpus/pandas/pandas.io.pytables.HDFStore.append.txt": (
        "numpydoc: 'default' in the description becomes a default value"
    ),
    "corpus/pydantic/pydantic.fields.Field.txt": (
        "google: an indented block in a description loses its indent"
    ),
    "corpus/scipy/scipy.signal._filter_design.sosfreqz.txt": (
        "numpydoc: a leading space in the short description is kept once"
    ),
    "google/examples/01.txt": (
        "google: an example titled like a section is composed as one"
    ),
    "google/google_typed_parameter_delimiters/03.txt": (
        "google: a type split over lines fails to parse once composed"
    ),
}


def _case_paths(paths: T.List[Path] = CASE_PATHS) -> T.Any:
    return pytest.mark.parametrize(
        "path", paths, ids=[str(path.relative_to(CASES_DIR)) for path in paths]
    )


@_case_paths()
def test_case(path: Path) -> None:
    """Test that every command in a case file gives its expected output."""
    case = read_case(path)
    actual = [
        (name, body if name == "input" else run(name, case.input))
        for name, body in case.sections
    ]
    if os.environ.get("UPDATE_CASES"):
        if actual != case.sections:
            write_case(path, Case(case.comments, actual))
        return
    for (name, expected), (_name, output) in zip(case.sections, actual):
        assert output == expected, f"=== {name}"


# Inputs with line endings of their own can't swap them for others.
@_case_paths([path for path in CASE_PATHS if b"\r" not in path.read_bytes()])
@pytest.mark.parametrize("line_ending", ["\r\n", "\r"], ids=["crlf", "cr"])
def test_case_line_endings(path: Path, line_ending: str) -> None:
    """Test that other line endings give every command the same output."""
    case = read_case(path)
    text = case.input.replace("\n", line_ending)
    for name, expected in case.sections:
        if name != "input":
            assert run(name, text) == expected, f"=== {name}"


@_case_paths()
def test_case_compose_is_stable(
    path: Path, request: pytest.FixtureRequest
) -> None:
    """Test that a composed docstring parses and composes back the same."""
    reason = UNSTABLE_COMPOSE.get(str(path.relative_to(CASES_DIR)))
    if reason:
        request.applymarker(pytest.mark.xfail(reason=reason, strict=True))
    case = read_case(path)
    styles = [
        DocstringStyle[name.split()[1].upper()]
        for name, _body in case.sections
        if name.startswith("parse ") and name != "parse auto"
    ]
    for style in styles:
        try:
            docstring = parse(case.input, style)
        except ParseError:
            continue
        composed = compose(docstring, style)
        assert compose(parse(composed, style), style) == composed, style
