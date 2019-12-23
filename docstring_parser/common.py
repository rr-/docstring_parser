"""Common methods for parsing."""

import typing as T

PARAM_KEYWORDS = {"param", "parameter", "arg", "argument", "key", "keyword"}
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

    def __init__(self, args: T.List[str], description: str) -> None:
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
        args: T.List[str],
        description: str,
        arg_name: str,
        type_name: T.Optional[str],
        is_optional: T.Optional[bool],
    ) -> None:
        """Initialize self."""
        super().__init__(args, description)
        self.arg_name = arg_name
        self.type_name = type_name
        self.is_optional = is_optional


class DocstringReturns(DocstringMeta):
    """DocstringMeta symbolizing :returns or :yields metadata."""

    def __init__(
        self,
        args: T.List[str],
        description: str,
        type_name: str,
        is_generator: bool,
    ) -> None:
        """Initialize self."""
        super().__init__(args, description)
        self.type_name = type_name
        self.is_generator = is_generator


class DocstringRaises(DocstringMeta):
    """DocstringMeta symbolizing :raises metadata."""

    def __init__(
        self, args: T.List[str], description: str, type_name: str
    ) -> None:
        """Initialize self."""
        super().__init__(args, description)
        self.type_name = type_name
        self.description = description


class Docstring:
    """Docstring object representation."""

    def __init__(self) -> None:
        """Initialize self."""
        self.short_description: T.Optional[str] = None
        self.long_description: T.Optional[str] = None
        self.blank_after_short_description = False
        self.blank_after_long_description = False
        self.meta: T.List[DocstringMeta] = []

    @property
    def params(self) -> T.List[DocstringParam]:
        return [item for item in self.meta if isinstance(item, DocstringParam)]

    @property
    def raises(self) -> T.List[DocstringRaises]:
        return [
            item for item in self.meta if isinstance(item, DocstringRaises)
        ]

    @property
    def returns(self) -> T.Optional[DocstringReturns]:
        for item in self.meta:
            if isinstance(item, DocstringReturns):
                return item
        return None
