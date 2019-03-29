"""ReST-style docstring parsing."""

import inspect
import re

from .common import Docstring, DocstringMeta, ParseError


def parse(text: str) -> Docstring:
    """
    Parse the ReST-style docstring into its components.

    :returns: parsed docstring
    """
    ret = Docstring()
    if not text:
        return ret

    text = inspect.cleandoc(text)
    match = re.search("^:", text, flags=re.M)
    if match:
        desc_chunk = text[: match.start()]
        meta_chunk = text[match.start() :]
    else:
        desc_chunk = text
        meta_chunk = ""

    parts = desc_chunk.split("\n", 1)
    ret.short_description = parts[0] or None
    if len(parts) > 1:
        long_desc_chunk = parts[1] or ""
        ret.blank_after_short_description = long_desc_chunk.startswith("\n")
        ret.blank_after_long_description = long_desc_chunk.endswith("\n\n")
        ret.long_description = long_desc_chunk.strip() or None

    for match in re.finditer(
        r"(^:.*?)(?=^:|\Z)", meta_chunk, flags=re.S | re.M
    ):
        chunk = match.group(0)
        if not chunk:
            continue
        try:
            args_chunk, desc_chunk = chunk.lstrip(":").split(":", 1)
        except ValueError:
            raise ParseError(f'Error parsing meta information near "{chunk}".')
        args = args_chunk.split()
        desc = desc_chunk.strip()
        if "\n" in desc:
            first_line, rest = desc.split("\n", 1)
            desc = first_line + "\n" + inspect.cleandoc(rest)
        ret.meta.append(DocstringMeta(args, description=desc))

    return ret
