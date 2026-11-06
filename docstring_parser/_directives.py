"""reST directives in the free text of a docstring, which styles share.

A directive starts at the start of a line, as in::

    .. deprecated:: 1.0
       Use :func:`other` instead.

Its body is the indented lines after it. Readers cut the directives they
know out of the lines before reading the rest, and keep where each was.
"""

import re
import textwrap
import typing as T

from ._compose import description_lines
from ._lines import Lines
from .common import Docstring, DocstringDeprecated

# The first line of a ``deprecated`` directive, after its ``..``, with the
# version it gives, if any.
DEPRECATED = r"deprecated[ \t]*::(?P<version>[^\n]*?)"


def directive_pattern(names: T.Sequence[str]) -> T.Pattern[str]:
    """Match the first line of any of some directives.

    :param names: patterns for what follows each directive's ``..``
    """
    return re.compile(
        r"^\.\.[ \t]+(?:" + "|".join(names) + r")[ \t]*$", flags=re.M
    )


class Directive(T.NamedTuple):
    """A directive cut out of a docstring's lines."""

    #: Where it was, as an offset into the text of the lines left.
    offset: int
    #: The match of its first line.
    match: T.Match[str]
    #: Its indented body, without blank lines at the end.
    body: T.List[str]


def lead_directive(lines: Lines, pattern: T.Pattern[str]) -> Lines:
    """Make a directive starting the docstring start a line.

    On the first line, it is dedented with its body. After blank lines, it
    is read whatever its indent, as the short description it would
    otherwise give is.
    """
    if pattern.match(lines.raw.lstrip(" \t")):
        return lines.with_lead()
    first = lines.lines[0] if lines.lines else ""
    if first[:1].isspace() and pattern.match(first.lstrip()):
        lines = lines.without([])
        lines.lines[0] = first.lstrip()
        lines.text = "\n".join(lines.lines)
    return lines


def cut_directives(
    lines: Lines, pattern: T.Pattern[str]
) -> T.Tuple[Lines, T.List[Directive]]:
    """Cut the directives whose first line matches a pattern.

    :param pattern: matches a directive's first line, at the start of a
        line of ``lines.text``
    :returns: the lines left, and each directive cut, in order
    """
    cut: T.List[T.Tuple[int, int]] = []
    found: T.List[T.Tuple[T.Match[str], T.List[str]]] = []
    every = lines.lines
    for match in pattern.finditer(lines.text):
        start = lines.line_at(match.start())
        end = start + 1
        # A line holding only whitespace, such as a form feed, is blank.
        while end < len(every) and (
            every[end][:1] == " " or not every[end].strip()
        ):
            end += 1
        body_end = end
        while body_end > start + 1 and not every[body_end - 1].strip():
            body_end -= 1
        # Blank lines after the directive go with it when blank lines
        # before it already set it off, so no extra blank lines are left.
        if start and every[start - 1].strip():
            end = body_end
        cut.append((start, end))
        found.append((match, every[start + 1 : body_end]))
    if not cut:
        return lines, []
    left = lines.without(cut)
    directives = []
    removed = offset = index = 0
    for (start, end), (match, body) in zip(cut, found):
        while index < start - removed:
            offset += len(left.lines[index]) + 1
            index += 1
        directives.append(Directive(offset=offset, match=match, body=body))
        removed += end - start
    return left, directives


def body_text(body: T.List[str]) -> str:
    """Return a directive's body dedented, keeping relative indents.

    A line holding only whitespace, such as a form feed, is blank.
    """
    lines = (line if line.strip() else "" for line in body)
    return textwrap.dedent("\n".join(lines)).strip()


def deprecation(
    version: str, body: T.List[str], key: str
) -> DocstringDeprecated:
    """Build a deprecation from a ``deprecated`` directive.

    :param version: the text after ``::`` on the directive's line
    :param body: the directive's indented body
    """
    return DocstringDeprecated(
        body_text(body) or None, version=version.strip() or None, key=key
    )


def deprecation_lines(meta: DocstringDeprecated, indent: str) -> str:
    """Write a deprecation as a ``deprecated`` directive."""
    first = ".. deprecated::"
    if meta.version:
        first += f" {meta.version}"
    rest = meta.description.split("\n") if meta.description else []
    return "\n".join(
        [first] + [indent + line if line else "" for line in rest]
    )


def leading_deprecation(
    docstring: Docstring,
) -> T.Optional[DocstringDeprecated]:
    """Return the deprecation to write right after the short description.

    A deprecation that comes first goes there, as Numpydoc writes it,
    with the long description read from after it. Not when the long
    description is followed by a blank line, which it is only when written
    before the directive, or when it starts indented, which would read
    back as the directive's body.
    """
    top = docstring.meta[0] if docstring.meta else None
    long = docstring.long_description
    if not isinstance(top, DocstringDeprecated) or (
        docstring.blank_after_long_description or (long and long[0].isspace())
    ):
        return None
    return top


def description_with_deprecation(
    docstring: Docstring,
    top: T.Optional[DocstringDeprecated],
    indent: str,
    blank: bool = False,
) -> T.List[str]:
    """The short and long description, each followed by a blank if asked,
    with a deprecation as a directive between them.

    :param blank: whether a blank line always ends the directive before
        the long description, as Numpydoc needs; in the other styles, one
        reads back as a blank after the short description unless one is
        also before the directive
    """
    if top is None:
        return description_lines(docstring)
    long = docstring.long_description
    parts: T.List[str] = []
    if docstring.short_description:
        parts.append(docstring.short_description)
    if docstring.blank_after_short_description:
        parts.append("")
    # A blank line after the directive goes with it when one is before it.
    before = not parts or not parts[-1]
    parts.append(deprecation_lines(top, indent))
    if long:
        if blank or before:
            parts.append("")
        parts.append(long)
    elif before and not blank:
        parts.append("")
    return parts
