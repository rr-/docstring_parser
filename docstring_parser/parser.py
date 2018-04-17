"""Docstring parser implementation."""

import inspect
import re
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

    def __init__(
            self,
            args: T.List[str],
            description: str
    ) -> None:
        """
        Initialize self.

        :param args: list of arguments before delimiting colon.
        :param description: associated docstring description.
        """
        self.args = args
        self.description = description

    @classmethod
    def from_meta(cls, meta: 'DocstringMeta') -> T.Any:
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
        """Return list of :param meta."""
        return [
            DocstringParam.from_meta(meta)
            for meta in self.meta
            if meta.args[0] in {
                'param', 'parameter', 'arg', 'argument', 'key', 'keyword'
            }
        ]

    @property
    def raises(self) -> T.List[DocstringRaises]:
        """Return list of :raises meta."""
        return [
            DocstringRaises.from_meta(meta)
            for meta in self.meta
            if meta.args[0] in {'raises', 'raise', 'except', 'exception'}
        ]

    @property
    def returns(self) -> T.Optional[DocstringReturns]:
        """Return :returns meta, if available."""
        try:
            return next(
                DocstringReturns.from_meta(meta)
                for meta in self.meta
                if meta.args[0] in {'return', 'returns'}
            )
        except StopIteration:
            return None


def parse(text: str) -> Docstring:
    """
    Parse the docstring into its components.

    :returns: parsed docstring
    """
    ret = Docstring()
    if not text:
        return ret

    text = inspect.cleandoc(text)
    match = re.search('^:', text, flags=re.M)
    if match:
        desc_chunk = text[:match.start()]
        meta_chunk = text[match.start():]
    else:
        desc_chunk = text
        meta_chunk = ''

    parts = desc_chunk.split('\n', 1)
    ret.short_description = parts[0] or None
    if len(parts) > 1:
        long_desc_chunk = parts[1] or ''
        ret.blank_after_short_description = long_desc_chunk.startswith('\n')
        ret.blank_after_long_description = long_desc_chunk.endswith('\n\n')
        ret.long_description = long_desc_chunk.strip() or None

    for match in re.finditer(
            r'(^:.*?)(?=^:|\Z)', meta_chunk, flags=re.S | re.M
    ):
        chunk = match.group(0)
        if not chunk:
            continue
        try:
            args_chunk, desc_chunk = chunk.lstrip(':').split(':', 1)
        except ValueError:
            raise ParseError(
                f'Error parsing meta information near "{chunk}".'
            )
        args = args_chunk.split()
        desc = desc_chunk.strip()
        if '\n' in desc:
            first_line, rest = desc.split('\n', 1)
            desc = first_line + '\n' + inspect.cleandoc(rest)
        ret.meta.append(DocstringMeta(args, description=desc))

    return ret
