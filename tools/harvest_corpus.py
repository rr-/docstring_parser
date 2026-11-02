#!/usr/bin/env python3
"""Collect real-world docstrings into the corpus the snapshot tests parse.

Each package's wheel is downloaded from PyPI at a pinned version and its
docstrings are read from the source with ast, so nothing gets installed or
imported. A fixed sample per package becomes one case file per docstring
in docstring_parser/tests/cases/corpus/<package>/, with empty output
sections that ``UPDATE_CASES=1 pytest`` then fills in. The sample depends
only on the pinned wheel, so rerunning this gives the same files.

Run it on a recent Python: files using syntax newer than the running
interpreter can't be read and get skipped.
"""

import ast
import hashlib
import io
import json
import shutil
import sys
import typing as T
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from docstring_parser.tests.cases import (  # noqa: E402
    CASES_DIR,
    Case,
    write_case,
)

CORPUS_DIR = CASES_DIR / "corpus"
SAMPLE_SIZE = 100


class Package(T.NamedTuple):
    name: str
    version: str
    license: str
    style: str


PACKAGES = [
    Package("numpy", "2.5.4", "BSD-3-Clause", "numpydoc"),
    Package("scipy", "1.18.1", "BSD-3-Clause", "numpydoc"),
    Package("pandas", "3.1.0", "BSD-3-Clause", "numpydoc"),
    Package("jsonargparse", "4.53.0", "MIT", "google"),
    Package("rich", "15.0.0", "MIT", "google"),
    Package("pydantic", "2.14.2", "MIT", "google"),
    Package("google-auth", "2.62.0", "Apache-2.0", "google"),
    Package("requests", "2.34.2", "Apache-2.0", "rest"),
    Package("flask", "3.1.3", "BSD-3-Clause", "rest"),
    Package("sphinx", "9.2.0", "BSD-2-Clause", "rest"),
    Package("twisted", "26.10.0", "MIT", "epydoc"),
]


def fetch_wheel(package: Package) -> zipfile.ZipFile:
    """Download any wheel of the pinned version.

    Platform wheels differ only in compiled code, so any one of them carries
    the same Python sources.
    """
    url = f"https://pypi.org/pypi/{package.name}/{package.version}/json"
    with urllib.request.urlopen(url) as response:
        release = json.load(response)
    wheels = sorted(
        (f for f in release["urls"] if f["packagetype"] == "bdist_wheel"),
        key=lambda f: f["filename"],
    )
    if not wheels:
        raise RuntimeError(f"{package.name} {package.version} has no wheel")
    with urllib.request.urlopen(wheels[0]["url"]) as response:
        return zipfile.ZipFile(io.BytesIO(response.read()))


def iter_docstrings(
    module: str, tree: ast.Module
) -> T.Iterator[T.Tuple[str, str]]:
    """Yield (qualified name, raw docstring) for a module and its defs."""
    doc = ast.get_docstring(tree, clean=False)
    if doc is not None:
        yield module, doc

    def walk(node: ast.AST, prefix: str) -> T.Iterator[T.Tuple[str, str]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                name = f"{prefix}.{child.name}"
                doc = ast.get_docstring(child, clean=False)
                if doc is not None:
                    yield name, doc
                yield from walk(child, name)
            elif not isinstance(child, ast.Lambda):
                # Defs nested in if/try blocks still belong to the scope.
                yield from walk(child, prefix)

    yield from walk(tree, module)


def harvest(package: Package) -> T.List[T.Dict[str, str]]:
    """Return the sampled docstrings of a package, sorted by id."""
    wheel = fetch_wheel(package)
    found: T.Dict[str, str] = {}
    for path in sorted(wheel.namelist()):
        parts = path.split("/")
        if (
            not path.endswith(".py")
            or ".dist-info" in parts[0]
            or any(p in {"tests", "testing", "test"} for p in parts)
        ):
            continue
        try:
            tree = ast.parse(wheel.read(path))
        except SyntaxError as ex:
            print(f"{path}: skipped, {ex}", file=sys.stderr)
            continue
        module = path[: -len(".py")].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        for name, doc in iter_docstrings(module, tree):
            # Skip one-liners: every style parses those the same way.
            if len(doc.strip().splitlines()) < 2:
                continue
            key, n = name, 1
            while key in found:
                n += 1
                key = f"{name}#{n}"
            found[key] = doc

    def rank(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    sample = sorted(found, key=rank)[:SAMPLE_SIZE]
    return [{"id": key, "text": found[key]} for key in sorted(sample)]


def main() -> int:
    shutil.rmtree(CORPUS_DIR, ignore_errors=True)
    for package in PACKAGES:
        docstrings = harvest(package)
        comment = (
            f"# {package.name} {package.version} ({package.license}),"
            " harvested by tools/harvest_corpus.py"
        )
        for docstring in docstrings:
            case = Case(
                [comment],
                [
                    ("input", docstring["text"]),
                    (f"parse {package.style}", ""),
                    ("detect", ""),
                    (f"compose {package.style}", ""),
                ],
            )
            path = CORPUS_DIR / package.name / f"{docstring['id']}.txt"
            write_case(path, case)
        print(f"{package.name}: {len(docstrings)} docstrings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
