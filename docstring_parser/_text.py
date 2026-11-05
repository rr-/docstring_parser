"""Text rules that every style shares."""

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
