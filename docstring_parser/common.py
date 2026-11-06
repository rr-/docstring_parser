"""Common methods for parsing."""

import enum
import typing as T

# Kept here for code that imported them from this module.
from ._lines import cleandoc, normalize_line_endings  # noqa: F401

PARAM_KEYWORDS = {
    "param",
    "parameter",
    "arg",
    "argument",
    "attribute",
    "key",
    "keyword",
}
RAISES_KEYWORDS = {"raises", "raise", "except", "exception"}
DEPRECATION_KEYWORDS = {"deprecation", "deprecated"}
RETURNS_KEYWORDS = {"return", "returns"}
YIELDS_KEYWORDS = {"yield", "yields"}
EXAMPLES_KEYWORDS = {"example", "examples"}


def continuation_indented(text: str) -> bool:
    """Tell whether every non-blank line after the first is indented.

    Composed after a field's head, such lines read back as the field's
    continuation indent, losing their indent relative to the first line,
    so the description has to start on a line of its own.
    """
    rest = [line for line in text.splitlines()[1:] if line.strip()]
    return bool(rest) and all(line[0].isspace() for line in rest)


def excerpt(text: str, limit: int = 60) -> str:
    """Shorten text quoted in an error message to its first characters."""
    return text if len(text) <= limit else text[:limit] + "..."


class Problem(T.NamedTuple):
    """Something in a docstring that could not be parsed.

    Its ``code`` names what is wrong, and stays the same from one version
    to the next, while the message may change:

    ``bad-field``
        A ReST or Epydoc field that cannot be read, such as ``:param x``
        with no colon after its head, or ``:: text`` with no name.
    ``wrong-arguments``
        A field with too many or too few words in its head, such as
        ``:param a b c d:`` or ``:returns int str:``.
    ``mixed-returns-and-yields``
        An Epydoc docstring with both ``@return`` and ``@yield`` fields.
    ``missing-colon``
        A Google item with no colon between its head and its description,
        in a section that takes several items, such as ``Args:``.
    ``missing-name``
        A Google section of params that holds text and no named item.
    ``no-items``
        A Google section whose items cannot be told apart by their
        indent.
    """

    #: The line it is on, from 1, in the docstring as written.
    line: int
    #: What is wrong, as one of the codes above.
    code: str
    #: What is wrong, for people to read.
    message: str


class ParseError(RuntimeError):
    """A docstring could not be parsed.

    :ivar problems: everything that could not be parsed, in order
    :ivar result: what could be parsed, with the problems, if known
    """

    def __init__(
        self,
        message: str = "",
        problems: T.Optional[T.List[Problem]] = None,
        result: T.Optional["ParseResult"] = None,
    ) -> None:
        """Initialize self."""
        super().__init__(message)
        self.problems: T.List[Problem] = problems or []
        self.result = result


class ItemError(ParseError):
    """An item of a docstring that cannot be parsed, with the code of its
    problem."""

    def __init__(self, code: str, message: str) -> None:
        """Initialize self."""
        super().__init__(message)
        self.code = code


class DocstringStyle(str, enum.Enum):
    """Docstring style, by the name of the parser that reads it.

    Each member equals its parser's ``name``, so ``"google"`` works
    wherever ``DocstringStyle.GOOGLE`` does.
    """

    REST = "rest"
    GOOGLE = "google"
    NUMPYDOC = "numpydoc"
    EPYDOC = "epydoc"
    AUTO = "auto"


class RenderingStyle(enum.Enum):
    """Rendering style when unparsing parsed docstrings."""

    COMPACT = 1
    CLEAN = 2
    EXPANDED = 3


class Kind(enum.IntEnum):
    """What a docstring meta documents."""

    PARAM = 1
    KEYWORD = 2
    OTHER_PARAM = 3
    RECEIVES = 4
    ATTRIBUTE = 5
    RETURNS = 6
    YIELDS = 7
    RAISES = 8
    WARNS = 9
    EXAMPLES = 10
    DEPRECATION = 11
    TEXT = 12


PARAM_KINDS = frozenset(
    {Kind.PARAM, Kind.KEYWORD, Kind.OTHER_PARAM, Kind.RECEIVES, Kind.ATTRIBUTE}
)
RETURNS_KINDS = frozenset({Kind.RETURNS, Kind.YIELDS})
RAISES_KINDS = frozenset({Kind.RAISES, Kind.WARNS})


def _repr(obj: T.Any, fields: T.Iterable[str]) -> str:
    """Show an object as its class called with the fields it has set.

    A field holding None or False is left out, as most of them do.
    """
    parts = []
    for field in fields:
        value = getattr(obj, field, None)
        if value is None or value is False:
            continue
        if isinstance(value, enum.Enum):
            parts.append(f"{field}={type(value).__name__}.{value.name}")
        else:
            parts.append(f"{field}={value!r}")
    return f"{type(obj).__name__}({', '.join(parts)})"


