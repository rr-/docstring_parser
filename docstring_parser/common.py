"""Common methods for parsing."""
from typing import Optional, List

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
RETURNS_KEYWORDS = {"return", "returns"}
YIELDS_KEYWORDS = {"yield", "yields"}


class ParseError(RuntimeError):
    """Base class for all parsing related errors."""

    pass


class DocstringMeta:
    """Docstring meta information.

    Symbolizes lines in form of

        :param arg: description
        :raises ValueError: if something happens
    """

    def __init__(self, args: List[str], description: str) -> None:
        """Initialize self.

        :param args: list of arguments. The exact content of this variable is
                     dependent on the kind of docstring; it's used to distinguish between
                     custom docstring meta information items.
        :param description: associated docstring description.
        """
        self.args = args
        self.description = description


class DocstringParam(DocstringMeta):
    """DocstringMeta symbolizing :param metadata."""

    def __init__(
            self,
            args: List[str],
            description: Optional[str],
            arg_name: str,
            type_name: Optional[str],
            is_optional: Optional[bool],
            default: Optional[str],
    ) -> None:
        """Initialize self."""
        super().__init__(args, description)
        self.arg_name = arg_name
        self.type_name = type_name
        self.is_optional = is_optional
        self.default = default


class DocstringReturns(DocstringMeta):
    """DocstringMeta symbolizing :returns or :yields metadata."""

    def __init__(
            self,
            args: List[str],
            description: Optional[str],
            type_name: Optional[str],
            is_generator: bool,
            return_name: Optional[str] = None,
    ) -> None:
        """Initialize self."""
        super().__init__(args, description)
        self.type_name = type_name
        self.is_generator = is_generator
        self.return_name = return_name


class DocstringRaises(DocstringMeta):
    """DocstringMeta symbolizing :raises metadata."""

    def __init__(
            self,
            args: List[str],
            description: Optional[str],
            type_name: Optional[str],
    ) -> None:
        """Initialize self."""
        super().__init__(args, description)
        self.type_name = type_name
        self.description = description


class DocstringDeprecated(DocstringMeta):
    """DocstringMeta symbolizing deprecation metadata."""

    def __init__(
            self,
            args: List[str],
            description: Optional[str],
            version: Optional[str],
    ) -> None:
        """Initialize self."""
        super().__init__(args, description)
        self.version = version
        self.description = description


class Docstring:
    """Docstring object representation."""

    def __init__(self) -> None:
        """Initialize self."""
        self.short_description = None  # type: Optional[str]
        self.long_description = None  # type: Optional[str]
        self.blank_after_short_description = False
        self.blank_after_long_description = False
        self.meta = []  # type: List[DocstringMeta]

    @property
    def params(self) -> List[DocstringParam]:
        return [item for item in self.meta if isinstance(item, DocstringParam)]

    @property
    def raises(self) -> List[DocstringRaises]:
        return [
            item for item in self.meta if isinstance(item, DocstringRaises)
        ]

    @property
    def returns(self) -> Optional[DocstringReturns]:
        for item in self.meta:
            if isinstance(item, DocstringReturns):
                return item
        return None

    @property
    def deprecation(self) -> Optional[DocstringDeprecated]:
        for item in self.meta:
            if isinstance(item, DocstringDeprecated):
                return item
        return None
