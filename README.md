docstring_parser
================

[![Build](https://github.com/rr-/docstring_parser/actions/workflows/build.yml/badge.svg)](https://github.com/rr-/docstring_parser/actions/workflows/build.yml)

Parse Python docstrings. Currently support ReST, Google, Numpydoc-style and
Epydoc docstrings.

Example usage:

```python
>>> from docstring_parser import parse
>>>
>>>
>>> docstring = parse(
...     '''
...     Short description
...
...     Long description spanning multiple lines
...     - First line
...     - Second line
...     - Third line
...
...     :param name: description 1
...     :param int priority: description 2
...     :param str sender: description 3
...     :raises ValueError: if name is invalid
...     ''')
>>>
>>> docstring.long_description
'Long description spanning multiple lines\n- First line\n- Second line\n- Third line'
>>> docstring.params[1].arg_name
'priority'
>>> docstring.raises[0].type_name
'ValueError'
```

Read [API Documentation](https://rr-.github.io/docstring_parser/).

# Custom sections

Every style recognises a list of sections, or for ReST and Epydoc, fields.
A `SectionSpec` declares one: the titles that start it, the kind of items in
it and, optionally, the key each item records. Pass a
list as `sections` to `parse()`, to `parse_from_object()` or to a style's
parser. It replaces the style's own list, which `default_sections(style)`
returns, so start from that to add to it:

```python
>>> from docstring_parser import DocstringStyle, parse
>>> from docstring_parser.sections import Kind, SectionSpec, default_sections
>>>
>>> sections = [
...     *default_sections(DocstringStyle.GOOGLE),
...     SectionSpec(("Keyword Args", "Kwargs"), Kind.KEYWORD),
...     SectionSpec("C++ Notes", Kind.TEXT),
... ]
>>> docstring = parse(
...     '''
...     Short description
...
...     Kwargs:
...         timeout (float): seconds to wait
...     ''',
...     sections=sections,
... )
>>> param = docstring.params[0]
>>> param.kind, param.key, param.arg_name, param.type_name
(<Kind.KEYWORD: 2>, 'keyword', 'timeout', 'float')
```

- Titles are matched as written, so they may hold any characters, such as
  `C++ Notes` or `Args (old)`. List every spelling to accept, such as
  `ARGS` next to `Args`.
- `bare=True` marks a title that stands alone on its line: with no colon
  after it in Google, or no underline below it in Numpydoc.
- In ReST and Epydoc, titles are field names: `SectionSpec("input",
  Kind.PARAM)` reads `:input x:` and `@input x:` as params.
- `parse_item` is a function that gets the meta of each item of the section,
  already split into its name, type and description. It may change the meta
  and return None, or return the meta to use instead.

These replace the ways parsers used to be customised, which a later release
removes:

| Instead of | Use |
| --- | --- |
| overriding `GoogleParser._setup` to set `titles_re` | `SectionSpec` titles, with `bare=True` for titles with no colon |
| overriding `numpydoc.Section.title_pattern` | `SectionSpec` titles, with `bare=True` for titles with no underline |
| replacing `numpydoc.KV_REGEX` | `parse_item` |
| overriding `GoogleParser._build_meta` or `numpydoc._KVSection._parse_item` | `parse_item` |
| changing `google.DEFAULT_SECTIONS` or `numpydoc.DEFAULT_SECTIONS` | passing `sections` |

# Installation

Installation using pip

```shell
pip install docstring_parser

# or if you want to install it in a virtual environment

python -m venv venv # create environment
source venv/bin/activate # activate environment
python -m pip install docstring_parser
```

Installation using conda


1. Download and install miniconda or anaconda
2. Install the package from the conda-forge channel via:
  - `conda install -c conda-forge docstring_parser`
  - or create a new conda environment via `conda create -n my-new-environment -c conda-forge docstring_parser`


# Contributing

To set up the project:
```sh
git clone https://github.com/rr-/docstring_parser.git
cd docstring_parser

uv sync  # create .venv with the dev dependencies
uv run prek install  # set up the lint and message hooks
```

To run tests:
```
uv run pytest
```

The `justfile` wraps these and other common tasks; run `just` to list them.
