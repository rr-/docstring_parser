"""Google-style docstring parsing."""

import re
import textwrap
import typing as T
from collections import namedtuple
from enum import IntEnum

from ._compose import (
    SectionTable,
    description_lines,
    examples_text,
    sections,
)
from ._lines import Lines
from ._text import (
    Example,
    append_loose,
    param_spec,
    split_description,
    split_examples,
)
from .common import (
    EXAMPLES_KEYWORDS,
    PARAM_KEYWORDS,
    PARAM_KINDS,
    RAISES_KEYWORDS,
    RAISES_KINDS,
    RETURNS_KEYWORDS,
    RETURNS_KINDS,
    YIELDS_KEYWORDS,
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
    cleandoc,
    continuation_indented,
    excerpt,
)
from .sections import Layout, ParserCache, SectionSpec, apply


class SectionType(IntEnum):
    """Types of sections."""

    SINGULAR = 0
    """For sections like examples."""

    MULTIPLE = 1
    """For sections like params."""

    SINGULAR_OR_MULTIPLE = 2
    """For sections like returns or yields."""


class Section(namedtuple("SectionBase", "title key type")):
    """A docstring section."""


# Kept for code that imports it. Parsing finds defaults with the rule all
# styles share, in ``_text.param_spec``.
GOOGLE_ARG_DESC_REGEX = re.compile(r".*\. Defaults to (.+)\.")
MULTIPLE_PATTERN = re.compile(
    r"(\s*[^:\s]+:)|"  # simple word:
    r"([^:]*\]:.*)|"  # name[type]:
    r"(\s*\w+(?:\s*\|\s*\w+)+:)"  # word | word | ... :  (PEP 604 union)
)

# One member of a union type: a dotted name with an optional subscript,
# such as ``None``, ``np.ndarray`` or ``dict[str, int]``.
_UNION_MEMBER = re.compile(r"[A-Za-z_][\w.]*(?:\[[^:]*\])?")


def _is_union_head(text: str) -> bool:
    """Tell whether an item starts with a union type and a colon.

    The members are split at each ``|`` outside brackets, as in
    ``dict[str, int | None] | None:``, in one pass over the head.
    """
    colon = text.find(":")
    if colon < 0:
        return False
    head = text[:colon]
    if "|" not in head or "\n" in head.strip():
        return False
    members = []
    depth = start = 0
    for i, char in enumerate(head):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth < 0:
                return False
        elif char == "|" and not depth:
            members.append(head[start:i])
            start = i + 1
    members.append(head[start:])
    return not depth and all(
        _UNION_MEMBER.fullmatch(member.strip()) for member in members
    )


# One exception type: a dotted name, maybe marked as Sphinx does it
# (``~pkg.Error``) or quoted (```Error```), with an optional subscript.
_TYPE = r"`?[~!]?[A-Za-z_][\w.]*(?:\[[^\]\n]*\])?`?"
# An exception type, or several, as written under ``Raises:`` with no
# colon: ``ValueError``, ``os.error`` or ``KeyError, TypeError``.
_BARE_TYPE = re.compile(
    _TYPE + r"(?:[ \t]*(?:,|\||[ \t]or[ \t])[ \t]*" + _TYPE + ")*"
)


def _has_item_head(item: str) -> bool:
    """Tell whether a raises item starts with a head.

    That is a type alone on its first line, or something before a colon on
    it that is no sentence: a type, one word with no spaces, as in
    ``~pkg.Error:``, or nothing at all.
    """
    head, colon, _ = item.split("\n", 1)[0].partition(":")
    head = head.strip()
    if colon and (not head or not any(c.isspace() for c in head)):
        return True
    return _BARE_TYPE.fullmatch(head) is not None


