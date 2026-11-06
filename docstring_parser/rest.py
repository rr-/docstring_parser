"""ReST-style docstring parsing."""

import re
import textwrap
import typing as T

from ._compose import (
    description_lines,
    field_name,
    field_text,
    written_type,
)
from ._fields import AFTER_ALL, ParamTypes, ReturnTypes, assign_types
from ._lines import Lines
from ._text import (
    append_loose,
    param_spec,
    split_description,
)
from .common import (
    ATTRIBUTE_FIELD_KEYWORDS,
    PARAM_KEYWORDS,
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
    ItemError,
    Kind,
    ParseResult,
    Problem,
    RenderingStyle,
    continuation_indented,
    excerpt,
)
from .sections import ParserCache, SectionSpec, apply

# The fields ReST recognises by default, by the kind of item each gives.
# ReST has no example fields of its own.
_DEFAULT_FIELDS = (
    (Kind.PARAM, ("param", "parameter", "arg", "argument")),
    (Kind.KEYWORD, ("key", "keyword")),
    (Kind.ATTRIBUTE, ("attribute", "ivar", "var", "cvar")),
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


# Words that join the words around them into one type, as in
# ``int or None`` or ``list of str``.
_TYPE_JOINERS = frozenset({"or", "of", "|"})


def _join_type(words: T.List[str]) -> T.Optional[str]:
    """Join the words of a field's head that make up one type.

    A type can have spaces inside brackets, as in ``Dict[str, int]``,
    after a comma, as in ``A, B``, and around ``or``, ``of`` and ``|``.
    Other words in a row are no type, so the field cannot be read.

    :returns: the type, or None if the words are not one
    """
    if len(words) == 1:
        return words[0]
    parts: T.List[str] = []
    depth = 0
    for word in words:
        if depth > 0:
            parts[-1] += " " + word
        elif not parts or (
            parts[-1].endswith(",")
            or parts[-1] in _TYPE_JOINERS
            or word in _TYPE_JOINERS
        ):
            parts.append(word)
        else:
            return None
        for char in word:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
                if depth < 0:
                    return None
    return " ".join(parts) if depth == 0 else None


def _build_meta(args: T.List[str], desc: str, kind: Kind) -> DocstringMeta:
    key = args[0]

    if kind in PARAM_KINDS:
        # The field's head is its key, maybe a type, and the param's name.
        raw_type_name = _join_type(args[1:-1]) if len(args) > 2 else None
        if len(args) < 2 or (len(args) > 2 and raw_type_name is None):
            raise ItemError(
                "wrong-arguments",
                f"Expected one or two arguments for a {key} keyword.",
            )
        arg_name = args[-1]
        spec = param_spec(raw_type_name, desc)
        return DocstringParam(
            key=key,
            description=desc,
            arg_name=arg_name,
            type_name=spec.type_name,
            is_optional=spec.is_optional,
            default=spec.default,
            kind=kind,
            raw_type_name=raw_type_name,
        )

    if kind in (Kind.RETURNS, Kind.YIELDS) or kind in RAISES_KINDS:
        type_name = _join_type(args[1:]) if len(args) > 1 else None
        if len(args) > 1 and type_name is None:
            raise ItemError(
                "wrong-arguments",
                f"Expected one or no arguments for a {key} keyword.",
            )
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


# A field's name and the colon closing it, as docutils reads them: a colon
# in the name is followed by neither whitespace nor a backtick, and the
# closing one is followed by whitespace or the end of the line. So a line
# starting with a role, as in ``:meth:`run` does stuff.``, is text.
_NAME = r"((?:[^:\n]|:(?![\s`]))*):(?=\s|\Z)"
_FIELD_NAME = re.compile(_NAME)
# What follows the colon starting a field: a name, or a line with no other
# colon, as in ``:param x``, which is a field that cannot be read.
_STARTS_FIELD = rf"{_NAME}|[^:\n]*$"
_START = rf"^:(?={_STARTS_FIELD})"
_FIELD_START = re.compile(_START, flags=re.M)
# A field ends at the next field, at the end of the text (``\Z``), or at a
# blank line followed by unindented content that starts no field.
_FIELD = re.compile(
    rf"({_START}.*?)(?={_START}"
    rf"|\n[ \t]*\n(?=[^ \t\n:]|:(?!{_STARTS_FIELD}))|\Z)",
    flags=re.S | re.M,
)
_TYPE_FIELD = re.compile(r":(?:[ry]|var)?type\b")
_UNINDENTED = re.compile(r"\n(?=[^ \t\n])")
_NOT_INLINE = re.compile(r"[\s:]")
# An attribute directive, as Sphinx writes one:
#
#   .. attribute:: name
#      :type: int
#
#      Its description.
_ATTRIBUTE = re.compile(
    r"^\.\.[ \t]+(?:py:)?attribute[ \t]*::[ \t]*(\S[^\n]*?)[ \t]*$",
    flags=re.M,
)
_OPTION = re.compile(r":([\w-]+):[ \t]*(.*)")
_VERSION = re.compile(
    r"^(?P<version>v?((?:\d+)(?:\.[0-9a-z\.]+))) (?P<desc>.+)",
    flags=re.I | re.S,
)


def _attribute(name: str, body: T.List[str]) -> DocstringParam:
    """Build an attribute from its directive's name and indented body."""
    body = textwrap.dedent("\n".join(body)).split("\n")
    options: T.Dict[str, str] = {}
    # Options Sphinx has but that say nothing of the attribute, such as
    # ``:no-index:``, are kept with the description.
    other: T.List[str] = []
    start = 0
    while start < len(body):
        option = _OPTION.fullmatch(body[start])
        if option is None:
            break
        if option.group(1) in ("type", "value"):
            options[option.group(1)] = option.group(2).strip()
        else:
            other.append(body[start])
        start += 1
    raw_type_name = options.get("type") or None
    description = "\n".join(other + body[start:]).strip()
    spec = param_spec(raw_type_name, description)
    default = options.get("value") or spec.default
    return DocstringParam(
        description,
        arg_name=name,
        type_name=spec.type_name,
        is_optional=spec.is_optional or default is not None,
        default=default,
        kind=Kind.ATTRIBUTE,
        key="attribute",
        raw_type_name=raw_type_name,
    )


def _cut_attributes(
    lines: Lines, spec: SectionSpec
) -> T.Tuple[Lines, T.List[T.Tuple[int, DocstringMeta]]]:
    """Cut the attribute directives out of a docstring.

    :returns: the lines left, and each attribute with the offset into
        their text where it was
    """
    cut: T.List[T.Tuple[int, int]] = []
    found: T.List[T.Tuple[int, str, T.List[str]]] = []
    every = lines.lines
    for match in _ATTRIBUTE.finditer(lines.text):
        start = lines.line_at(match.start())
        end = start + 1
        while end < len(every) and (not every[end] or every[end][0] == " "):
            end += 1
        body_end = end
        while body_end > start + 1 and not every[body_end - 1].strip():
            body_end -= 1
        # Blank lines after the directive go with it when blank lines
        # before it already set it off, so no extra blank lines are left.
        if start and every[start - 1].strip():
            end = body_end
        cut.append((start, end))
        found.append((start, match.group(1), every[start + 1 : body_end]))
    if not cut:
        return lines, []
    left = lines.without(cut)
    # Where each attribute was, as an offset into the text left.
    attributes = []
    removed = offset = index = 0
    for (start, end), (_start, name, body) in zip(cut, found):
        while index < start - removed:
            offset += len(left.lines[index]) + 1
            index += 1
        attributes.append((offset, apply(spec, _attribute(name, body))))
        removed += end - start
    return left, attributes


class Parser(BaseParser):
    """Parser for ReST-style docstrings."""

    name = "rest"

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
        spec = self._table.get("attribute")
        # The spec of attribute directives, if attributes are recognised.
        self._attribute = (
            spec if spec is not None and spec.kind is Kind.ATTRIBUTE else None
        )

    def try_parse(self, text: T.Optional[str]) -> ParseResult:
        """Parse what can be parsed of a docstring, and tell what cannot."""
        table = self._table
        ret = Docstring(style=DocstringStyle.REST)
        if not text:
            return ParseResult(ret, [])

        lines = Lines(text)
        attributes: T.List[T.Tuple[int, DocstringMeta]] = []
        if self._attribute is not None and "attribute" in lines.text:
            lines, attributes = _cut_attributes(lines, self._attribute)
        text = lines.text
        problems: T.List[Problem] = []
        match = _FIELD_START.search(text)
        meta_start = match.start() if match else len(text)
        if match:
            desc_chunk = text[: match.start()]
            meta_chunk = text[match.start() :]
        else:
            desc_chunk = text
            meta_chunk = ""
            if attributes and text.endswith("\n"):
                # A blank line set the description off from the directives
                # cut from after it, as it would from fields.
                desc_chunk += "\n"

        split_description(ret, desc_chunk)

        types: ParamTypes = {}
        vartypes: ParamTypes = {}
        # The type fields with no type, by field name, name and position.
        untyped: T.List[T.Tuple[str, str, int]] = []
        rtypes: ReturnTypes = {}
        ytypes: ReturnTypes = {}
        # Whether the field before gave an item, rather than a type.
        after_item = False
        # Text between or after the fields, such as an example block, which
        # goes to the long description instead of being dropped.
        loose_chunks = []
        loose_start = 0
        # A field ends at the next field, at the end of the chunk
        # (``\Z``), or at a blank line followed by unindented, non-field
        # content. The last case ends the field list so that a trailing block
        # (e.g. an ``Example`` section) is not absorbed into the last field.
        # The next attribute to add, in the order it was written in, and
        # where it was in the fields.
        next_attribute = 0
        next_at = attributes[0][0] - meta_start if attributes else len(text)
        for match in _FIELD.finditer(meta_chunk):
            if match.start() >= next_at:
                while (
                    next_attribute < len(attributes)
                    and attributes[next_attribute][0]
                    <= meta_start + match.start()
                ):
                    ret.meta.append(attributes[next_attribute][1])
                    next_attribute += 1
                next_at = (
                    attributes[next_attribute][0] - meta_start
                    if next_attribute < len(attributes)
                    else len(text)
                )
            loose_chunks.append(meta_chunk[loose_start : match.start()])
            loose_start = match.end()
            chunk = match.group(0)
            if not chunk:
                continue
            # A type is a single value, so an unindented line after it ends the
            # field rather than continuing the type.
            if _TYPE_FIELD.match(chunk):
                unindented = _UNINDENTED.search(chunk)
                if unindented:
                    loose_chunks.append(chunk[unindented.end() :])
                    chunk = chunk[: unindented.start()]
            at = meta_start + match.start()
            stripped = chunk.lstrip(":")
            name = _FIELD_NAME.match(stripped)
            if name:
                head, colon = name.group(1), ":"
                desc_chunk = stripped[name.end() :]
            else:
                head, colon, desc_chunk = stripped.partition(":")
            args = head.split()
            if not colon or not args:
                # A field that cannot be read is kept as text.
                problems.append(
                    Problem(
                        lines.source_line(at),
                        "bad-field",
                        "Error parsing meta information near "
                        f'"{excerpt(chunk)}".',
                    )
                )
                loose_chunks.append(chunk)
                after_item = False
                continue
            desc = desc_chunk.strip()

            if "\n" in desc:
                # Dedent every continuation line alike, keeping blank lines and
                # indents relative to each other, as Google does.
                first_line, rest = desc.split("\n", 1)
                desc = first_line + "\n" + textwrap.dedent(rest)

            # Add special handling for :type a: typename
            if len(args) == 2 and args[0] in ("type", "vartype"):
                if desc:
                    by_name = types if args[0] == "type" else vartypes
                    by_name.setdefault(args[1], []).append(
                        (desc, len(ret.meta))
                    )
                else:
                    untyped.append((args[0], args[1], len(ret.meta)))
            elif len(args) in [1, 2] and args[0] in ("rtype", "ytype"):
                name = None if len(args) == 1 else args[1]
                yields = args[0] == "ytype"
                last = ret.meta[-1] if ret.meta and after_item else None
                if (
                    name is not None
                    and isinstance(last, DocstringReturns)
                    and last.return_name is None
                    and last.type_name is None
                    and (last.is_generator or not yields)
                ):
                    # A type for a named return value, right after a
                    # return with neither, names that return.
                    last.return_name = name
                    last.type_name = desc or None
                elif yields:
                    # A yield made of a type alone goes after every field.
                    ytypes.setdefault(name, []).append(
                        (desc, AFTER_ALL, Kind.YIELDS, None)
                    )
                else:
                    # A return made of a type alone goes after every field.
                    rtypes.setdefault(name, []).append(
                        (desc, AFTER_ALL, Kind.RETURNS, None)
                    )
            else:
                spec = table.get(args[0])
                kind = spec.kind if spec else Kind.TEXT
                try:
                    meta = _build_meta(args, desc, kind)
                except ItemError as ex:
                    problems.append(
                        Problem(lines.source_line(at), ex.code, str(ex))
                    )
                    loose_chunks.append(chunk)
                    after_item = False
                    continue
                ret.meta.append(apply(spec, meta))
                after_item = True
                continue
            after_item = False
        loose_chunks.append(meta_chunk[loose_start:])
        if attributes:
            ret.meta.extend(meta for _at, meta in attributes[next_attribute:])

        append_loose(ret, loose_chunks, blank_around=True)

        if untyped:
            # A type field with no type types nothing, but one naming what no
            # other field does still gives an item, so that its name is kept.
            named = {
                meta.arg_name
                for meta in ret.meta
                if isinstance(meta, DocstringParam)
            }
            for field, name, at in untyped:
                by_name = types if field == "type" else vartypes
                if name not in named and name not in by_name:
                    by_name[name] = [("", at)]
        assign_types(ret.meta, types, rtypes, ytypes, vartypes)
        return ParseResult(ret, problems)


_DEFAULT_PARSER = Parser()
_parsers: ParserCache[Parser] = ParserCache()


def parse(
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[SectionSpec]] = None,
) -> Docstring:
    """Parse the ReST-style docstring into its components.

    :param sections: the fields to recognise, instead of the default ones;
        each meta's ``key`` is the name its field is written with
    :returns: parsed docstring
    """
    return _parser(sections).parse(text)


