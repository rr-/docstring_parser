"""The main parsing routine."""

import inspect
import typing as T

from docstring_parser import auto, epydoc, google, numpydoc, rest
from docstring_parser.attrdoc import add_attribute_docstrings
from docstring_parser.common import (
    BaseParser,
    Docstring,
    DocstringStyle,
    RenderingStyle,
)
from docstring_parser.sections import ParserCache, SectionSpec

_STYLE_MAP = {
    DocstringStyle.REST: rest,
    DocstringStyle.GOOGLE: google,
    DocstringStyle.NUMPYDOC: numpydoc,
    DocstringStyle.EPYDOC: epydoc,
}


def _parse_in(
    module: T.Any,
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[SectionSpec]],
) -> Docstring:
    # A style's parse is called as before when no sections are given, so
    # code that wraps it keeps working.
    if sections is None:
        return module.parse(text)
    return module.parse(text, sections)


def parse(
    text: T.Optional[str],
    style: T.Union[DocstringStyle, str, BaseParser] = DocstringStyle.AUTO,
    sections: T.Optional[T.Sequence[SectionSpec]] = None,
) -> Docstring:
    """Parse the docstring into its components.

    :param text: docstring text to parse
    :param style: the style's name, such as ``"google"`` or
        ``DocstringStyle.GOOGLE``, or a parser to parse with
    :param sections: the sections, or fields, to recognise instead of the
        style's own, as described in :mod:`docstring_parser.sections`; in
        auto mode, every style recognises them. A parser has its own.
    :returns: parsed docstring representation
    """
    if isinstance(style, BaseParser):
        if sections is not None:
            raise ValueError("A parser has its sections; pass none")
        return style.parse(text)
    if not isinstance(style, DocstringStyle):
        style = DocstringStyle(style)
    if style != DocstringStyle.AUTO:
        return _parse_in(_STYLE_MAP[style], text, sections)
    if sections is None:
        return auto.detect(
            text, [module.parse for module in _STYLE_MAP.values()], True
        )
    return _auto_parsers.get(list(sections), auto.Parser, sections).parse(text)


_auto_parsers: ParserCache[auto.Parser] = ParserCache()


def parse_from_object(
    obj: T.Any,
    style: DocstringStyle = DocstringStyle.AUTO,
    sections: T.Optional[T.Sequence[SectionSpec]] = None,
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
    :param sections: the sections, or fields, to recognise instead of the
        style's own
    :returns: parsed docstring representation
    """
    docstring = parse(obj.__doc__, style=style, sections=sections)

    if inspect.isclass(obj) or inspect.ismodule(obj):
        add_attribute_docstrings(obj, docstring)

    return docstring


def compose(
    docstring: Docstring,
    style: T.Union[DocstringStyle, str, BaseParser] = DocstringStyle.AUTO,
    rendering_style: RenderingStyle = RenderingStyle.COMPACT,
    indent: str = "    ",
) -> str:
    """Render a parsed docstring into docstring text.

    :param docstring: parsed docstring representation
    :param style: the style to render, by its name, such as ``"google"``
        or ``DocstringStyle.GOOGLE``, or by its parser
    :param indent: the characters used as indentation in the docstring string
    :returns: docstring text
    """
    if isinstance(style, BaseParser):
        style = style.name
    if not isinstance(style, DocstringStyle):
        style = DocstringStyle(style)
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
