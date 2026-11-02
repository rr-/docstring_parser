"""Line-oriented helpers shared by all the parsers.

Docstrings are handled as lists of lines with trailing whitespace removed.
Blank lines are empty strings. Structure is derived from indentation only.
"""

import inspect
import re
from collections.abc import Callable, Sequence
from typing import NamedTuple

from ..common import normalize_line_endings

Lines = list[str]

_DEPRECATED_RE = re.compile(r"^\.\.\s+deprecated::(?P<version>.*)$")


def clean_lines(text: str) -> Lines:
    """Split a docstring into lines, cleaned according to PEP 257."""
    text = inspect.cleandoc(normalize_line_endings(text))
    return [line.rstrip() for line in text.splitlines()]


def indent_of(line: str) -> int:
    """Return the indentation width of a non-blank line."""
    return len(line) - len(line.lstrip())


def is_indented(line: str) -> bool:
    """Tell whether a line starts with whitespace; faster than indent_of."""
    return line[:1].isspace()


def dedent(lines: Lines) -> Lines:
    """Remove the indentation common to all non-blank lines."""
    widths = [indent_of(line) for line in lines if line]
    width = min(widths, default=0)
    return [line[width:] for line in lines]


def trim(lines: Lines) -> Lines:
    """Remove leading and trailing blank lines."""
    start, end = 0, len(lines)
    while start < end and not lines[start]:
        start += 1
    while end > start and not lines[end - 1]:
        end -= 1
    return lines[start:end]


def to_text(lines: Lines) -> str | None:
    """Join lines into text, or None if there is no content."""
    return "\n".join(trim(lines)) or None


def item_text(first: str, rest: Lines) -> str | None:
    """Build the text of an item whose first line was already consumed.

    ``first`` is what follows the item's header on its first line, and
    ``rest`` the following lines, which are dedented as a block.
    """
    return to_text([first.strip()] + dedent(rest))


def split_block(lines: Lines, start: int) -> tuple[Lines, int]:
    """Return the indented block that starts at ``start`` and its end.

    The block contains blank lines and lines indented deeper than zero. It
    ends at the first non-blank line without indentation. Trailing blank
    lines are left out of the block.
    """
    end = start
    while end < len(lines) and (not lines[end] or is_indented(lines[end])):
        end += 1
    while end > start and not lines[end - 1]:
        end -= 1
    return lines[start:end], end


def split_items(
    body: Lines, is_header: Callable[[str], bool] | None = None
) -> list[tuple[str, Lines]]:
    """Split a section into items: (first line, continuation lines).

    A line without indentation starts an item and the lines after it
    continue it. With ``is_header``, a line it rejects continues the
    previous item instead, except at the start of the section.
    """
    items: list[tuple[str, Lines]] = []
    for line in body:
        starts_item = (
            line
            and not is_indented(line)
            and (not items or is_header is None or is_header(line))
        )
        if starts_item:
            items.append((line, []))
        elif items:
            items[-1][1].append(line)
    return items


class Description(NamedTuple):
    """The free text of a docstring, split as stored in ``Docstring``."""

    short: str | None
    long: str | None
    blank_after_short: bool
    blank_after_long: bool


def split_description(
    lines: Lines, trailing: Sequence[str] = ()
) -> Description:
    """Split the free text found before the sections of a docstring.

    The short description is the first paragraph, the long description the
    rest. ``trailing`` is free text found after the sections; it is appended
    to the long description as a separate paragraph so that no text is lost,
    or makes up the description if there is no free text before the
    sections. The ``blank_after_*`` flags tell whether a blank line
    separates each part from what follows it.
    """
    lines = list(lines)
    if to_text(lines) is None:
        lines, trailing = list(trailing), ()
    while lines and not lines[0]:
        lines.pop(0)
    end = lines.index("") if "" in lines else len(lines)
    short = to_text(lines[:end])
    after = lines[end:]
    long = to_text(after)
    blank_after_long = long is not None and not after[-1]
    extra = to_text(list(trailing))
    if extra:
        long = f"{long}\n\n{extra}" if long else extra
    blank_after_short = short is not None and bool(after or extra)
    return Description(short, long, blank_after_short, blank_after_long)


class Deprecation(NamedTuple):
    """A ``.. deprecated::`` directive found in the free text."""

    version: str | None
    description: str | None


def extract_deprecations(
    lines: Lines, trailing: Sequence[str] = ()
) -> tuple[Lines, Lines, list[Deprecation]]:
    """Remove the ``.. deprecated::`` directives from the free text.

    A directive must start a line without indentation, either before the
    sections (``lines``) or after them (``trailing``). Its argument is the
    version and its indented content the description. The blank lines that
    follow a directive are removed with it.
    """
    lines, found = _extract_deprecations(lines)
    trailing, found_after = _extract_deprecations(list(trailing))
    return lines, trailing, found + found_after


def _extract_deprecations(
    lines: Lines,
) -> tuple[Lines, list[Deprecation]]:
    if not any(line.startswith("..") for line in lines):
        return list(lines), []
    rest: Lines = []
    found: list[Deprecation] = []
    i = 0
    while i < len(lines):
        match = _DEPRECATED_RE.match(lines[i])
        if match is None:
            rest.append(lines[i])
            i += 1
            continue
        body, i = split_block(lines, i + 1)
        while i < len(lines) and not lines[i]:
            i += 1
        version = match.group("version").strip() or None
        found.append(Deprecation(version, to_text(dedent(body))))
    return rest, found
