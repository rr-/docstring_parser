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


class Docstring:
    """Docstring object representation."""

    def __init__(self) -> None:
        """Intializes self."""
        self.short_description: T.Optional[str] = None
        self.long_description: T.Optional[str] = None
        self.blank_after_short_description = False
        self.blank_after_long_description = False
        self.meta: T.List[DocstringMeta] = []


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
