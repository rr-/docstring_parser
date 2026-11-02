"""Golden tests over a corpus of real-world docstrings.

Every docstring in ``corpus/docstrings.json`` is parsed with its declared
style and with ``AUTO``, then composed back. The results must match the
recorded ones exactly:

- ``expected_legacy.json.gz`` pins the behavior of ``legacy=True`` (the
  default). It changes only with a deliberate fix to a legacy parser.
- ``expected.json.gz`` pins the behavior of ``legacy=False``. When it changes
  on purpose, regenerate it with ``pytest --update-golden`` and review the
  differences reported by ``python scripts/golden_diff.py``.

The files are gzipped JSON with one docstring per line.
"""

import difflib
import gzip
import json
import sys
import typing as T
from pathlib import Path

import pytest

from docstring_parser import DocstringStyle, RenderingStyle, compose, parse
from docstring_parser.tests._serialize import (
    STYLES,
    docstring_to_dict,
    parse_to_dict,
)

CORPUS_DIR = Path(__file__).parent / "corpus"
EXPECTED = {
    True: CORPUS_DIR / "expected_legacy.json.gz",
    False: CORPUS_DIR / "expected.json.gz",
}


def _load_corpus() -> T.List[T.Dict[str, T.Any]]:
    with (CORPUS_DIR / "docstrings.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def _run(text: str, style: DocstringStyle, legacy: bool):
    return parse(text, style, legacy=legacy)


def _compose(text: str, style: DocstringStyle, legacy: bool) -> T.Any:
    try:
        docstring = _run(text, style, legacy)
    except Exception:
        return None
    try:
        return compose(docstring)
    except Exception as ex:
        return {"error": type(ex).__name__}


def compute_results(legacy: bool) -> T.Dict[str, T.Any]:
    """Compute the results for the whole corpus."""
    results = {}
    for entry in _load_corpus():
        text = entry["text"]
        style = STYLES.get(entry["style"], DocstringStyle.AUTO)
        auto = parse_to_dict(_run, text, DocstringStyle.AUTO, legacy)
        results[entry["id"]] = {
            "auto_style": auto.get("style", auto.get("error")),
            "parsed": parse_to_dict(_run, text, style, legacy),
            "composed": _compose(text, style, legacy),
        }
    return results


def _dump(data: T.Any) -> str:
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False)


def _dump_results(results: T.Dict[str, T.Any]) -> str:
    """Serialize with one docstring per line to keep diffs reviewable."""
    lines = [
        json.dumps(key, ensure_ascii=False)
        + ": "
        + json.dumps(value, sort_keys=True, ensure_ascii=False)
        for key, value in sorted(results.items())
    ]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def load_expected(path: Path) -> T.Dict[str, T.Any]:
    """Load a gzipped golden file."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def save_expected(path: Path, results: T.Dict[str, T.Any]) -> None:
    """Save a gzipped golden file reproducibly (no timestamp)."""
    data = _dump_results(results).encode("utf-8")
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as fh:
            fh.write(data)


requires_new_parser = pytest.mark.skipif(
    sys.version_info < (3, 10), reason="legacy=False requires Python 3.10"
)


@pytest.mark.parametrize(
    "legacy",
    [True, pytest.param(False, marks=requires_new_parser)],
    ids=["legacy", "new"],
)
def test_corpus(legacy: bool, request: pytest.FixtureRequest) -> None:
    """Compare the parse results of the corpus with the recorded ones."""
    path = EXPECTED[legacy]
    actual = compute_results(legacy)
    if request.config.getoption("--update-golden"):
        save_expected(path, actual)
        # ty misreads the signature of pytest.skip on Python 3.8
        pytest.skip(f"updated {path.name}")  # ty: ignore[too-many-positional-arguments]
    expected = load_expected(path)

    assert sorted(actual) == sorted(expected), "corpus and results differ"
    mismatches = [key for key in expected if expected[key] != actual[key]]
    if mismatches:
        report = [f"{len(mismatches)} docstrings changed; first ones:"]
        for key in mismatches[:5]:
            report.append(f"=== {key}")
            report.extend(
                difflib.unified_diff(
                    _dump(expected[key]).splitlines(),
                    _dump(actual[key]).splitlines(),
                    lineterm="",
                    n=2,
                )
            )
        raise AssertionError("\n".join(report))


@requires_new_parser
@pytest.mark.parametrize("rendering_style", list(RenderingStyle))
def test_corpus_round_trip(rendering_style: RenderingStyle) -> None:
    """Without legacy, parsing composed docstrings gives the same result."""
    failures = []
    for entry in _load_corpus():
        style = STYLES.get(entry["style"])
        if style is None:
            continue
        docstring = parse(entry["text"], style, legacy=False)
        composed = compose(docstring, rendering_style=rendering_style)
        again = parse(composed, style, legacy=False)
        if docstring_to_dict(again) != docstring_to_dict(docstring):
            failures.append(entry["id"])
    assert not failures
