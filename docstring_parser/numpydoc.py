"""Numpydoc-style docstring parsing.

:see: https://numpydoc.readthedocs.io/en/latest/format.html
"""

import itertools
import re
import typing as T

from ._compose import (
    SectionTable,
    examples_text,
    section_runs,
    start_on_new_line,
    written_type,
)
from ._directives import (
    deprecation_lines,
    description_with_deprecation,
    leading_deprecation,
)
from ._lines import Lines, dedent
from ._text import (
    DEFAULT_IN_DESCRIPTION,
    DEFAULT_REGEX,
    EXCEPTION_TYPE,
    OPTIONAL_REGEX,
    append_loose,
    clean_str,
    param_spec,
    renamed,
    split_description,
    split_examples,
    split_names,
    unescape,
)
from .common import (
    BaseParser,
    Docstring,
    DocstringDeprecated,
    DocstringExample,
    DocstringMeta,
    DocstringMethod,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
    Kind,
    ParseResult,
    Problem,
    RenderingStyle,
    cleandoc,
)
from .sections import ParserCache, SectionSpec, apply


def _pairwise(iterable: T.Iterable, end=None) -> T.Iterable:
    left, right = itertools.tee(iterable)
    next(right, None)
    return itertools.zip_longest(left, right, fillvalue=end)


_KV_REGEX = re.compile(r"^[^\s].*$", flags=re.M)
# A line of dashes that may underline the title on the line before it.
_UNDERLINE = re.compile(r"^-{3,}[ \t]*$", flags=re.M)
_NOT_WORD = re.compile(r"[^0-9a-z]+")


def _headings(
    text: str, known: T.List[T.Match[str]]
) -> T.List[T.Tuple[int, int, str]]:
    """Find the underlined headings no section declares.

    A heading is an unindented line underlined by as many dashes as it has
    characters, as a section's title is.

    :param known: the declared sections' title matches, in order
    :returns: each heading's start and end in the text, and its title
    """
    found = []
    k = 0
    for underline in _UNDERLINE.finditer(text):
        end = underline.start() - 1
        if end <= 0:
            continue
        start = text.rfind("\n", 0, end) + 1
        title = text[start:end].rstrip()
        if (
            not title
            or title[0].isspace()
            or len(title) != len(underline.group().rstrip())
            or not title.strip("-")
        ):
            continue
        while k < len(known) and known[k].end() <= start:
            k += 1
        if k < len(known) and known[k].start() <= start:
            continue  # A declared section's title.
        found.append((start, underline.end(), title))
    return found


def _merge_heads(
    known: T.List[T.Tuple[int, int, T.Any]],
    others: T.List[T.Tuple[int, int, str]],
) -> T.List[T.Tuple[int, int, T.Any]]:
    """Put the headings among the declared sections, in order.

    A heading in an examples section is left in it, since doctest output
    there may hold a table whose header row looks underlined.
    """
    merged: T.List[T.Tuple[int, int, T.Any]] = []
    k = 0
    for head in others:
        while k < len(known) and known[k][0] < head[0]:
            merged.append(known[k])
            k += 1
        if not (merged and isinstance(merged[-1][2], ExamplesSection)):
            merged.append(head)
    merged.extend(known[k:])
    return merged


def _heading_key(title: str) -> str:
    """Make a key of a heading's title, such as ``custom_title``."""
    return _NOT_WORD.sub("_", title.lower()).strip("_")


PARAM_KEY_REGEX = re.compile(r"^(?P<name>.*?)(?:\s*:\s*(?P<type>.*?))?$")
# Kept for code that imports them. Parsing reads types and defaults with
# the rule all styles share, in ``_text.param_spec``.
PARAM_OPTIONAL_REGEX = OPTIONAL_REGEX
PARAM_DEFAULT_REGEX = DEFAULT_REGEX
PARAM_DEFAULT_REGEX_IN_DESC = DEFAULT_IN_DESCRIPTION