def try_parse(
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[SectionSpec]] = None,
) -> ParseResult:
    """Parse what can be parsed of a ReST-style docstring, and tell what
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


def _fits_inline(type_name: T.Optional[str]) -> bool:
    """Tell whether a type can go inside a field name, as in ``:param int a:``.

    A type with a space or a colon in it would read back as more arguments
    or end the field name early, so it needs a ``:type:`` field of its own.
    """
    return not type_name or not _NOT_INLINE.search(type_name)


_PARAM_FIELD_OF_KIND = {Kind.ATTRIBUTE: "attribute"}
_OWN_PARAM_FIELDS = frozenset(PARAM_KEYWORDS | ATTRIBUTE_FIELD_KEYWORDS)


def _attribute_directive(meta: DocstringParam, indent: str) -> str:
    """Compose an attribute as a directive, with its type and value."""
    lines = [f".. attribute:: {meta.arg_name}"]
    type_name = meta.raw_type_name or meta.type_name
    if type_name:
        lines.append(f"{indent}:type: {type_name}")
    lines.append(f"{indent}:value: {meta.default}")
    if meta.description:
        lines.append("")
        lines.extend(
            indent + line if line else ""
            for line in meta.description.split("\n")
        )
    return "\n".join(lines)


def _type_field(indent: str, head: str, type_name: str) -> str:
    """Compose a type field, whose lines after the first are indented, as
    an unindented line ends it."""
    return f":{head}: " + f"\n{indent}".join(type_name.split("\n"))


# The kind of item each field ReST recognises by default gives.
_KIND_OF_FIELD = {name: spec.kind for name, spec in _DEFAULT_TABLE.items()}


def _own_key(meta: DocstringMeta, default: str) -> str:
    """Return the field name a return or raises was read from, such as
    ``raise``, if ReST reads it as the same kind, or else the default one."""
    key = meta.key
    if key and key != default and _KIND_OF_FIELD.get(key) is meta.kind:
        return key
    return default


def _param_key(meta: DocstringParam) -> str:
    """Return the field name that keeps a param's kind, such as ``key``."""
    return field_name(meta, _OWN_PARAM_FIELDS, _PARAM_FIELD_OF_KIND)


