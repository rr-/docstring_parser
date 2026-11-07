"""Google-style docstring parsing."""

import re
import typing as T
from collections import namedtuple
from enum import IntEnum

from ._compose import (
    SectionTable,
    description_lines,
    examples_text,
    section_runs,
    start_on_new_line,
    written_type,
)
from ._directives import (
    DEPRECATED,
    cut_directives,
    deprecation,
    deprecation_lines,
    description_with_deprecation,
    directive_pattern,
    lead_directive,
)
from ._lines import Lines, dedent
from ._text import (
    EXCEPTION_TYPE,
    Example,
    append_loose,
    leading_deprecation,
    param_spec,
    renamed,
    split_description,
    split_examples,
    split_names,
    unescape,
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

# A return's type of two or three words before a colon, joined by ``of``,
# ``or`` or ``|``, as in ``list of str:`` or ``int or None:``. Words in a
# row with nothing between them are a sentence, as in ``The value:``.
# Brackets nest one deep, as in ``dict[str, list[int]]``, so that a
# match never backtracks far.
_IN_BRACKETS = r"[^\[\]:\n]*"
_TYPE_WORD = (
    r"[~!`]?[A-Za-z_][\w.`]*"
    rf"(?:\[{_IN_BRACKETS}(?:\[{_IN_BRACKETS}\]{_IN_BRACKETS})*\])?"
)
# A named return's head, as in ``x (int):``, whole on its line.
_NAMED_RETURN_HEAD = re.compile(
    r"[ \t]*[A-Za-z_]\w*[ \t]+\((?:[^()\n]|\([^()\n]*\))+\)[ \t]*:(?:\s|$)"
)
_SHORT_TYPE_HEAD = re.compile(
    rf"{_TYPE_WORD}(?:[ \t]+(?:of|or|\|)[ \t]+{_TYPE_WORD}){{1,2}}[ \t]*:"
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


# An exception type, or several, as written under ``Raises:`` with no
# colon: ``ValueError``, ``os.error`` or ``KeyError, TypeError``.
_BARE_TYPE = re.compile(
    rf"{EXCEPTION_TYPE}(?:[ \t]*(?:,|\||[ \t]or[ \t])[ \t]*{EXCEPTION_TYPE})*"
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
    # The rest of the sections napoleon reads.
    Section("Keyword Args", "keyword", SectionType.MULTIPLE),
    Section("Keyword Arguments", "keyword", SectionType.MULTIPLE),
    Section("Other Parameters", "other_param", SectionType.MULTIPLE),
    Section("Receives", "receives", SectionType.MULTIPLE),
    Section("Receive", "receives", SectionType.MULTIPLE),
    Section("Raise", "raises", SectionType.MULTIPLE),
    Section("Warns", "warns", SectionType.MULTIPLE),
    Section("Warn", "warns", SectionType.MULTIPLE),
    Section("Return", "returns", SectionType.SINGULAR_OR_MULTIPLE),
    Section("Yield", "yields", SectionType.SINGULAR_OR_MULTIPLE),
    Section("Notes", "notes", SectionType.SINGULAR),
    Section("Note", "notes", SectionType.SINGULAR),
    Section("Warnings", "warnings", SectionType.SINGULAR),
    Section("Warning", "warnings", SectionType.SINGULAR),
    Section("See Also", "see_also", SectionType.SINGULAR),
    Section("References", "references", SectionType.SINGULAR),
    Section("Todo", "todo", SectionType.SINGULAR),
    Section("Methods", "methods", SectionType.SINGULAR),
    Section("Attention", "attention", SectionType.SINGULAR),
    Section("Caution", "caution", SectionType.SINGULAR),
    Section("Danger", "danger", SectionType.SINGULAR),
    Section("Error", "error", SectionType.SINGULAR),
    Section("Hint", "hint", SectionType.SINGULAR),
    Section("Important", "important", SectionType.SINGULAR),
    Section("Tip", "tip", SectionType.SINGULAR),
    Section("Deprecated", "deprecation", SectionType.SINGULAR),
]

# A version on the first line of a Deprecated section, alone or before
# the text, as in ``1.2 Use bar instead.``
# The colon ending an item's head on its first line, with no brackets
# before it, as in ``x:``, or one pair of parentheses, as in ``x (int):``.
_PLAIN_HEAD = re.compile(r"[^:()\[\]{}\n]*(?:\([^:()\n]*\)[^:()\[\]{}\n]*)?:")


def _head_colon(text: str) -> int:
    """Find the colon that ends an item's head, or -1 if there is none.

    A colon inside brackets is part of the type, as in
    ``x (int, default: 3): text``, and brackets left open at the end of a
    line go on to the next, as in a wrapped type. Brackets that never close
    leave the first colon anywhere.
    """
    match = _PLAIN_HEAD.match(text)
    if match is not None:
        return match.end() - 1
    depth = 0
    for i, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth:
                depth -= 1
        elif not depth and char == ":":
            return i
        elif not depth and char == "\n":
            return -1
    return text.find(":") if depth else -1


# The names of a param's head: one with no spaces, or several, as in
# ``x, y``.
_ITEM_NAME = r"[^\s,:()\[\]{}]+(?:[ \t]*,[ \t]*[^\s,:()\[\]{}]+)*"
_NAMES = re.compile(_ITEM_NAME)
# The most common heads, which need no closer look: ``x:`` or
# ``x (int):``.
_PLAIN_PARAM_HEAD = re.compile(rf"{_ITEM_NAME}[ \t]*(?:\([^:()\n]*\)[ \t]*)?:")
_BRACKETED = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
# A param's head alone on its line, with no colon: ``x`` or ``x (int)``.
_BARE_ITEM = re.compile(rf"({_ITEM_NAME})(?:[ \t]*\(([^()]*)\))?")


def _has_param_head(item: str) -> bool:
    """Tell whether a param item starts with a head: names, with a type in
    parentheses or not, before a colon or alone on the line.

    A line that has none, such as wrapped prose, goes on with the item
    before it.
    """
    if _PLAIN_PARAM_HEAD.match(item) is not None:
        return True
    colon = _head_colon(item)
    if colon < 0:
        first = item.split("\n", 1)[0].strip()
        return _BARE_ITEM.fullmatch(first) is not None
    head = item[:colon]
    if "\n" in head:
        head = _join_wrapped(head)
    head = head.strip()
    if not head:
        return True
    typed = _split_typed_arg(head)
    if _NAMES.fullmatch(typed.name if typed else head) is not None:
        return True
    # A name and a type with no parentheses, as in ``x Optional[int]:``,
    # but no sentence.
    return len(_BRACKETED.sub("", head).split()) <= 2


_VERSION = re.compile(r"v?\d+\.[0-9a-z.]+(?=\s|\Z)", flags=re.I)


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


# The kind of a section given as a Section, by its key.
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
    {
        "key": Kind.KEYWORD,
        "keyword": Kind.KEYWORD,
        "attribute": Kind.ATTRIBUTE,
        "other_param": Kind.OTHER_PARAM,
        "receives": Kind.RECEIVES,
        "warns": Kind.WARNS,
        "deprecation": Kind.DEPRECATION,
    }
)


class _SpecSection(Section):
    """A section made from a SectionSpec, which it keeps as ``spec``."""

    spec: SectionSpec


def _section_kind(section: Section) -> Kind:
    if isinstance(section, _SpecSection):
        return section.spec.kind
    return _KIND_OF_KEY.get(section.key, Kind.TEXT)


_DEPRECATED = directive_pattern([DEPRECATED])
_UNINDENTED = re.compile(r"\n\S")
# The colon that ends a line, before any trailing whitespace.
_COLON_END = re.compile(r":[ \t\r\f\v]*$", flags=re.M)

_SECTION_TYPE = {
    Layout.ITEMS: SectionType.MULTIPLE,
    Layout.BLOCK: SectionType.SINGULAR,
    Layout.ITEM_OR_BLOCK: SectionType.SINGULAR_OR_MULTIPLE,
}
_LAYOUT = {v: k for k, v in _SECTION_TYPE.items()}


def _title(match: T.Match[str]) -> str:
    """Return the title a match of a title regex found."""
    return next(group for group in match.groups() if group is not None)


def _after_blank(text: str, match: T.Match[str]) -> bool:
    """Tell whether a title starts the text or follows a blank line.

    A title written in another case than declared starts a section only
    there, so that prose such as ``For`` and ``example:`` on the next line
    stays prose.
    """
    start = match.start()
    return start < 2 or text.startswith("\n\n", start - 2)


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
        version = _VERSION.match(desc or "")
        if version is None:
            return DocstringDeprecated(desc, version=None, key=section.key)
        return DocstringDeprecated(
            desc[version.end() :].lstrip(),
            version=version.group(),
            key=section.key,
        )
    if kind in PARAM_KINDS:
        raise ItemError("missing-name", "Expected paramenter name.")
    meta = DocstringMeta(desc, section.key)
    meta.title = section.title
    return meta


def _bare_param(section: Section, text: str) -> T.Optional[DocstringMeta]:
    """Build a param from an item whose head has no colon, as in ``x`` or
    ``x (int)``, with its description, if any, indented below it."""
    if _section_kind(section) not in PARAM_KINDS:
        return None
    first, _, rest = text.partition("\n")
    match = _BARE_ITEM.fullmatch(first.strip())
    if match is None:
        return None
    name, type_name = match.groups()
    head = f"{name} ({type_name})" if type_name is not None else name
    return _multi_meta(section, head, dedent(rest).strip("\n"))


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
        named = _NAMED_RETURN_HEAD.match(before + ":")
        typed = _split_typed_arg(before) if named else None
        return DocstringReturns(
            key=section.key,
            description=desc,
            type_name=typed.type_name if typed else before,
            is_generator=kind is Kind.YIELDS,
            return_name=typed.name if typed else None,
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
        # One group for the title, since a group around each alternative
        # keeps the regex engine from skipping it at its first letter.
        titles = "|".join(re.escape(t) for t in self.sections if t not in bare)
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
            "^" + titles + colon + "[ \t\r\f\v]*$", flags=re.M | re.I
        )
        # Whether every title ends its line with a colon.
        self._colon_ends = bool(colon)
        # Titles match in any case, as napoleon reads them, so each is
        # found by its lowercase too. The first declared of titles that
        # differ only in case wins.
        self._by_lower: T.Dict[str, str] = {}
        for title in self.sections:
            self._by_lower.setdefault(title.lower(), title)

    def _find_titles(self, text: str) -> T.Iterator[T.Match[str]]:
        """Find the titles in a text, as the title regex finds them."""
        if not self._colon_ends:
            return self._titles_re.finditer(text)
        # Only a line that ends in a colon can be a title, and finding those
        # first is much cheaper than trying every title at every line start,
        # which the regex engine cannot skip when matching in any case.
        return (
            match
            for match in (
                self._titles_re.match(text, text.rfind("\n", 0, c.start()) + 1)
                for c in _COLON_END.finditer(text)
            )
            if match is not None
        )

    def _declared(self, title: str) -> T.Optional[str]:
        """Return the declared title a title as written stands for."""
        if title in self.sections:
            return title
        return self._by_lower.get(title.lower())

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
            and not _SHORT_TYPE_HEAD.match(text)
            and not _NAMED_RETURN_HEAD.match(text)
        ) or section.type == SectionType.SINGULAR:
            return _single_meta(section, text)

        if _section_kind(section) in RAISES_KINDS:
            # A type alone on its line, with the description, if any,
            # indented below it.
            first, _, rest = text.partition("\n")
            if ":" not in first and _BARE_TYPE.fullmatch(first.strip()):
                return DocstringRaises(
                    description=dedent(rest).strip("\n") or None,
                    type_name=first.strip(),
                    kind=_section_kind(section),
                    key=section.key,
                )

        colon = _head_colon(text)
        if colon < 0:
            bare = _bare_param(section, text)
            if bare is not None:
                return bare
            # A head wrapped over several lines ends at the first colon.
            colon = text.find(":")
        if colon < 0:
            raise ItemError(
                "missing-colon", f"Expected a colon in {excerpt(text)!r}."
            )

        # Split spec and description
        before, desc = text[:colon], text[colon + 1 :]

        if before and "\n" in before:
            before = _join_wrapped(before)

        if desc:
            # The spaces after the colon set the description off.
            desc = desc.lstrip(" \t")
            if "\n" in desc:
                # Dedent every continuation line alike. cleandoc would strip
                # the first of them entirely and lose its indent relative
                # to the rest.
                first_line, rest = desc.split("\n", 1)
                # A first line of only whitespace is blank, as the others.
                if not first_line.strip():
                    first_line = ""
                desc = first_line + "\n" + dedent(rest)
            elif not desc.strip():
                desc = ""
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

    def _metas(self, text: str, title: str) -> T.List[DocstringMeta]:
        """Build an item's metas: one per name for a param whose head
        lists several, as in ``x, y (int): text``."""
        section = self.sections[title]
        meta = self._meta_of(text, title)
        metas: T.List[DocstringMeta] = [meta]
        if type(meta) is DocstringParam:
            if meta.arg_name and "\\" in meta.arg_name:
                meta.arg_name = unescape(meta.arg_name)
            names = split_names(meta.arg_name)
            if names is not None:
                metas = [renamed(meta, name) for name in names]
        if isinstance(section, _SpecSection):
            return [apply(section.spec, meta) for meta in metas]
        return metas

    def try_parse(self, text: T.Optional[str]) -> ParseResult:
        """Parse what can be parsed of a docstring, and tell what cannot."""
        ret = Docstring(style=DocstringStyle.GOOGLE)
        if not text:
            return ParseResult(ret, [])
        lines = Lines(text)

        # A title on the first line has no summary before it. Dedent it with
        # its entries, instead of stripping only the first line and leaving
        # the entries flush with the title.
        marked = "deprecated" in lines.text
        if self._titles_re.match(lines.raw.lstrip()):
            lines = lines.with_lead()
        elif marked:
            lines = lead_directive(lines, _DEPRECATED)
        # Deprecated directives in the free text, each with where it was.
        deprecations: T.List[T.Tuple[int, DocstringMeta]] = []
        if marked:
            lines, found = cut_directives(lines, _DEPRECATED)
            deprecations = [
                (
                    d.offset,
                    deprecation(
                        d.match.group("version"), d.body, "deprecation"
                    ),
                )
                for d in found
            ]
        text = lines.text

        # Split by sections determined by titles
        matches = [
            match
            for match in self._find_titles(text)
            if _title(match) in self.sections or _after_blank(text, match)
        ]
        if not matches:
            if deprecations and text.endswith("\n"):
                # A blank line set the description off from the directives
                # cut from after it, as it would from a section.
                text += "\n"
            split_description(ret, text)
            ret.meta.extend(meta for _at, meta in deprecations)
            return ParseResult(ret, [])
        split_description(ret, text[: matches[0].start()])
        ends = [m.start() for m in matches[1:]] + [len(text)]

        # A list rather than a dict, so that a section whose title appears
        # twice keeps both of its chunks, with where each starts.
        chunks: T.List[T.Tuple[str, str, int]] = []
        # Unindented text after a section, and items that cannot be read,
        # which go to the long description instead of being dropped.
        loose: T.List[str] = []
        problems: T.List[Problem] = []
        for match, end in zip(matches, ends):
            title = self._declared(_title(match))
            if title is None:
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

        # Add elements from each chunk, and each deprecation before the
        # chunk after it.
        next_deprecation = 0
        for title, chunk, offset in chunks:
            while (
                next_deprecation < len(deprecations)
                and deprecations[next_deprecation][0] < offset
            ):
                ret.meta.append(deprecations[next_deprecation][1])
                next_deprecation += 1
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
            kind = _section_kind(self.sections[title])
            if kind in RAISES_KINDS:
                heads = [_has_item_head(part) for part in parts]
                if not any(heads):
                    # A section of prose says what may go wrong, with no
                    # type.
                    ret.meta.append(self._prose_meta(cleandoc(chunk), title))
                    continue
            elif kind in PARAM_KINDS:
                heads = [_has_param_head(part) for part in parts]
            else:
                heads = []
            if heads and not all(heads[1:]):
                # A line at the items' indent with no head, such as wrapped
                # prose, goes on with the item before it.
                kept = [0] + [i for i in range(1, len(parts)) if heads[i]]
                c_ends = [c_matches[i].start() for i in kept[1:]]
                c_ends.append(len(chunk))
                c_matches = [c_matches[i] for i in kept]
                parts = [
                    chunk[c_match.end() : c_end].strip("\n")
                    for c_match, c_end in zip(c_matches, c_ends)
                ]
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

        ret.meta.extend(meta for _at, meta in deprecations[next_deprecation:])
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
            ret.meta.extend(self._metas(part, title))
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
_COMPOSE_SECTIONS = SectionTable(
    (
        ("Args:", {Kind.PARAM}),
        ("Keyword Args:", {Kind.KEYWORD}),
        ("Other Parameters:", {Kind.OTHER_PARAM}),
        ("Receives:", {Kind.RECEIVES}),
        ("Attributes:", {Kind.ATTRIBUTE}),
        ("Returns:", {Kind.RETURNS}),
        ("Yields:", {Kind.YIELDS}),
        ("Raises:", {Kind.RAISES}),
        ("Warns:", {Kind.WARNS}),
    )
)

