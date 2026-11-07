"""Parse docstrings as per Sphinx notation."""

from .common import (
    BaseParser,
    Docstring,
    DocstringDeprecated,
    DocstringMeta,
    DocstringMethod,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
    ParseError,
    ParseResult,
    Problem,
    RenderingStyle,
)
from .parser import compose, parse, parse_from_object, try_parse
from .util import combine_docstrings

Style = DocstringStyle  # backwards compatibility

__all__ = [
    "parse",
    "try_parse",
    "parse_from_object",
    "combine_docstrings",
    "compose",
    "ParseError",
    "ParseResult",
    "Problem",
    "Docstring",
    "DocstringMeta",
    "BaseParser",
    "DocstringParam",
    "DocstringRaises",
    "DocstringReturns",
    "DocstringDeprecated",
    "DocstringMethod",
    "DocstringStyle",
    "RenderingStyle",
    "Style",
]
