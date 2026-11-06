#!/usr/bin/env python3
"""Compare parse and compose output with a base commit.

Both versions of the package load into one process, as in ``bench.py``.
Every input is parsed in each style and in auto mode, and every parsed
docstring is composed in each style and rendering. The run lists the
inputs whose output differs and fails if there are any. The inputs are
the case files, the standard library's docstrings and generated ones.
"""

import argparse
import collections
import importlib
import random
import sys
import tempfile
import typing as T
from pathlib import Path

from bench import BASE_NAME, case_inputs, extract_base, stdlib_inputs

import docstring_parser

STYLES = ("REST", "GOOGLE", "NUMPYDOC", "EPYDOC")
RENDERINGS = ("COMPACT", "CLEAN", "EXPANDED")

# Lines that generated docstrings are made of: titles, underlines, fields
# and items in every style, and the whitespace and punctuation that edge
# cases come from.
PIECES = [
    "Args:",
    "Arguments:",
    "Returns:",
    "Yields:",
    "Raises:",
    "Example:",
    "Examples:",
    "Attributes:",
    "Note:",
    "Parameters",
    "----------",
    "Returns",
    "-------",
    "Raises",
    "------",
    "Notes",
    "-----",
    "Examples",
    "--------",
    ".. deprecated:: 1.0",
    "..",
    "   deprecated::",
    "See Also",
    "x : int",
    "x (int): desc",
    "y: thing",
    "    x (int): desc",
    "    y: more",
    "        continued",
    "  shallow",
    "",
    "",
    "   ",
    "\t",
    "\tx: tabbed",
    "\x0c",
    " \x0c ",
    "\xa0x: nbsp",
    "Args:  ",
    "Args :",
    "Summary.",
    "    a",
    "    b : str, optional",
    "        desc of b",
    "  c",
    ">>> 1 + 1",
    "2",
    "    >>> f()",
    "x",
    "Default is 3.",
    "Args:\t",
    "Returns:\x0b",
    "Methods",
    "Other Parameters",
    "deprecated",
    "..  deprecated  ::",
    "\r\n",
    "Returns\r",
    "C++ Notes:",
    " Lead:",
    " Lead",
    "Trail :",
    "Trail  ",
    "Args (old):",
    "**Stars**",
    ".. versionadded:: 2",
    "Trail ",
    "Stars",
    ":param x: desc",
    ":param int y: desc",
    ":type x: str",
    ":returns: thing",
    ":rtype: int",
    ":raises ValueError: bad",
    ":raises:",
    ":meta:",
    ": no name:",
    ":param x:",
    "    continued field",
    "@param x: desc",
    "@type x: int",
    "@return: thing",
    "@rtype: str",
    "@raise ValueError: bad",
    "@yield: y",
    "@ytype: int",
    "@ivar a: attr",
    "@note: n",
    "@keyword k: kw",
    "x (List[int], optional): desc. Defaults to 3.",
    "y (Dict[str, int]): mapping",
    "    ValueError: if bad",
    "int: the result",
    "    Optional[int]: maybe",
    ":Example:",
]


def generated_inputs(count: int, seed: int = 1) -> T.List[str]:
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        lines = [rng.choice(PIECES) for _ in range(rng.randint(1, 14))]
        indent = rng.choice(["", "    ", "  ", "\t"])
        lines = [lines[0]] + [
            indent + line if line and rng.random() < 0.7 else line
            for line in lines[1:]
        ]
        text = "\n".join(lines)
        if rng.random() < 0.2:
            text = "\n" + text
        if rng.random() < 0.2:
            text = text + "\n" + indent
        out.append(text)
    return out


def dump(value: T.Any) -> str:
    """Render a parsed docstring, or anything in it, as text."""
    if hasattr(value, "meta"):
        fields = {k: v for k, v in vars(value).items() if k != "meta"}
        parts = [dump(fields)]
        # The base may lack fields the tree has added, which it cannot
        # differ in.
        parts.extend(
            f"{type(meta).__name__} {dump(_shared_fields(meta))}"
            for meta in value.meta
        )
        return "\n".join(parts)
    if isinstance(value, dict):
        return repr({k: dump(v) for k, v in value.items()})
    if hasattr(value, "name") and hasattr(value, "value"):
        return value.name
    return repr(value)


# Fields of the meta that the base may not have yet.
NEW_FIELDS = {"args", "kind", "key", "name", "extra", "raw_type_name"}


def _shared_fields(meta: T.Any) -> T.Dict[str, T.Any]:
    return {k: v for k, v in vars(meta).items() if k not in NEW_FIELDS}


def outputs(package: T.Any, text: str) -> T.Dict[str, str]:
    """Everything the package makes of one docstring."""
    style_of, rendering_of = package.DocstringStyle, package.RenderingStyle
    out = {}
    for style in STYLES + ("AUTO",):
        try:
            doc = package.parse(text, style_of[style])
        except Exception as ex:  # noqa: BLE001
            out[f"parse {style}"] = f"{type(ex).__name__}: {ex}"
            continue
        out[f"parse {style}"] = dump(doc)
        for target in STYLES:
            for rendering in RENDERINGS:
                key = f"compose {style} {target} {rendering}"
                try:
                    out[key] = package.compose(
                        doc,
                        style=style_of[target],
                        rendering_style=rendering_of[rendering],
                    )
                except Exception as ex:  # noqa: BLE001
                    out[key] = f"{type(ex).__name__}: {ex}"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n")[0]
    )
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--generated", type=int, default=20000)
    parser.add_argument("--show", type=int, default=5)
    args = parser.parse_args()

    named = [("case", t) for t in case_inputs()]
    named += [("stdlib", t) for t in stdlib_inputs()]
    named += [("generated", t) for t in generated_inputs(args.generated)]
    with tempfile.TemporaryDirectory() as tmp:
        extract_base(args.base, Path(tmp))
        sys.path.insert(0, tmp)
        base = importlib.import_module(BASE_NAME)
        differ = []
        for origin, text in named:
            old, new = outputs(base, text), outputs(docstring_parser, text)
            keys = [k for k in old if old[k] != new.get(k)]
            if keys:
                differ.append((origin, text, keys, old, new))

    print(f"{len(named)} docstrings, {len(differ)} differ from {args.base}")
    counts = collections.Counter(
        key.rsplit(" ", 1)[0] if key.startswith("compose") else key
        for _origin, _text, keys, _old, _new in differ
        for key in keys
    )
    for key, count in sorted(counts.items()):
        print(f"  {key}: {count}")
    for origin, text, keys, old, new in differ[: args.show]:
        print(f"\n--- {origin} input {text!r}")
        for key in keys[:3]:
            print(f"  {key}\n    base: {old[key]!r}\n    new:  {new[key]!r}")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())
