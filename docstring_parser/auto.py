"""Auto-detection: parsing a docstring in the style it is written in."""

import re
import typing as T

from . import epydoc, google, numpydoc, rest
from ._sections import SectionSpec
from .common import BaseParser, Docstring, ParseError, ParseResult

# Any line that could start a field or a section in some style: a ReST
# ``:field``, an Epydoc ``@field``, a Google title ending in a colon, or a
# Numpydoc underline of dashes or equals signs, or ``..`` directive.
_FIELD_LINE = re.compile(
    r"^[^\S\n]*[:@]"
    r"|:[^\S\n]*$"
    r"|^[^\S\n]*(?:-+|=+)[^\S\n]*$"
    r"|^[^\S\n]*\.\.",
    flags=re.M,
)


def _has_no_fields(text: str) -> bool:
    """Tell whether no style can find a field or a section in the text.

    Every style then parses it with no meta and without raising, so the
    ReST result wins the tie that auto-detection would otherwise break
    after parsing it four times.
    """
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return _FIELD_LINE.search(text) is None


def detect(
    text: T.Optional[str],
    parsers: T.Sequence[T.Callable[[T.Optional[str]], Docstring]],
    shortcut: bool,
) -> Docstring:
    """Parse a docstring in every style and keep the result with most meta.

    :param parsers: each style's parse, ReST's first
    :param shortcut: parse text that no style finds a field in as ReST
        only; with a title that needs no marker, a style may find one
    """
    if not text or (shortcut and _has_no_fields(text)):
        return parsers[0](text)

    exc: T.Optional[Exception] = None
    rets = []
    for parse_style in parsers:
        try:
            ret = parse_style(text)
        except ParseError as ex:
            exc = ex
        else:
            rets.append(ret)

    if not rets:
        assert exc is not None
        raise exc

    return sorted(rets, key=lambda d: len(d.meta), reverse=True)[0]


def try_detect(
    text: T.Optional[str],
    parsers: T.Sequence[T.Callable[[T.Optional[str]], ParseResult]],
    shortcut: bool,
) -> ParseResult:
    """Parse a docstring in every style and keep the best result.

    A result with no problems beats one with problems, and then the one
    with most meta wins, as in :func:`detect`.

    :param parsers: each style's ``try_parse``, ReST's first
    :param shortcut: as for :func:`detect`
    """
    if not text or (shortcut and _has_no_fields(text)):
        return parsers[0](text)
    results = [try_parse_style(text) for try_parse_style in parsers]
    return min(
        results, key=lambda r: (bool(r.problems), -len(r.docstring.meta))
    )


class Parser(BaseParser):
    """Parser that tells a docstring's style and parses it in that style.

    It parses the docstring in every style and keeps the result with the
    most meta, preferring ReST, then Google, Numpydoc and Epydoc on a tie.
    """

    name = "auto"

    def __init__(
        self, sections: T.Optional[T.Sequence[SectionSpec]] = None
    ) -> None:
        """Set up a parser for every style.

        :param sections: the sections, or fields, every style recognises
            instead of its own
        """
        self._parsers = [
            rest.Parser(sections),
            google.Parser(sections),
            numpydoc.Parser(sections),
            epydoc.Parser(sections),
        ]
        self._shortcut = not any(spec.bare for spec in sections or ())

    def parse(self, text: T.Optional[str]) -> Docstring:
        """Parse a docstring in the style it is written in."""
        return detect(
            text, [parser.parse for parser in self._parsers], self._shortcut
        )

    def try_parse(self, text: T.Optional[str]) -> ParseResult:
        """Parse a docstring in the style it is written in, or the style
        that reads most of it."""
        return try_detect(
            text,
            [parser.try_parse for parser in self._parsers],
            self._shortcut,
        )
