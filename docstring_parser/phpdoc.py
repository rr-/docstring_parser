"""Javadoc docstring parsing."""
import inspect
import re
import typing as T

from docstring_parser.common import (  # RenderingStyle,
    DEPRECATION_KEYWORDS,
    PARAM_KEYWORDS,
    RAISES_KEYWORDS,
    RETURNS_KEYWORDS,
    YIELDS_KEYWORDS,
    Docstring,
    DocstringDeprecated,
    DocstringMeta,
    DocstringParam,
    DocstringRaises,
    DocstringReturns,
    DocstringStyle,
    ParseError,
)


def _build_meta(args: T.List[str], desc: str) -> DocstringMeta:
    """Build docstring element.

    :param text: docstring element text
    :param title: title of section containing element
    :return:
    """
    key = args[0]

    if key in PARAM_KEYWORDS:
        if len(args) == 3:
            key, _arg_name = args[0], args[1:]
        elif len(args) == 2:
            key, _arg_name = args[0], args[1]
        else:
            raise ParseError(
                f"Expected two or three arguments for a {key} keyword."
            )

        is_optional = None
        default = None
        type_name = None
        arg_name = None
        for name in _arg_name:
            name_match = re.search(r"\$.*?", name)  # args
            if name_match:
                arg_name = re.search(r"[\w\d_-]*$", name.strip()).group()
                # arg_name = name.rstrip().replace('$', '')
                # type_name = type_name[:-1]
                continue
            else:
                type_name = name

        return DocstringParam(
            args=args,
            description=desc,
            arg_name=arg_name,
            type_name=type_name,
            is_optional=is_optional,
            default=default,
        )

    if key in RETURNS_KEYWORDS | YIELDS_KEYWORDS:
        type_name = None
        if len(args) == 2:
            type_name = args[1]

        return DocstringReturns(
            args=args,
            description=desc,
            type_name=type_name,
            is_generator=key in YIELDS_KEYWORDS,
        )

    if key in DEPRECATION_KEYWORDS:
        match = re.search(
            r"^(?P<version>v?((?:\d+)(?:\.[0-9a-z\.]+))) (?P<desc>.+)",
            desc,
            flags=re.I,
        )
        return DocstringDeprecated(
            args=args,
            version=match.group("version") if match else None,
            description=match.group("desc") if match else desc,
        )

    if key in RAISES_KEYWORDS:
        type_name = None
        if len(args) == 2:  # throws
            type_name = args[1]

        return DocstringRaises(
            args=args, description=desc, type_name=type_name
        )

    return DocstringMeta(args=args, description=desc)


def parse(text) -> Docstring:
    """
    Parser the Javadoc docstring into its components.
    :param text: Docstring for parse
    :type text: str

    :returns: parsed docstring
    """
    ret = Docstring(style=DocstringStyle.PHPDOC)
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

    for match in re.finditer(
        r"(^@.*?)(?=^@|\Z)", meta_chunk, flags=re.S | re.M
    ):
        chunk = match.group(0).replace('\n', ' ').replace('\r', ' ')

        try:
            tag, desc_chunk = chunk.lstrip().split(" ", 1)
            # @tag (name) description
        except ValueError as ex:
            raise ParseError(
                f'Error parsing meta information near "{chunk}".'
            ) from ex

        tag = tag.strip("@")
        desc_chunk = " ".join(desc_chunk.split())  # trim whitespace

        if tag in ["param", "global", "property", "property-read", "property-write"]:
            splited = desc_chunk.rstrip().strip('\n').split(" ", 2)
            desc_chunk = ""
            
            if len(splited) == 3:
                _, args_chunk, desc_chunk = splited
            elif len(splited) == 2:
                _, args_chunk = splited
            else:
                raise ParseError(
                    f'Expected two or three arguments for a "{tag}" keyword.'
                )

            args = [tag, _, args_chunk.strip("\n")]
        
        elif tag in ["return", "var", "name", "throws", "exception"]:
            splited = desc_chunk.lstrip().split(" ", 1)
            desc_chunk = ""
            if len(splited) == 2:
                args_chunk, desc_chunk = splited
            elif len(splited) == 1:
                args_chunk = splited[0]
            else:
                raise ParseError(
                    f'Expected two arguments for a "{tag}" keyword.'
                )
            args = [tag, args_chunk]
        else:
            args = [tag.strip("\n")]
        

        desc = desc_chunk.strip()
        if "\n" in desc:
            first_line, rest = desc.split("\n", 1)
            desc = first_line + "\n" + inspect.cleandoc(rest)

        ret.meta.append(_build_meta(args, desc))

    # for meta in ret.meta:
    #     if isinstance(meta, DocstringParam):
    #         meta.type_name = meta.type_name or types.get(meta.arg_name)

    return ret
