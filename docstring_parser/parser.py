"""The main parsing routine."""

from docstring_parser import epydoc, google, numpydoc, rest
from docstring_parser.common import (
    Docstring,
    DocstringStyle,
    ParseError,
    RenderingStyle,
)

STYLES = {
    DocstringStyle.rest: rest,
    DocstringStyle.google: google,
    DocstringStyle.numpydoc: numpydoc,
    DocstringStyle.epydoc: epydoc,
}


def parse(text: str, style: DocstringStyle = DocstringStyle.auto) -> Docstring:
    """Parse the docstring into its components.

    :param text: docstring text to parse
    :param style: docstring style
    :returns: parsed docstring representation
    """
    if style != DocstringStyle.auto:
        return STYLES[style].parse(text)

    rets = []
    for module in STYLES.values():
        try:
            rets.append(module.parse(text))
        except ParseError as e:
            exc = e

    if not rets:
        raise exc

    return sorted(rets, key=lambda d: len(d.meta), reverse=True)[0]


def unparse(
    docstring: Docstring,
    style: DocstringStyle = DocstringStyle.auto,
    rendering_style: RenderingStyle = RenderingStyle.compact,
    indent: str = "    ",
) -> str:
    """Render a parsed docstring into docstring text.

    :param docstring: parsed docstring representation
    :param style: docstring style to render (default renders style of `docstring`)
    :param indent: the characters used as indentation in the docstring string
    :returns: docstring text
    """
    if style != DocstringStyle.auto:
        return STYLES[style].unparse(
            docstring, rendering_style=rendering_style, indent=indent
        )
    else:
        return STYLES[docstring.style].unparse(
            docstring, rendering_style=rendering_style, indent=indent
        )
