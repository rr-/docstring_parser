"""Parsers for the small pieces of text inside docstring items.

These understand nesting of brackets and quotes, so that a comma or a colon
inside ``Dict[str, int]`` or ``'a:b'`` is not taken as a separator.
"""

import functools
import re
from collections.abc import Iterator
from typing import NamedTuple

_OPENING = {"(": ")", "[": "]", "{": "}"}
_CLOSING = set(_OPENING.values())
_QUOTES = {"'", '"', "`"}


_NESTING = "()[]{}'\"`"
_NESTING_RE = re.compile(r"[()\[\]{}'\"`]")
_QUOTES_RE = re.compile(r"['\"`]")
_SEPARATOR_RE = re.compile(r"(?<!:):(?=\s|\Z)")


@functools.cache
def _scanner(targets: str) -> re.Pattern[str]:
    """Return a regex matching nesting characters and the given targets."""
    return re.compile(f"[{re.escape(_NESTING + targets)}]")


def _top_level_positions(text: str, targets: str) -> Iterator[int]:
    """Yield the positions of ``targets`` outside brackets and quotes.

    Only nesting characters and targets are visited, found with a regex. A
    closing bracket without a matching opening one is also yielded, so
    callers can stop at it. If a quote is never closed, quotes are not
    special.
    """
    quotes = _quotes_balanced(text)
    stack: list[str] = []
    quote = None
    for match in _scanner(targets).finditer(text):
        i = match.start()
        char = text[i]
        if quote:
            if char == quote:
                quote = None
        elif char in _QUOTES:
            if quotes:
                quote = char
            elif not stack and char in targets:
                yield i
        elif char in _OPENING:
            stack.append(_OPENING[char])
        elif char in _CLOSING:
            if stack and stack[-1] == char:
                stack.pop()
            elif not stack:
                yield i
        elif not stack:
            yield i


def _quotes_balanced(text: str) -> bool:
    quote = None
    for match in _QUOTES_RE.finditer(text):
        char = match.group()
        if quote:
            if char == quote:
                quote = None
        else:
            quote = char
    return quote is None


def is_balanced(text: str) -> bool:
    """Tell whether all brackets and quotes in the text are closed."""
    stack: list[str] = []
    quote = None
    for match in _NESTING_RE.finditer(text):
        char = match.group()
        if quote:
            if char == quote:
                quote = None
        elif char in _QUOTES:
            quote = char
        elif char in _OPENING:
            stack.append(_OPENING[char])
        elif not stack or stack.pop() != char:
            return False
    return not stack and quote is None


def find_separator(text: str) -> int:
    """Return the position of the colon separating a name from a type.

    It is the first top-level colon followed by whitespace or the end of
    the text, so that the colons of reST roles (``:class:`Foo```) are not
    taken as separators, nor is ``::``.
    """
    if not _NESTING_RE.search(text):
        match = _SEPARATOR_RE.search(text)
        return match.start() if match else -1
    for i in _top_level_positions(text, ":"):
        if (
            text[i] == ":"
            and (i + 1 == len(text) or text[i + 1].isspace())
            and text[i - 1 : i] != ":"
        ):
            return i
    return -1


def split_top_level(text: str, sep: str = ",") -> list[str]:
    """Split the text on a separator found at the top level."""
    if not _NESTING_RE.search(text):
        return text.split(sep)
    parts, start = [], 0
    for i in _top_level_positions(text, sep):
        if text[i] == sep:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def matching_bracket(text: str, start: int) -> int:
    """Return the position of the bracket closing the one at ``start``."""
    closing = _OPENING[text[start]]
    for i in _top_level_positions(text[start + 1 :], ""):
        if text[start + 1 + i] == closing:
            return start + 1 + i
        if text[start + 1 + i] in _CLOSING:
            return -1
    return -1


def normalize_space(text: str) -> str:
    """Collapse runs of whitespace, including newlines, to single spaces."""
    return " ".join(text.split())


def strip_literal(text: str) -> str:
    """Remove reST inline-literal backticks around a value."""
    for ticks in ("``", "`"):
        if (
            len(text) > 2 * len(ticks)
            and text.startswith(ticks)
            and text.endswith(ticks)
        ):
            return text[len(ticks) : -len(ticks)]
    return text


class TypeSpec(NamedTuple):
    """The parts of a type specification such as ``int, optional``."""

    type_name: str | None
    is_optional: bool
    default: str | None


_SPEC_DEFAULT_RE = re.compile(
    r"^defaults?(?:\s*[=:]\s*|\s+(?:is|to)\s+|\s+)(?P<value>\S.*)$",
    flags=re.I,
)
_OPTIONAL_RE = re.compile(r"^(\*{0,2})optional\1$", re.I)
_OPTIONAL_SUFFIX_RE = re.compile(r"^(?P<type>.*?)\s*\(optional\)$", re.I)