# The fields a meta shows in its repr, in order, of those its class has.
_META_FIELDS = (
    "kind",
    "key",
    "name",
    "arg_name",
    "return_name",
    "type_name",
    "is_optional",
    "default",
    "version",
    "snippet",
    "description",
    "extra",
    "title",
)


class DocstringMeta:
    """Docstring meta information: one item of a docstring.

    Symbolizes lines in form of

        :param arg: description
        :raises ValueError: if something happens

    :ivar description: the item's text
    :ivar kind: what the item documents. Each class sets it, so that the
        class and the kind cannot disagree.
    :ivar key: the field or section key it was written with, such as
        ``param``, ``keyword`` or ``see_also``
    :ivar name: for a text item, the words after its key, such as ``x``
        in a ReST ``:ivar x:`` field
    :ivar extra: words in the item's head after the parts a parser
        recognised, such as ``more`` in Google's ``x (int) more:``
    :ivar title: for a text item read from a section no spec declares, the
        section's title as written, such as ``Custom Title``
    """

    # Set only on the items it applies to, so the others carry no field.
    title: T.Optional[str] = None

    def __init__(
        self,
        description: T.Optional[str],
        key: T.Optional[str] = None,
        name: T.Optional[str] = None,
    ) -> None:
        """Initialize self."""
        self.description = description
        self.kind = Kind.TEXT
        self.key = key
        self.name = name
        self.extra: T.Optional[str] = None

    def __repr__(self) -> str:
        return _repr(self, _META_FIELDS)


class DocstringParam(DocstringMeta):
    """DocstringMeta symbolizing :param metadata."""

    def __init__(
        self,
        description: T.Optional[str],
        arg_name: str,
        type_name: T.Optional[str],
        is_optional: T.Optional[bool],
        default: T.Optional[str],
        kind: Kind = Kind.PARAM,
        key: T.Optional[str] = "param",
        raw_type_name: T.Optional[str] = None,
    ) -> None:
        """Initialize self.

        :param kind: the kind of param, such as a keyword or an attribute
        :param raw_type_name: the type as written, before the marks of an
            optional param and its default are split off, as in
            ``int, optional``
        """
        super().__init__(description, key)
        if kind not in PARAM_KINDS:
            raise ValueError(f"{kind} is not a kind of param")
        self.kind = kind
        self.arg_name = arg_name
        self.type_name = type_name
        self.is_optional = is_optional
        self.default = default
        self.raw_type_name = raw_type_name


class DocstringReturns(DocstringMeta):
    """DocstringMeta symbolizing :returns or :yields metadata."""

    def __init__(
        self,
        description: T.Optional[str],
        type_name: T.Optional[str],
        is_generator: bool,
        return_name: T.Optional[str] = None,
        key: T.Optional[str] = None,
    ) -> None:
        """Initialize self."""
        super().__init__(description, key)
        self.kind = Kind.YIELDS if is_generator else Kind.RETURNS
        self.type_name = type_name
        self.is_generator = is_generator
        self.return_name = return_name


class DocstringRaises(DocstringMeta):
    """DocstringMeta symbolizing :raises metadata."""

    def __init__(
        self,
        description: T.Optional[str],
        type_name: T.Optional[str],
        kind: Kind = Kind.RAISES,
        key: T.Optional[str] = "raises",
    ) -> None:
        """Initialize self.

        :param kind: raises or warns
        """
        super().__init__(description, key)
        if kind not in RAISES_KINDS:
            raise ValueError(f"{kind} is not a kind of raises")
        self.kind = kind
        self.type_name = type_name


class DocstringDeprecated(DocstringMeta):
    """DocstringMeta symbolizing deprecation metadata."""

    def __init__(
        self,
        description: T.Optional[str],
        version: T.Optional[str],
        key: T.Optional[str] = "deprecation",
    ) -> None:
        """Initialize self."""
        super().__init__(description, key)
        self.kind = Kind.DEPRECATION
        self.version = version


class DocstringExample(DocstringMeta):
    """DocstringMeta symbolizing example metadata."""

    def __init__(
        self,
        snippet: T.Optional[str],
        description: T.Optional[str],
        key: T.Optional[str] = "examples",
    ) -> None:
        """Initialize self."""
        super().__init__(description, key)
        self.kind = Kind.EXAMPLES
        self.snippet = snippet


# ReST fields for attributes, which parse as plain meta rather than params.
ATTRIBUTE_FIELD_KEYWORDS = {"ivar", "var", "cvar"}


