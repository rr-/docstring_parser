"""Epyoc-style docstring parsing.

.. seealso:: http://epydoc.sourceforge.net/manual-fields.html
"""

import re
import typing as T

from ._compose import description_lines, field_name, field_text
from ._fields import ParamTypes, ReturnTypes, assign_types
from ._lines import Lines
from ._text import append_loose, split_description
from .common import (
    PARAM_KINDS,
    RAISES_KINDS,
    BaseParser,
    Docstring,
    DocstringDeprecated,
    DocstringExample,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
    Kind,
    ParseResult,
    Problem,
    RenderingStyle,
    cleandoc,
    excerpt,
)
from .sections import ParserCache, SectionSpec, apply

_FIELD_START = re.compile("^@", flags=re.M)
_DEFAULTS_TO = re.compile(r".*defaults to (.+)", flags=re.DOTALL)
_FIELD = re.compile(r"(^@.*?)(?=^@|\Z)", flags=re.S | re.M)
# A field's header: its name, then the names it is about, then a colon.
_HEADER = re.compile(r"([_A-z][_A-z0-9]*)((?:\s+[_A-z][_A-z0-9]*\??)*):")

# The fields that give the type of a param, a return value or a yield,
# which are not items of their own.
_TYPE_FIELDS = {
    "type": ("param", Kind.PARAM),
    "rtype": ("return", Kind.RETURNS),
    "ytype": ("return", Kind.YIELDS),
}


def _base(
    spec: T.Optional[SectionSpec], args: T.List[str]
) -> T.Tuple[str, Kind]:
    """Tell how a field combines with others, and its kind."""
    if spec is None:
        return "meta", Kind.TEXT
    kind = spec.kind
    if kind in PARAM_KINDS:
        return "param", kind
    if kind in (Kind.RETURNS, Kind.YIELDS):
        return "return", kind
    if kind in RAISES_KINDS:
        # A raises field names one exception at most; one naming more is
        # plain text.
        return ("raise", kind) if len(args) <= 1 else ("meta", Kind.TEXT)
    return "meta", kind


def default_sections() -> T.List[SectionSpec]:
    """Return the fields Epydoc recognises when given none."""
    return [
        SectionSpec("param", Kind.PARAM),
        SectionSpec("keyword", Kind.KEYWORD),
        SectionSpec(("ivar", "cvar", "var"), Kind.ATTRIBUTE),
        SectionSpec("return", Kind.RETURNS),
        SectionSpec("yield", Kind.YIELDS),
        SectionSpec("raise", Kind.RAISES),
    ]


def _field_table(
    sections: T.Sequence[SectionSpec],
) -> T.Dict[str, SectionSpec]:
    return {name: spec for spec in sections for name in spec.titles}


_DEFAULT_TABLE = _field_table(default_sections())


class Parser(BaseParser):
    """Parser for Epydoc-style docstrings."""

    name = "epydoc"

    def __init__(
        self, sections: T.Optional[T.Sequence[SectionSpec]] = None
    ) -> None:
        """Set up the parser.

        :param sections: the fields to recognise, instead of the default
            ones; each meta's ``key`` is the name its field is written with
        """
        self._table = (
            _DEFAULT_TABLE if sections is None else _field_table(sections)
        )

    def try_parse(self, text: T.Optional[str]) -> ParseResult:
        """Parse what can be parsed of a docstring, and tell what cannot."""
        table = self._table
        ret = Docstring(style=DocstringStyle.EPYDOC)
        if not text:
            return ParseResult(ret, [])

        lines = Lines(text)
        text = lines.text
        match = _FIELD_START.search(text)
        if not match:
            split_description(ret, text)
            return ParseResult(ret, [])
        meta_start = match.start()
        meta_chunk = text[meta_start:]
        split_description(ret, text[:meta_start])

        metas: T.List[DocstringMeta] = []
        specs: T.Dict[int, T.Optional[SectionSpec]] = {}
        types: ParamTypes = {}
        rtypes: ReturnTypes = {}
        # Whether the return fields are about yields, which they must all
        # be or none of them.
        generator: T.Optional[bool] = None
        # Fields that cannot be read, which are kept as text.
        loose: T.List[str] = []
        problems: T.List[Problem] = []
        for match in _FIELD.finditer(meta_chunk):
            chunk = match.group(0)
            if not chunk:
                continue
            at = meta_start + match.start()

            # Each chunk starts with @; description text is not a field header.
            header = _HEADER.match(chunk, 1)
            key = header.group(1) if header else ""
            args = header.group(2).split() if header else []
            spec = table.get(key)
            base, kind = _TYPE_FIELDS.get(key) or _base(spec, args)
            if (
                not header
                or (base == "param" and len(args) != 1)
                or (base == "return" and args)
                or (base == "meta" and spec is None and len(key) < 2)
            ):
                problems.append(
                    Problem(
                        lines.source_line(at),
                        "Error parsing meta information near "
                        f'"{excerpt(chunk)}".',
                    )
                )
                loose.append(chunk)
                continue
            if base == "return":
                is_generator = kind is Kind.YIELDS
                if generator is not None and generator != is_generator:
                    problems.append(
                        Problem(
                            lines.source_line(at),
                            'Error parsing meta information for "return".',
                        )
                    )
                    loose.append(chunk)
                    continue
                generator = is_generator

            desc = chunk[header.end() :].strip()
            if "\n" in desc:
                first_line, rest = desc.split("\n", 1)
                desc = first_line + "\n" + cleandoc(rest)

            if key in _TYPE_FIELDS:
                if base == "param":
                    types.setdefault(args[0], []).append((desc, len(metas)))
                else:
                    rtypes.setdefault(None, []).append(
                        (desc, len(metas), kind, key)
                    )
                continue
            meta: DocstringMeta
            if base == "param":
                defaults_to = _DEFAULTS_TO.match(desc)
                meta = DocstringParam(
                    desc,
                    arg_name=args[0],
                    type_name=None,
                    is_optional=False,
                    default=defaults_to.group(1).rstrip(".")
                    if defaults_to
                    else None,
                    kind=kind,
                    key=key,
                )
            elif base == "return":
                meta = DocstringReturns(
                    desc, None, kind is Kind.YIELDS, key=key
                )
            elif base == "raise":
                (type_name,) = args or (None,)
                meta = DocstringRaises(desc, type_name, kind=kind, key=key)
            elif kind is Kind.EXAMPLES:
                meta = DocstringExample(None, desc, key=key)
            elif kind is Kind.DEPRECATION:
                meta = DocstringDeprecated(desc, None, key=key)
            else:
                meta = DocstringMeta(desc, key, " ".join(args) or None)
            if spec is not None and spec.parse_item is not None:
                specs[id(meta)] = spec
            metas.append(meta)

        assign_types(metas, types, rtypes)
        if specs:
            metas = [apply(specs.get(id(meta)), meta) for meta in metas]
        ret.meta = metas
        if loose:
            append_loose(ret, loose, blank_around=True)
        return ParseResult(ret, problems)


