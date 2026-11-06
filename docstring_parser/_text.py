"""Text rules that every style shares."""

import re
import typing as T

from .common import Docstring


def clean_str(string: str) -> T.Optional[str]:
    """Strip a string, giving None if nothing is left."""
    return string.strip() or None


def split_description(ret: Docstring, text: str) -> None:
    """Set the short and long description from the text before any field.

    The short description is the first line, and the long description is
    everything after it. Its lines keep their indent in the dedented
    docstring, the first one too, which stripping it would lose.
    """
    parts = text.split("\n", 1)
    ret.short_description = parts[0].strip() or None
    if len(parts) > 1:
        rest = parts[1]
        ret.blank_after_short_description = rest.startswith("\n")
        ret.blank_after_long_description = rest.endswith("\n\n")
        long = rest.strip()
        lead = rest[: len(rest) - len(rest.lstrip())]
        if long and lead and not lead.endswith("\n"):
            long = lead[lead.rfind("\n") + 1 :] + long
        ret.long_description = long or None


def append_loose(
    ret: Docstring, chunks: T.Iterable[str], blank_around: bool
) -> None:
    """Add text found between or after the fields to the long description.

    :param chunks: the pieces of text, each a paragraph of its own
    :param blank_around: mark the description as followed by blank lines
    """
    loose = "\n\n".join(part.strip() for part in chunks if part.strip())
    if not loose:
        return
    if ret.short_description is None and ret.long_description is None:
        # With nothing before the fields, the text is the description, as
        # if written before them.
        split_description(ret, loose + "\n\n" if blank_around else loose)
        return
    ret.long_description = (
        f"{ret.long_description}\n\n{loose}" if ret.long_description else loose
    )
    if blank_around:
        ret.blank_after_short_description = True
        ret.blank_after_long_description = True


# One exception type: a dotted name, maybe marked as Sphinx does it
# (``~pkg.Error``) or quoted (```Error```), with an optional subscript.
EXCEPTION_TYPE = r"`?[~!]?[A-Za-z_][\w.]*(?:\[[^\]\n]*\])?`?"

OPTIONAL_REGEX = re.compile(r"(?P<type>.*?)(?:, optional|\(optional\))$")

# A default given in the type, as in:
#
#   copy : bool, default True
#   copy : bool, default=True
#   copy : bool, default: True
#
DEFAULT_REGEX = re.compile(
    r"(?P<type>.*?)(?:, default|\(default\))(?: | |=| = |= |: |)*(?P<value>.*)$"  # noqa: E501
)


class TypeSpec(T.NamedTuple):
    """A param's type with the marks of an optional param split off."""

    type_name: T.Optional[str]
    is_optional: bool
    default: T.Optional[str]


_CLOSING = {"(": ")", "[": "]", "{": "}"}


def _split_commas(text: str) -> T.List[str]:
    """Split a type on the commas outside brackets and quotes."""
    parts = []
    closing: T.List[str] = []
    quote = ""
    start = 0
    for i, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
        elif char in _CLOSING:
            closing.append(_CLOSING[char])
        elif closing and char == closing[-1]:
            closing.pop()
        elif char == "," and not closing:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


# A part of a type that marks the param optional.
_OPTIONAL = re.compile(r"\*?optional\*?", flags=re.I)
# A part of a type that names the default, as in ``default 1``,
# ``default=1``, ``default: 1``, ``default is 1``, ``defaults to 1`` or
# ``defaults 1``.
_DEFAULT_PART = re.compile(
    r"defaults?(?:\s*[=:]\s*|\s+(?:is\s+|to\s+)?)(?P<value>\S.*)",
    flags=re.I | re.S,
)
# The mark written after the type without a comma, as in ``int (optional)``.
_OPTIONAL_SUFFIX = re.compile(r"\s*\(optional\)$", flags=re.I)


def _strip_backticks(value: str) -> str:
    return value.strip("`") or value


