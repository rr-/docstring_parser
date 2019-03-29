"""Common methods for parsing."""

import typing as T


class ParseError(RuntimeError):
    """Base class for all parsing related errors."""

    pass


class DocstringMeta:
    """
    Docstring meta information.

    Symbolizes lines in form of

        :param arg: description
        :raises ValueError: if something happens
    """

    def __init__(self, args: T.List[str], description: str) -> None:
        """
        Initialize self.

        :param args: list of arguments before delimiting colon.
        :param description: associated docstring description.
        """
        self.args = args
        self.description = description

    @classmethod
    def from_meta(cls, meta: "DocstringMeta") -> T.Any:
        """Copy DocstringMeta from another instance."""
        return cls(args=meta.args, description=meta.description)


class DocstringTypeMeta(DocstringMeta):
    """Docstring meta whose only optional arg contains type information."""

    @property
    def type_name(self) -> T.Optional[str]:
        """Return type name associated with given docstring metadata."""
        return self.args[1] if len(self.args) > 1 else None


class DocstringParam(DocstringMeta):
    """DocstringMeta symbolizing :param metadata."""

    @property
    def arg_name(self) -> T.Optional[str]:
        """Return argument name associated with given param."""
        if len(self.args) > 2:
            return self.args[2]
        elif len(self.args) > 1:
            return self.args[1]
        return None

    @property
    def type_name(self) -> T.Optional[str]:
        """Return type name associated with given param."""
        return self.args[1] if len(self.args) > 2 else None


class DocstringReturns(DocstringTypeMeta):
    """DocstringMeta symbolizing :returns metadata."""

    pass


class DocstringRaises(DocstringTypeMeta):
    """DocstringMeta symbolizing :raises metadata."""

    pass


class Docstring:
    """Docstring object representation."""

    def __init__(self) -> None:
        """Intializes self."""
        self.short_description: T.Optional[str] = None
        self.long_description: T.Optional[str] = None
        self.blank_after_short_description = False
        self.blank_after_long_description = False
        self.meta: T.List[DocstringMeta] = []

    @property
    def params(self) -> T.List[DocstringParam]:
        """Return parameters indicated in docstring."""
        return [
            DocstringParam.from_meta(meta)
            for meta in self.meta
            if meta.args[0]
            in {"param", "parameter", "arg", "argument", "key", "keyword"}
        ]

    @property
    def raises(self) -> T.List[DocstringRaises]:
        """Return exceptions indicated in docstring."""
        return [
            DocstringRaises.from_meta(meta)
            for meta in self.meta
            if meta.args[0] in {"raises", "raise", "except", "exception"}
        ]

    @property
    def returns(self) -> T.Optional[DocstringReturns]:
        """Return return information indicated in docstring."""
        try:
            return next(
                DocstringReturns.from_meta(meta)
                for meta in self.meta
                if meta.args[0] in {"return", "returns", "yield", "yields"}
            )
        except StopIteration:
            return None