_DEFAULT_PARSER = Parser()
_parsers: ParserCache[Parser] = ParserCache()


def parse(
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[SectionSpec]] = None,
) -> Docstring:
    """Parse the epydoc-style docstring into its components.

    :param sections: the fields to recognise, instead of the default ones;
        each meta's ``key`` is the name its field is written with
    :returns: parsed docstring
    """
    return _parser(sections).parse(text)


def try_parse(
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[SectionSpec]] = None,
) -> ParseResult:
    """Parse what can be parsed of a epydoc-style docstring, and tell what
    cannot, instead of raising.

    :param sections: as for :func:`parse`
    :returns: the docstring, and a problem for each part that cannot be
        read, whose text goes to the long description
    """
    return _parser(sections).try_parse(text)


def _parser(sections: T.Optional[T.Sequence[SectionSpec]]) -> Parser:
    if sections is None:
        return _DEFAULT_PARSER
    return _parsers.get(list(sections), Parser, sections)


_OWN_PARAM_FIELDS = frozenset({"param", "keyword", "ivar", "cvar", "var"})
_PARAM_FIELD_OF_KIND = {Kind.ATTRIBUTE: "ivar", Kind.KEYWORD: "keyword"}


def _param_key(meta: DocstringParam) -> str:
    """Return the field name that keeps a param's kind, such as ``ivar``."""
    return field_name(meta, _OWN_PARAM_FIELDS, _PARAM_FIELD_OF_KIND)


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

    def process_desc(desc: T.Optional[str], is_type: bool) -> str:
        if not desc:
            return ""

        if rendering_style == RenderingStyle.EXPANDED or (
            rendering_style == RenderingStyle.CLEAN and not is_type
        ):
            (first, *rest) = desc.splitlines()
            return "\n".join(
                ["\n" + indent + first] + [indent + line for line in rest]
            )

        (first, *rest) = desc.splitlines()
        return "\n".join([" " + first] + [indent + line for line in rest])

    parts = description_lines(docstring)

    for meta in docstring.meta:
        if isinstance(meta, DocstringParam):
            if meta.type_name:
                type_name = (
                    f"{meta.type_name}?"
                    if meta.is_optional
                    else meta.type_name
                )
                text = f"@type {meta.arg_name}:"
                text += process_desc(type_name, True)
                parts.append(text)
            text = f"@{_param_key(meta)} {meta.arg_name}:" + process_desc(
                meta.description, False
            )
            parts.append(text)
        elif isinstance(meta, DocstringReturns):
            (arg_key, type_key) = (
                ("yield", "ytype")
                if meta.is_generator
                else ("return", "rtype")
            )
            if meta.type_name:
                text = f"@{type_key}:" + process_desc(meta.type_name, True)
                parts.append(text)
            if meta.description:
                text = f"@{arg_key}:" + process_desc(meta.description, False)
                parts.append(text)
        elif isinstance(meta, DocstringRaises):
            text = f"@raise {meta.type_name}:" if meta.type_name else "@raise:"
            text += process_desc(meta.description, False)
            parts.append(text)
        else:
            text = f"@{field_text(meta)}:"
            text += process_desc(meta.description, False)
            parts.append(text)
    return "\n".join(parts)
