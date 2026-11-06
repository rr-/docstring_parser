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


class ParseError(RuntimeError):
    """Base class for all parsing related errors."""


class DocstringStyle(enum.Enum):
    """Docstring style."""

    REST = 1
    GOOGLE = 2
    NUMPYDOC = 3
    EPYDOC = 4
    AUTO = 255


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
RAISES_KINDS = frozenset({Kind.RAISES, Kind.WARNS})


class DocstringMeta:
    """Docstring meta information.

    Symbolizes lines in form of

        :param arg: description
        :raises ValueError: if something happens
    """

    def __init__(
        self, args: T.List[str], description: T.Optional[str]
    ) -> None:
        """Initialize self.

        :param args: list of arguments. The exact content of this variable is
            dependent on the kind of docstring; it's used to distinguish
            between custom docstring meta information items.
        :param description: associated docstring description.
        """
        self.args = args
        self.description = description
        #: What the meta documents. Each class sets it, so that the class
        #: and the kind cannot disagree.
        self.kind = Kind.TEXT


class DocstringParam(DocstringMeta):
    """DocstringMeta symbolizing :param metadata."""

    def __init__(
        self,
        args: T.List[str],
        description: T.Optional[str],
        arg_name: str,
        type_name: T.Optional[str],
        is_optional: T.Optional[bool],
        default: T.Optional[str],
        kind: Kind = Kind.PARAM,
    ) -> None:
        """Initialize self.

        :param kind: the kind of param, such as a keyword or an attribute
        """
        super().__init__(args, description)
        if kind not in PARAM_KINDS:
            raise ValueError(f"{kind} is not a kind of param")
        self.kind = kind
        self.arg_name = arg_name
        self.type_name = type_name
        self.is_optional = is_optional
        self.default = default


class DocstringReturns(DocstringMeta):
    """DocstringMeta symbolizing :returns or :yields metadata."""

    def __init__(
        self,
        args: T.List[str],
        description: T.Optional[str],
        type_name: T.Optional[str],
        is_generator: bool,
        return_name: T.Optional[str] = None,
    ) -> None:
        """Initialize self."""
        super().__init__(args, description)
        self.kind = Kind.YIELDS if is_generator else Kind.RETURNS
        self.type_name = type_name
        self.is_generator = is_generator
        self.return_name = return_name


class DocstringRaises(DocstringMeta):
    """DocstringMeta symbolizing :raises metadata."""

    def __init__(
        self,
        args: T.List[str],
        description: T.Optional[str],
        type_name: T.Optional[str],
        kind: Kind = Kind.RAISES,
    ) -> None:
        """Initialize self.

        :param kind: raises or warns
        """
        super().__init__(args, description)
        if kind not in RAISES_KINDS:
            raise ValueError(f"{kind} is not a kind of raises")
        self.kind = kind
        self.type_name = type_name
        self.description = description


class DocstringDeprecated(DocstringMeta):
    """DocstringMeta symbolizing deprecation metadata."""

    def __init__(
        self,
        args: T.List[str],
        description: T.Optional[str],
        version: T.Optional[str],
    ) -> None:
        """Initialize self."""
        super().__init__(args, description)
        self.kind = Kind.DEPRECATION
        self.version = version
        self.description = description


class DocstringExample(DocstringMeta):
    """DocstringMeta symbolizing example metadata."""

    def __init__(
        self,
        args: T.List[str],
        snippet: T.Optional[str],
        description: T.Optional[str],
    ) -> None:
        """Initialize self."""
        super().__init__(args, description)
        self.kind = Kind.EXAMPLES
        self.snippet = snippet
        self.description = description


# ReST fields for attributes, which parse as plain meta rather than params.
ATTRIBUTE_FIELD_KEYWORDS = {"ivar", "var", "cvar"}


def meta_as_attribute(meta: DocstringMeta) -> T.Optional[DocstringParam]:
    """Return a ReST ``:ivar name:`` style field as an attribute param.

    :param meta: any docstring meta
    :returns: the attribute, or None if the meta is not such a field
    """
    if (
        type(meta) is DocstringMeta
        and len(meta.args) == 2
        and meta.args[0] in ATTRIBUTE_FIELD_KEYWORDS
    ):
        return DocstringParam(
            args=["attribute", meta.args[1]],
            description=meta.description,
            arg_name=meta.args[1],
            type_name=None,
            is_optional=None,
            default=None,
            kind=Kind.ATTRIBUTE,
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
        """Return a list of information on function params."""
        return [item for item in self.meta if isinstance(item, DocstringParam)]

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

        Takes the first return information.
        """
        for item in self.meta:
            if isinstance(item, DocstringReturns):
                return item
        return None

    @property
    def many_returns(self) -> T.List[DocstringReturns]:
        """Return a list of information on function return."""
        return [
            item for item in self.meta if isinstance(item, DocstringReturns)
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
