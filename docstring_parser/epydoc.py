"""Epyoc-style docstring parsing.

.. seealso:: http://epydoc.sourceforge.net/manual-fields.html
"""
import inspect
import re
import typing as T

from .common import (
    Docstring,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
    ParseError,
)


def _clean_str(string: str) -> T.Optional[str]:
    string = string.strip()
    if len(string) > 0:
        return string


def parse(text: str) -> Docstring:
    """Parse the epydoc-style docstring into its components.

    :returns: parsed docstring
    """
    ret = Docstring(style=DocstringStyle.epydoc)
    if not text:
        return ret

    text = inspect.cleandoc(text)
    match = re.search("^@", text, flags=re.M)
    if match:
        desc_chunk = text[: match.start()]
        meta_chunk = text[match.start() :]
    else:
        desc_chunk = text
        meta_chunk = ""

    parts = desc_chunk.split("\n", 1)
    ret.short_description = parts[0] or None
    if len(parts) > 1:
        long_desc_chunk = parts[1] or ""
        ret.blank_after_short_description = long_desc_chunk.startswith("\n")
        ret.blank_after_long_description = long_desc_chunk.endswith("\n\n")
        ret.long_description = long_desc_chunk.strip() or None

    param_pattern = re.compile(
        r"(param|keyword|type)(\s+[_A-z][_A-z0-9]*\??):"
    )
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

        param_match = re.search(param_pattern, chunk)
        raise_match = re.search(raise_pattern, chunk)
        return_match = re.search(return_pattern, chunk)
        meta_match = re.search(meta_pattern, chunk)

        match = param_match or raise_match or return_match or meta_match
        if not match:
            raise ParseError(
                'Error parsing meta information near "{}".'.format(chunk)
            )

        desc_chunk = chunk[match.end() :]
        if param_match:
            base = "param"
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
            token = _clean_str(match.group(2).strip())
            args = [] if token is None else re.split(r"\s+", token)

            # Make sure we didn't match some existing keyword in an incorrect
            # way here:
            if key in [
                "param",
                "keyword",
                "type",
                "return",
                "rtype",
                "yield",
                "ytype",
            ]:
                raise ParseError(
                    'Error parsing meta information near "{}".'.format(chunk)
                )

        desc = desc_chunk.strip()
        if "\n" in desc:
            first_line, rest = desc.split("\n", 1)
            desc = first_line + "\n" + inspect.cleandoc(rest)
        stream.append((base, key, args, desc))

    # Combine type_name, arg_name, and description information
    params: T.Dict[str, T.Dict[str, T.Any]] = {}
    for (base, key, args, desc) in stream:
        if base not in ["param", "return"]:
            continue  # nothing to do

        (arg_name,) = args or ("return",)
        info = params.setdefault(arg_name, {})
        info_key = "type_name" if "type" in key else "description"
        info[info_key] = desc

        if base == "return":
            is_generator = key == "ytype" or key == "yield"
            if info.setdefault("is_generator", is_generator) != is_generator:
                raise ParseError(
                    'Error parsing meta information for "{}".'.format(arg_name)
                )

    is_done: T.Dict[str, bool] = {}
    for (base, key, args, desc) in stream:
        if base == "param" and not is_done.get(args[0], False):
            (arg_name,) = args
            info = params[arg_name]
            type_name = info.get("type_name")

            if type_name and type_name.endswith("?"):
                is_optional = True
                type_name = type_name[:-1]
            else:
                is_optional = False

            m = re.match(r".*defaults to (.+)", desc, flags=re.DOTALL)
            default = m.group(1).rstrip(".") if m else None

            r = DocstringParam(
                args=[key, arg_name],
                description=info["description"],
                arg_name=arg_name,
                type_name=type_name,
                is_optional=is_optional,
                default=default,
            )
            is_done[arg_name] = True
        elif base == "return" and not is_done.get("return", False):
            info = params["return"]
            r = DocstringReturns(
                args=[key],
                description=info["description"],
                type_name=info.get("type_name"),
                is_generator=info.get("is_generator", False),
            )
            is_done["return"] = True
        elif base == "raise":
            (type_name,) = args or (None,)
            r = DocstringRaises(
                args=[key] + args,
                description=desc,
                type_name=type_name,
            )
        elif base == "meta":
            r = DocstringMeta(
                args=[key] + args,
                description=desc,
            )
        else:
            (key, *_) = args or ("return",)
            assert is_done.get(key, False)
            continue  # don't append

        ret.meta.append(r)


    return ret
