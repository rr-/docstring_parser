"""Parse docstrings as per Sphinx notation."""

from .common import (
    Docstring,
    DocstringDeprecated,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
)
from .common import DocstringStyle  # backwards compatibility
from .common import DocstringStyle as Style
from .common import ParseError
from .parser import parse, unparse

__all__ = [
    "parse",
    "unparse",
    "ParseError",
    "Docstring",
    "DocstringMeta",
    "DocstringParam",
    "DocstringRaises",
    "DocstringReturns",
    "DocstringDeprecated",
    "DocstringStyle",
    "Style",
]