# The title of each text section's key, such as ``See Also`` for
# ``see_also``, for a meta that has no title of its own.
_TEXT_TITLES = {
    s.key: s.title
    for s in reversed(DEFAULT_SECTIONS)
    if _section_kind(s) is Kind.TEXT
}


# The types of compose's nested functions, named once: on Python 3.8 an
# annotation is evaluated each time its function is defined, and a
# subscripted one costs a lookup in typing's cache.
_Item = T.Union[DocstringParam, DocstringReturns, DocstringRaises]
_Items = T.List[T.Any]


def _key_title(key: T.Optional[str]) -> str:
    """Make a section title of a key, as in ``Examples`` for ``examples``."""
    return (key or "").replace("_", "").title()


def _write_section(
    parts: T.List[str], indent: str, title: str, body: str
) -> None:
    """Write a section of text under its title."""
    parts.append(title + ":")
    if body:
        lines = [indent + line if line else "" for line in body.split("\n")]
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
        one: _Item,
        alone: bool = False,
    ):
        head = ""

        if isinstance(one, DocstringRaises):
            if (
                one.type_name
                and one.description is None
                and one.type_name == one.type_name.rstrip()
            ):
                # A type alone reads back with no description, as does one
                # with a colon after it, which keeps the spaces before it.
                parts.append(indent + one.type_name)
                return
            if (
                not one.type_name
                and one.description
                and alone
                and not any(
                    _has_item_head(line)
                    for line in one.description.split("\n")
                    if line and not line[0].isspace()
                )
            ):
                # The only raises, with no type, is a section of prose.
                parts.append(
                    "\n".join(
                        indent + line if line else ""
                        for line in one.description.split("\n")
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
        ):
            # A return with neither name nor type is just its description,
            # if any; a colon before it would be read back as text.
            if one.description:
                parts.append(
                    "\n".join(
                        indent + line for line in one.description.split("\n")
                    )
                )
            return

        type_name = one.type_name
        written = (
            written_type(one) if isinstance(one, DocstringParam) else None
        )
        if written is not None:
            type_name, optional = written, ""
        if type_name and head:
            head += f" ({type_name}{optional})"
            head += f" {one.extra}:" if one.extra else ":"
        elif type_name:
            head += f"{type_name}{optional}:"
        else:
            head += ":"
        head = indent + head

        # Lines after the first that are all indented further than it lose
        # that indent when read back, unless the first line goes below the
        # head with them, as does a first line indented further than them.
        if one.description and (
            rendering_style == RenderingStyle.EXPANDED
            or one.description[0].isspace()
            or continuation_indented(one.description)
        ):
            body = f"\n{indent}{indent}".join(
                [head] + one.description.split("\n")
            )
            parts.append(body)
        elif one.description:
            (first, *rest) = one.description.split("\n")
            body = f"\n{indent}{indent}".join([head + " " + first] + rest)
            parts.append(body)
        else:
            parts.append(head)

    def process_sect(name: str, args: _Items):
        if args:
            parts.append(name)
            for arg in args:
                process_one(arg, alone=len(args) == 1)
            parts.append("")

    # Most docstrings have no deprecation, so only look for one to write
    # after the short description when the first meta is one.
    metas = docstring.meta
    top = None
    if metas and type(metas[0]) is DocstringDeprecated:
        top = leading_deprecation(docstring)
    parts = (
        description_with_deprecation(docstring, top, indent)
        if top is not None
        else description_lines(docstring)
    )
    # Examples in a row share a section. One with no snippet is the text
    # after a section's last snippet, so it ends its section: written with
    # the next ones, it would read back as part of their text. An empty
    # one comes from an empty section, and is a section of its own. Each
    # return is a section of its own, which reads back as one item.
    group: T.List[DocstringExample] = []
    for title, items in section_runs(
        docstring, _COMPOSE_SECTIONS, alone=RETURNS_KINDS
    ):
        meta = items[0]
        if title is None and isinstance(meta, DocstringExample):
            if not meta.snippet and not meta.description and group:
                _write_section(
                    parts,
                    indent,
                    _key_title(group[0].key),
                    examples_text(group),
                )
                group = []
            group.append(meta)
            if meta.snippet:
                continue
        if group:
            _write_section(
                parts, indent, _key_title(group[0].key), examples_text(group)
            )
            group = []
        if title is not None:
            process_sect(title, items)
        elif meta is top:
            continue
        elif isinstance(meta, DocstringDeprecated) and meta.key in (
            None,
            "deprecation",
        ):
            # A directive at the start of a line, which ends the section
            # before it. Blank lines around it read back as one after the
            # descriptions, unless one is before it.
            blank = not parts or not parts[-1]
            parts.append(deprecation_lines(meta, indent))
            if blank:
                parts.append("")
        elif not isinstance(meta, DocstringExample):
            title = (
                meta.title
                or _TEXT_TITLES.get(meta.key or "")
                or _key_title(meta.key)
            )
            _write_section(parts, indent, title, meta.description or "")
    if group:
        _write_section(
            parts, indent, _key_title(group[0].key), examples_text(group)
        )

    while parts and not parts[-1]:
        parts.pop()

    text = "\n".join(parts)
    # A summary such as "Note:" reads back as a title unless indented
    # further than an unindented line after it, as it was to be read as a
    # summary. Every default title ends in a colon, so only a summary
    # whose first line does may read as one. Most have no colon at all,
    # which is the cheaper test, so it comes first.
    short = docstring.short_description
    if (
        short
        and ":" in short
        and short.partition("\n")[0].rstrip().endswith(":")
        and _parser(None)._titles_re.match(text)
        and _UNINDENTED.search(text) is not None
    ):
        text = indent + text
    # Every section starts with an unindented title, and one on the first
    # line is dedented with its items already.
    long_description = docstring.long_description
    if docstring.meta or not (
        long_description and long_description[0].isspace()
    ):
        return text
    return start_on_new_line(text)
