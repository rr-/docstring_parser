"""Docstring parsing."""

import enum

from . import google, rest
from .common import Docstring, ParseError


class Style(enum.Enum):
    rest = enum.auto()
    google = enum.auto()
    auto = enum.auto()


_styles = {Style.rest: rest.parse, Style.google: google.parse}


def parse(text: str, style: Style = Style.auto) -> Docstring:
    """
    Parse the docstring into its components.

    :param text: docstring text to parse
    :param style: docstring style
    :returns: parsed docstring representation
    """

    if style != Style.auto:
        return _styles[style](text)
    rets = []
    for parse_ in _styles.values():
        try:
            rets.append(parse_(text))
        except ParseError as e:
            exc = e
    if not rets:
        raise exc
    return sorted(rets, key=lambda d: len(d.meta), reverse=True)[0]
