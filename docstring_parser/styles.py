"""Style enum declaration."""

import enum

from . import google, numpydoc, rest


class Style(enum.Enum):
    rest = 1
    google = 2
    numpydoc = 3
    auto = 255


STYLES = {
    Style.rest: rest.parse,
    Style.google: google.parse,
    Style.numpydoc: numpydoc.parse,
}