def parse_type_spec(spec: str | None) -> TypeSpec:
    """Parse a type specification.

    The specification is split on top-level commas. The parts ``optional``
    and ``default <value>`` (also ``default=<value>``, ``default: <value>``,
    ``default is <value>``, ``defaults to <value>`` and ``defaults <value>``)
    are recognized wherever they appear, case insensitively; the remaining
    parts make up the type. ``optional`` may be emphasized, as in
    ``*optional*``.
    A part ending in ``?`` or ``(optional)`` is also optional. A default
    implies optional.
    """
    if spec is None:
        return TypeSpec(None, False, None)
    is_optional = False
    default = None
    parts = []
    for part in split_top_level(normalize_space(spec)):
        part = part.strip()
        match = _OPTIONAL_SUFFIX_RE.match(part)
        if match:
            is_optional = True
            part = match.group("type")
        elif part.endswith("?"):
            is_optional = True
            part = part[:-1].rstrip()
        if _OPTIONAL_RE.match(part):
            is_optional = True
            continue
        match = _SPEC_DEFAULT_RE.match(part)
        if match:
            default = strip_literal(match.group("value").strip())
            continue
        if part:
            parts.append(part)
    type_name = ", ".join(parts) or None
    return TypeSpec(type_name, is_optional or default is not None, default)


_DESC_DEFAULT_RE = re.compile(
    r"(?<![\w-])(?:defaults?\s+to|default\s+(?:value\s+)?is|default\s*[:=])"
    r"\s*",
    flags=re.I,
)


def find_default(description: str | None) -> str | None:
    """Find a default value stated in a description.

    Recognized phrases (case insensitive) are ``defaults to``, ``default
    is``, ``default value is``, ``default:`` and ``default=``. What follows,
    up to the end of the sentence, clause or enclosing bracket, is the
    default if it is a single value: a literal, a name, or a quoted or
    bracketed expression, optionally followed by a condition starting with
    ``if``, ``when`` or ``unless``. So ``(default: 3)``, ``Defaults to 3 if
    unset.`` and ``Defaults to ``None``, meaning all`` give ``3``, ``3`` and
    ``None``, while ``The default is to use all`` gives no default.
    """
    if not description:
        return None
    match = _DESC_DEFAULT_RE.search(description)
    if match is None:
        return None
    rest = description[match.end() :]
    end = len(rest)
    for i in _top_level_positions(rest, ",;.\n"):
        char = rest[i]
        if char in ",;" or char in _CLOSING or rest.startswith("\n\n", i):
            end = i
            break
        if char == "." and (i + 1 == len(rest) or rest[i + 1].isspace()):
            end = i
            break
    words = split_top_level(normalize_space(rest[:end]), " ")
    for i, word in enumerate(words):
        if word.lower() in _CONDITIONS:
            words = words[:i]
            break
    if len(words) != 1:
        return None
    return strip_literal(words[0]) or None


_CONDITIONS = {"if", "when", "unless"}

_NAME_RE = re.compile(r"\*{0,2}[^\W\d]\w*(?:\.\w+)*")


def unescape_name(name: str) -> str:
    """Remove backslashes escaping reST markup: ``\\*args``, ``class\\_``."""
    return name.replace("\\", "")


def escape_name(name: str) -> str:
    """Escape what reST would take as markup in a name.

    That is stars and a trailing underscore, which would make the name a
    reference. It is the inverse of :func:`unescape_name`.
    """
    name = name.replace("*", "\\*")
    return name[:-1] + "\\_" if name.endswith("_") else name


def parse_names(text: str) -> list[str] | None:
    """Parse a comma separated list of parameter names.

    Escaping backslashes are removed. ``...`` is kept as a name, as in
    ``arg1, arg2, ...``, like sphinx.ext.napoleon does. Returns None if any
    of the parts is not a valid name, or if they are all ``...``.
    """
    names = [name.strip() for name in unescape_name(text).split(",")]
    real = [name for name in names if name != "..."]
    if real and all(_NAME_RE.fullmatch(name) for name in real):
        return names
    return None


_TYPE_CONNECTORS = {"|", "or", "of"}
_PROSE_STARTS = {"a", "an", "the", "if", "when", "whether", "this", "it"}


def looks_like_type(text: str) -> bool:
    """Tell whether the text is plausibly a type rather than prose.

    It must be non-empty and balanced, must not end a sentence or start like
    one, and may have at most three top-level words besides ``of``, ``or``
    and ``|``. That allows ``list of str`` or ``int | None`` but not prose.
    """
    text = text.strip()
    if not text or not is_balanced(text) or text.endswith("."):
        return False
    words = [word for word in split_top_level(text, " ") if word]
    if words[0].lower() in _PROSE_STARTS:
        return False
    content = [word for word in words if word not in _TYPE_CONNECTORS]
    return len(content) <= 3 and not any(word.endswith(".") for word in words)


def split_typed_text(line: str) -> tuple[str, str] | None:
    """Split an item header like ``Type: text`` into the type and the text.

    The separator is the first colon followed by whitespace, so ``Type :
    text`` also works. Without one the whole line is the type. Returns None
    if what would be the type doesn't look like one, e.g. prose.
    """
    colon = find_separator(line)
    head = line[:colon] if colon >= 0 else line
    text = line[colon + 1 :] if colon >= 0 else ""
    if not looks_like_type(head):
        return None
    return head.strip(), text
