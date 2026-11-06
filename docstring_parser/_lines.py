"""The lines of a docstring, which every style reads.

A docstring is normalised and dedented once, into :class:`Lines`. Readers
search its text and get line numbers and indents from it, so that all
styles agree on where a line starts and how far it is indented.

The dedenting is done here rather than by ``inspect.cleandoc``, because
Python 3.13 changed how that measures indentation: it strips only spaces,
so a blank line holding a tab, a form feed or a ``\\r`` counts as text with
no indent, and nothing in the docstring is dedented. The same docstring
would parse differently from one Python version to the next. Here every
line holding only whitespace counts as blank, on every version, and line
endings are made plain newlines first.
"""

import bisect
import typing as T


def normalize_line_endings(text: str) -> str:
    """Turn Windows and old Mac line endings into plain newlines.

    ``inspect.cleandoc`` splits lines on ``\\n`` only, so a ``\\r`` stays at
    the end of each line. From Python 3.13 on it measures indentation by
    stripping spaces only, so a blank line holding just ``\\r`` counts as
    unindented text and nothing gets dedented.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _dedent(text: str) -> T.Tuple[T.List[str], int]:
    """Dedent a docstring's lines, and count the blank lines cut at its top."""
    if "\n" not in text:
        line = text.expandtabs().lstrip()
        return ([line], 0) if line else ([], 0)
    lines = text.expandtabs().split("\n")
    margin = None
    for line in lines[1:]:
        content = len(line.lstrip())
        if content:
            indent = len(line) - content
            if margin is None or indent < margin:
                margin = indent
    lines[0] = lines[0].lstrip()
    if margin:
        lines[1:] = [line[margin:] for line in lines[1:]]
    while lines and not lines[-1]:
        lines.pop()
    start = 0
    while start < len(lines) and not lines[start]:
        start += 1
    return (lines[start:] if start else lines), start


def dedent_lines(text: str) -> T.List[str]:
    """Dedent a docstring's lines as ``inspect.cleandoc`` did before 3.13.

    The first line loses its leading whitespace, and the others lose the
    smallest indent among them. Blank lines at either end are dropped. A
    line holding only whitespace counts as blank, on every version.
    """
    return _dedent(text)[0]


def cleandoc(text: str) -> str:
    """Dedent a docstring as ``inspect.cleandoc`` did before Python 3.13.

    From 3.13 on, ``inspect.cleandoc`` measures indentation by stripping
    spaces only, so a blank line holding a tab or a form feed counts as
    text with no indent and nothing gets dedented. Here every line holding
    only whitespace counts as blank, on every version.
    """
    return "\n".join(dedent_lines(text))


class Lines:
    """A docstring with normalised line endings, dedented once.

    :ivar raw: the text with plain newlines, before dedenting
    :ivar lines: the dedented lines, without blank lines at either end
    :ivar text: the dedented lines joined with newlines, for searching
    """

    __slots__ = ("_lead", "_skipped", "_starts", "lines", "raw", "text")

    def __init__(self, text: str, lead: bool = False) -> None:
        """Normalise and dedent a docstring.

        :param text: the docstring
        :param lead: dedent the first line with the others, as if the
            docstring started on the line after the quotes
        """
        if "\r" in text:
            text = normalize_line_endings(text)
        self.raw = text
        self.lines, skipped = _dedent("\n" + text if lead else text)
        # The lines of the docstring as written before the first one kept.
        self._skipped = skipped - 1 if lead else skipped
        self.text = "\n".join(self.lines)
        self._starts: T.Optional[T.List[int]] = None
        self._lead: T.Optional[Lines] = self if lead else None

    def with_lead(self) -> "Lines":
        """The same docstring dedented as if it started on a new line."""
        if self._lead is None:
            self._lead = Lines(self.raw, lead=True)
        return self._lead

    def line_at(self, offset: int) -> int:
        """Return the index of the line holding an offset into ``text``."""
        if self._starts is None:
            starts = [0]
            for line in self.lines[:-1]:
                starts.append(starts[-1] + len(line) + 1)
            self._starts = starts
        return bisect.bisect_right(self._starts, offset) - 1

    def source_line(self, offset: int) -> int:
        """Return the line of the docstring as written, from 1, holding an
        offset into ``text``."""
        return self.line_at(offset) + self._skipped + 1

    def indent(self, index: int) -> int:
        """Return the indent of a line, or -1 if it holds only whitespace."""
        line = self.lines[index]
        content = len(line.lstrip())
        return len(line) - content if content else -1
