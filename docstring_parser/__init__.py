"""Parse docstrings as per Sphinx notation."""

from .common import (
    Docstring,
    DocstringDeprecated,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
    ParseError,
    RenderingStyle,
)
from .parser import compose, parse

Style = DocstringStyle  # backwards compatibility

__all__ = [
    "parse",
    "compose",
    "ParseError",
    "Docstring",
    "DocstringMeta",
    "DocstringParam",
    "DocstringRaises",
    "DocstringReturns",
    "DocstringDeprecated",
    "DocstringStyle",
    "RenderingStyle",
    "Style",
]
