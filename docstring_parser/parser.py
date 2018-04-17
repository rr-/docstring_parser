import inspect
import re
import typing as T


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
        """Returns type name associated with given docstring metadata."""
        return self.args[1] if len(self.args) > 1 else None


class DocstringParam(DocstringMeta):
    """DocstringMeta symbolizing :param metadata."""

    @property
    def arg_name(self) -> str:
        """Returns argument name associated with given param."""
        return self.args[2] if len(self.args) > 2 else self.args[1]

    @property
    def type_name(self) -> T.Optional[str]:
        """Returns type name associated with given param."""
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
        """Returns list of :param meta."""
        return [
            DocstringParam.from_meta(meta)
            for meta in self.meta
            if meta.args[0] in {
                'param', 'parameter', 'arg', 'argument', 'key', 'keyword'
            }
        ]

    @property
    def raises(self) -> T.List[DocstringRaises]:
        """Returns list of :raises meta."""
        return [
            DocstringRaises.from_meta(meta)
            for meta in self.meta
            if meta.args[0] in {'raises', 'raise', 'except', 'exception'}
        ]

    @property
    def returns(self) -> T.Optional[DocstringReturns]:
        """Returns :returns meta, if available."""
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

    parts = inspect.cleandoc(text).split('\n', 1)
    ret.short_description = parts[0]
    if ret.short_description == '':
        ret.short_description = None
    if len(parts) <= 1:
        return ret

    rest = parts[1]
    match = re.search('^:', rest, flags=re.M)
    if match:
        long_desc_chunk = rest[:match.start()]
        meta_chunk = rest[match.start():]
    else:
        long_desc_chunk = rest
        meta_chunk = ''
    ret.blank_after_short_description = long_desc_chunk.startswith('\n')
    ret.blank_after_long_description = long_desc_chunk.endswith('\n\n')
    ret.long_description = long_desc_chunk.strip()
    if not ret.long_description:
        ret.long_description = None

    for match in re.finditer(
            r'(^:.*?)(?=^:|\Z)', meta_chunk, flags=re.S | re.M
    ):
        chunk = match.group(0)
        if not chunk:
            continue
        args_chunk, desc_chunk = chunk.lstrip(':').split(':', 1)
        args = args_chunk.split()
        desc = desc_chunk.strip()
        if '\n' in desc:
            first_line, rest = desc.split('\n', 1)
            desc = first_line + '\n' + inspect.cleandoc(rest)
        ret.meta.append(DocstringMeta(args, description=desc))

    return ret
