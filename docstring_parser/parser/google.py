"""Google-style docstring parsing."""

import inspect
import re

from .common import Docstring, DocstringMeta, ParseError

_sections = {
    "Arguments": "param",
    "Args": "param",
    "Parameters": "param",
    "Params": "param",
    "Raises": "raises",
    "Exceptions": "raises",
    "Except": "raises",
    "Attributes": None,
    "Example": None,
    "Examples": None,
    "Returns": "returns",
    "Yields": "yields",
}
_titles_re = re.compile(
    "^(" + "|".join("(%s)" % t for t in _sections) + "):", flags=re.M
)
_valid = {t for t, a in _sections.items() if a}


def _build_meta(text: str, title: str) -> DocstringMeta:
    """Build docstring element.

    :param text: docstring element text
    :param title: title of section containing element
    :return:
    """

    meta = _sections[title]
    if meta == "returns" and ":" not in text.split()[0]:
        return DocstringMeta([meta], description=text)

    # Split spec and description
    before, desc = text.split(":", 1)
    if desc:
        desc = desc[1:] if desc[0] == " " else desc
        if "\n" in desc:
            first_line, rest = desc.split("\n", 1)
            desc = first_line + "\n" + inspect.cleandoc(rest)
        desc = desc.strip("\n")

    # Build Meta args
    m = re.match(r"(\S+) \((\S+)\)$", before)
    if meta == "param" and m:
        arg_name, type_name = m.group(1, 2)
        args = [meta, type_name, arg_name]
    else:
        args = [meta, before]

    return DocstringMeta(args, description=desc)


def parse(text: str) -> Docstring:
    """
    Parse the Google-style docstring into its components.

    :returns: parsed docstring
    """
    ret = Docstring()
    if not text:
        return ret

    # Clean according to PEP-0257
    text = inspect.cleandoc(text)

    # Find first title and split on its position
    match = _titles_re.search(text)
    if match:
        desc_chunk = text[: match.start()]
        meta_chunk = text[match.start() :]
    else:
        desc_chunk = text
        meta_chunk = ""

    # Break description into short and long parts
    parts = desc_chunk.split("\n", 1)
    ret.short_description = parts[0] or None
    if len(parts) > 1:
        long_desc_chunk = parts[1] or ""
        ret.blank_after_short_description = long_desc_chunk.startswith("\n")
        ret.blank_after_long_description = long_desc_chunk.endswith("\n\n")
        ret.long_description = long_desc_chunk.strip() or None

    # Split by sections determined by titles
    matches = list(_titles_re.finditer(meta_chunk))
    if not matches:
        return ret
    splits = []
    for j in range(len(matches) - 1):
        splits.append((matches[j].end(), matches[j + 1].start()))
    splits.append((matches[-1].end(), len(meta_chunk)))

    chunks = {}
    for j, (start, end) in enumerate(splits):
        title = matches[j].group(1)
        if title not in _valid:
            continue
        chunks[title] = meta_chunk[start:end].strip("\n")
    if not chunks:
        return ret

    # Add elements from each chunk
    for title, chunk in chunks.items():
        # Determine indent
        indent_match = re.search(r"^\s+", chunk)
        if not indent_match:
            raise ParseError(f'Can\'t infer indent from "{chunk}"')
        indent = indent_match.group()

        # Check for returns/yeilds (only one element)
        if _sections[title] in ("returns", "yields"):
            part = inspect.cleandoc(chunk)
            ret.meta.append(_build_meta(part, title))
            continue

        # Split based on lines which have exactly that indent
        _re = "^" + indent + r"(?=\S)"
        c_matches = list(re.finditer(_re, chunk, flags=re.M))
        if not c_matches:
            raise ParseError(f'No specification for "{title}": "{chunk}"')
        c_splits = []
        for j in range(len(c_matches) - 1):
            c_splits.append((c_matches[j].end(), c_matches[j + 1].start()))
        c_splits.append((c_matches[-1].end(), len(chunk)))
        for j, (start, end) in enumerate(c_splits):
            part = chunk[start:end].strip("\n")
            ret.meta.append(_build_meta(part, title))

    return ret
