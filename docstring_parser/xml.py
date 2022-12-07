"""XML docstring parsing."""
import inspect
import re
import typing as T

import xml.etree.ElementTree as ET

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


def get_node_description(node):
    description = []
    def traverse_node(node, description):
        text = node.text 
        tail = node.tail
        
        if text and text != '\n' and text != '':
            description.append(text)
            if not node:
                return

        if tail and tail != '\n' and tail != '':
            description.append(tail)

        # if not node and not appended:
        #     description.append(text)
        #     return
            
        for n in node:
            traverse_node(n, description)
    traverse_node(node, description)
    return description


def _build_meta(tag: str, args) -> DocstringMeta:
    """Build docstring element.

    :param args: element tag
    :param title: title of section containing element
    :return:
    """
    desc = ''.join(get_node_description(args))
    _args = [tag, desc]
    if tag in PARAM_KEYWORDS | YIELDS_KEYWORDS:
        arg_name = None
        if args.attrib and 'name' in args.attrib.keys():
            arg_name = args.attrib['name']

        else:
            raise ParseError(
                f"Expected param arguments have name"
            )
            

        is_optional = None
        match = re.match(r".*defaults to (.+)", desc, flags=re.DOTALL)
        default = match.group(1).rstrip(".") if match else None
        type_name = None
        
        _args = [arg_name, desc]

        return DocstringParam(
            args=_args,
            description=desc,
            arg_name=arg_name,
            type_name=type_name,
            is_optional=is_optional,
            default=default,
        )

    elif tag in RETURNS_KEYWORDS:
        type_name = None

        return DocstringReturns(
            args=_args,
            description=desc,
            type_name=type_name,
            is_generator=tag in YIELDS_KEYWORDS,
        )

    elif tag in RAISES_KEYWORDS:
        type_name = None
        if args.attrib:
            if 'cref' in args.attrib.keys():
                arg_name = args.attrib['cref']

        return DocstringRaises(
            args=_args, description=desc, type_name=type_name
        )

    return DocstringMeta(args=_args, description=desc)


def parse(text) -> Docstring:
    """
    Parser the Javadoc docstring into its components.
    :param text: Docstring for parse
    :type text: str

    :returns: parsed docstring
    """
    ret = Docstring(style=DocstringStyle.XML)
    text = inspect.cleandoc(text)
    
    # add a tag warper
    text = '<docstring>\n' + text + '\n</docstring>'
    tree = ET.fromstring(text)
    
    metadata = {}
    for meta in tree:
        tag = meta.tag
        if tag == 'summary':
            metadata[tag] =   ''.join(get_node_description(meta))
        else:
            if tag in metadata.keys():
                metadata[tag].append(meta)
            else:
                metadata[tag] = [meta]

    description = metadata['summary']
    ret.short_description = description
    ret.blank_after_short_description = description.startswith("\n")
    ret.blank_after_long_description = description.endswith("\n\n")
    ret.long_description = None
    
    for tag, meta_list in metadata.items():
        if tag == 'summary':
            continue
        for meta in meta_list:
            ret.meta.append(_build_meta(tag, meta))

    return ret