DEFAULT_SECTIONS = [
    Section("Arguments", "param", SectionType.MULTIPLE),
    Section("Args", "param", SectionType.MULTIPLE),
    Section("Parameters", "param", SectionType.MULTIPLE),
    Section("Params", "param", SectionType.MULTIPLE),
    Section("Raises", "raises", SectionType.MULTIPLE),
    Section("Exceptions", "raises", SectionType.MULTIPLE),
    Section("Except", "raises", SectionType.MULTIPLE),
    Section("Attributes", "attribute", SectionType.MULTIPLE),
    Section("Example", "examples", SectionType.SINGULAR),
    Section("Examples", "examples", SectionType.SINGULAR),
    Section("Returns", "returns", SectionType.SINGULAR_OR_MULTIPLE),
    Section("Yields", "yields", SectionType.SINGULAR_OR_MULTIPLE),
]


def _join_wrapped(text: str) -> str:
    """Join the lines of a wrapped item head into one line.

    Lines are joined with a space, as wrapped prose and types are written,
    except right inside brackets: ``List[`` and ``int]`` give ``List[int]``.
    """
    joined = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if joined and not joined.endswith(("(", "[", "{")):
            if not line.startswith((")", "]", "}")):
                joined += " "
        joined += line
    return joined


class TypedArg(T.NamedTuple):
    """A param's head split into its name, its type and what follows."""

    name: str
    type_name: T.Optional[str]
    extra: str


def _split_typed_arg(text: str) -> T.Optional[TypedArg]:
    """Split a parameter name and the type in parentheses after it.

    The type ends at the parenthesis matching the opening one, found in a
    single pass, so anything after it is ignored.
    """
    text = text.lstrip()
    opening = text.find("(", 1)
    if opening < 0:
        return None
    name = text[:opening].rstrip()
    if not name:
        return None
    depth = 0
    for closing in range(opening, len(text)):
        if text[closing] in "([{":
            depth += 1
        elif text[closing] in ")]}":
            depth -= 1
            if depth == 0:
                break
    else:
        return None
    type_name = text[opening + 1 : closing].strip()
    if not type_name:
        return None
    return TypedArg(
        name=name, type_name=type_name, extra=text[closing + 1 :].strip()
    )


# The kind of a section given as a Section, by its key. Google has no
# deprecation items, so a section keyed as one is plain text.
_KIND_OF_KEY = {
    key: kind
    for keys, kind in (
        (PARAM_KEYWORDS, Kind.PARAM),
        (RETURNS_KEYWORDS, Kind.RETURNS),
        (YIELDS_KEYWORDS, Kind.YIELDS),
        (RAISES_KEYWORDS, Kind.RAISES),
        (EXAMPLES_KEYWORDS, Kind.EXAMPLES),
    )
    for key in keys
}
_KIND_OF_KEY.update(
    {"key": Kind.KEYWORD, "keyword": Kind.KEYWORD, "attribute": Kind.ATTRIBUTE}
)


class _SpecSection(Section):
    """A section made from a SectionSpec, which it keeps as ``spec``."""

    spec: SectionSpec


def _section_kind(section: Section) -> Kind:
    if isinstance(section, _SpecSection):
        return section.spec.kind
    return _KIND_OF_KEY.get(section.key, Kind.TEXT)


_UNINDENTED = re.compile(r"\n\S")

_SECTION_TYPE = {
    Layout.ITEMS: SectionType.MULTIPLE,
    Layout.BLOCK: SectionType.SINGULAR,
    Layout.ITEM_OR_BLOCK: SectionType.SINGULAR_OR_MULTIPLE,
}
_LAYOUT = {v: k for k, v in _SECTION_TYPE.items()}


def _title(match: T.Match[str]) -> str:
    """Return the title a match of a title regex found."""
    return next(group for group in match.groups() if group is not None)


def default_sections() -> T.List[SectionSpec]:
    """Return the sections Google recognises when given none."""
    return [
        SectionSpec(
            s.title, _section_kind(s), key=s.key, layout=_LAYOUT[s.type]
        )
        for s in DEFAULT_SECTIONS
    ]


