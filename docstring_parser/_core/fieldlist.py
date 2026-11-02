"""Parsing of field lists, shared by the reST and epydoc styles.

A field is a line without indentation like ``:name args: text`` (reST) or
``@name args: text`` (epydoc). Its text continues with the indented lines
that follow, and also with lines without indentation that are not separated
from it by a blank line. A blank line followed by a line without
indentation that is not a field ends the field list; such text is appended
to the long description so that no text is lost.

Type fields (``:type x:``, ``:rtype:``...) are merged into the item they
refer to. A type field for an undocumented name creates an item without
description. Empty type fields are ignored.
"""

import re
from typing import NamedTuple, cast

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
from . import build
from . import compose as compose_
from .fields import escape_name, unescape_name
from .text import (
    Deprecation,
    Lines,
    clean_lines,
    is_indented,
    item_text,
)


class Field(NamedTuple):
    """A field: name and arguments, first line of text, following lines."""

    name: str
    args: list[str]
    first: str
    rest: Lines


class Keywords(NamedTuple):
    """How the field names of a style map to items.

    ``params``, ``returns`` and ``raises`` are the field names that create
    parameter-like, returns-like and raises-like items; their canonical key
    comes from :func:`.build.canonical_key`. ``param_types`` maps type field
    names to the canonical keys whose type they set; the first key is used
    for a type field whose name is not otherwise documented.
    ``return_types`` maps type field names to ``returns`` or ``yields``.
    """

    params: set[str]
    param_types: dict[str, list[str]]
    returns: set[str]
    return_types: dict[str, str]
    raises: set[str]
    deprecation: set[str]


_VERSION_RE = re.compile(r"^(?P<version>v?\d+(?:\.\w+)*)(?:\s+|$)")


def parse(
    text: str | None,
    marker: str,
    keywords: Keywords,
    style: DocstringStyle,
    *,
    directives: bool,
) -> Docstring:
    """Parse a docstring made of free text followed by a field list.

    :param text: docstring text
    :param marker: character that starts and ends field names
    :param keywords: field names known by the style
    :param style: style of the resulting docstring
    :param directives: whether to extract a ``.. deprecated::`` directive
        from the description
    """
    free, fields, trailing = scan(clean_lines(text or ""), marker)
    meta = build_items(fields, keywords)
    return build.assemble(style, free, meta, trailing, directives=directives)


def scan(lines: Lines, marker: str) -> tuple[Lines, list[Field], Lines]:
    """Split lines into free text, fields and trailing free text.

    The field name ends at the first colon, which must be followed by
    whitespace or the end of the line, so that reST roles such as
    ``:class:`Foo``` at the start of a line are not taken as fields.
    """
    marker = re.escape(marker)
    field_re = re.compile(
        rf"^{marker}(?P<name>[^\s{marker}:][^:]*?)\s*:(?:\s+(?P<first>.*))?$"
    )
    free: Lines = []
    fields: list[Field] = []
    trailing: Lines = []
    state = free
    previous = ""
    for line in lines:
        match = field_re.match(line)
        if match:
            name, *args = match.group("name").split()
            fields.append(Field(name, args, match.group("first") or "", []))
            state = fields[-1].rest
        elif state is not free and state is not trailing:
            if line and not is_indented(line) and not previous:
                state = trailing
            state.append(line)
        else:
            state.append(line)
        previous = line
    return free, fields, trailing


