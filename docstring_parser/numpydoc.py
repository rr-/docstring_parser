"""Numpydoc-style docstring parsing.

:see: https://numpydoc.readthedocs.io/en/latest/format.html
"""

import itertools
import re
import typing as T
from textwrap import dedent

from ._compose import SectionTable, kind_of, sections
from ._lines import Lines
from ._text import (
    DEFAULT_REGEX,
    OPTIONAL_REGEX,
    append_loose,
    clean_str,
    split_description,
    type_spec,
)
from .common import (
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
    RenderingStyle,
    cleandoc,
)
from .sections import ParserCache, SectionSpec, apply


def _pairwise(iterable: T.Iterable, end=None) -> T.Iterable:
    left, right = itertools.tee(iterable)
    next(right, None)
    return itertools.zip_longest(left, right, fillvalue=end)


_KV_REGEX = re.compile(r"^[^\s].*$", flags=re.M)
PARAM_KEY_REGEX = re.compile(r"^(?P<name>.*?)(?:\s*:\s*(?P<type>.*?))?$")
PARAM_OPTIONAL_REGEX = OPTIONAL_REGEX
PARAM_DEFAULT_REGEX = DEFAULT_REGEX

# If the default value isn't specified in the type declaration,
# it might be in the description. There isn't any formal grammar for this
# in numpydoc, but we can make some educated guesses. A bare "default"
# followed by a word is left out, since prose such as "the default engine"
# or "by default only" reads the same.
PARAM_DEFAULT_REGEX_IN_DESC = re.compile(
    r"(?<!\S)[Dd]efault(?:s to |\s*(?:is|[=:])\s*)(?P<value>(?:['\"]).*?(?:['\"])|[\w\-\.]*\w)"  # noqa: E501
)

