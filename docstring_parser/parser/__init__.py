"""Docstring parsing."""

from . import rest
from . import google
from .common import ParseError, Docstring

_styles = {"rest": rest.parse, "google": google.parse}


def _parse_score(docstring: Docstring) -> int:
    """
    Produce a score for the parsing.

    :param Docstring docstring: parsed docstring representation
    :returns int: parse score, higher is better
    """

    return len(docstring.meta)


def parse(text: str, style: str = 'auto') -> Docstring:
    """
    Parse the docstring into its components.

    :param str text: docstring text to parse
    :param str style: docstring style, choose from: 'rest', 'auto'
    :returns Docstring: parsed docstring representation
    """

    if style == 'auto':
        rets = []
        for _parse in _styles.values():
            try:
                rets.append(_parse(text))
            except ParseError as e:
                exc = e
        if not rets:
            raise exc
        return sorted(rets, key=_parse_score, reverse=True)[0]
    else:
        return _styles[style](text)
