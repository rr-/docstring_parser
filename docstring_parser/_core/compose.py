"""Helpers shared by the composers.

The composers are the inverse of the parsers: parsing composed text gives
back the same items. To keep the order of items, consecutive items with the
same key are rendered in one section, in the order of ``Docstring.meta``.
"""

import inspect
from collections.abc import Callable, Iterable, Iterator

from ..common import (
    Docstring,
    DocstringDeprecated,
    DocstringExample,
    DocstringMeta,
    DocstringParam,
)
from .fields import find_default
from .text import Lines, dedent


def description_lines(
    docstring: Docstring, indent: str, directives: bool = True
) -> Lines:
    """Render the descriptions, keeping blank lines.

    With ``directives``, deprecations are rendered as ``.. deprecated::``
    directives after the descriptions, each followed by a blank line. There
    no text can follow and be taken as part of a directive.
    """
    lines: Lines = []
    if docstring.short_description:
        lines.extend(docstring.short_description.splitlines())
    if docstring.blank_after_short_description:
        lines.append("")
    if docstring.long_description:
        lines.extend(docstring.long_description.splitlines())
    if docstring.blank_after_long_description:
        lines.append("")
    for item in docstring.meta if directives else ():
        if isinstance(item, DocstringDeprecated):
            head = ".. deprecated::"
            if item.version:
                head += f" {item.version}"
            lines.append(head)
            lines.extend(indented(item.description, indent))
            lines.append("")
    return lines


def finish(lines: Lines) -> str:
    """Join the lines of a composed docstring.

    PEP 257 cleaning, applied when parsing, removes the indentation of the
    first line separately from the others. When that would change the text,
    it is started with an empty line so that it is cleaned as a whole.
    """
    while lines and not lines[-1]:
        lines.pop()
    text = "\n".join(lines)
    if inspect.cleandoc(text) != text:
        text = "\n" + text
    return text


def without_deprecation(meta: list[DocstringMeta]) -> list[DocstringMeta]:
    """Return the items other than deprecations."""
    return [item for item in meta if not isinstance(item, DocstringDeprecated)]


def text_lines(text: str | None) -> Lines:
    """Split a text into lines; there are none if there is no text."""
    return text.splitlines() if text else []


def section_title(titles: dict[str, str], key: str) -> str:
    """Return the title of a section, e.g. ``See Also`` for ``see_also``."""
    return titles.get(key, key.replace("_", " ").title())


def indented(text: str | None, indent: str) -> Lines:
    """Indent every non-blank line of the text."""
    if not text:
        return []
    return [indent + line if line else "" for line in text.splitlines()]


def first_and_rest(
    head: str, text: str | None, indent: str, expanded: bool
) -> Lines:
    """Render an item: its header, then the text.

    The text starts on the header line unless ``expanded``, and its other
    lines are indented. It also starts on the next line when the indentation
    of its first line relative to the others would otherwise be lost.
    """
    if not text:
        return [head]
    first, *rest = text.splitlines()
    if expanded or first[:1].isspace() or dedent(rest) != rest:
        return [head] + indented(text, indent)
    sep = " " if head else ""
    return [f"{head}{sep}{first}"] + indented("\n".join(rest), indent)


def sections(
    meta: Iterable[DocstringMeta],
    starts_section: Callable[[DocstringMeta, DocstringMeta], bool],
) -> Iterator[tuple[str, list[DocstringMeta]]]:
    """Group consecutive items with the same key into sections.

    An item for which ``starts_section(item, previous)`` is true always
    starts a new one.
    """
    current: list[DocstringMeta] = []
    for item in meta:
        if current and (
            item.args[:1] != current[0].args[:1]
            or starts_section(item, current[-1])
        ):
            yield current[0].args[0], current
            current = []
        current.append(item)
    if current:
        yield current[0].args[0], current


def spec_parts(param: DocstringParam) -> list[str]:
    """Return the type specification of a parameter as a list of parts.

    The default is only included when it can not be found again in the
    description, and ``optional`` when it is not implied by a default.
    """
    parts = [param.type_name] if param.type_name else []
    default = param.default
    if default is not None and find_default(param.description) != default:
        parts.append(f"default: {default}")
    elif param.is_optional and default is None:
        parts.append("optional")
    return parts


def example_lines(example: DocstringExample) -> Lines:
    """Render an example: its description, then its snippet."""
    lines = text_lines(example.description)
    if example.description and example.snippet:
        lines.append("")
    return lines + text_lines(example.snippet) + [""]


def follows_text_example(previous: DocstringMeta) -> bool:
    """Tell whether the previous item is an example without snippet.

    Such an example can only be the last one in its section, since text
    after it would be taken as part of its description.
    """
    return isinstance(previous, DocstringExample) and not previous.snippet
