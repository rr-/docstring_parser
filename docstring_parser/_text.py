"""Text rules that every style shares."""

import re
import typing as T

from .common import Docstring


def clean_str(string: str) -> T.Optional[str]:
    """Strip a string, giving None if nothing is left."""
    return string.strip() or None


def split_description(ret: Docstring, text: str) -> None:
    """Set the short and long description from the text before any field.

    The short description is the first line, and the long description is
    everything after it.
    """
    parts = text.split("\n", 1)
    ret.short_description = parts[0].strip() or None
    if len(parts) > 1:
        rest = parts[1]
        ret.blank_after_short_description = rest.startswith("\n")
        ret.blank_after_long_description = rest.endswith("\n\n")
        ret.long_description = rest.strip() or None


def append_loose(
    ret: Docstring, chunks: T.Iterable[str], blank_around: bool
) -> None:
    """Add text found between or after the fields to the long description.

    :param chunks: the pieces of text, each a paragraph of its own
    :param blank_around: mark the description as followed by blank lines
    """
    loose = "\n\n".join(part.strip() for part in chunks if part.strip())
    if not loose:
        return
    if ret.short_description is None and ret.long_description is None:
        # With nothing before the fields, the text is the description, as
        # if written before them.
        split_description(ret, loose + "\n\n" if blank_around else loose)
        return
    ret.long_description = (
        f"{ret.long_description}\n\n{loose}" if ret.long_description else loose
    )
    if blank_around:
        ret.blank_after_short_description = True
        ret.blank_after_long_description = True


OPTIONAL_REGEX = re.compile(r"(?P<type>.*?)(?:, optional|\(optional\))$")

# A default given in the type, as in:
#
#   copy : bool, default True
#   copy : bool, default=True
#   copy : bool, default: True
#
DEFAULT_REGEX = re.compile(
    r"(?P<type>.*?)(?:, default|\(default\))(?: | |=| = |= |: |)*(?P<value>.*)$"  # noqa: E501
)


class TypeSpec(T.NamedTuple):
    """A param's type with the marks of an optional param split off."""

    type_name: T.Optional[str]
    is_optional: T.Optional[bool]
    default: T.Optional[str]


def type_spec(type_name: T.Optional[str]) -> TypeSpec:
    """Split the marks of an optional param, and its default, off its type.

    A param is optional when its type ends with ``?``, ``, optional`` or
    ``(optional)``, or names a default with ``, default`` followed by the
    value. The same rule holds in every style. A param with no type at all
    is neither optional nor not.
    """
    if type_name is None:
        return TypeSpec(type_name=None, is_optional=None, default=None)
    if type_name.endswith("?"):
        return TypeSpec(
            type_name=type_name[:-1], is_optional=True, default=None
        )
    is_optional = False
    default = None
    # "optional" may come before the default or after it.
    for regex in (OPTIONAL_REGEX, DEFAULT_REGEX, OPTIONAL_REGEX):
        match = regex.match(type_name)
        if match is not None:
            type_name = match.group("type").rstrip()
            is_optional = True
            if regex is DEFAULT_REGEX:
                default = match.group("value")
    return TypeSpec(
        type_name=type_name, is_optional=is_optional, default=default
    )
