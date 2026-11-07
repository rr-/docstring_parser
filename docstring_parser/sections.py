"""Declare the sections, or fields, that a docstring style recognises.

A :class:`SectionSpec` says which titles start a section, what its items
document and how they are laid out. The same spec works for every style:
in Google and Numpydoc its titles are section titles, and in ReST and
Epydoc they are field names. Pass a list of specs as ``sections`` to
:func:`docstring_parser.parse` or to a style's parser to replace the
style's own, which :func:`default_sections` returns.

For example, to read ``Inputs:`` as a Google params section, and to keep
a ``Remarks:`` section as text of its own::

    from docstring_parser import DocstringStyle, parse
    from docstring_parser.sections import Kind, SectionSpec, default_sections

    sections = [
        *default_sections(DocstringStyle.GOOGLE),
        SectionSpec("Inputs", Kind.PARAM),
        SectionSpec("Remarks", Kind.TEXT),
    ]
    parse(text, DocstringStyle.GOOGLE, sections=sections)
"""

import enum
import typing as T

from .common import DocstringMeta, DocstringStyle, Kind

__all__ = ["Kind", "Layout", "SectionSpec", "default_sections"]


class Layout(enum.Enum):
    """How the body of a section is laid out."""

    ITEMS = 1
    """One item per entry, each starting with a name or type."""

    BLOCK = 2
    """The whole body is one item."""

    ITEM_OR_BLOCK = 3
    """Items if the body starts like one, as in ``int: The sum.``, and one
    block otherwise. This is how Google's ``Returns`` reads."""


_DEFAULT_KEY = {
    Kind.PARAM: "param",
    Kind.KEYWORD: "keyword",
    Kind.OTHER_PARAM: "other_param",
    Kind.RECEIVES: "receives",
    Kind.ATTRIBUTE: "attribute",
    Kind.RETURNS: "returns",
    Kind.YIELDS: "yields",
    Kind.RAISES: "raises",
    Kind.WARNS: "warns",
    Kind.EXAMPLES: "examples",
    Kind.DEPRECATION: "deprecation",
    Kind.METHOD: "methods",
}

_DEFAULT_LAYOUT = {
    Kind.RETURNS: Layout.ITEM_OR_BLOCK,
    Kind.YIELDS: Layout.ITEM_OR_BLOCK,
    Kind.EXAMPLES: Layout.BLOCK,
    Kind.DEPRECATION: Layout.BLOCK,
    Kind.TEXT: Layout.BLOCK,
}

ParseItem = T.Callable[[DocstringMeta], T.Optional[DocstringMeta]]


class SectionSpec:
    """A section, or a field, that a docstring style recognises.

    :ivar titles: the titles that start the section, matched exactly, but
        in any case in Google and Numpydoc
    :ivar kind: what the section's items document
    :ivar key: the first element of each item's ``args``
    :ivar layout: how the section's body is laid out, in Google
    :ivar bare: whether the title stands alone on its line, without
        Google's colon after it or Numpydoc's underline below it
    :ivar parse_item: a function that gets the meta of each item of the
        section, already split into its name, type and description, and
        returns the meta to use instead, or None to keep it, maybe changed
    """

    __slots__ = ("bare", "key", "kind", "layout", "parse_item", "titles")

    def __init__(
        self,
        titles: T.Union[str, T.Iterable[str]],
        kind: Kind,
        key: T.Optional[str] = None,
        layout: T.Optional[Layout] = None,
        bare: bool = False,
        parse_item: T.Optional[ParseItem] = None,
    ) -> None:
        """Declare a section.

        :param titles: one title, or several that mean the same section
        :param kind: what the section's items document
        :param key: the first element of each item's ``args``; by default
            the kind's usual key, such as ``param``, or for a text section
            its first title in lowercase with underscores for spaces
        :param layout: how the body is laid out; by default one block for
            text, examples and deprecations, items or a block for returns
            and yields, and items for the rest
        :param bare: the title stands alone on its line, with no colon
            after it in Google or underline below it in Numpydoc
        :param parse_item: see :attr:`parse_item`
        """
        self.titles = (titles,) if isinstance(titles, str) else tuple(titles)
        if not self.titles:
            raise ValueError("A section needs at least one title")
        self.kind = kind
        self.key = (
            key
            or _DEFAULT_KEY.get(kind)
            or self.titles[0].lower().replace(" ", "_")
        )
        self.layout = layout or _DEFAULT_LAYOUT.get(kind, Layout.ITEMS)
        self.bare = bare
        self.parse_item = parse_item

    def __repr__(self) -> str:
        return (
            f"SectionSpec({self.titles!r}, {self.kind!s}, key={self.key!r},"
            f" layout={self.layout!s}, bare={self.bare!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SectionSpec):
            return NotImplemented
        return all(
            getattr(self, k) == getattr(other, k) for k in self.__slots__
        )

    def __hash__(self) -> int:
        return hash((self.titles, self.kind, self.key, self.layout, self.bare))


_P = T.TypeVar("_P")


class ParserCache(T.Generic[_P]):
    """Parsers or tables built for lists of sections, found by the list.

    Building a parser compiles its title regex, so a parser is reused for
    an equal list of sections. Lists are compared rather than hashed: for
    the same section objects, which is how sections are passed again and
    again, the comparison stops at their identity.
    """

    def __init__(self, size: int = 16) -> None:
        self._size = size
        self._entries: T.List[T.Tuple[T.List[T.Any], _P]] = []

    def get(
        self, key: T.List[T.Any], make: T.Callable[..., _P], *args: T.Any
    ) -> _P:
        """Return the parser for a list of sections, or ``make(*args)``."""
        for stored, parser in self._entries:
            if stored == key:
                return parser
        parser = make(*args)
        self._entries.insert(0, (key, parser))
        del self._entries[self._size :]
        return parser

    def parsers(self) -> T.List[_P]:
        """Return the parsers cached, the latest first."""
        return [parser for _key, parser in self._entries]


def apply(spec: T.Optional[SectionSpec], meta: DocstringMeta) -> DocstringMeta:
    """Give a meta to its section's ``parse_item``, if it has one."""
    if spec is not None and spec.parse_item is not None:
        return spec.parse_item(meta) or meta
    return meta


def default_sections(style: DocstringStyle) -> T.List[SectionSpec]:
    """Return the sections a style recognises when given none.

    :param style: any style but auto, which has no sections of its own
    """
    from . import epydoc, google, numpydoc, rest  # noqa: PLC0415

    modules = {
        DocstringStyle.REST: rest,
        DocstringStyle.GOOGLE: google,
        DocstringStyle.NUMPYDOC: numpydoc,
        DocstringStyle.EPYDOC: epydoc,
    }
    if style not in modules:
        raise ValueError(f"{style} has no sections of its own")
    return modules[style].default_sections()
