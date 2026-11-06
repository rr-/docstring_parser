"""Epyoc-style docstring parsing.

.. seealso:: http://epydoc.sourceforge.net/manual-fields.html
"""

import re
import typing as T

from ._compose import description_lines, field_name, field_text
from ._lines import Lines
from ._text import split_description
from .common import (
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
    cleandoc,
    excerpt,
)
from .sections import SectionSpec, apply

_FIELD_START = re.compile("^@", flags=re.M)
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

# A field as read: how it combines with others, its name, the names it is
# about, its text, its kind and the spec it was recognised by.
_Field = T.Tuple[str, str, T.List[str], str, Kind, T.Optional[SectionSpec]]


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


_DEFAULT_TABLE = {
    name: spec for spec in default_sections() for name in spec.titles
}


def parse(
    text: T.Optional[str],
    sections: T.Optional[T.Sequence[SectionSpec]] = None,
) -> Docstring:
    """Parse the epydoc-style docstring into its components.

    :param sections: the fields to recognise, instead of the default ones;
        each meta's ``key`` is the name its field is written with
    :returns: parsed docstring
    """
    table = (
        _DEFAULT_TABLE
        if sections is None
        else {name: spec for spec in sections for name in spec.titles}
    )
    ret = Docstring(style=DocstringStyle.EPYDOC)
    if not text:
        return ret

    text = Lines(text).text
    match = _FIELD_START.search(text)
    if match:
        desc_chunk = text[: match.start()]
        meta_chunk = text[match.start() :]
    else:
        desc_chunk = text
        meta_chunk = ""

    split_description(ret, desc_chunk)

    # tokenize
    stream: T.List[_Field] = []
    for match in _FIELD.finditer(meta_chunk):
        chunk = match.group(0)
        if not chunk:
            continue

        # Each chunk starts with @; description text is not a field header.
        header = _HEADER.match(chunk, 1)
        if not header:
            raise ParseError(
                f'Error parsing meta information near "{excerpt(chunk)}".'
            )
        key = header.group(1)
        args = header.group(2).split()
        spec = table.get(key)
        base, kind = _TYPE_FIELDS.get(key) or _base(spec, args)
        if (
            (base == "param" and len(args) != 1)
            or (base == "return" and args)
            or (base == "meta" and spec is None and len(key) < 2)
        ):
            raise ParseError(
                f'Error parsing meta information near "{excerpt(chunk)}".'
            )

        desc = chunk[header.end() :].strip()
        if "\n" in desc:
            first_line, rest = desc.split("\n", 1)
            desc = first_line + "\n" + cleandoc(rest)
        stream.append((base, key, args, desc, kind, spec))

    # Combine type_name, arg_name, and description information
    params: T.Dict[str, T.Dict[str, T.Any]] = {}
    for base, key, args, desc, kind, spec in stream:
        if base not in ["param", "return"]:
            continue  # nothing to do

        (arg_name,) = args or ("return",)
        info = params.setdefault(arg_name, {})
        info_key = "type_name" if key in _TYPE_FIELDS else "description"
        info[info_key] = desc
        if info_key == "description":
            # The field that says what kind of param this is, even when a
            # @type field for it comes first.
            info["key"] = key
            info["kind"] = kind
            info["spec"] = spec

        if base == "return":
            is_generator = kind is Kind.YIELDS
            if info.setdefault("is_generator", is_generator) != is_generator:
                raise ParseError(
                    f'Error parsing meta information for "{arg_name}".'
                )

    is_done: T.Dict[str, bool] = {}
    for base, key, args, desc, kind, spec in stream:
        if base == "param" and not is_done.get(args[0], False):
            (arg_name,) = args
            info = params[arg_name]
            type_name = info.get("type_name")

            if type_name and type_name.endswith("?"):
                is_optional = True
                type_name = type_name[:-1]
            else:
                is_optional = False

            match = re.match(r".*defaults to (.+)", desc, flags=re.DOTALL)
            default = match.group(1).rstrip(".") if match else None

            param_key = info.get("key", key)
            meta_item = DocstringParam(
                key=param_key,
                description=info.get("description"),
                arg_name=arg_name,
                type_name=type_name,
                is_optional=is_optional,
                default=default,
                kind=info.get("kind", Kind.PARAM),
            )
            spec = info.get("spec")
            is_done[arg_name] = True
        elif base == "return" and not is_done.get("return", False):
            info = params["return"]
            meta_item = DocstringReturns(
                key=key,
                description=info.get("description"),
                type_name=info.get("type_name"),
                is_generator=info.get("is_generator", False),
            )
            spec = info.get("spec")
            is_done["return"] = True
        elif base == "raise":
            (type_name,) = args or (None,)
            meta_item = DocstringRaises(
                key=key,
                description=desc,
                type_name=type_name,
                kind=kind,
            )
        elif kind is Kind.EXAMPLES:
            meta_item = DocstringExample(
                snippet=None, description=desc, key=key
            )
        elif kind is Kind.DEPRECATION:
            meta_item = DocstringDeprecated(desc, version=None, key=key)
        elif base == "meta":
            meta_item = DocstringMeta(
                key=key,
                name=" ".join(args) or None,
                description=desc,
            )
        else:
            (key, *_) = args or ("return",)
            assert is_done.get(key, False)
            continue  # don't append

        ret.meta.append(apply(spec, meta_item))

    return ret


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