def _single_meta(section: Section, desc: str) -> DocstringMeta:
    kind = _section_kind(section)
    if kind in RETURNS_KINDS:
        return DocstringReturns(
            key=section.key,
            description=desc,
            type_name=None,
            is_generator=kind is Kind.YIELDS,
        )
    if kind in RAISES_KINDS:
        return DocstringRaises(
            description=desc, type_name=None, kind=kind, key=section.key
        )
    if kind is Kind.EXAMPLES:
        return DocstringExample(
            snippet=None, description=desc, key=section.key
        )
    if kind is Kind.DEPRECATION:
        return DocstringDeprecated(desc, version=None, key=section.key)
    if kind in PARAM_KINDS:
        raise ItemError("missing-name", "Expected paramenter name.")
    return DocstringMeta(desc, section.key)


def _multi_meta(section: Section, before: str, desc: str) -> DocstringMeta:
    kind = _section_kind(section)
    if kind in PARAM_KINDS:
        head = _split_typed_arg(before) or TypedArg(
            name=before, type_name=None, extra=""
        )
        spec = param_spec(head.type_name, desc)
        param = DocstringParam(
            key=section.key,
            description=desc,
            arg_name=head.name,
            type_name=spec.type_name,
            is_optional=spec.is_optional,
            default=spec.default,
            kind=kind,
            raw_type_name=head.type_name,
        )
        param.extra = head.extra or None
        return param
    if kind in RETURNS_KINDS:
        return DocstringReturns(
            key=section.key,
            description=desc,
            type_name=before,
            is_generator=kind is Kind.YIELDS,
        )
    if kind in RAISES_KINDS:
        return DocstringRaises(
            description=desc,
            type_name=before or None,
            kind=kind,
            key=section.key,
        )
    return DocstringMeta(desc, section.key, before)


