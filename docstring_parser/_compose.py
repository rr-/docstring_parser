"""What every style's composer shares."""

import typing as T

from .common import (
    Docstring,
    DocstringExample,
    DocstringMeta,
    Kind,
    meta_as_attribute,
)


def kind_of(meta: DocstringMeta) -> Kind:
    """Tell what a meta documents, for composing it.

    That is its ``kind``, except that a text meta keyed like a ReST
    ``:ivar:`` field is an attribute.
    """
    if meta.kind is Kind.TEXT and meta_as_attribute(meta):
        return Kind.ATTRIBUTE
    return meta.kind


class SectionTable:
    """The titled sections a composer writes items in, by kind.

    :param titles: each section's title and the kinds that go in it, in
        the order the sections are written
    """

    def __init__(
        self, titles: T.Sequence[T.Tuple[str, T.AbstractSet[Kind]]]
    ) -> None:
        self.titles = [title for title, _kinds in titles]
        self.index = {
            kind: i
            for i, (_title, kinds) in enumerate(titles)
            for kind in kinds
        }


def sections(
    docstring: Docstring, table: SectionTable
) -> T.Tuple[T.List[T.Tuple[str, T.List[T.Any]]], T.List[DocstringMeta]]:
    """Sort a docstring's meta into titled sections by kind.

    A text meta keyed like a ReST ``:ivar:`` field goes in as the
    attribute it stands for.

    :returns: the sections that have items, each with its items in the
        order of the docstring, and the meta that no section took
    """
    index = table.index
    found: T.List[T.List[T.Any]] = [[] for _title in table.titles]
    rest = []
    for meta in docstring.meta:
        item = meta
        if type(meta) is DocstringMeta:
            item = meta_as_attribute(meta) or meta
            kind = Kind.TEXT if item is meta else Kind.ATTRIBUTE
        else:
            kind = kind_of(meta)
        position = index.get(kind)
        if position is None:
            rest.append(meta)
        else:
            found[position].append(item)
    return [
        (title, items) for title, items in zip(table.titles, found) if items
    ], rest


def section_runs(
    docstring: Docstring,
    table: SectionTable,
    alone: T.AbstractSet[Kind] = frozenset(),
) -> T.List[T.Tuple[T.Optional[str], T.List[T.Any]]]:
    """Split a docstring's meta into titled sections, in its order.

    Items in a row that go in one section are written in one, so that the
    sections read back in the order of the meta. A ReST ``:ivar:`` style
    field goes in as the attribute it stands for.

    :param alone: the kinds whose items each take a section of their own,
        as the style reads one item from such a section
    :returns: each section's title and items, with None as the title of
        a meta that no section takes, which is alone in its run
    """
    index = table.index
    runs: T.List[T.Tuple[T.Optional[str], T.List[T.Any]]] = []
    last: T.Optional[int] = None
    for meta in docstring.meta:
        item = meta
        if type(meta) is DocstringMeta:
            item = meta_as_attribute(meta) or meta
            kind = Kind.TEXT if item is meta else Kind.ATTRIBUTE
        else:
            kind = kind_of(meta)
        position = index.get(kind)
        if position is None:
            runs.append((None, [meta]))
        elif position == last and kind not in alone:
            runs[-1][1].append(item)
        else:
            runs.append((table.titles[position], [item]))
        last = position
    return runs


def field_name(
    meta: DocstringMeta, own: T.AbstractSet[str], by_kind: T.Dict[Kind, str]
) -> str:
    """Return the field name a param is written with in a style.

    :param own: the keys the style writes as they are
    :param by_kind: the style's field name for each kind of param, where
        the param's own key is not one of them; ``param`` otherwise
    """
    key = meta.key or "param"
    if key in own:
        return key
    return by_kind.get(kind_of(meta), "param")


def field_text(meta: DocstringMeta) -> str:
    """Return a text meta's key and the words after it, as in a field."""
    return " ".join(part for part in (meta.key, meta.name) if part)


def description_lines(docstring: Docstring) -> T.List[str]:
    """The short and long description, each followed by a blank if asked."""
    parts = []
    if docstring.short_description:
        parts.append(docstring.short_description)
    if docstring.blank_after_short_description:
        parts.append("")
    if docstring.long_description:
        parts.append(docstring.long_description)
    if docstring.blank_after_long_description:
        parts.append("")
    return parts


def examples_text(examples: T.Sequence[DocstringExample]) -> str:
    """Write examples as doctest reads them back: each one's text, a blank
    line, then its snippet.

    A blank line ends a snippet's expected output, so one goes before an
    example's text. A snippet with no text follows the last one directly,
    as its ``>>>`` already ends that output.
    """
    text = ""
    for example in examples:
        if example.description:
            text += ("\n\n" if text else "") + example.description
            if example.snippet:
                text += "\n\n" + example.snippet
        elif example.snippet:
            text += ("\n" if text else "") + example.snippet
    return text
