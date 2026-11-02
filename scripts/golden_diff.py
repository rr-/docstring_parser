"""Show how parse results of the corpus differ from the recorded ones.

Use it to review a behavior change before accepting it with
``pytest docstring_parser/tests/test_corpus.py --update-golden``::

    python scripts/golden_diff.py            # legacy=False results
    python scripts/golden_diff.py --legacy   # legacy=True results
    python scripts/golden_diff.py --limit 0  # only the summary
"""

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docstring_parser.tests.test_corpus import (  # noqa: E402
    EXPECTED,
    _dump,
    compute_results,
    load_expected,
)


def main() -> None:
    """Print the differences and a summary."""
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n", maxsplit=1)[0]
    )
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    expected = load_expected(EXPECTED[args.legacy])
    actual = compute_results(args.legacy)
    changed = sorted(
        key for key, value in actual.items() if expected.get(key) != value
    )
    for key in changed[: args.limit]:
        print(f"=== {key}")
        diff = difflib.unified_diff(
            _dump(expected.get(key)).splitlines(),
            _dump(actual[key]).splitlines(),
            lineterm="",
            n=2,
        )
        print("\n".join(diff))
    print(f"{len(changed)} of {len(actual)} docstrings changed")


if __name__ == "__main__":
    main()
