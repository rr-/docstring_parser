"""ReST-style docstring parsing."""

import re
import textwrap
import typing as T

from ._compose import description_lines, field_name, field_text
from ._lines import Lines
from ._text import append_loose, split_description
from .common import (
    PARAM_KEYWORDS,
    PARAM_KINDS,
    RAISES_KINDS,
    Docstring,
    DocstringDeprecated,
    DocstringExample,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
    Kind,
    ParseError,
    RenderingStyle,
    continuation_indented,
    excerpt,
)
from .sections import SectionSpec, apply

# The fields ReST recognises by default, by the kind of item each gives.
# ReST has no example fields of its own.
_DEFAULT_FIELDS = (
    (Kind.PARAM, ("param", "parameter", "arg", "argument")),
    (Kind.KEYWORD, ("key", "keyword")),
    (Kind.ATTRIBUTE, ("attribute",)),
    (Kind.RETURNS, ("returns", "return")),
    (Kind.YIELDS, ("yields", "yield")),
    (Kind.RAISES, ("raises", "raise", "except", "exception")),
    (Kind.DEPRECATION, ("deprecation", "deprecated")),
)


def default_sections() -> T.List[SectionSpec]:
    """Return the fields ReST recognises when given none."""
    return [SectionSpec(names, kind) for kind, names in _DEFAULT_FIELDS]


def _field_table(
    sections: T.Optional[T.Sequence[SectionSpec]],
) -> T.Dict[str, SectionSpec]:
    return {
        name: spec
        for spec in (default_sections() if sections is None else sections)
        for name in spec.titles
    }


_DEFAULT_TABLE = _field_table(None)


def _build_meta(args: T.List[str], desc: str, kind: Kind) -> DocstringMeta:
    key = args[0]

    if kind in PARAM_KINDS:
        if len(args) == 3:
            key, type_name, arg_name = args
            if type_name.endswith("?"):
                is_optional = True
                type_name = type_name[:-1]
            else:
                is_optional = False
        elif len(args) == 2:
            key, arg_name = args
            type_name = None
            is_optional = None
        else:
            raise ParseError(
                f"Expected one or two arguments for a {key} keyword."
            )

        match = _DEFAULTS_TO.match(desc)
        default = match.group(1).rstrip(".") if match else None

        return DocstringParam(
            key=key,
            description=desc,
            arg_name=arg_name,
            type_name=type_name,
            is_optional=is_optional,
            default=default,
            kind=kind,
        )

    if kind in (Kind.RETURNS, Kind.YIELDS) or kind in RAISES_KINDS:
        if len(args) > 2:
            raise ParseError(
                f"Expected one or no arguments for a {key} keyword."
            )
        type_name = args[1] if len(args) == 2 else None
        if kind in RAISES_KINDS:
            return DocstringRaises(
                description=desc, type_name=type_name, kind=kind, key=key
            )
        return DocstringReturns(
            key=key,
            description=desc,
            type_name=type_name,
            is_generator=kind is Kind.YIELDS,
        )

    if kind is Kind.DEPRECATION:
        match = _VERSION.search(desc)
        return DocstringDeprecated(
            key=key,
            version=match.group("version") if match else None,
            description=match.group("desc") if match else desc,
        )

    if kind is Kind.EXAMPLES:
        return DocstringExample(snippet=None, description=desc, key=key)

    return DocstringMeta(desc, key, " ".join(args[1:]) or None)


_DEFAULTS_TO = re.compile(r".*defaults to (.+)", flags=re.DOTALL)
_VERSION = re.compile(
    r"^(?P<version>v?((?:\d+)(?:\.[0-9a-z\.]+))) (?P<desc>.+)", flags=re.I
)


