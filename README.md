docstring_parser
================

Parse Python docstrings. Currently support ReST, Google, and Numpydoc-style
docstrings.

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

# Contributing

This project uses [Black](https://github.com/psf/black) with `-l79` setting as
well as [isort](https://github.com/timothycrosley/isort).
