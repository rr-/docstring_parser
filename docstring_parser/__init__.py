"""Parse docstrings as per Sphinx notation."""

from .common import (
    Docstring,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringDeprecated,
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
