#!/usr/bin/env python3
"""Compare parse and compose speed against a base commit.

The package as it is at the base commit is extracted into a temporary
directory under another name, so that both versions load into one
process. Every workload then alternates between the two, over the same
inputs: the case files plus the docstrings of the running Python's
standard library. The inputs are timed in small chunks, base and working
tree back to back, so that load from other processes hits both sides
alike. The run fails when the median over the rounds of the working tree
to base ratio is above ``--gate`` on any workload.
"""

import argparse
import ast
import importlib
import io
import re
import statistics
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import time
import typing as T
from pathlib import Path

import docstring_parser
from docstring_parser.tests.cases import read_case

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "docstring_parser" / "tests" / "cases"
BASE_NAME = "docstring_parser_base"
STYLES = ("rest", "google", "numpydoc", "epydoc")
RENDERINGS = ("compact", "clean", "expanded")
CHUNK = 200
SKIP_STDLIB = {"site-packages", "test", "tests", "idlelib"}
ABSOLUTE_IMPORT = re.compile(r"^(\s*(?:from|import) )docstring_parser\b", re.M)


def case_inputs() -> T.List[str]:
    return [read_case(p).input for p in sorted(CASES_DIR.rglob("*.txt"))]


def stdlib_inputs() -> T.List[str]:
    """Docstrings of every stdlib module, read with ast, never imported."""
    lib = Path(sysconfig.get_paths()["stdlib"])
    kinds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    out = []
    for path in sorted(lib.rglob("*.py")):
        if SKIP_STDLIB & set(path.relative_to(lib).parts):
            continue
        try:
            tree = ast.parse(path.read_text("utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, kinds):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    out.append(doc)
    return out


def extract_base(ref: str, into: Path) -> None:
    """Write the package at ``ref`` into ``into`` as ``BASE_NAME``."""
    archive = subprocess.run(
        ["git", "archive", ref, "docstring_parser"],
        check=True,
        stdout=subprocess.PIPE,
        cwd=str(ROOT),
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(str(into))
    package = into / BASE_NAME
    (into / "docstring_parser").rename(package)
    for path in package.rglob("*.py"):
        text = path.read_text("utf-8")
        path.write_text(ABSOLUTE_IMPORT.sub(r"\1" + BASE_NAME, text), "utf-8")


def chunks(items: T.List[T.Any]) -> T.List[T.List[T.Any]]:
    return [items[i : i + CHUNK] for i in range(0, len(items), CHUNK)]


def workloads(
    package: T.Any, texts: T.List[str]
) -> T.Dict[str, T.List[T.Callable[[], None]]]:
    """Every workload this version of the package can run, in chunks."""
    style_of = package.DocstringStyle
    rendering_of = package.RenderingStyle
    parse, compose, error = package.parse, package.compose, package.ParseError

    def parse_all(part: T.List[str], style: T.Any) -> T.Callable[[], None]:
        def run() -> None:
            for text in part:
                try:
                    parse(text, style)
                except error:
                    pass

        return run

    def compose_all(
        part: T.List[T.Any], style: T.Any, rendering: T.Any
    ) -> T.Callable[[], None]:
        def run() -> None:
            for doc in part:
                compose(doc, style=style, rendering_style=rendering)

        return run

    out = {}
    for name in STYLES + ("auto",):
        style = style_of[name.upper()]
        out[f"parse {name}"] = [parse_all(p, style) for p in chunks(texts)]
    for name in STYLES:
        style = style_of[name.upper()]
        docs = []
        for text in texts:
            try:
                docs.append(parse(text, style))
            except error:
                pass
        for rendering in RENDERINGS:
            out[f"compose {name} {rendering}"] = [
                compose_all(p, style, rendering_of[rendering.upper()])
                for p in chunks(docs)
            ]
    return out


def timed(func: T.Callable[[], None]) -> float:
    start = time.perf_counter()
    func()
    return time.perf_counter() - start


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n")[0]
    )
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--rounds", type=int, default=15)
    parser.add_argument("--gate", type=float, default=1.10)
    args = parser.parse_args()

    texts = case_inputs() + stdlib_inputs()
    with tempfile.TemporaryDirectory() as tmp:
        extract_base(args.base, Path(tmp))
        sys.path.insert(0, tmp)
        base = workloads(importlib.import_module(BASE_NAME), texts)
    new = workloads(docstring_parser, texts)

    print(
        f"Python {sys.version.split()[0]}, {len(texts)} docstrings,"
        f" base {args.base}"
    )
    print(f"{'workload':26} {'base':>9} {'new':>9} {'new/base':>8}")
    slow = []
    for name, base_runs in base.items():
        pairs = list(zip(base_runs, new[name]))
        for base_run, new_run in pairs:
            base_run()
            new_run()
        ratios, base_times, new_times = [], [], []
        for i in range(args.rounds):
            old = now = 0.0
            for j, (base_run, new_run) in enumerate(pairs):
                if (i + j) % 2:
                    now += timed(new_run)
                    old += timed(base_run)
                else:
                    old += timed(base_run)
                    now += timed(new_run)
            ratios.append(now / old)
            base_times.append(old)
            new_times.append(now)
        old, now = min(base_times), min(new_times)
        ratio = statistics.median(ratios)
        flag = "  SLOWER" if ratio > args.gate else ""
        print(
            f"{name:26} {old * 1e3:7.1f}ms {now * 1e3:7.1f}ms"
            f" {ratio:8.2f}{flag}"
        )
        if ratio > args.gate:
            slow.append(name)
    if slow:
        print(f"More than {args.gate:.2f}x slower: {', '.join(slow)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
