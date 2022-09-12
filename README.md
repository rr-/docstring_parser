docstring_parser
================

[![Build](https://github.com/rr-/docstring_parser/actions/workflows/build.yml/badge.svg)](https://github.com/rr-/docstring_parser/actions/workflows/build.yml)

# Developing note
Clone this repo and install requirements:
```bash
pip install -r requirements.txt
```

Manual install:
```bash
poetry install -v
poetry run pre-commit install
pip install -e .

```

I am working on new Javadoc and JSdoc parser (Rdoc will be next), using by:
```python
>>> from docstring_parser import parse
>>> text = '''
...     This is a function.

...     @param n - A string param
...     @return int This return integer
...     @exception IOException On input error.    
        '''
>>> parse(text)
<docstring_parser.common.Docstring object at 0x7f6d4982bc40>
```
*Notes:* Javadoc style and Jsdoc style are under developing, I recommend selecting them by manual specify:
```python
>>> from docstring_parser import parse, DocstringStyle
>>> parse(text, DocstringStyle.JAVADOC)  # or DocstringStyle.JSDOC
```

Get docstring style by:
```python
>>> ret = parse(text)
>>> ret.style
DocstringStyle.JAVADOC
```

## Docstring style
Current supported docstring style:
- [x] Javadoc
- [x] JSdoc (JavaScript)
- [x] Epydoc (Python)
- [x] reST (Python)
- [x] Google (Python)
- [x] Numpy (Python)
- [] XML
- [] Rdoc (Ruby)

# Original

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
