"""Text case files: a docstring and what each command makes of it.

A case file is plain text. Lines starting with ``#`` before the first
section are comments. Each section opens with a ``=== <command>`` line and
holds every line up to the next one, byte for byte. The ``input`` section
is the docstring; every other section is the expected output of a command
run on it:

- ``parse <style>``: the parsed docstring, dumped by :func:`dump`
- ``detect``: the style that auto-detection picks
- ``compose <style> [<rendering>]``: the docstring parsed and composed
  back in a style, with a lowercase :class:`RenderingStyle` name that
  defaults to compact
- ``convert <style> <style>``: the docstring parsed in the first style
  and composed in the second one

Styles are the lowercase :class:`DocstringStyle` names.
"""

import enum
import re
import typing as T
from pathlib import Path

from docstring_parser.common import (
    Docstring,
    DocstringStyle,
    ParseError,
    RenderingStyle,
)
from docstring_parser.parser import compose, parse

CASES_DIR = Path(__file__).parent / "cases"

_HEADER = re.compile(r"=== (\S.*)")


class Case(T.NamedTuple):
    comments: T.List[str]
    sections: T.List[T.Tuple[str, str]]

    @property
    def input(self) -> str:
        return dict(self.sections)["input"]


def read_case(path: Path) -> Case:
    """Read a case file."""
    # Read the bytes so that \r in an input survives universal newlines.
    text = path.read_bytes().decode("utf-8")
    if text.endswith("\n"):
        text = text[:-1]
    comments: T.List[str] = []
    sections: T.List[T.Tuple[str, T.List[str]]] = []
    for line in text.split("\n"):
        match = _HEADER.fullmatch(line)
        if match:
            sections.append((match.group(1), []))
        elif sections:
            sections[-1][1].append(line)
        elif line.startswith("#"):
            comments.append(line)
        elif line:
            raise ValueError(f"{path}: text before the first section")
    names = [name for name, _lines in sections]
    if "input" not in names or len(set(names)) != len(names):
        raise ValueError(f"{path}: needs one input and unique sections")
    return Case(
        comments, [(name, "\n".join(lines)) for name, lines in sections]
    )


def write_case(path: Path, case: Case) -> None:
    """Write a case file so that :func:`read_case` gives it back."""
    for _name, body in case.sections:
        if any(_HEADER.fullmatch(line) for line in body.split("\n")):
            raise ValueError(f"{path}: a line looks like a section header")
    parts = list(case.comments)
    for name, body in case.sections:
        parts.append(f"=== {name}")
        parts.append(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(parts) + "\n").encode("utf-8"))


def _style(name: str) -> DocstringStyle:
    return DocstringStyle[name.upper()]


def _value(value: T.Any) -> T.List[str]:
    """Dump a value as one line, or a ``|`` block for multi-line text."""
    if isinstance(value, str) and "\n" in value:
        return ["|"] + ["  " + line for line in value.split("\n")]
    if isinstance(value, enum.Enum):
        return [value.name.lower()]
    return [repr(value)]


def _fields(obj: T.Any, skip: T.Container[str] = ()) -> T.List[str]:
    lines = []
    for key, value in vars(obj).items():
        if key in skip or value is None:
            continue
        first, *rest = _value(value)
        lines.append(f"{key}: {first}")
        lines.extend(rest)
    return lines


def dump(docstring: Docstring) -> str:
    """Render every attribute of a parsed docstring, one per line.

    Attributes that are None are left out. Strings are shown with repr, so
    an empty string and surrounding whitespace stay visible; multi-line
    strings become an indented block. Each meta lists its class and then
    its attributes. A param's raw type is shown only where it differs from
    its type.
    """
    lines = _fields(docstring, skip={"meta"})
    for meta in docstring.meta:
        skip = (
            {"raw_type_name"}
            if getattr(meta, "raw_type_name", None)
            == getattr(meta, "type_name", None)
            else ()
        )
        lines.append(f"- {type(meta).__name__}")
        lines.extend("  " + line for line in _fields(meta, skip))
    return "\n".join(lines)


def run(command: str, text: str) -> str:
    """Run a case command on a docstring and return its output."""
    name, *args = command.split()
    try:
        if name == "parse" and len(args) == 1:
            return dump(parse(text, _style(args[0])))
        if name == "detect" and not args:
            style = parse(text).style
            assert style is not None
            return style.name.lower()
        if name == "compose" and len(args) in {1, 2}:
            style = _style(args[0])
            rendering = RenderingStyle[(args[1:] or ["compact"])[0].upper()]
            return compose(parse(text, style), style, rendering)
        if name == "convert" and len(args) == 2:
            return compose(parse(text, _style(args[0])), _style(args[1]))
    except ParseError as ex:
        return f"ParseError: {ex}"
    raise ValueError(f"Unknown case command {command!r}")
