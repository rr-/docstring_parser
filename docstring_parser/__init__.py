"""Parse docstrings as per Sphinx notation."""

from .common import (
    Docstring,
    DocstringDeprecated,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    ParseError,
)
from .parser import parse
from .styles import Style

__all__ = [
    "parse",
    "ParseError",
    "Docstring",
    "DocstringMeta",
    "DocstringParam",
    "DocstringRaises",
    "DocstringReturns",
    "DocstringDeprecated",
    "Style",
]
