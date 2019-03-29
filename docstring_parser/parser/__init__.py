"""Docstring parsing."""

import enum

from . import google, rest
from .common import Docstring, ParseError

try:
    from . import numpy
except ImportError as e:
    numpy = e


class Style(enum.Enum):
    rest = enum.auto()
    google = enum.auto()
    auto = enum.auto()
    numpy = enum.auto()


_styles = {Style.rest: rest, Style.google: google, Style.numpy: numpy}


def parse(text: str, style: Style = Style.auto) -> Docstring:
    """
    Parse the docstring into its components.

    :param text: docstring text to parse
    :param style: docstring style
    :returns: parsed docstring representation
    """

    if style != Style.auto:
        if isinstance(_styles[style], Exception):
            raise _styles[style]
        return _styles[style].parse(text)
    rets = []
    for style_ in _styles.values():
        try:
            rets.append(style_.parse(text))
        except ParseError as e_:
            exc = e_
        except ImportError:
            pass
    if not rets:
        raise exc
    return sorted(rets, key=lambda d: len(d.meta), reverse=True)[0]
