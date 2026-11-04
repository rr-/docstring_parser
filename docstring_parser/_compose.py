"""What every style's composer shares."""

import typing as T

from .common import (
    Docstring,
    DocstringMeta,
    Kind,
    meta_as_attribute,
)


def kind_of(meta: DocstringMeta) -> Kind:
    """Tell what a meta documents, for composing it.

    That is its ``kind``, except that a ReST ``:ivar:`` style field, which
    parses as text, is an attribute.
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

    A ReST ``:ivar:`` style field goes in as the attribute it stands for.

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
