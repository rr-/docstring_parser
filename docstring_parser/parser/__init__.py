"""Docstring parsing."""

from . import rest
from . import google
from .common import ParseError, Docstring

_styles = {"rest": rest.parse, "google": google.parse}


def parse(text: str, style: str = 'auto') -> Docstring:
    """
    Parse the docstring into its components.

    :param text: docstring text to parse
    :param style: docstring style, choose from: 'rest', 'google', 'auto'
    :returns: parsed docstring representation
    """

    if style != 'auto':
        return _styles[style](text)
    rets = []
    for parse_ in _styles.values():
        try:
            rets.append(parse_(text))
        except ParseError as e:
            exc = e
    if not rets:
        raise exc
    return sorted(rets, key=lambda d: len(d.meta), reverse=True)[0]
