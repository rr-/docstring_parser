"""JavaScript docstring parsing."""
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
    key = args[0].strip().strip('-').strip('`')  # strip ` `
    desc = desc.strip().strip('-')

    if key in PARAM_KEYWORDS:
        arg_name = args[1]
        is_optional = None
        default = None
        type_name = None

        return DocstringParam(
            args=args,
            description=desc,
            arg_name=arg_name,
            type_name=type_name,
            is_optional=is_optional,
            default=default,
        )

    elif key in RETURNS_KEYWORDS | YIELDS_KEYWORDS:
        type_name = None
        
        if len(args) <= 1:
            args = key

        else:
            type_name = str(args[1]).replace('-', '').lstrip()[1:-1]
            args = [key, type_name]

        return DocstringReturns(
            args=args,
            description=desc,
            type_name=type_name,
            is_generator=key in YIELDS_KEYWORDS,
        )

    # if key in RAISES_KEYWORDS:
    #     type_name = None
    #     for name in args[1:]:
    #         match = re.match(r"\{.*?\}", name)
    #         if match:
    #             type_name = match.group()
                
    #             if type_name.startswith("{"):
    #                 type_name = type_name[1:]
    #             if type_name.endswith("}"):
    #                 type_name = type_name[:-1]

    #     return DocstringRaises(
    #         args=args, description=desc, type_name=type_name
    #     )

    return DocstringMeta(args=args, description=desc)


def parse(text):
    """
    Parser the Javadoc docstring into its components.
    :param text: Docstring for parse
    :type text: str

    :returns: parsed docstring
    """
    ret = Docstring(style=DocstringStyle.RUSTDOC)
    text = inspect.cleandoc(text)

    match = re.search("^#", text, flags=re.M)
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
        r"(^#.*?)(?=^#|\Z)", meta_chunk, flags=re.S | re.M
    ):
        chunk = match.group(0)

        try:
            splited = chunk.lstrip().split("\n", 1)
            if len(splited) == 1:
                tag = splited[0]
                desc_chunk = ""
            else:
                tag, desc_chunk = splited
            # @tag (name) description
        except ValueError as ex:
            raise ParseError(
                f'Error parsing meta information near "{chunk}".'
            ) from ex

        tag = tag.strip("#").lstrip().lower()

        if tag in ["parameters", "arguments", "type parameters"]:
            tag = 'param'
            for match in re.finditer(
                r"(^-\s*.*?)(?=^-|\Z)", desc_chunk, flags=re.S | re.M):
                
                chunk = match.group(0)
                _name = re.search(r'-\s*`.*?`:*\s*', chunk)
                if _name:
                    args_name = re.search(r'`.*?`', chunk).group(0)[1:-1]  # remove ` and `
                    desc = chunk.replace(_name.group(0), '')
                
                else:
                    raise ParseError(
                        f'Expected two or three arguments for a "{tag}" keyword.'
                    )

                args = [tag, args_name]
                ret.meta.append(_build_meta(args, desc))

        elif tag in ["returns", "lifetimes"]:
            if re.search(r"-\s*`.*?`", desc_chunk):
                for match in re.finditer(
                    r"(^-\s*.*?)(?=^-|\Z)", desc_chunk, flags=re.S | re.M):
                    
                    chunk = match.group(0)
                    _name = re.search(r'-\s*`.*?`', chunk)
                    if _name:
                        args_name = str(_name.group(0)).replace('-', '').lstrip()[1:-1]  # remove ` and `
                        desc = chunk.replace(_name.group(0), '')
                    
                    else:
                        raise ParseError(
                            f'Expected two or three arguments for a "{tag}" keyword.'
                        )

                    args = [tag, args_name]
                    ret.meta.append(_build_meta(args, desc))
            else:
                args = [tag]
                ret.meta.append(_build_meta(args, desc_chunk))

        else:
            ret.meta.append(_build_meta([tag], desc_chunk))

    return ret
