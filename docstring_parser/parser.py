import inspect
import typing as T


class Docstring:
    """Docstring object representation."""

    def __init__(self) -> None:
        """Intializes self."""
        self.short_description: T.Optional[str] = None
        self.long_description: T.Optional[str] = None
        self.nl_after_short_description = False


def parse(text: str) -> Docstring:
    """
    Parse the docstring into its components.
    :returns: parsed docstring
    """
    docstring = Docstring()

    if text:
        parts = inspect.cleandoc(text).split('\n', 1)
        docstring.short_description = parts[0]

        if len(parts) > 1:
            docstring.nl_after_short_description = parts[1].startswith('\n')
            docstring.long_description = parts[1].strip()

    return docstring