class Parser(BaseParser):
    """Parser for Google-style docstrings."""

    name = "google"

    def __init__(
        self,
        sections: T.Optional[T.Sequence[T.Union[Section, SectionSpec]]] = None,
        title_colon=True,
    ):
        """Setup sections.

        :param sections: Recognized sections or None to defaults.
        :param title_colon: require colon after section title.
        """
        if not sections:
            sections = DEFAULT_SECTIONS
        self.sections: T.Dict[str, Section] = {}
        for section in sections:
            self._add(section)
        self.title_colon = title_colon
        self._setup()

    def _setup(self):
        colon = ":" if self.title_colon else ""
        bare = [
            t
            for t, s in self.sections.items()
            if colon and isinstance(s, _SpecSection) and s.spec.bare
        ]
        titles = "|".join(
            f"({re.escape(t)})" for t in self.sections if t not in bare
        )
        if bare:
            titles = (
                f"(?:({titles}){colon}|("
                + "|".join(re.escape(t) for t in bare)
                + "))"
            )
            colon = ""
        else:
            titles = f"({titles})"
        self._titles_re = re.compile(
            "^" + titles + colon + "[ \t\r\f\v]*$", flags=re.M
        )

    def _meta_of(self, text: str, title: str) -> DocstringMeta:
        """Build docstring element.

        :param text: docstring element text
        :param title: title of section containing element
        :return:
        """

        section = self.sections[title]

        if (
            section.type == SectionType.SINGULAR_OR_MULTIPLE
            and not MULTIPLE_PATTERN.match(text)
            and not _is_union_head(text)
        ) or section.type == SectionType.SINGULAR:
            return _single_meta(section, text)

        if _section_kind(section) in RAISES_KINDS:
            # A type alone on its line, with the description, if any,
            # indented below it.
            first, _, rest = text.partition("\n")
            if ":" not in first and _BARE_TYPE.fullmatch(first.strip()):
                return DocstringRaises(
                    description=textwrap.dedent(rest).strip("\n") or None,
                    type_name=first.strip(),
                    kind=_section_kind(section),
                    key=section.key,
                )

        if ":" not in text:
            raise ItemError(
                "missing-colon", f"Expected a colon in {excerpt(text)!r}."
            )

        # Split spec and description
        before, desc = text.split(":", 1)

        if before and "\n" in before:
            before = _join_wrapped(before)

        if desc:
            desc = desc[1:] if desc[0] == " " else desc
            if "\n" in desc:
                # Dedent every continuation line alike. cleandoc would strip
                # the first of them entirely and lose its indent relative
                # to the rest.
                first_line, rest = desc.split("\n", 1)
                desc = first_line + "\n" + textwrap.dedent(rest)
            desc = desc.strip("\n")

        return _multi_meta(section, before, desc)

    def add_section(self, section: T.Union[Section, SectionSpec]):
        """Add or replace a section.

        :param section: The new section.
        """
        self._add(section)
        self._setup()

    def _add(self, section: T.Union[Section, SectionSpec]) -> None:
        if not isinstance(section, SectionSpec):
            self.sections[section.title] = section
            return
        for title in section.titles:
            one = _SpecSection(
                title, section.key, _SECTION_TYPE[section.layout]
            )
            one.spec = section
            self.sections[title] = one

    def _prose_meta(self, text: str, title: str) -> DocstringMeta:
        """Build the one raises of a section that holds only prose."""
        section = self.sections[title]
        meta = DocstringRaises(
            description=text,
            type_name=None,
            kind=_section_kind(section),
            key=section.key,
        )
        if isinstance(section, _SpecSection):
            return apply(section.spec, meta)
        return meta

    def _meta(self, text: str, title: str) -> DocstringMeta:
        section = self.sections[title]
        meta = self._meta_of(text, title)
        if isinstance(section, _SpecSection):
            return apply(section.spec, meta)
        return meta

    def try_parse(self, text: T.Optional[str]) -> ParseResult:
        """Parse what can be parsed of a docstring, and tell what cannot."""
        ret = Docstring(style=DocstringStyle.GOOGLE)
        if not text:
            return ParseResult(ret, [])
        lines = Lines(text)

        # A title on the first line has no summary before it. Dedent it with
        # its entries, instead of stripping only the first line and leaving
        # the entries flush with the title.
        if self._titles_re.match(lines.raw.lstrip()):
            lines = lines.with_lead()
        text = lines.text

        # Split by sections determined by titles
        matches = list(self._titles_re.finditer(text))
        split_description(ret, text[: matches[0].start()] if matches else text)
        if not matches:
            return ParseResult(ret, [])
        ends = [m.start() for m in matches[1:]] + [len(text)]

        # A list rather than a dict, so that a section whose title appears
        # twice keeps both of its chunks, with where each starts.
        chunks: T.List[T.Tuple[str, str, int]] = []
        # Unindented text after a section, and items that cannot be read,
        # which go to the long description instead of being dropped.
        loose: T.List[str] = []
        problems: T.List[Problem] = []
        for match, end in zip(matches, ends):
            title = _title(match)
            if title not in self.sections:
                continue

            # An unindented line ends the section, as in issue #29.
            meta_details = text[match.end() : end]
            unknown_meta = _UNINDENTED.search(meta_details)
            if unknown_meta is not None:
                loose.append(meta_details[unknown_meta.start() :])
                meta_details = meta_details[: unknown_meta.start()]

            chunk = meta_details.strip("\n")
            offset = (
                match.end()
                + len(meta_details)
                - len(meta_details.lstrip("\n"))
            )
            chunks.append((title, chunk, offset))

        # Add elements from each chunk
        for title, chunk, offset in chunks:
            # Check for singular elements
            if self.sections[title].type in [
                SectionType.SINGULAR,
                SectionType.SINGULAR_OR_MULTIPLE,
            ]:
                part = cleandoc(chunk)
                section = self.sections[title]
                if _section_kind(section) is Kind.EXAMPLES:
                    # One meta per example, as doctest reads them. A
                    # section with nothing in it still gives one, empty.
                    examples = split_examples(part) or [
                        Example(description=part, snippet=None)
                    ]
                    for example in examples:
                        meta = DocstringExample(
                            snippet=example.snippet,
                            description=example.description,
                            key=section.key,
                        )
                        if isinstance(section, _SpecSection):
                            meta = apply(section.spec, meta)
                        ret.meta.append(meta)
                    continue
                self._add_meta(
                    ret, part, title, problems, loose, lines, offset
                )
                continue

            # Split based on lines which have exactly that indent
            indent = chunk[: len(chunk) - len(chunk.lstrip())]
            _re = "^" + indent + r"(?=\S)"
            c_matches = list(re.finditer(_re, chunk, flags=re.M))
            if not c_matches:
                problems.append(
                    Problem(
                        lines.source_line(offset),
                        "no-items",
                        f'No specification for "{title}": "{excerpt(chunk)}"',
                    )
                )
                loose.append(chunk)
                continue
            c_ends = [m.start() for m in c_matches[1:]] + [len(chunk)]
            parts = [
                chunk[c_match.end() : c_end].strip("\n")
                for c_match, c_end in zip(c_matches, c_ends)
            ]
            if _section_kind(self.sections[title]) in RAISES_KINDS and not any(
                _has_item_head(part) for part in parts
            ):
                # A section of prose says what may go wrong, with no type.
                ret.meta.append(self._prose_meta(cleandoc(chunk), title))
                continue
            for c_match, part in zip(c_matches, parts):
                self._add_meta(
                    ret,
                    part,
                    title,
                    problems,
                    loose,
                    lines,
                    offset + c_match.start(),
                )

        append_loose(ret, loose, blank_around=True)
        return ParseResult(ret, problems)

    def _add_meta(
        self,
        ret: Docstring,
        part: str,
        title: str,
        problems: T.List[Problem],
        loose: T.List[str],
        lines: Lines,
        offset: int,
    ) -> None:
        """Add an item's meta, or its text and a problem if it cannot be
        read."""
        try:
            ret.meta.append(self._meta(part, title))
        except ItemError as ex:
            problems.append(
                Problem(lines.source_line(offset), ex.code, str(ex))
            )
            loose.append(part)