def type_spec(type_name: T.Optional[str]) -> TypeSpec:
    """Split the marks of an optional param, and its default, off its type.

    The type is split on the commas outside brackets and quotes:

    - A part ``optional``, in any case or emphasized as ``*optional*``, a
      part ending in ``(optional)`` and a part ending in ``?`` mark the
      param optional.
    - A part ``default 1``, ``default=1``, ``default: 1``, ``default is
      1``, ``defaults to 1`` or ``defaults 1`` gives the default, without
      backticks around it, and makes the param optional too.
    - The other parts are the type.

    The same rule holds in every style.
    """
    if type_name is None or not type_name.strip():
        return TypeSpec(type_name=type_name, is_optional=False, default=None)
    is_optional = False
    default = None
    kept = []
    for part in _split_commas(type_name):
        part = part.strip()
        if _OPTIONAL.fullmatch(part):
            is_optional = True
            continue
        match = _DEFAULT_PART.fullmatch(part)
        if match is not None:
            is_optional = True
            default = _strip_backticks(match.group("value").strip())
            continue
        suffix = _OPTIONAL_SUFFIX.search(part)
        if suffix is not None:
            is_optional = True
            part = part[: suffix.start()]
        if part.endswith("?"):
            is_optional = True
            part = part[:-1].rstrip()
        if part:
            kept.append(part)
    return TypeSpec(
        type_name=", ".join(kept) or None,
        is_optional=is_optional,
        default=default,
    )


# A default that a description states, as in "Defaults to 3.", "(default:
# 3)" or "default is ``None`` if unset". The value must be one value: a
# literal, a name, a call, or a quoted or bracketed expression, maybe
# followed by a remark in parentheses or a condition. So "The default is to
# use all of them." states no default, and neither does "the default
# :meth:`run`".
DEFAULT_IN_DESCRIPTION = re.compile(
    r"(?<!\w)(?:defaults\s+to|default\s+(?:value\s+)?is|default:|default\s*=)"
    r"\s*(?P<value>"
    r"``[^`\n]+``|`[^`\n]+`"
    r"|'[^'\n]*'|\"[^\"\n]*\""
    r"|\([^()\n]*\)|\[[^\[\]\n]*\]|\{[^{}\n]*\}"
    r"|[-+]?[\w.]*\w(?:\([^()\n]*\))?"
    r")"
    r"(?=\s*(?:[.,;)]|$)|\s+(?:\(|(?:if|when|unless)\b))",
    flags=re.I | re.M,
)


def default_in(description: T.Optional[str]) -> T.Optional[str]:
    """Find the default that a description states, if any."""
    if not description:
        return None
    match = DEFAULT_IN_DESCRIPTION.search(description)
    if match is None:
        return None
    return _strip_backticks(match.group("value"))


def param_spec(
    type_name: T.Optional[str], description: T.Optional[str]
) -> TypeSpec:
    """Read a param's type, with its default from the type or else from
    its description. A param with a default is optional."""
    spec = type_spec(type_name)
    if spec.default is not None:
        return spec
    default = default_in(description)
    if default is None:
        return spec
    return TypeSpec(
        type_name=spec.type_name, is_optional=True, default=default
    )


class Example(T.NamedTuple):
    """One example of an examples section, as doctest reads it."""

    #: The text that introduces it, or None.
    description: T.Optional[str]
    #: The ``>>>`` lines with their ``...`` continuations and expected
    #: output, or None for text after the last snippet.
    snippet: T.Optional[str]


def _intro(lines: T.List[str]) -> T.Optional[str]:
    """Join the lines of an example's text, without blank lines around."""
    text = "\n".join(lines).strip("\n")
    return text if text.strip() else None


def split_examples(text: str) -> T.List[Example]:
    """Split an examples section into examples, the way doctest reads it.

    A snippet is a ``>>>`` line, the ``...`` lines that continue it, and
    its expected output: the lines up to a blank line or the next ``>>>``
    line. The text before a snippet introduces it, and text after the last
    snippet is an example of its own, with no snippet.
    """
    lines = text.split("\n")
    examples: T.List[Example] = []
    intro: T.List[str] = []
    i = 0
    count = len(lines)
    while i < count:
        line = lines[i]
        source = line.lstrip()
        if not source.startswith(">>>"):
            intro.append(line)
            i += 1
            continue
        # The continuations and output are indented at least as the
        # prompt, as doctest wants.
        indent = line[: len(line) - len(source)]
        start = i
        i += 1
        while (
            i < count
            and lines[i].startswith(indent)
            and lines[i].lstrip().startswith("...")
        ):
            i += 1
        while (
            i < count
            and lines[i].strip()
            and lines[i].startswith(indent)
            and not lines[i].lstrip().startswith(">>>")
        ):
            i += 1
        examples.append(Example(_intro(intro), "\n".join(lines[start:i])))
        intro = []
    description = _intro(intro)
    if description is not None:
        examples.append(Example(description, None))
    return examples