RETURN_KEY_REGEX = re.compile(r"^(?:(?P<name>.*?)\s*:\s*)?(?P<type>.*?)$")


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
                  en-dashes ('-') on the following line.
    :param key: meta key string. In the parsed ``DocstringMeta`` instance this
                is the ``key`` of the parsed ``DocstringMeta``.
    """

    # The spec the section was made from, if any, which decides its kind.
    _spec: T.Optional[SectionSpec] = None

    def __init__(self, title: str, key: str) -> None:
        self.title = title
        self.key = key

    @property
    def _title_pattern(self) -> str:
        """Regular expression pattern matching this section's header.

        This pattern will match this instance's ``title`` attribute in
        an anonymous group.
        """
        if self._spec is not None and self._spec.bare:
            return rf"^({re.escape(self.title)})[ \t]*$"
        dashes = "-" * len(self.title)
        return rf"^({re.escape(self.title)})\s*?\n{dashes}\s*$"

    def _parse(self, text: str) -> T.Iterable[DocstringMeta]:
        """Parse ``DocstringMeta`` objects from the body of this section.

        :param text: section body text. Should be cleaned with
                     ``inspect.cleandoc`` before parsing.
        """
        yield DocstringMeta(clean_str(text), self.key)


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

    def _parse_item(self, key: str, value: str) -> DocstringParam:
        # The key is a single line, which the pattern always matches.
        match = PARAM_KEY_REGEX.match(key)
        assert match is not None
        arg_name: str = match.group("name")
        raw_type_name = match.group("type")
        spec = type_spec(raw_type_name)
        default = spec.default

        # If the default wasn't specifified in the type declaration,
        # try and see if we can find it in the description.
        if len(value) > 0 and default is None:
            default_match = PARAM_DEFAULT_REGEX_IN_DESC.search(value)
            if default_match is not None:
                default = default_match.group("value")

        return DocstringParam(
            key=self.key,
            description=clean_str(value),
            arg_name=arg_name,
            type_name=spec.type_name,
            is_optional=spec.is_optional,
            default=default,
            raw_type_name=raw_type_name,
            kind=self._spec.kind
            if self._spec
            else _PARAM_KINDS.get(self.key, Kind.PARAM),
        )


class RaisesSection(_KVSection):
    """Parser for numpydoc raises sections.

    E.g. any section that looks like this:
        ValueError
            A description of what might raise ValueError
    """

    def _parse_item(self, key: str, value: str) -> DocstringRaises:
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
        lines = dedent(text).strip().splitlines()
        # Walk an index instead of popping from the front, which is
        # quadratic in the number of lines.
        i = 0
        while i < len(lines):
            snippet_lines = []
            description_lines = []
            while i < len(lines) and lines[i].startswith(">>>"):
                snippet_lines.append(lines[i])
                i += 1
            while i < len(lines) and not lines[i].startswith(">>>"):
                description_lines.append(lines[i])
                i += 1
            yield DocstringExample(
                key=self.key,
                snippet="\n".join(snippet_lines) if snippet_lines else None,
                description="\n".join(description_lines),
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
    ):
        """Setup sections.

        :param sections: Recognized sections or None to defaults.
        """
        sections = sections or DEFAULT_SECTIONS
        self.sections: T.Dict[str, Section] = {}
        for section in sections:
            for one in _from_spec(section):
                self.sections[one.title] = one
        self._setup()

    def _setup(self):
        self._titles_re = re.compile(
            r"|".join(s._title_pattern for s in self.sections.values()),
            flags=re.M,
        )

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
        text = Lines(text).text

        # Find first title and split on its position
        match = self._titles_re.search(text)
        if match:
            desc_chunk = text[: match.start()]
            meta_chunk = text[match.start() :]
        else:
            desc_chunk = text
            meta_chunk = ""

        split_description(ret, desc_chunk)

        # Text after a directive's body, which goes to the long description.
        loose_chunks = []
        for match, nextmatch in _pairwise(
            self._titles_re.finditer(meta_chunk)
        ):
            title = next(g for g in match.groups() if g is not None)
            factory = self.sections[title]

            # section chunk starts after the header,
            # ends at the start of the next header
            start = match.end()
            end = nextmatch.start() if nextmatch is not None else None
            chunk = meta_chunk[start:end]
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
        return ParseResult(ret, [])


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
# Keyword params, which Numpydoc has no section for, go with the others
# rather than being dropped.
_COMPOSE_SECTIONS = SectionTable(
    (
        ("Parameters", {Kind.PARAM, Kind.KEYWORD}),
        ("Attributes", {Kind.ATTRIBUTE}),
        ("Returns", {Kind.RETURNS}),
        ("Yields", {Kind.YIELDS}),
        ("Receives", {Kind.RECEIVES}),
        ("Other Parameters", {Kind.OTHER_PARAM}),
        ("Raises", {Kind.RAISES}),
        ("Warns", {Kind.WARNS}),
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
        one: T.Union[DocstringParam, DocstringReturns, DocstringRaises],
    ):
        if isinstance(one, DocstringParam):
            head = one.arg_name
        elif isinstance(one, DocstringReturns):
            head = one.return_name
        else:
            head = None

        if one.type_name and head:
            head += f" : {one.type_name}"
        elif one.type_name:
            head = one.type_name
        elif not head:
            head = ""

        # If this is a parameter, check if it's optional.
        # If it is and there's a not-None default, include that in the type
        # declaration, otherwise just mark it as optional.
        if isinstance(one, DocstringParam):
            if one.default not in [None, "None"]:
                head += f", default={one.default}"
            elif one.is_optional or one.default == "None":
                head += ", optional"

        if one.description:
            body = f"\n{indent}".join([head] + one.description.splitlines())
            parts.append(body)
        else:
            parts.append(head)

    def blank_line() -> None:
        # One blank line between blocks, however many ask for one.
        if parts and parts[-1] != "":
            parts.append("")

    def process_sect(name: str, args: T.List[T.Any]):
        if args:
            blank_line()
            parts.append(name)
            parts.append("-" * len(parts[-1]))
            for arg in args:
                process_one(arg)

    parts: T.List[str] = []
    if docstring.short_description:
        parts.append(docstring.short_description)
    if docstring.blank_after_short_description:
        blank_line()

    if docstring.deprecation:
        first = ".. deprecated::"
        if docstring.deprecation.version:
            first += f" {docstring.deprecation.version}"
        if docstring.deprecation.description:
            rest = docstring.deprecation.description.splitlines()
        else:
            rest = []
        parts.append(
            "\n".join(
                [first] + [indent + line if line else "" for line in rest]
            )
        )
        if docstring.long_description:
            blank_line()

    if docstring.long_description:
        parts.append(docstring.long_description)
        if docstring.blank_after_long_description:
            blank_line()

    found, rest = sections(docstring, _COMPOSE_SECTIONS)
    for title, items in found:
        process_sect(title, items)

    if len(docstring.examples) > 0:
        blank_line()
        parts.append("Examples")
        parts.append("--------")
        for example in docstring.examples:
            if example.snippet:
                parts.append(example.snippet)
            if example.description:
                parts.append(example.description)

    for meta in rest:
        if kind_of(meta) in {Kind.DEPRECATION, Kind.EXAMPLES}:
            continue  # Already handled

        # Use the section's own title, e.g. "See Also" for see_also.
        key = meta.key or ""
        title = next(
            (s.title for s in DEFAULT_SECTIONS if s.key == key),
            key.replace("_", "").title(),
        )
        blank_line()
        parts.append(title)
        parts.append("-" * len(title))

        if meta.description:
            parts.append(meta.description)

    # A blank line at the very end separates nothing.
    while parts and parts[-1] == "":
        parts.pop()
    return "\n".join(parts)