# The name the parser had before every style had a ``Parser``.
GoogleParser = Parser


_parsers: ParserCache[Parser] = ParserCache()


def parse(
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[T.Union[Section, SectionSpec]]] = None,
) -> Docstring:
    """Parse the Google-style docstring into its components.

    :param sections: the sections to recognise, instead of
        ``DEFAULT_SECTIONS``
    :returns: parsed docstring
    """
    return _parser(sections).parse(text)


def try_parse(
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[T.Union[Section, SectionSpec]]] = None,
) -> ParseResult:
    """Parse what can be parsed of a Google-style docstring, and tell what
    cannot, instead of raising.

    :param sections: as for :func:`parse`
    :returns: the docstring, and a problem for each part that cannot be
        read, whose text goes to the long description
    """
    return _parser(sections).try_parse(text)


def _parser(
    sections: T.Optional[T.Sequence[T.Union[Section, SectionSpec]]],
) -> Parser:
    # Building a parser compiles its title regex, so reuse one for the same
    # sections, including DEFAULT_SECTIONS until it changes.
    key = list(sections or DEFAULT_SECTIONS)
    return _parsers.get(key, Parser, key)


# The sections compose writes items in, in order, and the kinds each takes.
# Google has no sections of its own for keyword, other or received params,
# so they go with the others rather than being dropped.
_COMPOSE_SECTIONS = SectionTable(
    (
        ("Args:", {Kind.PARAM, Kind.KEYWORD, Kind.OTHER_PARAM, Kind.RECEIVES}),
        ("Attributes:", {Kind.ATTRIBUTE}),
        ("Returns:", {Kind.RETURNS}),
        ("Yields:", {Kind.YIELDS}),
        ("Raises:", {Kind.RAISES, Kind.WARNS}),
    )
)