def _type_key(meta: DocstringParam) -> str:
    """Return the name of a param's type field: ``vartype`` for one
    written as ``:ivar:``, ``:var:`` or ``:cvar:``, as Sphinx reads it."""
    return "vartype" if meta.key in ATTRIBUTE_FIELD_KEYWORDS else "type"


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
        (first, *rest) = desc.split("\n")
        rest = [indent + line if line else "" for line in rest]
        if rendering_style == RenderingStyle.EXPANDED or (
            continuation_indented(desc)
        ):
            return "\n".join(["\n" + indent + first] + rest)
        return "\n".join([" " + first] + rest)

    parts = description_lines(docstring)

    for meta in docstring.meta:
        if isinstance(meta, DocstringParam):
            type_name = written_type(meta)
            if type_name is None and meta.type_name:
                type_name = (
                    f"{meta.type_name}?"
                    if meta.is_optional
                    else meta.type_name
                )
            if (
                meta.kind is Kind.ATTRIBUTE
                and meta.default is not None
                and param_spec(type_name, meta.description).default
                != meta.default
            ):
                # Only the directive gives an attribute a default of its
                # own, as its value.
                parts.append(_attribute_directive(meta, indent))
            elif meta.description is None and type_name:
                # A type field alone, which reads back as a param with no
                # description.
                parts.append(
                    _type_field(indent, f"type {meta.arg_name}", type_name)
                )
            elif rendering_style == RenderingStyle.EXPANDED or not (
                _fits_inline(type_name)
            ):
                text = f":{_param_key(meta)} {meta.arg_name}:"
                text += process_desc(meta.description)
                parts.append(text)
                if type_name:
                    parts.append(
                        _type_field(
                            indent,
                            f"{_type_key(meta)} {meta.arg_name}",
                            type_name,
                        )
                    )
            else:
                type_text = f" {type_name} " if type_name else " "
                text = f":{_param_key(meta)}{type_text}{meta.arg_name}:"
                text += process_desc(meta.description)
                parts.append(text)
        elif isinstance(meta, DocstringReturns):
            type_text = f" {meta.type_name}" if meta.type_name else ""
            key = _own_key(meta, "yields" if meta.is_generator else "returns")
            type_key = "ytype" if meta.is_generator else "rtype"
            if meta.return_name:
                type_key += f" {meta.return_name}"

            if meta.description is None and meta.type_name:
                # A type field alone, which reads back as a return with no
                # description.
                parts.append(_type_field(indent, type_key, meta.type_name))
            elif meta.return_name:
                # ReST names a return value only in its type field, which
                # names the return right before it.
                parts.append(f":{key}:" + process_desc(meta.description))
                parts.append(f":{type_key}:{type_text}")
            elif (
                rendering_style == RenderingStyle.EXPANDED
                or not _fits_inline(meta.type_name)
            ):
                parts.append(f":{key}:" + process_desc(meta.description))
                if meta.type_name:
                    parts.append(_type_field(indent, type_key, meta.type_name))
            else:
                text = f":{key}{type_text}:"
                text += process_desc(meta.description)
                parts.append(text)
        elif isinstance(meta, DocstringRaises):
            type_text = f" {meta.type_name} " if meta.type_name else ""
            key = _own_key(meta, "raises")
            text = f":{key}{type_text}:" + process_desc(meta.description)
            parts.append(text)
        elif isinstance(meta, DocstringDeprecated) and meta.version:
            # The version starts the description, on the same line.
            desc = meta.version
            if meta.description:
                desc += " " + meta.description
            parts.append(f":{meta.key or 'deprecated'}:" + process_desc(desc))
        else:
            text = f":{field_text(meta)}:" + process_desc(meta.description)
            parts.append(text)
    return "\n".join(parts)