def build_items(
    fields: list[Field], keywords: Keywords
) -> list[DocstringMeta]:
    """Turn fields into docstring items, merging type fields.

    The name of a parameter is the last argument of its field, which is the
    only argument of a type field.
    """

    def name_of(field: Field) -> str:
        return unescape_name(field.args[-1])

    documented = {
        (build.canonical_key(field.name), name_of(field))
        for field in fields
        if field.name in keywords.params and field.args
    }
    has_returns = {
        build.canonical_key(field.name)
        for field in fields
        if field.name in keywords.returns
    }
    texts = [item_text(field.first, field.rest) for field in fields]
    types: dict[tuple[str, str], str] = {}
    return_types: dict[str, str] = {}
    for field, text in zip(fields, texts, strict=True):
        if not text:
            continue
        if field.name in keywords.param_types and len(field.args) == 1:
            for key in keywords.param_types[field.name]:
                types.setdefault((key, name_of(field)), text)
        elif field.name in keywords.return_types and not field.args:
            return_types.setdefault(keywords.return_types[field.name], text)

    items: list[DocstringMeta] = []
    for field, text in zip(fields, texts, strict=True):
        name = field.name
        if name in keywords.params and field.args:
            key = build.canonical_key(name)
            arg_name = name_of(field)
            type_spec = " ".join(field.args[:-1]) or types.get((key, arg_name))
            items.append(build.make_param(key, arg_name, type_spec, text))
        elif name in keywords.param_types and len(field.args) == 1:
            keys = keywords.param_types[name]
            arg_name = name_of(field)
            if text and not any((key, arg_name) in documented for key in keys):
                documented.add((keys[0], arg_name))
                items.append(build.make_param(keys[0], arg_name, text, None))
        elif name in keywords.returns:
            key = build.canonical_key(name)
            type_name = " ".join(field.args) or return_types.get(key)
            items.append(build.make_returns(key, type_name, text))
        elif name in keywords.return_types and not field.args:
            key = keywords.return_types[name]
            if text and key not in has_returns:
                items.append(build.make_returns(key, text, None))
        elif name in keywords.raises:
            key = build.canonical_key(name)
            items.append(build.make_raises(key, " ".join(field.args), text))
        elif name in keywords.deprecation:
            items.append(_deprecation(field.args, text))
        else:
            items.append(build.make_meta(name, text, *field.args))
    return items


def _deprecation(args: list[str], text: str | None) -> DocstringMeta:
    """Build a deprecation item; the version is an argument or leads text."""
    version = " ".join(args) or None
    if version is None and text:
        match = _VERSION_RE.match(text)
        if match:
            version = match.group("version")
            text = text[match.end() :] or None
    return build.make_deprecation(Deprecation(version, text))


class FieldNames(NamedTuple):
    """Field names used when composing, by canonical key."""

    params: dict[str, str]
    param_types: dict[str, str]
    returns: dict[str, str]
    return_types: dict[str, str]
    raises: str
    deprecation: str | None


def compose(
    docstring: Docstring,
    marker: str,
    names: FieldNames,
    *,
    expanded: bool,
    inline_types: bool,
    escape_names: bool,
    indent: str,
) -> str:
    """Render a docstring as free text followed by a field list.

    :param docstring: docstring to render
    :param marker: character that starts field names
    :param names: field names to use
    :param expanded: whether descriptions start on the line after the field
        name instead of on the same line
    :param inline_types: whether simple parameter types are written in the
        parameter field (``:param int x:``) instead of in a type field
    :param escape_names: whether to escape reST markup in parameter names
    :param indent: indentation of continuation lines
    """
    directives = names.deprecation is None
    lines = compose_.description_lines(docstring, indent, directives)
    meta = docstring.meta
    if directives:
        meta = compose_.without_deprecation(meta)

    def field(name: str, args: list[str], text: str | None) -> None:
        head = f"{marker}{' '.join([name, *args])}:"
        lines.extend(compose_.first_and_rest(head, text, indent, expanded))

    for item in meta:
        key = item.args[0] if item.args else ""
        if isinstance(item, DocstringParam):
            name = names.params.get(key, names.params["param"])
            arg_name = (
                escape_name(item.arg_name) if escape_names else item.arg_name
            )
            spec = ", ".join(compose_.spec_parts(item))
            if inline_types and spec and not re.search(r"[\s:]", spec):
                field(name, [spec, arg_name], item.description)
            else:
                field(name, [arg_name], item.description)
                if spec:
                    type_name = names.param_types.get(key, "type")
                    lines.append(f"{marker}{type_name} {arg_name}: {spec}")
        elif isinstance(item, DocstringReturns):
            if item.description or not item.type_name:
                field(names.returns[key], [], item.description)
            if item.type_name:
                type_name = names.return_types[key]
                lines.append(f"{marker}{type_name}: {item.type_name}")
        elif isinstance(item, DocstringRaises):
            args = [item.type_name] if item.type_name else []
            field(names.raises, args, item.description)
        elif isinstance(item, DocstringDeprecated):
            text = " ".join(
                part for part in (item.version, item.description) if part
            )
            field(cast(str, names.deprecation), [], text or None)
        elif isinstance(item, DocstringExample):
            text = "\n".join(
                part for part in (item.description, item.snippet) if part
            )
            field(key, [], text or None)
        else:
            field(key, item.args[1:], item.description)
    return compose_.finish(lines)