def meta_as_attribute(meta: DocstringMeta) -> T.Optional[DocstringParam]:
    """Return a ReST ``:ivar name:`` style field as an attribute param.

    :param meta: any docstring meta
    :returns: the attribute, or None if the meta is not such a field
    """
    if (
        meta.kind is Kind.TEXT
        and meta.key in ATTRIBUTE_FIELD_KEYWORDS
        and meta.name
        and " " not in meta.name
    ):
        return DocstringParam(
            meta.description,
            arg_name=meta.name,
            type_name=None,
            is_optional=None,
            default=None,
            kind=Kind.ATTRIBUTE,
            key="attribute",
        )
    return None


class Docstring:
    """Docstring object representation."""

    def __init__(
        self,
        style=None,  # type: T.Optional[DocstringStyle]
    ) -> None:
        """Initialize self."""
        self.short_description = None  # type: T.Optional[str]
        self.long_description = None  # type: T.Optional[str]
        self.blank_after_short_description = False
        self.blank_after_long_description = False
        self.meta = []  # type: T.List[DocstringMeta]
        self.style = style  # type: T.Optional[DocstringStyle]

    def __repr__(self) -> str:
        return _repr(
            self,
            (
                "style",
                "short_description",
                "long_description",
                "blank_after_short_description",
                "blank_after_long_description",
                "meta",
            ),
        )

    @property
    def description(self) -> T.Optional[str]:
        """Return the full description of the function

        Returns None if the docstring did not include any description
        """
        ret = []
        if self.short_description:
            ret.append(self.short_description)
            if self.blank_after_short_description:
                ret.append("")
        if self.long_description:
            ret.append(self.long_description)

        if not ret:
            return None

        return "\n".join(ret)

    @property
    def params(self) -> T.List[DocstringParam]:
        """Return a list of information on function params, without the
        attributes."""
        return [
            item
            for item in self.meta
            if isinstance(item, DocstringParam)
            and item.kind is not Kind.ATTRIBUTE
        ]

    @property
    def attrs(self) -> T.List[DocstringParam]:
        """Return a list of information on attributes."""
        return [
            item
            for item in self.meta
            if isinstance(item, DocstringParam) and item.kind is Kind.ATTRIBUTE
        ]

    @property
    def raises(self) -> T.List[DocstringRaises]:
        """Return a list of information on the exceptions that the function
        may raise.
        """
        return [
            item for item in self.meta if isinstance(item, DocstringRaises)
        ]

    @property
    def returns(self) -> T.Optional[DocstringReturns]:
        """Return a single information on function return.

        Takes the first return information, leaving out yields.
        """
        for item in self.meta:
            if (
                isinstance(item, DocstringReturns)
                and item.kind is Kind.RETURNS
            ):
                return item
        return None

    @property
    def many_returns(self) -> T.List[DocstringReturns]:
        """Return a list of information on function return, leaving out
        yields."""
        return [
            item
            for item in self.meta
            if isinstance(item, DocstringReturns) and item.kind is Kind.RETURNS
        ]

    @property
    def yields(self) -> T.Optional[DocstringReturns]:
        """Return a single information on what a generator yields.

        Takes the first yields information.
        """
        for item in self.meta:
            if isinstance(item, DocstringReturns) and item.kind is Kind.YIELDS:
                return item
        return None

    @property
    def many_yields(self) -> T.List[DocstringReturns]:
        """Return a list of information on what a generator yields."""
        return [
            item
            for item in self.meta
            if isinstance(item, DocstringReturns) and item.kind is Kind.YIELDS
        ]

    @property
    def deprecation(self) -> T.Optional[DocstringDeprecated]:
        """Return a single information on function deprecation notes."""
        for item in self.meta:
            if isinstance(item, DocstringDeprecated):
                return item
        return None

    @property
    def examples(self) -> T.List[DocstringExample]:
        """Return a list of information on function examples."""
        return [
            item for item in self.meta if isinstance(item, DocstringExample)
        ]


class ParseResult(T.NamedTuple):
    """A parsed docstring with everything in it that could not be parsed."""

    docstring: Docstring
    problems: T.List[Problem]


class BaseParser:
    """A parser of one docstring style, set up with the sections to know.

    Build one once and call :meth:`parse` for every docstring; its sections
    are read when it is made, not on every call.
    """

    #: The name of the style the parser reads, such as ``"google"``.
    name: str

    def parse(self, text: T.Optional[str]) -> Docstring:
        """Parse a docstring into its components.

        :raises ParseError: for everything that could not be parsed
        """
        result = self.try_parse(text)
        if result.problems:
            raise parse_error(result)
        return result.docstring

    def try_parse(self, text: T.Optional[str]) -> ParseResult:
        """Parse what can be parsed of a docstring, and tell what cannot.

        Text that cannot be parsed goes to the long description.
        """
        raise NotImplementedError


def parse_error(result: ParseResult) -> ParseError:
    """Make the error for a docstring's problems, telling the first one."""
    first, *rest = result.problems
    message = first.message
    if rest:
        message += f" (and {len(rest)} more)"
    return ParseError(message, result.problems, result)
