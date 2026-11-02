"""Run the text case files in the cases directory.

Set UPDATE_CASES=1 to write the actual output into the files instead.
"""

import os
from pathlib import Path

import pytest

from .cases import CASES_DIR, Case, read_case, run, write_case

CASE_PATHS = sorted(CASES_DIR.rglob("*.txt"))


@pytest.mark.parametrize(
    "path",
    CASE_PATHS,
    ids=[str(path.relative_to(CASES_DIR)) for path in CASE_PATHS],
)
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
