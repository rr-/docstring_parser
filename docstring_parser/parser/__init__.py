"""Docstring parsing."""

from . import rest

from .common import ParseError

_styles = {"rest": rest.parse}


def parse(text: str, style: str = "auto"):
    """
    Parse the docstring into its components.

    :returns: parsed docstring
    """

    if style == "auto":
        rets = []
        for _parse in _styles.values():
            try:
                rets.append(_parse(text))
            except ParseError as e:
                exc = e
        if not rets:
            raise exc
        return sorted(rets, key=lambda ret: len(ret.meta), reverse=True)[0]
    else:
        return _styles[style]