def parse(
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[SectionSpec]] = None,
) -> Docstring:
    """Parse the ReST-style docstring into its components.

    :param sections: the fields to recognise, instead of the default ones;
        each meta's ``key`` is the name its field is written with
    :returns: parsed docstring
    """
    table = _DEFAULT_TABLE if sections is None else _field_table(sections)
    ret = Docstring(style=DocstringStyle.REST)
    if not text:
        return ret

    text = Lines(text).text
    match = re.search("^:", text, flags=re.M)
    if match:
        desc_chunk = text[: match.start()]
        meta_chunk = text[match.start() :]
    else:
        desc_chunk = text
        meta_chunk = ""

    split_description(ret, desc_chunk)

    types = {}
    rtypes = {}
    # Text between or after the fields, such as an example block, which
    # goes to the long description instead of being dropped.
    loose_chunks = []
    loose_start = 0
    # A field ends at the next field (``^:``), at the end of the chunk
    # (``\Z``), or at a blank line followed by unindented, non-field
    # content. The last case ends the field list so that a trailing block
    # (e.g. an ``Example`` section) is not absorbed into the last field.
    for match in re.finditer(
        r"(^:.*?)(?=^:|\n[ \t]*\n(?=[^ \t\n:])|\Z)",
        meta_chunk,
        flags=re.S | re.M,
    ):
        loose_chunks.append(meta_chunk[loose_start : match.start()])
        loose_start = match.end()
        chunk = match.group(0)
        if not chunk:
            continue
        # A type is a single value, so an unindented line after it ends the
        # field rather than continuing the type.
        if re.match(r":r?type\b", chunk):
            unindented = re.search(r"\n(?=[^ \t\n])", chunk)
            if unindented:
                loose_chunks.append(chunk[unindented.end() :])
                chunk = chunk[: unindented.start()]
        try:
            args_chunk, desc_chunk = chunk.lstrip(":").split(":", 1)
        except ValueError as ex:
            raise ParseError(
                f'Error parsing meta information near "{excerpt(chunk)}".'
            ) from ex
        args = args_chunk.split()
        if not args:
            raise ParseError(
                f'Error parsing meta information near "{excerpt(chunk)}".'
            )
        desc = desc_chunk.strip()

        if "\n" in desc:
            # Dedent every continuation line alike, keeping blank lines and
            # indents relative to each other, as Google does.
            first_line, rest = desc.split("\n", 1)
            desc = first_line + "\n" + textwrap.dedent(rest)

        # Add special handling for :type a: typename
        if len(args) == 2 and args[0] == "type":
            types[args[1]] = desc
        elif len(args) in [1, 2] and args[0] == "rtype":
            rtypes[None if len(args) == 1 else args[1]] = desc
        else:
            spec = table.get(args[0])
            kind = spec.kind if spec else Kind.TEXT
            ret.meta.append(apply(spec, _build_meta(args, desc, kind)))
    loose_chunks.append(meta_chunk[loose_start:])

    append_loose(ret, loose_chunks, blank_around=True)

    for meta in ret.meta:
        if isinstance(meta, DocstringParam):
            meta.type_name = meta.type_name or types.get(meta.arg_name)
        elif isinstance(meta, DocstringReturns):
            meta.type_name = meta.type_name or rtypes.get(meta.return_name)

    if not any(isinstance(m, DocstringReturns) for m in ret.meta) and rtypes:
        for return_name, type_name in rtypes.items():
            ret.meta.append(
                DocstringReturns(
                    type_name=type_name,
                    description=None,
                    is_generator=False,
                    return_name=return_name,
                )
            )

    return ret


def _fits_inline(type_name: T.Optional[str]) -> bool:
    """Tell whether a type can go inside a field name, as in ``:param int a:``.

    A type with a space or a colon in it would read back as more arguments
    or end the field name early, so it needs a ``:type:`` field of its own.
    """
    return not type_name or not re.search(r"[\s:]", type_name)


_PARAM_FIELD_OF_KIND = {Kind.ATTRIBUTE: "attribute"}


def _param_key(meta: DocstringParam) -> str:
    """Return the field name that keeps a param's kind, such as ``key``."""
    return field_name(meta, PARAM_KEYWORDS, _PARAM_FIELD_OF_KIND)


def compose(
    docstring: Docstring,
    rendering_style: RenderingStyle = RenderingStyle.COMPACT,
    indent: str = "    ",
) -> str:
    """Render a parsed docstring into docstring text.

    :param docstring: parsed docstring representation
    :param rendering_style: the style to render docstrings
    :param indent: the characters used as indentation in the docstring string
    :returns: docstring text
    """

    def process_desc(desc: T.Optional[str]) -> str:
        if not desc:
            return ""

        # Continuation lines are indented, so that one starting with a colon
        # is not read back as a field of its own.
        (first, *rest) = desc.splitlines()
        rest = [indent + line if line else "" for line in rest]
        if rendering_style == RenderingStyle.EXPANDED or (
            continuation_indented(desc)
        ):
            return "\n".join(["\n" + indent + first] + rest)
        return "\n".join([" " + first] + rest)

    parts = description_lines(docstring)

    for meta in docstring.meta:
        if isinstance(meta, DocstringParam):
            if meta.type_name:
                type_text = (
                    f" {meta.type_name}? "
                    if meta.is_optional
                    else f" {meta.type_name} "
                )
            else:
                type_text = " "
            if rendering_style == RenderingStyle.EXPANDED or not _fits_inline(
                meta.type_name
            ):
                text = f":{_param_key(meta)} {meta.arg_name}:"
                text += process_desc(meta.description)
                parts.append(text)
                if type_text[:-1]:
                    parts.append(f":type {meta.arg_name}:{type_text[:-1]}")
            else:
                text = f":{_param_key(meta)}{type_text}{meta.arg_name}:"
                text += process_desc(meta.description)
                parts.append(text)
        elif isinstance(meta, DocstringReturns):
            type_text = f" {meta.type_name}" if meta.type_name else ""
            key = "yields" if meta.is_generator else "returns"

            if rendering_style == RenderingStyle.EXPANDED or not _fits_inline(
                meta.type_name
            ):
                if meta.description:
                    text = f":{key}:"
                    text += process_desc(meta.description)
                    parts.append(text)
                if type_text:
                    parts.append(f":rtype:{type_text}")
            else:
                text = f":{key}{type_text}:"
                text += process_desc(meta.description)
                parts.append(text)
        elif isinstance(meta, DocstringRaises):
            type_text = f" {meta.type_name} " if meta.type_name else ""
            text = f":raises{type_text}:" + process_desc(meta.description)
            parts.append(text)
        else:
            text = f":{field_text(meta)}:" + process_desc(meta.description)
            parts.append(text)
    return "\n".join(parts)
