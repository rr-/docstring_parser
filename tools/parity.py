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
import sys
import tempfile
import typing as T
from pathlib import Path

from bench import BASE_NAME, case_inputs, extract_base, stdlib_inputs

import docstring_parser
from docstring_parser.tests.generated import generated_inputs

STYLES = ("REST", "GOOGLE", "NUMPYDOC", "EPYDOC")
RENDERINGS = ("COMPACT", "CLEAN", "EXPANDED")


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
NEW_FIELDS = {
    "args",
    "kind",
    "key",
    "name",
    "extra",
    "raw_type_name",
    "title",
}


def _shared_fields(meta: T.Any) -> T.Dict[str, T.Any]:
    return {k: v for k, v in vars(meta).items() if k not in NEW_FIELDS}


def outputs(
    package: T.Any, text: str
) -> T.Tuple[T.Dict[str, str], T.Set[str]]:
    """Everything the package makes of one docstring.

    Also the styles it fails to parse the docstring in.
    """
    style_of, rendering_of = package.DocstringStyle, package.RenderingStyle
    out, failed = {}, set()
    for style in STYLES + ("AUTO",):
        try:
            doc = package.parse(text, style_of[style])
        except Exception as ex:  # noqa: BLE001
            out[f"parse {style}"] = f"{type(ex).__name__}: {ex}"
            failed.add(style)
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
    return out, failed


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
        # Inputs one side fails to parse in a style the other parses in.
        one_sided: T.Dict[str, list] = {
            "parses only in base": [],
            "parses only in tree": [],
        }
        for origin, text in named:
            old, old_failed = outputs(base, text)
            new, new_failed = outputs(docstring_parser, text)
            only_base = new_failed - old_failed
            only_tree = old_failed - new_failed
            for label, styles in (
                ("parses only in base", only_base),
                ("parses only in tree", only_tree),
            ):
                if styles:
                    keys = [f"parse {style}" for style in sorted(styles)]
                    one_sided[label].append((origin, text, keys, old, new))
            # The compose output of a style only one side parses in has
            # nothing to compare with.
            skip = only_base | only_tree
            keys = [
                k
                for k in dict.fromkeys([*old, *new])
                if k.split(" ")[1] not in skip and old.get(k) != new.get(k)
            ]
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
    for label, items in one_sided.items():
        if items:
            origins = collections.Counter(origin for origin, *_ in items)
            print(
                f"{len(items)} {label}: "
                + ", ".join(f"{o} {n}" for o, n in sorted(origins.items()))
            )
    for label, items in [("differs", differ), *one_sided.items()]:
        for origin, text, keys, old, new in items[: args.show]:
            print(f"\n--- {origin} input {label}: {text!r}")
            for key in keys[:3]:
                print(
                    f"  {key}\n    base: {old.get(key)!r}"
                    f"\n    new:  {new.get(key)!r}"
                )
    return 1 if differ or any(one_sided.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