RETURN_KEY_REGEX = re.compile(r"^(?:(?P<name>.*?)\s*:\s*)?(?P<type>.*?)$")
# A raises item's head that starts its description after a type and a
# colon, as in ``ValueError : if bad.``, which napoleon reads too.
_RAISES_HEAD = re.compile(
    rf"(?P<type>{EXCEPTION_TYPE})[ \t]*:(?:[ \t]+(?P<desc>.*)|[ \t]*)"
)


# The kinds of param that section keys other than ``param`` give.
_PARAM_KINDS = {
    "key": Kind.KEYWORD,
    "keyword": Kind.KEYWORD,
    "attribute": Kind.ATTRIBUTE,
    "other_param": Kind.OTHER_PARAM,
    "receives": Kind.RECEIVES,
}


class Section:
    """Numpydoc section parser.

    :param title: section title. For most sections, this is a heading like
                  "Parameters" which appears on its own line, underlined by
                  dashes ('-') or equals signs ('=') on the following line.
    :param key: meta key string. In the parsed ``DocstringMeta`` instance this
                is the ``key`` of the parsed ``DocstringMeta``.
    """

    # The spec the section was made from, if any, which decides its kind.
    _spec: T.Optional[SectionSpec] = None

    def __init__(self, title: str, key: str) -> None:
        self.title = title
        self.key = key

    @property
    def _title_tail(self) -> T.Optional[str]:
        """The pattern of what follows the title in this section's header,
        or None if the header does not start with the title."""
        if self._spec is not None and self._spec.bare:
            return r"[ \t]*$"
        # Any underline of dashes or equals signs makes the header, so
        # that one the parser's underline rule rejects is still read as its
        # section, with a problem.
        return r"\s*?\n(?:-+|=+)\s*$"

    @property
    def _title_pattern(self) -> str:
        """Regular expression pattern matching this section's header.

        This pattern will match this instance's ``title`` attribute in
        an anonymous group.
        """
        return rf"^({re.escape(self.title)})" + (self._title_tail or "")

    def _parse(self, text: str) -> T.Iterable[DocstringMeta]:
        """Parse ``DocstringMeta`` objects from the body of this section.

        :param text: section body text. Should be cleaned with
                     ``inspect.cleandoc`` before parsing.
        """
        meta = DocstringMeta(clean_str(text), self.key)
        meta.title = self.title
        yield meta


class _KVSection(Section):
    """Base parser for numpydoc sections with key-value syntax.

    E.g. sections that look like this:
        key
            value
        key2 : type
            values can also span...
            ... multiple lines
    """

    def _parse_item(self, key: str, value: str) -> DocstringMeta:
        raise NotImplementedError

    def _parse(self, text: str) -> T.Iterable[DocstringMeta]:
        for match, next_match in _pairwise(_KV_REGEX.finditer(text)):
            start = match.end()
            end = next_match.start() if next_match is not None else None
            value = text[start:end]
            yield self._parse_item(key=match.group(), value=cleandoc(value))


class _SphinxSection(Section):
    """Base parser for numpydoc sections with sphinx-style syntax.

    E.g. sections that look like this:
        .. title:: something
            possibly over multiple lines
    """

    @property
    def _title_tail(self) -> T.Optional[str]:
        return None

    @property
    def _title_pattern(self) -> str:
        return rf"^\.\.\s*({re.escape(self.title)})\s*::"


