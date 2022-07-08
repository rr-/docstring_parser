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

# Contributing

To set up the project:
```sh
pip install --user poetry

git clone https://github.com/rr-/docstring_parser.git
cd docstring_parser

poetry install
poetry run pre-commit install
```

To run tests:
```
poetry run pytest
```
