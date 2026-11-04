"""Epyoc-style docstring parsing.

.. seealso:: http://epydoc.sourceforge.net/manual-fields.html
"""

import re
import typing as T

from ._compose import description_lines, field_name
from ._lines import Lines
from ._text import clean_str, split_description
from .common import (
    Docstring,
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

# The kinds of param that Epydoc fields other than ``@param`` give.
_PARAM_KINDS = {
    "keyword": Kind.KEYWORD,
    "ivar": Kind.ATTRIBUTE,
    "cvar": Kind.ATTRIBUTE,
    "var": Kind.ATTRIBUTE,
}


def parse(text: T.Optional[str]) -> Docstring:
    """Parse the epydoc-style docstring into its components.

    :returns: parsed docstring
    """
    ret = Docstring(style=DocstringStyle.EPYDOC)
    if not text:
        return ret

    text = Lines(text).text
    match = re.search("^@", text, flags=re.M)
    if match:
        desc_chunk = text[: match.start()]
        meta_chunk = text[match.start() :]
    else:
        desc_chunk = text
        meta_chunk = ""

    split_description(ret, desc_chunk)

    param_pattern = re.compile(
        r"(param|keyword|type)(\s+[_A-z][_A-z0-9]*\??):"
    )
    attribute_pattern = re.compile(r"(ivar|cvar|var)(\s+[_A-z][_A-z0-9]*\??):")
    raise_pattern = re.compile(r"(raise)(\s+[_A-z][_A-z0-9]*\??)?:")
    return_pattern = re.compile(r"(return|rtype|yield|ytype):")
    meta_pattern = re.compile(
        r"([_A-z][_A-z0-9]+)((\s+[_A-z][_A-z0-9]*\??)*):"
    )

    # tokenize
    stream: T.List[T.Tuple[str, str, T.List[str], str]] = []
    for match in re.finditer(
        r"(^@.*?)(?=^@|\Z)", meta_chunk, flags=re.S | re.M
    ):
        chunk = match.group(0)
        if not chunk:
            continue

        # Each chunk starts with @; description text is not a field header.
        param_match = param_pattern.match(chunk, 1)
        attribute_match = attribute_pattern.match(chunk, 1)
        raise_match = raise_pattern.match(chunk, 1)
        return_match = return_pattern.match(chunk, 1)
        meta_match = meta_pattern.match(chunk, 1)

        match = (
            param_match
            or attribute_match
            or raise_match
            or return_match
            or meta_match
        )
        if not match:
            raise ParseError(
                f'Error parsing meta information near "{excerpt(chunk)}".'
            )

        desc_chunk = chunk[match.end() :]
        if param_match:
            base = "param"
            key: str = match.group(1)
            args = [match.group(2).strip()]
        elif attribute_match:
            base = "attribute"
            key: str = match.group(1)
            args = [match.group(2).strip()]
        elif raise_match:
            base = "raise"
            key: str = match.group(1)
            args = [] if match.group(2) is None else [match.group(2).strip()]
        elif return_match:
            base = "return"
            key: str = match.group(1)
            args = []
        else:
            base = "meta"
            key: str = match.group(1)
            token = clean_str(match.group(2).strip())
            args = [] if token is None else re.split(r"\s+", token)

            # Make sure we didn't match some existing keyword in an incorrect
            # way here:
            if key in [
                "param",
                "ivar",
                "cvar",
                "var",
                "keyword",
                "type",
                "return",
                "rtype",
                "yield",
                "ytype",
            ]:
                raise ParseError(
                    f'Error parsing meta information near "{excerpt(chunk)}".'
                )

        desc = desc_chunk.strip()
        if "\n" in desc:
            first_line, rest = desc.split("\n", 1)
            desc = first_line + "\n" + cleandoc(rest)
        stream.append((base, key, args, desc))

    # Combine type_name, arg_name, and description information
    params: T.Dict[str, T.Dict[str, T.Any]] = {}
    for base, key, args, desc in stream:
        if base not in ["param", "attribute", "return"]:
            continue  # nothing to do

        (arg_name,) = args or ("return",)
        info = params.setdefault(arg_name, {})
        info_key = "type_name" if "type" in key else "description"
        info[info_key] = desc
        if info_key == "description":
            # The field that says what kind of param this is, even when a
            # @type field for it comes first.
            info["key"] = key

        if base == "return":
            is_generator = key in {"ytype", "yield"}
            if info.setdefault("is_generator", is_generator) != is_generator:
                raise ParseError(
                    f'Error parsing meta information for "{arg_name}".'
                )

    is_done: T.Dict[str, bool] = {}
    for base, key, args, desc in stream:
        if base in ["param", "attribute"] and not is_done.get(args[0], False):
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
                args=[param_key, arg_name],
                description=info.get("description"),
                arg_name=arg_name,
                type_name=type_name,
                is_optional=is_optional,
                default=default,
                kind=_PARAM_KINDS.get(param_key, Kind.PARAM),
            )
            is_done[arg_name] = True
        elif base == "return" and not is_done.get("return", False):
            info = params["return"]
            meta_item = DocstringReturns(
                args=[key],
                description=info.get("description"),
                type_name=info.get("type_name"),
                is_generator=info.get("is_generator", False),
            )
            is_done["return"] = True
        elif base == "raise":
            (type_name,) = args or (None,)
            meta_item = DocstringRaises(
                args=[key] + args,
                description=desc,
                type_name=type_name,
            )
        elif base == "meta":
            meta_item = DocstringMeta(
                args=[key] + args,
                description=desc,
            )
        else:
            (key, *_) = args or ("return",)
            assert is_done.get(key, False)
            continue  # don't append

        ret.meta.append(meta_item)

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
            text = f"@{' '.join(meta.args)}:"
            text += process_desc(meta.description, False)
            parts.append(text)
    return "\n".join(parts)
