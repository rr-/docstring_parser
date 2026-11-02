"""Construction of docstring items, shared by all the parsers.

Every style maps its keywords to the same canonical keys, which become the
first element of ``DocstringMeta.args``:

- ``param``, ``keyword``, ``other_param``, ``receives`` and ``attribute``
  for :class:`DocstringParam`;
- ``returns`` and ``yields`` for :class:`DocstringReturns`;
- ``raises`` and ``warns`` for :class:`DocstringRaises`;
- ``examples`` for :class:`DocstringExample`;
- ``deprecation`` for :class:`DocstringDeprecated`.

Any other key gives a plain :class:`DocstringMeta`.
"""

import re
from collections.abc import Iterable, Sequence

from ..common import (
    Docstring,
    DocstringDeprecated,
    DocstringExample,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
)
from .fields import find_default, normalize_space, parse_type_spec
from .text import (
    Deprecation,
    Lines,
    extract_deprecations,
    split_description,
    to_text,
)

KEY_ALIASES = {
    "param": "param",
    "parameter": "param",
    "params": "param",
    "parameters": "param",
    "arg": "param",
    "argument": "param",
    "args": "param",
    "arguments": "param",
    "key": "param",
    "keyword": "keyword",
    "kwarg": "keyword",
    "kwparam": "keyword",
    "other_param": "other_param",
    "receives": "receives",
    "attribute": "attribute",
    "attr": "attribute",
    "ivar": "attribute",
    "cvar": "attribute",
    "var": "attribute",
    "return": "returns",
    "returns": "returns",
    "yield": "yields",
    "yields": "yields",
    "raise": "raises",
    "raises": "raises",
    "except": "raises",
    "exception": "raises",
    "exceptions": "raises",
    "warn": "warns",
    "warns": "warns",
    "example": "examples",
    "examples": "examples",
    "deprecated": "deprecation",
    "deprecation": "deprecation",
}

PARAM_KEYS = {"param", "keyword", "other_param", "receives", "attribute"}
RETURNS_KEYS = {"returns", "yields"}
RAISES_KEYS = {"raises", "warns"}


def canonical_key(key: str) -> str:
    """Map a style specific keyword to its canonical key."""
    return KEY_ALIASES.get(key.lower(), key)


def section_key(title: str) -> str:
    """Build the key of a section from its title, e.g. ``see_also``."""
    return re.sub(r"\W+", "_", title.strip().lower()).strip("_")


def assemble(
    style: DocstringStyle,
    free: Lines,
    meta: Iterable[DocstringMeta],
    trailing: Sequence[str] = (),
    *,
    directives: bool = True,
) -> Docstring:
    """Create a non-legacy docstring from the parts found by a parser.

    ``free`` is the free text before the sections or fields, ``meta`` the
    items parsed from them and ``trailing`` the free text after them. With
    ``directives``, the ``.. deprecated::`` directives in the free text
    become the first items.

    The ``blank_after_*`` flags tell whether a blank line separates a part
    from the next one, so they are False when nothing follows.
    """
    if directives:
        free, trailing, deprecations = extract_deprecations(free, trailing)
        meta = [*map(make_deprecation, deprecations), *meta]
    description = split_description(free, trailing)
    ret = Docstring(style=style)
    ret.legacy = False
    ret.meta = list(meta)
    ret.short_description = description.short
    ret.long_description = description.long
    if ret.meta:
        ret.blank_after_short_description = description.blank_after_short
        ret.blank_after_long_description = description.blank_after_long
    else:
        ret.blank_after_short_description = bool(
            description.short and description.long
        )
    return ret


def make_param(
    key: str,
    name: str,
    type_spec: str | None,
    description: str | None,
) -> DocstringParam:
    """Create a parameter or attribute item.

    The default comes from the type specification or else from the
    description. Having a default makes the item optional.
    """
    spec = parse_type_spec(type_spec)
    default = spec.default
    if default is None:
        default = find_default(description)
    return DocstringParam(
        args=[key, name],
        description=description,
        arg_name=name,
        type_name=spec.type_name,
        is_optional=spec.is_optional or default is not None,
        default=default,
    )


def make_params(
    key: str,
    names: list[str],
    type_spec: str | None,
    description: str | None,
) -> list[DocstringMeta]:
    """Create one parameter item per name, as for ``x, y : int``."""
    return [make_param(key, name, type_spec, description) for name in names]


def make_returns(
    key: str,
    type_name: str | None,
    description: str | None,
    return_name: str | None = None,
) -> DocstringReturns:
    """Create a returns or yields item."""
    return DocstringReturns(
        args=[key],
        description=description,
        type_name=normalize_space(type_name) or None if type_name else None,
        is_generator=key == "yields",
        return_name=return_name,
    )


def make_raises(
    key: str, type_name: str | None, description: str | None
) -> DocstringRaises:
    """Create a raises or warns item."""
    type_name = normalize_space(type_name) or None if type_name else None
    return DocstringRaises(
        args=[key, type_name] if type_name else [key],
        description=description,
        type_name=type_name,
    )


def make_deprecation(deprecation: Deprecation) -> DocstringDeprecated:
    """Create a deprecation item from a parsed directive."""
    return DocstringDeprecated(
        args=["deprecation"],
        description=deprecation.description,
        version=deprecation.version,
    )


def make_meta(key: str, description: str | None, *args: str) -> DocstringMeta:
    """Create an item for a section without a specific meaning."""
    return DocstringMeta(args=[key, *args], description=description)


def make_single(key: str, lines: Lines) -> list[DocstringMeta]:
    """Create the items of a section that holds free text."""
    if key == "examples":
        return split_examples(lines)
    text = to_text(lines)
    if key in RETURNS_KEYS:
        return [make_returns(key, None, text)]
    if key in RAISES_KEYS:
        return [make_raises(key, None, text)]
    if key == "deprecation":
        return [make_deprecation(Deprecation(None, text))]
    return [make_meta(key, text)]


def _is_doctest(line: str) -> bool:
    return line.lstrip().startswith(">>>")


def _is_doctest_continuation(line: str) -> bool:
    stripped = line.lstrip()
    return stripped == "..." or stripped.startswith("... ")


def split_examples(lines: Lines) -> list[DocstringMeta]:
    """Split an examples section into examples, as doctest reads them.

    Each example is the text that introduces it (its description) followed
    by a snippet: ``>>>`` lines with their ``...`` continuations and the
    expected output, which ends at a blank line or at the next ``>>>``
    line. Text after the last snippet makes up an example without snippet.
    """
    examples: list[DocstringMeta] = []
    i = 0
    while i < len(lines):
        text: Lines = []
        while i < len(lines) and not _is_doctest(lines[i]):
            text.append(lines[i])
            i += 1
        snippet: Lines = []
        while i < len(lines) and (
            _is_doctest(lines[i])
            or (snippet and _is_doctest_continuation(lines[i]))
        ):
            snippet.append(lines[i])
            i += 1
        while i < len(lines) and lines[i] and not _is_doctest(lines[i]):
            snippet.append(lines[i])
            i += 1
        if snippet or to_text(text):
            examples.append(
                DocstringExample(
                    args=["examples"],
                    snippet=to_text(snippet),
                    description=to_text(text),
                )
            )
    return examples
