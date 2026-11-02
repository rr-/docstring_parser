"""Build the docstring corpus used by the golden tests.

The corpus is a deterministic sample of real-world docstrings extracted from
the source code of popular packages. Sources are read with ``ast``; nothing is
imported or executed.

Usage, with the package versions listed in the corpus README::

    uv pip install --no-deps --only-binary :all: --python-version 3.12 \
        --target /some/dir numpy==... scipy==... ...
    uv run --python 3.12 python scripts/build_corpus.py /some/dir

It must run on Python 3.12: the standard library docstrings come from the
running interpreter, and older versions of ``ast`` can't parse every source.

The result is written to ``docstring_parser/tests/corpus/docstrings.json``.
After rebuilding the corpus, regenerate the expected results with::

    uv run pytest docstring_parser/tests/test_corpus.py --update-golden
"""

import ast
import hashlib
import json
import re
import sys
import sysconfig
import typing as T
from pathlib import Path

OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "docstring_parser"
    / "tests"
    / "corpus"
    / "docstrings.json"
)

MARKERS = {
    "numpydoc": re.compile(
        r"^\s*(Parameters|Returns|Yields|Raises|Attributes|Examples|See Also"
        r"|Notes|Other Parameters|Warns|References)\s*\n\s*[-=]{3,}\s*$",
        flags=re.M,
    ),
    "google": re.compile(
        r"^\s*(Args|Arguments|Returns|Raises|Yields|Attributes|Example"
        r"|Examples|Note|Keyword Args):\s*$",
        flags=re.M,
    ),
    "rest": re.compile(
        r"^\s*:(param|returns?|rtype|raises?|type|ivar|var)\b", flags=re.M
    ),
    "epydoc": re.compile(
        r"^\s*@(param|return|rtype|raise|type|ivar|keyword)\b", flags=re.M
    ),
}

# (package directory, declared style, number of docstrings to sample)
SOURCES: T.List[T.Tuple[str, T.Optional[str], int]] = [
    ("numpy", "numpydoc", 210),
    ("scipy", "numpydoc", 210),
    ("pandas", "numpydoc", 210),
    ("sklearn", "numpydoc", 180),
    ("matplotlib", "numpydoc", 150),
    ("jax", "google", 180),
    ("keras", "google", 180),
    ("rich", "google", 150),
    ("absl", "google", 90),
    ("google/auth", "google", 90),
    ("transformers", "google", 180),
    ("torch", "google", 180),
    ("requests", "rest", 60),
    ("werkzeug", "rest", 120),
    ("click", "rest", 60),
    ("sqlalchemy", "rest", 150),
    ("boto3", "rest", 90),
    ("sphinx", "rest", 150),
    ("twisted", "epydoc", 270),
    ("pydoctor", "epydoc", 60),
    ("<stdlib>", None, 210),
]

MAX_LENGTH = 6_000
MARKED_FRACTION = 0.8

# The nodes ``ast.get_docstring`` accepts.
_DocNode = T.Union[
    ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef
]


def iter_docstrings(root: Path) -> T.Iterator[T.Tuple[str, str]]:
    """Yield ``(qualified name, raw docstring)`` for every docstring."""
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root.parent)
        if any(part in {"tests", "test", "testing"} for part in rel.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        stack: T.List[T.Tuple[_DocNode, str]] = [(tree, rel.as_posix())]
        while stack:
            node, name = stack.pop()
            doc = ast.get_docstring(node, clean=False)
            if doc and doc.strip():
                yield name, doc
            for child in ast.iter_child_nodes(node):
                if isinstance(
                    child,
                    (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    stack.append((child, f"{name}:{child.name}"))


def sample(
    root: Path, style: T.Optional[str], count: int
) -> T.List[T.Tuple[str, str]]:
    """Return a deterministic sample of docstrings found under root."""
    seen = set()
    marked, unmarked = [], []
    for name, doc in iter_docstrings(root):
        if len(doc) > MAX_LENGTH or doc in seen:
            continue
        seen.add(doc)
        is_marked = style is not None and MARKERS[style].search(doc)
        (marked if is_marked else unmarked).append((name, doc))

    def key(item: T.Tuple[str, str]) -> str:
        return hashlib.sha1(item[1].encode()).hexdigest()

    marked.sort(key=key)
    unmarked.sort(key=key)
    if style is None:
        return unmarked[:count]
    n_marked = min(len(marked), int(count * MARKED_FRACTION))
    return marked[:n_marked] + unmarked[: count - n_marked]


def main(target: str) -> None:
    """Build the corpus from packages installed in ``target``."""
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("build_corpus.py must run on Python 3.12")
    entries = []
    for package, style, count in SOURCES:
        if package == "<stdlib>":
            root = Path(sysconfig.get_paths()["stdlib"])
            roots = [
                p
                for p in sorted(root.iterdir())
                if p.name not in {"test", "idlelib", "site-packages"}
                and (p.suffix == ".py" or (p / "__init__.py").exists())
            ]
            items: T.List[T.Tuple[str, str]] = []
            for sub in roots:
                if sub.is_dir():
                    items.extend(sample(sub, None, count))
            items.sort(key=lambda i: hashlib.sha1(i[1].encode()).hexdigest())
            items = items[:count]
            label = "stdlib"
        else:
            root = Path(target) / package
            if not root.is_dir():
                raise SystemExit(f"{root} not found")
            items = sample(root, style, count)
            label = package.replace("/", ".")
        for name, doc in sorted(items):
            entries.append(
                {"id": f"{label}:{name}", "style": style, "text": doc}
            )
        print(f"{label:12} {len(items):4}", file=sys.stderr)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=0, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {len(entries)} docstrings to {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