class ParamSection(_KVSection):
    """Parser for numpydoc parameter sections.

    E.g. any section that looks like this:
        arg_name
            arg_description
        arg_2 : type, optional
            descriptions can also span...
            ... multiple lines
    """

    def _parse(self, text: str) -> T.Iterable[DocstringMeta]:
        # One param per name of a head that lists several, as in
        # ``x, y : int``.
        for meta in super()._parse(text):
            param = T.cast(DocstringParam, meta)
            if param.arg_name and "\\" in param.arg_name:
                param.arg_name = unescape(param.arg_name)
            names = split_names(param.arg_name)
            if names is None:
                yield param
            else:
                yield from (renamed(param, name) for name in names)

    def _parse_item(self, key: str, value: str) -> DocstringParam:
        # The key is a single line, which the pattern always matches.
        match = PARAM_KEY_REGEX.match(key)
        assert match is not None
        arg_name: str = match.group("name")
        raw_type_name = match.group("type")
        spec = param_spec(raw_type_name, value)
        return DocstringParam(
            key=self.key,
            description=clean_str(value),
            arg_name=arg_name,
            type_name=spec.type_name,
            is_optional=spec.is_optional,
            default=spec.default,
            raw_type_name=raw_type_name,
            kind=self._spec.kind
            if self._spec
            else _PARAM_KINDS.get(self.key, Kind.PARAM),
        )


class MethodsSection(_KVSection):
    """Parser for numpydoc methods sections.

    E.g. any section that looks like this:
        run(x, y=1)
            A description of what run does
    """

    def _parse(self, text: str) -> T.Iterable[DocstringMeta]:
        if _KV_REGEX.search(text) is None:
            # A section that lists no method stays its title.
            yield from Section._parse(self, text)
            return
        yield from super()._parse(text)

    def _parse_item(self, key: str, value: str) -> DocstringMethod:
        # The whole line is the method, as napoleon reads it, so that a
        # signature's annotations are not split off as a type.
        return DocstringMethod(key.strip(), clean_str(value), self.key)


class RaisesSection(_KVSection):
    """Parser for numpydoc raises sections.

    E.g. any section that looks like this:
        ValueError
            A description of what might raise ValueError
    """

    def _parse_item(self, key: str, value: str) -> DocstringRaises:
        head = _RAISES_HEAD.fullmatch(key)
        if head is not None:
            key = head.group("type")
            first = (head.group("desc") or "").strip()
            if first:
                value = f"{first}\n{value}" if value else first
        return DocstringRaises(
            key=self.key,
            description=clean_str(value),
            type_name=key if len(key) > 0 else None,
            kind=self._spec.kind
            if self._spec
            else Kind.WARNS
            if self.key == "warns"
            else Kind.RAISES,
        )


class ReturnsSection(_KVSection):
    """Parser for numpydoc returns sections.

    E.g. any section that looks like this:
        return_name : type
            A description of this returned value
        another_type
            Return names are optional, types are required
    """

    is_generator = False

    def _parse_item(self, key: str, value: str) -> DocstringReturns:
        match = RETURN_KEY_REGEX.match(key)
        if match is not None:
            return_name = match.group("name")
            type_name = match.group("type")
        else:
            return_name = None
            type_name = None

        return DocstringReturns(
            key=self.key,
            description=clean_str(value),
            type_name=type_name,
            is_generator=self.is_generator,
            return_name=return_name,
        )


class YieldsSection(ReturnsSection):
    """Parser for numpydoc generator "yields" sections."""

    is_generator = True


def _split_directive(text: str) -> T.Tuple[str, str]:
    """Split a directive from the unindented text that follows its body.

    The body is the directive's first line and the indented lines after it.
    It ends at a blank line followed by an unindented one.
    """
    lines = text.split("\n")
    for i in range(2, len(lines)):
        line = lines[i]
        if line and not line[0].isspace() and not lines[i - 1].strip():
            return "\n".join(lines[:i]), "\n".join(lines[i:])
    return text, ""


class DeprecationSection(_SphinxSection):
    """Parser for numpydoc "deprecation warning" sections."""

    def _parse(self, text: str) -> T.Iterable[DocstringDeprecated]:
        version, _, desc = text.partition("\n")

        yield DocstringDeprecated(
            key=self.key,
            description=clean_str(cleandoc(desc)),
            version=clean_str(version),
        )


