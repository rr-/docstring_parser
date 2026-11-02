"""Google-style docstring parsing.

A section starts with a line without indentation holding a known title and
a colon (``Args:``); titles are case insensitive. Its content is the
indented block that follows; a title without content is free text. Lines
without indentation that are not section titles are free text: before the
first section they are the description, after it they are appended to the
long description.

Within sections that hold several items, each item starts at the section's
base indentation and continues with the more indented lines.
"""

import re
from enum import IntEnum
from typing import NamedTuple

from ..common import (
    Docstring,
    DocstringExample,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
    RenderingStyle,
)
from . import build
from . import compose as compose_
from .fields import (
    find_separator,
    looks_like_type,
    matching_bracket,
    parse_names,
    split_typed_text,
)
from .text import (
    Lines,
    clean_lines,
    dedent,
    is_indented,
    item_text,
    split_block,
    split_items,
    to_text,
    trim,
)


class Kind(IntEnum):
    """What a section holds; the values are those of the legacy SectionType."""

    SINGULAR = 0  # Free text, such as Notes or Examples.
    MULTIPLE = 1  # Items with a header each, such as Args or Raises.
    SINGULAR_OR_MULTIPLE = 2  # A returns or yields item.


_NAMED_RETURN_RE = re.compile(r"^\w+\s+\(")

# (title, key, kind) of the sections recognized in non-legacy mode. These
# follow the sections supported by sphinx.ext.napoleon.
DEFAULT_SECTIONS = [
    ("Args", "param", Kind.MULTIPLE),
    ("Arguments", "param", Kind.MULTIPLE),
    ("Parameters", "param", Kind.MULTIPLE),
    ("Params", "param", Kind.MULTIPLE),
    ("Keyword Args", "keyword", Kind.MULTIPLE),
    ("Keyword Arguments", "keyword", Kind.MULTIPLE),
    ("Other Parameters", "other_param", Kind.MULTIPLE),
    ("Other Params", "other_param", Kind.MULTIPLE),
    ("Other Args", "other_param", Kind.MULTIPLE),
    ("Receives", "receives", Kind.MULTIPLE),
    ("Receive", "receives", Kind.MULTIPLE),
    ("Attributes", "attribute", Kind.MULTIPLE),
    ("Raises", "raises", Kind.MULTIPLE),
    ("Raise", "raises", Kind.MULTIPLE),
    ("Exceptions", "raises", Kind.MULTIPLE),
    ("Except", "raises", Kind.MULTIPLE),
    ("Warns", "warns", Kind.MULTIPLE),
    ("Warn", "warns", Kind.MULTIPLE),
    ("Returns", "returns", Kind.SINGULAR_OR_MULTIPLE),
    ("Return", "returns", Kind.SINGULAR_OR_MULTIPLE),
    ("Yields", "yields", Kind.SINGULAR_OR_MULTIPLE),
    ("Yield", "yields", Kind.SINGULAR_OR_MULTIPLE),
    ("Example", "examples", Kind.SINGULAR),
    ("Examples", "examples", Kind.SINGULAR),
    ("Methods", "methods", Kind.MULTIPLE),
    ("Note", "notes", Kind.SINGULAR),
    ("Notes", "notes", Kind.SINGULAR),
    ("Warning", "warnings", Kind.SINGULAR),
    ("Warnings", "warnings", Kind.SINGULAR),
    ("See Also", "see_also", Kind.SINGULAR),
    ("References", "references", Kind.SINGULAR),
    ("Todo", "todo", Kind.SINGULAR),
    ("Attention", "attention", Kind.SINGULAR),
    ("Caution", "caution", Kind.SINGULAR),
    ("Danger", "danger", Kind.SINGULAR),
    ("Error", "error", Kind.SINGULAR),
    ("Hint", "hint", Kind.SINGULAR),
    ("Important", "important", Kind.SINGULAR),
    ("Tip", "tip", Kind.SINGULAR),
]


class SectionSpec(NamedTuple):
    """A recognized section: its canonical key and kind of content."""

    key: str
    kind: Kind


def default_sections() -> dict[str, SectionSpec]:
    """Return the sections recognized by default, by lowercase title."""
    return {
        title.lower(): SectionSpec(key, kind)
        for title, key, kind in DEFAULT_SECTIONS
    }


