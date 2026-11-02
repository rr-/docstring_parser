"""Numpydoc-style docstring parsing.

A section starts with a title underlined by a line of ``-`` (or ``=``) of
at least three characters. Recognized titles are case insensitive. Before
the first recognized section, underlined headings are part of the
description; after it, every underlined heading starts a new section and
unrecognized ones give items keyed by the title, e.g. ``"custom_title"``.

Within sections that hold several items, each line without indentation
starts an item and the indented lines that follow are its description.
"""

import re
from collections.abc import Callable, Iterable
from enum import Enum, auto
from itertools import pairwise
from typing import NamedTuple

from ..common import (
    Docstring,
    DocstringExample,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
)
from . import build
from . import compose as compose_
from .fields import find_separator, parse_names, split_typed_text
from .text import (
    Lines,
    clean_lines,
    dedent,
    is_indented,
    item_text,
    split_items,
    trim,
)

_UNDERLINE_RE = re.compile(r"^(-{3,}|={3,})$")


class Kind(Enum):
    """What a section holds."""

    PARAM = auto()  # Parameter-like items: ``name : type``.
    RETURNS = auto()  # Returns or yields items: ``name : type`` or ``type``.
    RAISES = auto()  # Raises or warns items: ``Type``.
    EXAMPLES = auto()  # Doctest examples.
    TEXT = auto()  # Free text, such as Notes.
    METHODS = auto()  # Method signatures, each with a description.


class SectionSpec(NamedTuple):
    """A recognized section: its key, kind of content and custom parser.

    ``custom`` is a callable taking the section text and returning items; it
    is used for user defined sections whose parsing is not built in.
    """

    key: str
    kind: Kind
    custom: Callable[[str], Iterable[DocstringMeta]] | None = None


def parse(text: str | None, sections: dict[str, SectionSpec]) -> Docstring:
    """Parse a numpydoc-style docstring.

    :param text: docstring text
    :param sections: recognized sections by lowercase title
    """
    lines = clean_lines(text or "")
    headers = [i for i in range(len(lines) - 1) if _is_heading(lines, i)]
    known = [i for i in headers if lines[i].lower() in sections]
    if known:
        headers = [i for i in headers if i >= known[0]]
        free = lines[: known[0]]
    else:
        headers, free = [], lines

    meta: list[DocstringMeta] = []
    for start, end in pairwise([*headers, len(lines)]):
        title = lines[start]
        spec = sections.get(title.lower())
        if spec is None:
            spec = SectionSpec(build.section_key(title), Kind.TEXT)
        body = dedent(trim(lines[start + 2 : end]))
        meta.extend(_parse_section(spec, body))

    return build.assemble(DocstringStyle.NUMPYDOC, free, meta)


def _is_heading(lines: Lines, i: int) -> bool:
    title, underline = lines[i], lines[i + 1]
    return (
        bool(_UNDERLINE_RE.match(underline))
        and bool(title)
        and not is_indented(title)
        and not _UNDERLINE_RE.match(title)
    )


def _parse_section(spec: SectionSpec, body: Lines) -> list[DocstringMeta]:
    if spec.custom is not None:
        return list(spec.custom("\n".join(body)))
    if not body:
        return []
    if spec.kind == Kind.EXAMPLES:
        return build.split_examples(body)
    if spec.kind == Kind.TEXT:
        return build.make_single(spec.key, body)
    items: list[DocstringMeta] = []
    for first, rest in split_items(body):
        description = item_text("", rest)
        if first == ":":
            # An item without name nor type: keep its text, if any.
            if description is not None:
                items.extend(build.make_single(spec.key, dedent(rest)))
        elif spec.kind == Kind.PARAM:
            items.extend(_param_items(spec.key, first, description))
        elif spec.kind == Kind.RETURNS:
            items.append(_returns_item(spec.key, first, description))
        elif spec.kind == Kind.METHODS:
            items.append(build.make_meta(spec.key, description, first))
        else:
            # ``Type : text`` puts the start of the text on the header line.
            typed = split_typed_text(first)
            if typed is None:
                items.append(build.make_raises(spec.key, first, description))
            else:
                type_name, text = typed
                items.append(
                    build.make_raises(
                        spec.key, type_name, item_text(text, rest)
                    )
                )
    return items


def _param_items(
    key: str, header: str, description: str | None
) -> list[DocstringMeta]:
    """Build items from ``name : type``; ``a, b : type`` gives two items."""
    colon = find_separator(header)
    names_text = header[:colon] if colon >= 0 else header
    type_spec = header[colon + 1 :].strip() or None if colon >= 0 else None
    names = parse_names(names_text) or [names_text.strip()]
    return build.make_params(key, names, type_spec, description)


def _returns_item(
    key: str, header: str, description: str | None
) -> DocstringMeta:
    """Build an item from ``name : type`` or just ``type``."""
    colon = find_separator(header)
    if colon < 0:
        return build.make_returns(key, header, description)
    name = header[:colon].strip() or None
    return build.make_returns(key, header[colon + 1 :], description, name)


# Titles used when composing, by key.
TITLES = {
    "param": "Parameters",
    "keyword": "Parameters",
    "other_param": "Other Parameters",
    "receives": "Receives",
    "attribute": "Attributes",
    "raises": "Raises",
    "warns": "Warns",
    "returns": "Returns",
    "yields": "Yields",
    "examples": "Examples",
    "warnings": "Warnings",
    "see_also": "See Also",
    "notes": "Notes",
    "references": "References",
    "methods": "Methods",
}


def compose(docstring: Docstring, indent: str) -> str:
    """Render a docstring in numpydoc style.

    :param docstring: docstring to render
    :param indent: indentation of item descriptions
    """
    lines = compose_.description_lines(docstring, indent)
    meta = compose_.without_deprecation(docstring.meta)
    for i, (key, items) in enumerate(compose_.sections(meta, _starts)):
        title = compose_.section_title(TITLES, key)
        if i and lines[-1]:
            lines.append("")
        lines.extend([title, "-" * len(title)])
        for item in items:
            lines.extend(_item_lines(item, indent))
    return compose_.finish(lines)


def _starts(item: DocstringMeta, previous: DocstringMeta) -> bool:
    """Tell whether an item must start a section of its own.

    That is the case of items of text sections and of items after an
    example without snippet.
    """
    if isinstance(item, DocstringExample):
        return compose_.follows_text_example(previous)
    if isinstance(item, DocstringParam | DocstringReturns | DocstringRaises):
        return False
    return item.args[0] not in build.PARAM_KEYS and len(item.args) < 2


def _item_lines(item: DocstringMeta, indent: str) -> Lines:
    if isinstance(item, DocstringParam):
        spec = ", ".join(compose_.spec_parts(item))
        head = f"{item.arg_name} : {spec}" if spec else item.arg_name
    elif isinstance(item, DocstringReturns):
        head = item.type_name or ""
        if item.return_name:
            head = f"{item.return_name} : {head}".rstrip()
    elif isinstance(item, DocstringRaises):
        head = item.type_name or ""
    elif isinstance(item, DocstringExample):
        return compose_.example_lines(item)
    elif item.args[0] in build.PARAM_KEYS:
        head = ""
    elif len(item.args) > 1:
        head = " ".join(item.args[1:])
    else:
        return compose_.text_lines(item.description)
    return [head or ":"] + compose_.indented(item.description, indent)
