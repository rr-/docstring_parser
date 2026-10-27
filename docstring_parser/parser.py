"""The main parsing routine."""

import inspect
import re
import typing as T

from docstring_parser import epydoc, google, numpydoc, rest
from docstring_parser.attrdoc import add_attribute_docstrings
from docstring_parser.common import (
    Docstring,
    DocstringStyle,
    ParseError,
    RenderingStyle,
)

_STYLE_MAP = {
    DocstringStyle.REST: rest,
    DocstringStyle.GOOGLE: google,
    DocstringStyle.NUMPYDOC: numpydoc,
    DocstringStyle.EPYDOC: epydoc,
}

# Any line that could start a field or a section in some style: a ReST
# ``:field``, an Epydoc ``@field``, a Google title ending in a colon, or a
# Numpydoc dashes underline or ``..`` directive.
_FIELD_LINE = re.compile(
    r"^[^\S\n]*[:@]"
    r"|:[^\S\n]*$"
    r"|^[^\S\n]*-+[^\S\n]*$"
    r"|^[^\S\n]*\.\.",
    flags=re.M,
)

_NUMPYDOC_TITLE_PATTERNS = (
    numpydoc.Section.title_pattern,
    numpydoc._SphinxSection.title_pattern,
)


def _has_no_fields(text: str) -> bool:
    """Tell whether no style can find a field or a section in the text.

    Every style then parses it with no meta and without raising, so the
    ReST result wins the tie that auto-detection would otherwise break
    after parsing it four times.
    """
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    # A custom Numpydoc section may match its title any way it likes.
    if any(
        type(section).title_pattern not in _NUMPYDOC_TITLE_PATTERNS
        for section in numpydoc.DEFAULT_SECTIONS
    ):
        return False
    return _FIELD_LINE.search(text) is None


def parse(
    text: T.Optional[str], style: DocstringStyle = DocstringStyle.AUTO
) -> Docstring:
    """Parse the docstring into its components.

    :param text: docstring text to parse
    :param style: docstring style
    :returns: parsed docstring representation
    """
    if style != DocstringStyle.AUTO:
        return _STYLE_MAP[style].parse(text)

    if not text or _has_no_fields(text):
        return rest.parse(text)

    exc: T.Optional[Exception] = None
    rets = []
    for module in _STYLE_MAP.values():
        try:
            ret = module.parse(text)
        except ParseError as ex:
            exc = ex
        else:
            rets.append(ret)

    if not rets:
        assert exc is not None
        raise exc

    return sorted(rets, key=lambda d: len(d.meta), reverse=True)[0]


def parse_from_object(
    obj: T.Any,
    style: DocstringStyle = DocstringStyle.AUTO,
) -> Docstring:
    """Parse the object's docstring(s) into its components.

    The object can be anything that has a ``__doc__`` attribute. In contrast to
    the ``parse`` function, ``parse_from_object`` is able to parse attribute
    docstrings which are defined in the source code instead of ``__doc__``.

    Currently only attribute docstrings defined at class and module levels are
    supported. Attribute docstrings defined in ``__init__`` methods are not
    supported.

    When given a class, only the attribute docstrings of that class are parsed,
    not its inherited classes. This is a design decision. Separate calls to
    this function should be performed to get attribute docstrings of parent
    classes.

    :param obj: object from which to parse the docstring(s)
    :param style: docstring style
    :returns: parsed docstring representation
    """
    docstring = parse(obj.__doc__, style=style)

    if inspect.isclass(obj) or inspect.ismodule(obj):
        add_attribute_docstrings(obj, docstring)

    return docstring


def compose(
    docstring: Docstring,
    style: DocstringStyle = DocstringStyle.AUTO,
    rendering_style: RenderingStyle = RenderingStyle.COMPACT,
    indent: str = "    ",
) -> str:
    """Render a parsed docstring into docstring text.

    :param docstring: parsed docstring representation
    :param style: docstring style to render
    :param indent: the characters used as indentation in the docstring string
    :returns: docstring text
    """
    if style == DocstringStyle.AUTO:
        if docstring.style is None:
            raise ValueError(
                "Docstring has no style to render with; pass one explicitly"
            )
        style = docstring.style
    module = _STYLE_MAP[style]
    return module.compose(
        docstring, rendering_style=rendering_style, indent=indent
    )
