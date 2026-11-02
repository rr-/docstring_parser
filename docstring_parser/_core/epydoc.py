"""Epydoc-style (epytext field) docstring parsing."""

from ..common import Docstring, DocstringStyle, RenderingStyle
from . import fieldlist

KEYWORDS = fieldlist.Keywords(
    params={
        "param",
        "parameter",
        "arg",
        "argument",
        "keyword",
        "kwarg",
        "kwparam",
        "ivar",
        "cvar",
        "var",
    },
    param_types={"type": ["param", "keyword", "attribute"]},
    returns={"return", "returns", "yield", "yields"},
    return_types={
        "rtype": "returns",
        "returntype": "returns",
        "ytype": "yields",
    },
    raises={"raise", "raises", "except", "exception"},
    deprecation={"deprecated"},
)


def parse(text: str | None) -> Docstring:
    """Parse an epydoc-style docstring."""
    return fieldlist.parse(
        text, "@", KEYWORDS, DocstringStyle.EPYDOC, directives=False
    )


NAMES = fieldlist.FieldNames(
    params={"param": "param", "keyword": "keyword", "attribute": "ivar"},
    param_types={},
    returns={"returns": "return", "yields": "yield"},
    return_types={"returns": "rtype", "yields": "ytype"},
    raises="raise",
    deprecation="deprecated",
)


def compose(
    docstring: Docstring, rendering_style: RenderingStyle, indent: str
) -> str:
    """Render a docstring in epydoc style.

    ``CLEAN`` and ``EXPANDED`` put descriptions on the line after the field
    name. Parameter types are always written in ``@type`` fields.
    """
    return fieldlist.compose(
        docstring,
        "@",
        NAMES,
        expanded=rendering_style != RenderingStyle.COMPACT,
        inline_types=False,
        escape_names=False,
        indent=indent,
    )
