"""The main parsing routine."""

from docstring_parser import google, numpydoc, rest
from docstring_parser.common import Docstring, ParseError, Style

STYLES = {
    Style.rest: rest.parse,
    Style.google: google.parse,
    Style.numpydoc: numpydoc.parse,
}


def parse(text: str, style: Style = Style.auto) -> Docstring:
    """Parse the docstring into its components.

    :param text: docstring text to parse
    :param style: docstring style
    :returns: parsed docstring representation
    """
    if style != Style.auto:
        return STYLES[style](text)

    rets = []
    for parse_ in STYLES.values():
        try:
            rets.append(parse_(text))
        except ParseError as e:
            exc = e

    if not rets:
        raise exc

    return sorted(rets, key=lambda d: len(d.meta), reverse=True)[0]
