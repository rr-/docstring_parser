"""Declare the sections, or fields, that a docstring style recognises.

A :class:`SectionSpec` says which titles start a section, what its items
document and how they are laid out. The same spec works for every style:
in Google and Numpydoc its titles are section titles, and in ReST and
Epydoc they are field names. Pass a list of specs as ``sections`` to
:func:`docstring_parser.parse` or to a style's parser to replace the
style's own, which :func:`default_sections` returns.

For example, to read ``Inputs:`` as a Google params section, and to keep
a ``Remarks:`` section as text of its own::

    from docstring_parser import DocstringStyle, parse
    from docstring_parser.sections import Kind, SectionSpec, default_sections

    sections = [
        *default_sections(DocstringStyle.GOOGLE),
        SectionSpec("Inputs", Kind.PARAM),
        SectionSpec("Remarks", Kind.TEXT),
    ]
    parse(text, DocstringStyle.GOOGLE, sections=sections)
"""

import typing as T

from . import epydoc, google, numpydoc, rest
from ._sections import Layout, SectionSpec
from .common import DocstringStyle, Kind

__all__ = ["Kind", "Layout", "SectionSpec", "default_sections"]


def default_sections(style: DocstringStyle) -> T.List[SectionSpec]:
    """Return the sections a style recognises when given none.

    :param style: any style but auto, which has no sections of its own
    """
    modules = {
        DocstringStyle.REST: rest,
        DocstringStyle.GOOGLE: google,
        DocstringStyle.NUMPYDOC: numpydoc,
        DocstringStyle.EPYDOC: epydoc,
    }
    if style not in modules:
        raise ValueError(f"{style} has no sections of its own")
    return modules[style].default_sections()
