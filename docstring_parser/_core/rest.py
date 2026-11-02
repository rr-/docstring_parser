"""ReST-style (Sphinx field list) docstring parsing."""

from ..common import Docstring, DocstringStyle, RenderingStyle
from . import fieldlist

KEYWORDS = fieldlist.Keywords(
    params={
        "param",
        "parameter",
        "arg",
        "argument",
        "key",
        "keyword",
        "kwarg",
        "kwparam",
        "attribute",
        "ivar",
        "cvar",
        "var",
    },
    param_types={
        "type": ["param", "keyword"],
        "kwtype": ["keyword"],
        "vartype": ["attribute"],
    },
    returns={"return", "returns", "yield", "yields"},
    return_types={"rtype": "returns", "ytype": "yields"},
    raises={"raises", "raise", "except", "exception"},
    deprecation={"deprecated", "deprecation"},
)


def parse(text: str | None) -> Docstring:
    """Parse a ReST-style docstring."""
    return fieldlist.parse(
        text, ":", KEYWORDS, DocstringStyle.REST, directives=True
    )


NAMES = fieldlist.FieldNames(
    params={"param": "param", "keyword": "keyword", "attribute": "ivar"},
    param_types={"attribute": "vartype"},
    returns={"returns": "returns", "yields": "yields"},
    return_types={"returns": "rtype", "yields": "ytype"},
    raises="raises",
    deprecation=None,
)


def compose(
    docstring: Docstring, rendering_style: RenderingStyle, indent: str
) -> str:
    """Render a docstring in ReST style.

    ``EXPANDED`` puts descriptions on the line after the field name and
    parameter types in ``:type:`` fields. Otherwise simple types are written
    inline (``:param int x:``).
    """
    expanded = rendering_style == RenderingStyle.EXPANDED
    return fieldlist.compose(
        docstring,
        ":",
        NAMES,
        expanded=expanded,
        inline_types=not expanded,
        escape_names=True,
        indent=indent,
    )