class ExamplesSection(Section):
    """Parser for numpydoc examples sections.

    E.g. any section that looks like this:
        >>> import numpy.matlib
        >>> np.matlib.empty((2, 2))    # filled with random data
        matrix([[  6.76425276e-320,   9.79033856e-307], # random
                [  7.39337286e-309,   3.22135945e-309]])
        >>> np.matlib.empty((2, 2), dtype=int)
        matrix([[ 6600475,        0], # random
                [ 6586976, 22740995]])
    """

    def _parse(self, text: str) -> T.Iterable[DocstringMeta]:
        """Parse ``DocstringExample`` objects from the body of this section.

        :param text: section body text. Should be cleaned with
                     ``inspect.cleandoc`` before parsing.
        """
        for example in split_examples(dedent(text).strip()):
            yield DocstringExample(
                key=self.key,
                snippet=example.snippet,
                description=example.description,
            )


DEFAULT_SECTIONS = [
    ParamSection("Parameters", "param"),
    ParamSection("Params", "param"),
    ParamSection("Arguments", "param"),
    ParamSection("Args", "param"),
    ParamSection("Other Parameters", "other_param"),
    ParamSection("Other Params", "other_param"),
    ParamSection("Other Arguments", "other_param"),
    ParamSection("Other Args", "other_param"),
    ParamSection("Keyword Arguments", "keyword"),
    ParamSection("Keyword Args", "keyword"),
    ParamSection("Receives", "receives"),
    ParamSection("Receive", "receives"),
    RaisesSection("Raises", "raises"),
    RaisesSection("Raise", "raises"),
    RaisesSection("Warns", "warns"),
    RaisesSection("Warn", "warns"),
    ParamSection("Attributes", "attribute"),
    ParamSection("Attribute", "attribute"),
    ReturnsSection("Returns", "returns"),
    ReturnsSection("Return", "returns"),
    YieldsSection("Yields", "yields"),
    YieldsSection("Yield", "yields"),
    ExamplesSection("Examples", "examples"),
    ExamplesSection("Example", "examples"),
    Section("Warnings", "warnings"),
    Section("Warning", "warnings"),
    Section("See Also", "see_also"),
    Section("Related", "see_also"),
    Section("Notes", "notes"),
    Section("Note", "notes"),
    Section("References", "references"),
    Section("Reference", "references"),
    Section("Todo", "todo"),
    MethodsSection("Methods", "methods"),
    Section("Attention", "attention"),
    Section("Caution", "caution"),
    Section("Danger", "danger"),
    Section("Error", "error"),
    Section("Hint", "hint"),
    Section("Important", "important"),
    Section("Tip", "tip"),
    DeprecationSection("deprecated", "deprecation"),
]


def _section_kind(section: Section) -> Kind:
    if section._spec is not None:
        return section._spec.kind
    if isinstance(section, ParamSection):
        return _PARAM_KINDS.get(section.key, Kind.PARAM)
    if isinstance(section, RaisesSection):
        return Kind.WARNS if section.key == "warns" else Kind.RAISES
    if isinstance(section, ReturnsSection):
        return Kind.YIELDS if section.is_generator else Kind.RETURNS
    if isinstance(section, ExamplesSection):
        return Kind.EXAMPLES
    if isinstance(section, DeprecationSection):
        return Kind.DEPRECATION
    if isinstance(section, MethodsSection):
        return Kind.METHOD
    return Kind.TEXT


# The section class that reads each kind of item.
_SECTION_CLASS = {
    Kind.PARAM: ParamSection,
    Kind.KEYWORD: ParamSection,
    Kind.OTHER_PARAM: ParamSection,
    Kind.RECEIVES: ParamSection,
    Kind.ATTRIBUTE: ParamSection,
    Kind.RETURNS: ReturnsSection,
    Kind.YIELDS: YieldsSection,
    Kind.RAISES: RaisesSection,
    Kind.WARNS: RaisesSection,
    Kind.EXAMPLES: ExamplesSection,
    Kind.DEPRECATION: DeprecationSection,
    Kind.METHOD: MethodsSection,
    Kind.TEXT: Section,
}


