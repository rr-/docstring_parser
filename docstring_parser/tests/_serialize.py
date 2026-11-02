"""Helpers to turn parse results into plain data for golden comparisons."""

import typing as T

from docstring_parser.common import Docstring, DocstringStyle, ParseError


def docstring_to_dict(docstring: Docstring) -> T.Dict[str, T.Any]:
    """Convert a parsed docstring into a JSON-serializable dict."""
    return {
        "style": docstring.style.name if docstring.style else None,
        "short_description": docstring.short_description,
        "long_description": docstring.long_description,
        "blank_after_short_description": (
            docstring.blank_after_short_description
        ),
        "blank_after_long_description": docstring.blank_after_long_description,
        "meta": [
            {"kind": type(meta).__name__, **vars(meta)}
            for meta in docstring.meta
        ],
        "params": [param.arg_name for param in docstring.params],
    }


def parse_to_dict(
    func: T.Callable[..., Docstring], *args: T.Any
) -> T.Dict[str, T.Any]:
    """Run a parse call and serialize its result or its ParseError."""
    try:
        return docstring_to_dict(func(*args))
    except ParseError as ex:
        return {"error": type(ex).__name__, "message": str(ex)}


STYLES = {
    "rest": DocstringStyle.REST,
    "google": DocstringStyle.GOOGLE,
    "numpydoc": DocstringStyle.NUMPYDOC,
    "epydoc": DocstringStyle.EPYDOC,
}
