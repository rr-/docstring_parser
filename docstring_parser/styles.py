"""Style enum declaration."""

import enum

from . import google, numpydoc, rest


class Style(enum.Enum):
    rest = enum.auto()
    google = enum.auto()
    numpydoc = enum.auto()
    auto = enum.auto()


STYLES = {
    Style.rest: rest.parse,
    Style.google: google.parse,
    Style.numpydoc: numpydoc.parse,
}