def _from_spec(section: T.Union[Section, SectionSpec]) -> T.List[Section]:
    """Return a section as it is, or a spec as one section per title."""
    if not isinstance(section, SectionSpec):
        return [section]
    out = []
    for title in section.titles:
        one = _SECTION_CLASS[section.kind](title, section.key)
        one._spec = section
        out.append(one)
    return out


def default_sections() -> T.List[SectionSpec]:
    """Return the sections Numpydoc recognises when given none."""
    return [
        SectionSpec(s.title, _section_kind(s), key=s.key)
        for s in DEFAULT_SECTIONS
    ]


class Parser(BaseParser):
    """Parser for numpydoc-style docstrings."""

    name = "numpydoc"

    def __init__(
        self,
        sections: T.Optional[T.Sequence[T.Union[Section, SectionSpec]]] = None,
        min_underline: int = 3,
        exact_underline: bool = False,
    ):
        """Setup sections.

        :param sections: Recognized sections or None to defaults.
        :param min_underline: the fewest dashes or equals signs a section
            title's underline may have
        :param exact_underline: require a section title's underline to be
            as long as the title
        """
        self.min_underline = min_underline
        self.exact_underline = exact_underline
        sections = sections or DEFAULT_SECTIONS
        self.sections: T.Dict[str, Section] = {}
        for section in sections:
            for one in _from_spec(section):
                self.sections[one.title] = one
        self._setup()

    def _setup(self):
        # Headers that start with their title share one alternation with
        # no group in it, which the regex engine skips at the first letter
        # that differs; their title is the first line of the match. The
        # others have a group around their title.
        plain = []
        others = []
        for section in self.sections.values():
            tail = section._title_tail
            if tail is None:
                others.append(section._title_pattern)
            else:
                plain.append(re.escape(section.title) + tail)
        if plain:
            others.insert(0, "^(?:" + "|".join(plain) + ")")
        self._titles_re = re.compile("|".join(others), flags=re.M | re.I)
        # Titles match in any case, as napoleon reads them, so each is
        # found by its lowercase too. The first declared of titles that
        # differ only in case wins.
        self._by_lower: T.Dict[str, Section] = {}
        for title, section in self.sections.items():
            self._by_lower.setdefault(title.lower(), section)

    def _declared(self, match: T.Match[str]) -> Section:
        """Return the section of a header the title regex found."""
        title = next((g for g in match.groups() if g is not None), None)
        if title is None:
            title = match.group().split("\n", 1)[0].rstrip()
        section = self.sections.get(title)
        return section or self._by_lower[title.lower()]

    def add_section(self, section: T.Union[Section, SectionSpec]):
        """Add or replace a section.

        :param section: The new section.
        """

        for one in _from_spec(section):
            self.sections[one.title] = one
        self._setup()

    def try_parse(self, text: T.Optional[str]) -> ParseResult:
        """Parse a numpy-style docstring, which always parses."""
        ret = Docstring(style=DocstringStyle.NUMPYDOC)
        if not text:
            return ParseResult(ret, [])

        # Clean according to PEP-0257
        lines = Lines(text)
        text = lines.text

        # Find first title and split on its position
        match = self._titles_re.search(text)
        if match:
            desc_chunk = text[: match.start()]
            meta_chunk = text[match.start() :]
        else:
            desc_chunk = text
            meta_chunk = ""

        split_description(ret, desc_chunk)

        # Each section's title: a declared section's factory, or the title
        # of an underlined heading no section declares, which ends the
        # section before it rather than being read as its items.
        known = list(self._titles_re.finditer(meta_chunk))
        heads: T.List[T.Tuple[int, int, T.Union[Section, str]]] = [
            (
                match.start(),
                match.end(),
                self._declared(match),
            )
            for match in known
        ]
        problems = [
            Problem(
                lines.source_line(len(desc_chunk) + match.start()),
                "bad-underline",
                message,
            )
            for match in known
            for message in [self._underline_problem(match.group())]
            if message is not None
        ]
        if "---" in meta_chunk:
            others = _headings(meta_chunk, known)
            if others:
                heads = _merge_heads(heads, others)

        # Text after a directive's body, which goes to the long description.
        loose_chunks = []
        for (_start, start, factory), after in _pairwise(heads):
            # section chunk starts after the header,
            # ends at the start of the next header
            end = after[0] if after is not None else None
            chunk = meta_chunk[start:end]
            if isinstance(factory, str):
                meta = DocstringMeta(clean_str(chunk), _heading_key(factory))
                meta.title = factory
                ret.meta.append(meta)
                continue
            if isinstance(factory, _SphinxSection):
                chunk, loose = _split_directive(chunk)
                loose_chunks.append(loose)
            if isinstance(factory, _KVSection):
                # Indented text before the first item is no item.
                first = _KV_REGEX.search(chunk)
                split = first.start() if first else len(chunk)
                loose_chunks.append(chunk[:split])
                chunk = chunk[split:]
            spec = factory._spec
            ret.meta.extend(
                apply(spec, meta) for meta in factory._parse(chunk)
            )

        append_loose(ret, loose_chunks, blank_around=False)
        return ParseResult(ret, problems)

    def _underline_problem(self, header: str) -> T.Optional[str]:
        """Tell how a section header's underline breaks the parser's rule,
        or return None if it keeps it or the header has none."""
        title, _, rest = header.partition("\n")
        underline = rest.strip()
        if not underline or underline[0] not in "-=":
            return None
        title = title.rstrip()
        if self.exact_underline and len(underline) != len(title):
            return (
                f"Expected the underline of {title!r} to be as long as the"
                f" title, {len(title)} characters, not {len(underline)}."
            )
        if len(underline) < self.min_underline:
            return (
                f"Expected the underline of {title!r} to be at least"
                f" {self.min_underline} characters, not {len(underline)}."
            )
        return None


