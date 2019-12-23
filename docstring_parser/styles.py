"""Style enum declaration."""

import enum

from . import google, rest


class Style(enum.Enum):
    rest = enum.auto()
    google = enum.auto()
    auto = enum.auto()


STYLES = {Style.rest: rest.parse, Style.google: google.parse}