def parse(
    text: str | None,
    sections: dict[str, SectionSpec] | None = None,
    title_colon: bool = True,
) -> Docstring:
    """Parse a Google-style docstring.

    :param text: docstring text
    :param sections: recognized sections by lowercase title, or None for
        the defaults
    :param title_colon: whether section titles require a trailing colon
    """
    if sections is None:
        sections = default_sections()
    lines = _reindent_first_section(
        clean_lines(text or ""), sections, title_colon
    )

    free: Lines = []
    trailing: Lines = []
    meta: list[DocstringMeta] = []
    in_sections = False
    i = 0
    while i < len(lines):
        spec = _section_at(lines[i], sections, title_colon)
        if spec is not None:
            body, end = split_block(lines, i + 1)
            # A title without content is text, as napoleon renders it.
            if trim(body):
                in_sections = True
                meta.extend(_parse_section(spec, dedent(trim(body))))
                i = end
                continue
        (trailing if in_sections else free).append(lines[i])
        i += 1

    return build.assemble(DocstringStyle.GOOGLE, free, meta, trailing)


def _reindent_first_section(
    lines: Lines, sections: dict[str, SectionSpec], title_colon: bool
) -> Lines:
    """Restore the indentation of a section whose title is the first line.

    PEP 257 cleaning removes the indentation common to all lines but the
    first, so when a docstring starts with ``Args:`` and that is the only
    section, its items end up without indentation. In that case the lines
    up to the next section title are the section's content.
    """
    if not lines or _section_at(lines[0], sections, title_colon) is None:
        return lines
    following = [line for line in lines[1:] if line]
    if not following or is_indented(following[0]):
        return lines
    end = 1
    while end < len(lines) and (
        _section_at(lines[end], sections, title_colon) is None
    ):
        end += 1
    body = ["    " + line if line else "" for line in lines[1:end]]
    return lines[:1] + body + lines[end:]


def _section_at(
    line: str, sections: dict[str, SectionSpec], title_colon: bool
) -> SectionSpec | None:
    if not line or is_indented(line):
        return None
    if line.endswith(":"):
        line = line[:-1].rstrip()
    elif title_colon:
        return None
    return sections.get(line.lower())


def _parse_section(spec: SectionSpec, body: Lines) -> list[DocstringMeta]:
    if not body:
        return []
    if spec.kind == Kind.SINGULAR:
        return build.make_single(spec.key, body)
    if spec.kind == Kind.SINGULAR_OR_MULTIPLE:
        return [_parse_returns(spec.key, body)]
    return [
        item
        for first, rest in split_items(
            body, lambda line: _parse_header(spec.key, line) is not None
        )
        for item in _build_items(spec.key, first, rest)
    ]


class _Header(NamedTuple):
    names: list[str]
    type_spec: str | None
    first: str


def _parse_header(key: str, line: str) -> _Header | None:
    """Parse the first line of an item, or return None if it is not one.

    Parameter items look like ``name (type): text``, where the type and the
    text are optional; a line without colon must be a bare name. Raises
    items look like ``Type: text``; other items like ``name: text``.
    """
    if key in build.PARAM_KEYS:
        return _parse_param_header(line)
    if key in build.RAISES_KEYS:
        typed = split_typed_text(line)
        return _Header([], *typed) if typed else None
    colon = find_separator(line)
    head = line[:colon] if colon >= 0 else line
    first = line[colon + 1 :] if colon >= 0 else ""
    if colon >= 0 and head.strip():
        return _Header([head.strip()], None, first)
    return None


def _parse_param_header(line: str) -> _Header | None:
    paren = line.find("(")
    colon = line.find(":")
    stops = [pos for pos in (paren, colon) if pos >= 0]
    end = min(stops) if stops else len(line)
    names_text = line[:end].strip()
    rest = line[end:]
    type_spec = None
    if rest.startswith("("):
        close = matching_bracket(rest, 0)
        if close < 0:
            return None
        type_spec = rest[1:close].strip()
        rest = rest[close + 1 :].lstrip()
    names = parse_names(names_text) if names_text else None
    if rest.startswith(":"):
        if not names_text:
            return None
        return _Header(names or [names_text], type_spec, rest[1:])
    if rest or names is None:
        return None
    return _Header(names, type_spec, "")


def _build_items(key: str, first: str, rest: Lines) -> list[DocstringMeta]:
    """Build the items described by a header and its continuation lines.

    A header listing several names (``x, y (int): text``) gives one item per
    name. Only the first item of a section can lack a valid header; it is
    then kept as text in an item with no name or type.
    """
    header = _parse_header(key, first)
    if header is None:
        header = _Header([], None, first)
    description = item_text(header.first, rest)
    if key in build.PARAM_KEYS:
        if not header.names:
            return [build.make_meta(key, description)]
        return build.make_params(
            key, header.names, header.type_spec, description
        )
    if key in build.RAISES_KEYS:
        return [build.make_raises(key, header.type_spec, description)]
    return [build.make_meta(key, description, *header.names)]