def _write_section(
    parts: T.List[str], indent: str, key: T.Optional[str], body: str
) -> None:
    """Write a section of text, titled by its key."""
    parts.append((key or "").replace("_", "").title() + ":")
    if body:
        lines = [indent + line if line else "" for line in body.splitlines()]
        parts.append("\n".join(lines))
    parts.append("")


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

    def process_one(
        one: T.Union[DocstringParam, DocstringReturns, DocstringRaises],
        alone: bool = False,
    ):
        head = ""

        if isinstance(one, DocstringRaises):
            if one.type_name and not one.description:
                # A type alone reads back with no description, where a
                # colon after it would give an empty one.
                parts.append(indent + one.type_name)
                return
            if (
                not one.type_name
                and one.description
                and alone
                and not any(
                    _has_item_head(line)
                    for line in one.description.splitlines()
                    if line and not line[0].isspace()
                )
            ):
                # The only raises, with no type, is a section of prose.
                parts.append(
                    "\n".join(
                        indent + line if line else ""
                        for line in one.description.splitlines()
                    )
                )
                return

        if isinstance(one, DocstringParam):
            head += one.arg_name or ""
        elif isinstance(one, DocstringReturns):
            head += one.return_name or ""

        if isinstance(one, DocstringParam) and one.is_optional:
            optional = (
                "?"
                if rendering_style == RenderingStyle.COMPACT
                else ", optional"
            )
        else:
            optional = ""

        if (
            isinstance(one, DocstringReturns)
            and not head
            and not one.type_name
            and one.description
        ):
            # A return with neither name nor type is just its description;
            # a colon before it would be read back as text.
            parts.append(
                "\n".join(
                    indent + line for line in one.description.splitlines()
                )
            )
            return

        if one.type_name and head:
            head += f" ({one.type_name}{optional})"
            head += f" {one.extra}:" if one.extra else ":"
        elif one.type_name:
            head += f"{one.type_name}{optional}:"
        else:
            head += ":"
        head = indent + head

        # Lines after the first that are all indented further than it lose
        # that indent when read back, unless the first line goes below the
        # head with them.
        if one.description and (
            rendering_style == RenderingStyle.EXPANDED
            or continuation_indented(one.description)
        ):
            body = f"\n{indent}{indent}".join(
                [head] + one.description.splitlines()
            )
            parts.append(body)
        elif one.description:
            (first, *rest) = one.description.splitlines()
            body = f"\n{indent}{indent}".join([head + " " + first] + rest)
            parts.append(body)
        else:
            parts.append(head)

    def process_sect(name: str, args: T.List[T.Any]):
        if args:
            parts.append(name)
            for arg in args:
                process_one(arg, alone=len(args) == 1)
            parts.append("")

    parts = description_lines(docstring)
    found, rest = sections(docstring, _COMPOSE_SECTIONS)
    for title, items in found:
        process_sect(title, items)

    # Examples in a row share a section. One with no snippet is the text
    # after a section's last snippet, so it ends its section: written with
    # the next ones, it would read back as part of their text. An empty
    # one comes from an empty section, and is a section of its own.
    group: T.List[DocstringExample] = []
    for meta in rest:
        if isinstance(meta, DocstringExample):
            if not meta.snippet and not meta.description and group:
                _write_section(
                    parts, indent, group[0].key, examples_text(group)
                )
                group = []
            group.append(meta)
            if meta.snippet:
                continue
        if group:
            _write_section(parts, indent, group[0].key, examples_text(group))
            group = []
        if not isinstance(meta, DocstringExample):
            _write_section(parts, indent, meta.key, meta.description or "")
    if group:
        _write_section(parts, indent, group[0].key, examples_text(group))

    while parts and not parts[-1]:
        parts.pop()

    return "\n".join(parts)