# The name the parser had before every style had a ``Parser``.
NumpydocParser = Parser


_default_parser: T.Optional[Parser] = None
_default_parser_sections: T.Tuple[T.List[Section], T.List[str]] = ([], [])


_parsers: ParserCache[Parser] = ParserCache()


def _parser(
    sections: T.Optional[T.Sequence[T.Union[Section, SectionSpec]]],
) -> Parser:
    global _default_parser, _default_parser_sections  # noqa: PLW0603
    if sections:
        key = [*sections, *(getattr(s, "title", None) for s in sections)]
        return _parsers.get(key, Parser, sections)
    # Building a parser compiles its title regex, so reuse one until
    # DEFAULT_SECTIONS changes: a section added, removed or replaced, or a
    # title changed in place.
    current = (list(DEFAULT_SECTIONS), [s.title for s in DEFAULT_SECTIONS])
    if _default_parser is None or current != _default_parser_sections:
        _default_parser = Parser()
        _default_parser_sections = current
    return _default_parser


def parse(
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[T.Union[Section, SectionSpec]]] = None,
) -> Docstring:
    """Parse the numpy-style docstring into its components.

    :param sections: the sections to recognise, instead of
        ``DEFAULT_SECTIONS``
    :returns: parsed docstring
    """
    return _parser(sections).parse(text)


def try_parse(
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[T.Union[Section, SectionSpec]]] = None,
) -> ParseResult:
    """Parse what can be parsed of a numpy-style docstring, and tell what
    cannot, instead of raising.

    :param sections: as for :func:`parse`
    :returns: the docstring, and a problem for each part that cannot be
        read, whose text goes to the long description
    """
    return _parser(sections).try_parse(text)