def _parse_returns(key: str, body: Lines) -> DocstringMeta:
    """Parse a returns section as one item.

    The item is ``type: text``, ``name (type): text`` or just text. The type
    must look like one (see :func:`.fields.looks_like_type`), so that prose
    with a colon is kept as text.
    """
    first, rest = body[0], body[1:]
    named = _NAMED_RETURN_RE.match(first)
    if named:
        header = _parse_param_header(first)
        if header and len(header.names) == 1 and header.type_spec:
            return build.make_returns(
                key,
                header.type_spec,
                item_text(header.first, rest),
                header.names[0],
            )
    colon = find_separator(first)
    if colon >= 0 and looks_like_type(first[:colon]):
        return build.make_returns(
            key, first[:colon].strip(), item_text(first[colon + 1 :], rest)
        )
    return build.make_returns(key, None, to_text(body))


# Titles used when composing, by key.
TITLES = {
    "param": "Args",
    "keyword": "Keyword Args",
    "other_param": "Other Parameters",
    "receives": "Receives",
    "attribute": "Attributes",
    "raises": "Raises",
    "warns": "Warns",
    "returns": "Returns",
    "yields": "Yields",
    "examples": "Examples",
    "methods": "Methods",
    "notes": "Notes",
    "warnings": "Warnings",
    "see_also": "See Also",
}
_KINDS = {key: kind for _, key, kind in DEFAULT_SECTIONS}


def _kind(item: DocstringMeta) -> Kind:
    """Return the kind of section an item belongs to.

    Keys of custom sections are not known: an item with arguments (a name)
    is then taken to come from a section with several items.
    """
    default = Kind.MULTIPLE if len(item.args) > 1 else Kind.SINGULAR
    return _KINDS.get(item.args[0], default)


def compose(
    docstring: Docstring, rendering_style: RenderingStyle, indent: str
) -> str:
    """Render a docstring in Google style.

    :param docstring: docstring to render
    :param rendering_style: rendering style; ``EXPANDED``
        puts item descriptions on their own lines
    :param indent: indentation unit
    """
    expanded = rendering_style == RenderingStyle.EXPANDED
    lines = compose_.description_lines(docstring, indent)
    meta = compose_.without_deprecation(docstring.meta)
    for i, (key, items) in enumerate(compose_.sections(meta, _starts)):
        title = compose_.section_title(TITLES, key)
        if i and lines[-1]:
            lines.append("")
        lines.append(f"{title}:")
        for item in items:
            for line in _item_lines(key, item, indent, expanded):
                lines.append(indent + line if line else "")
    return compose_.finish(lines)


def _starts(item: DocstringMeta, previous: DocstringMeta) -> bool:
    """Tell whether an item must start a section of its own.

    That is the case of items of sections holding a single item, of items
    that can only come first in a section (those without header) and of
    items after an example without snippet.
    """
    if isinstance(item, DocstringExample):
        return compose_.follows_text_example(previous)
    if _kind(item) != Kind.MULTIPLE:
        return True
    if isinstance(item, DocstringRaises):
        return not item.type_name
    return item.args[0] in build.PARAM_KEYS and not isinstance(
        item, DocstringParam
    )


def _item_lines(
    key: str, item: DocstringMeta, indent: str, expanded: bool
) -> Lines:
    if isinstance(item, DocstringParam):
        spec = compose_.spec_parts(item)
        head = item.arg_name + (f" ({', '.join(spec)})" if spec else "")
        return compose_.first_and_rest(
            head + ":", item.description, indent, expanded
        )
    if isinstance(item, DocstringReturns):
        if item.return_name and item.type_name:
            head = f"{item.return_name} ({item.type_name}):"
        else:
            head = f"{item.type_name}:" if item.type_name else ""
        return _headed(head, item.description, indent, expanded)
    if isinstance(item, DocstringRaises):
        if not item.type_name:
            return _headerless(item.description, indent)
        return _headed(
            f"{item.type_name}:", item.description, indent, expanded
        )
    if isinstance(item, DocstringExample):
        return compose_.example_lines(item)
    if len(item.args) > 1 and _kind(item) == Kind.MULTIPLE:
        head = " ".join(item.args[1:]) + ":"
        return compose_.first_and_rest(
            head, item.description, indent, expanded
        )
    if key in build.PARAM_KEYS:
        return _headerless(item.description, indent)
    return compose_.text_lines(item.description)


def _headerless(text: str | None, indent: str) -> Lines:
    """Render an item without header: its text, continued with indentation."""
    first, *rest = compose_.text_lines(text) or [""]
    return [first] + compose_.indented("\n".join(rest), indent)


def _headed(head: str, text: str | None, indent: str, expanded: bool) -> Lines:
    if not head:
        return compose_.text_lines(text)
    return compose_.first_and_rest(head, text, indent, expanded)
