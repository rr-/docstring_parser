"""Doxygen docstring parsing."""
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
        if len(args) != 2:
            raise ParseError(f"Expected two arguments for a {key} keyword.")
        _, arg_name = args
        type_name = None
        is_optional = None

        match = re.match(r".*defaults to (.+)", desc, flags=re.DOTALL)
        default = match.group(1).rstrip(".") if match else None

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

        return DocstringReturns(
            args=args,
            description=desc,
            type_name=type_name,
            is_generator=key in YIELDS_KEYWORDS,
        )

    if key in DEPRECATION_KEYWORDS:

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

    :example:
        >>> from docstring_parser import parse, DocstringStyle
        >>> text = '''
        ...     This is a function.

        ...     @param n - A string param
        ...     @return int This return integer
        ...     @exception IOException On input error.
                '''
        >>> parse(text, DocstringStyle.JAVADOC)
        <docstring_parser.common.Docstring object at 0x7f6d4982bc40>

    """
    ret = Docstring(style=DocstringStyle.JAVADOC)
    text = inspect.cleandoc(text)

    match = re.search(r"^(@|\\)(?=\w)", text, flags=re.M)
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
        r"(^(@|\\).*?)(?=^@|^\\|\Z)", meta_chunk, flags=re.S | re.M
    ):
        chunk = match.group(0)

        try:
            tag, desc_chunk = chunk.lstrip().split(" ", 1)
            # @tag description
        except ValueError as ex:
            raise ParseError(
                f'Error parsing meta information near "{chunk}".'
            ) from ex

        tag = re.sub(r"([\\|@|]+)|(\[.*\])", '', tag)
        if tag == 'brief':
            desc_chunk = desc_chunk.strip()
            ret.short_description = '\n\n'.join(filter(None, [ret.short_description, desc_chunk]))
            continue

        elif tag in ["param", "retval", "throws"]:
            splited = desc_chunk.strip().split(" ", 1)
            desc_chunk = ""
            if len(splited) == 2:
                if re.match(r'\[.*\]', splited[0]):
                    splited = splited[1].split(" ", 1)
                args_chunk, desc_chunk = splited[0].strip(), splited[1].strip()
            if len(splited) == 1:
                args_chunk = splited[0].strip("\n")
            args = [tag, args_chunk]
        
        else:
            args = [tag]

        desc = desc_chunk.strip()
        if "\n" in desc:
            first_line, rest = desc.split("\n", 1)
            desc = first_line + "\n" + inspect.cleandoc(rest)

        ret.meta.append(_build_meta(args, desc))

    # for meta in ret.meta:
    #     if isinstance(meta, DocstringParam):
    #         meta.type_name = meta.type_name or types.get(meta.arg_name)

    return ret