# The sections compose writes items in, in order, and the kinds each takes.
_COMPOSE_SECTIONS = SectionTable(
    (
        ("Parameters", {Kind.PARAM}),
        ("Keyword Arguments", {Kind.KEYWORD}),
        ("Attributes", {Kind.ATTRIBUTE}),
        ("Methods", {Kind.METHOD}),
        ("Returns", {Kind.RETURNS}),
        ("Yields", {Kind.YIELDS}),
        ("Receives", {Kind.RECEIVES}),
        ("Other Parameters", {Kind.OTHER_PARAM}),
        ("Raises", {Kind.RAISES}),
        ("Warns", {Kind.WARNS}),
        ("Examples", {Kind.EXAMPLES}),
    )
)


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
        one: T.Union[
            DocstringParam, DocstringReturns, DocstringRaises, DocstringMethod
        ],
    ):
        if isinstance(one, DocstringMethod):
            lines = [one.name or ""]
            if one.description:
                lines += [
                    indent + line if line else ""
                    for line in one.description.split("\n")
                ]
            parts.append("\n".join(lines))
            return
        written = None
        if isinstance(one, DocstringParam):
            head = one.arg_name
            written = written_type(one)
        elif isinstance(one, DocstringReturns):
            head = one.return_name
        else:
            head = None

        if isinstance(one, DocstringParam) and written is not None:
            # With no name, a space before the colon would indent the line.
            head = (
                f"{one.arg_name} : {written}"
                if one.arg_name
                else f": {written}"
            )
        elif one.type_name and head:
            head += f" : {one.type_name}"
        elif one.type_name:
            # A colon on the first line of a return's type would read back
            # as one after its name, unless a colon before it says there
            # is none.
            if (
                isinstance(one, DocstringReturns)
                and ":" in one.type_name.split("\n", 1)[0]
            ):
                head = f": {one.type_name}"
            else:
                head = one.type_name
        elif (
            isinstance(one, DocstringReturns)
            and head
            and one.type_name is not None
        ):
            # A return's name alone would read back as its type; the colon
            # after it says the type is empty.
            head += " :"
        elif not head:
            head = ""

        # If this is a parameter, check if it's optional.
        # If it is and there's a not-None default, include that in the type
        # declaration, otherwise just mark it as optional.
        if isinstance(one, DocstringParam) and written is None:
            # With no type, the mark is the type, as in "x : optional", so
            # that it is not read back as part of the name.
            mark = ", " if one.type_name else " : "
            if one.default not in [None, "None"]:
                head += f"{mark}default={one.default}"
            elif one.is_optional or one.default == "None":
                head += f"{mark}optional"

        if one.description:
            body = f"\n{indent}".join([head] + one.description.split("\n"))
            parts.append(body)
        else:
            parts.append(head)

    def blank_line() -> None:
        # One blank line between blocks, however many ask for one. Right
        # after the descriptions, their own blank lines are kept instead.
        if parts and parts[-1] != "" and len(parts) != described:
            parts.append("")

    def process_sect(name: str, args: T.List[T.Any]):
        if args:
            blank_line()
            parts.append(name)
            parts.append("-" * len(parts[-1]))
            for arg in args:
                process_one(arg)

    long = docstring.long_description
    top = leading_deprecation(docstring)
    parts = description_with_deprecation(docstring, top, indent, blank=True)
    # Where the descriptions end, unless a directive came after them.
    described = len(parts) if top is None or long else -1

    for title, items in section_runs(docstring, _COMPOSE_SECTIONS):
        if title == "Examples":
            blank_line()
            parts.append("Examples")
            parts.append("--------")
            parts.append(examples_text(items))
            continue
        if title is not None:
            process_sect(title, items)
            continue
        (meta,) = items
        if meta is top:
            continue
        blank_line()
        if isinstance(meta, DocstringDeprecated):
            parts.append(deprecation_lines(meta, indent))
            continue

        # Use the section's own title, e.g. "See Also" for see_also.
        key = meta.key or ""
        title = meta.title or next(
            (s.title for s in DEFAULT_SECTIONS if s.key == key),
            key.replace("_", "").title(),
        )
        parts.append(title)
        parts.append("-" * len(title))

        if meta.description:
            parts.append(meta.description)

    # A blank line at the very end separates nothing.
    while parts and parts[-1] == "":
        parts.pop()
    text = "\n".join(parts)
    # Every section starts with an unindented title.
    long_description = docstring.long_description
    if docstring.meta or not (
        long_description and long_description[0].isspace()
    ):
        return text
    return start_on_new_line(text)
