# Unreleased

- General: **Breaking:** Remove `DocstringMeta.args`, which each style filled differently; the new `key`, `name` and `kind` fields say the same, and the meta classes no longer take `args`
- General: **Breaking:** Read the keyword sets in `common`, such as `PARAM_KEYWORDS`, once on import; pass `sections` instead of changing them
- General: **Breaking:** Make `DocstringStyle` values the style names, such as `"google"`, instead of numbers
- General: **Breaking:** Leave attributes out of `Docstring.params`, and list them in the new `Docstring.attrs`
- General: **Breaking:** Leave yields out of `Docstring.returns` and `many_returns`; read them from the new `yields` and `many_yields`
- General: **Breaking:** Make `is_optional` of a parsed param always a bool, `False` instead of `None` when it has no type
- Google, Numpydoc: **Breaking:** Remove customising parsing by overriding internals such as `titles_re`, `title_pattern`, `_build_meta` and `KV_REGEX`; use `SectionSpec` instead
- Google, Numpydoc: **Breaking:** Split examples as doctest reads them: an example's `description` is the text before its snippet, and its `snippet` holds the `>>>` lines, their `...` continuations and the expected output; text after the last snippet is an example with no snippet
- General: Parse docstrings with `\r\n` or `\r` line endings the same as with `\n`, on every Python version
- General: Dedent docstrings the same way on every Python version; from 3.13, `inspect.cleandoc` dedented nothing after a blank line holding a tab or form feed
- General: Strip the short description, which kept leading spaces when a later line was indented less than it
- General: Quote at most the first 60 characters of the text a `ParseError` points at, instead of the whole chunk
- General: Parse a docstring with no fields or sections once in auto-detection instead of four times, making it about 47% faster
- General: Raise `ValueError` instead of `KeyError` from `compose()` when the docstring has no style and none is given
- General: Stop `combine_docstrings` from taking an attribute named like a param as that param
- General: Give every meta a `kind`, a `Kind` that tells what it documents, such as a keyword param or a warning
- General: Compose items into sections by their `kind`, so a meta made by hand needs `kind=` for a sub-kind such as `Kind.ATTRIBUTE`
- General: Add `docstring_parser.sections`, where a `SectionSpec` declares a section or field for any style; pass a list as `sections` to `parse()` or a parser, starting from `default_sections(style)`
- General: Add `SectionSpec(bare=True)` for a title alone on its line, with no colon or underline
- General: Add `SectionSpec(parse_item=...)`, which gets each item's meta, already parsed, to change or replace
- General: Add a `Parser` to every style's module, and `auto.Parser`, which take `sections` once and parse with `parse(text)`; `GoogleParser` and `NumpydocParser` stay as aliases
- General: Accept a style by its name, such as `"google"`, or a parser in `parse()` and `compose()`
- General: Add `try_parse()`, which never raises for the docstring's text and returns a `ParseResult` of the docstring and its `problems`, each a `Problem` with its line and a stable `code`, such as `missing-colon`; text it cannot read goes to the long description
- General: Give `ParseError` the `problems` of the whole docstring and the `result` parsed despite them, and mention how many more there are in its message
- General: Show a docstring and its metas with the fields they have set in `repr()`, as in `DocstringParam(kind=Kind.PARAM, arg_name='x', ...)`
- General: Read optional params and defaults by one rule in every style: `optional` in any case or as `*optional*`, `(optional)`, `?`, and `default 1`, `default=1`, `default: 1`, `default is 1` or `defaults to 1` in the type, split at commas outside brackets and quotes
- General: Take a default from a param's description in every style when it states one value, as in `Defaults to 3.`, `(default: 3)` or `defaults to ``None`` if unset`, and make the param optional; prose such as `the default is to use all` gives none
- General: Add `raw_type_name` to params, the type as written, such as `int, optional`, before its optional mark and default are split off
- General: Keep a class attribute in `parse_from_object()` when the class docstring documents a param of the same name, instead of dropping it
- General: Return the docstring of a built-in class or module from `parse_from_object()` instead of raising `TypeError`, and ignore a `__doc__` that is not a string
- General: Cut a line holding only a tab or a form feed at either end of a docstring as a blank line, instead of reading it as the summary and the real summary as the long description
- General: Keep the indent of the long description's first line, as its other lines keep theirs, instead of stripping it, so an indented signature, table or code block keeps its shape
- General: Start a composed docstring on a new line when its long description is indented and nothing follows it, so that the indent reads back
- General: Compose a param's type as written, such as `int, optional` or `int, default 1`, when it reads back as the same type, instead of with the style's own optional mark, and add no mark for a default that only the description states
- General: Compose a description that holds a form feed or another line break that is not a newline on one line, as it was read, instead of breaking the line in two
- General: Keep the indent of the long description's first line relative to the lines after it, instead of stripping it, so an indented signature, table or code block keeps its shape
- ReST: Stop the last field from absorbing text after the field list; that text now goes to the long description (thanks to @apoorvdarshan)
- ReST: Raise `ParseError` instead of `IndexError` for a field with no name
- ReST: Indent composed continuation lines in compact mode, so one starting with a role such as `:class:` is no longer read back as a new field
- ReST: Compose a type with a space or a colon, such as `float or tuple`, as a field of its own instead of one that fails to parse
- ReST: End a `:type:` or `:rtype:` field at the next unindented line, which goes to the long description instead of into the type
- ReST: Keep blank lines and relative indents in a field's description, so paragraphs and literal blocks survive
- ReST: Keep a `:type x:` field that no other field describes as a param, and an `:rtype name:` as a return, instead of dropping them
- ReST: Read `:ivar:`, `:var:` and `:cvar:` as attributes typed by `:vartype:`, instead of text
- ReST: Read an empty `:type x:` as no type rather than an empty one
- ReST: Compose a return value's name as `:returns:` followed by `:rtype name:`, and read it back, instead of dropping it
- ReST: Read a `:ytype:` field as the type of the yields, as `:rtype:` is of the returns, and compose a yield's type with it
- ReST: Parse an `.. attribute:: name` directive, with its `:type:` and `:value:` options, as an attribute instead of leaving it in the long description
- ReST: Read a type with spaces in a field's head, as in `:param Dict[str, int] x:`, `:param int or None x:` or `:raises A, B:`, instead of raising `ParseError`
- ReST: Read a line starting with a role, such as ``:meth:`run` does stuff.``, as text of the description or of the field before it, instead of a field named `meth`; as in docutils, a field's closing colon must be followed by whitespace or the end of the line
- ReST: Keep every line of a `:deprecated:` field that starts with a version, instead of only its first
- ReST: Keep a type field for a param or return that has a type already, as in `:param int x:` followed by `:type x: str`, as an item of its own instead of dropping it
- ReST: Compose a param or return that only a type field gives as that field alone, instead of adding an empty `:param:` or `:returns:` field that reads back with an empty description
- ReST: Compose returns, yields and raises with the field name they were read from, such as `:return:` or `:raise:`, instead of `:returns:` and `:raises:` for all
- ReST: Compose the version of a deprecation instead of dropping it, and indent the lines after the first of a type, which an unindented line ended
- ReST: Compose an attribute with a default that neither its type nor its description gives, such as one read from a directive's `:value:`, as an `.. attribute::` directive, instead of dropping the default
- Google: Parse PEP 604 union types (e.g. `int | str`) in return sections (thanks to @binggao1230)
- Google: Parse a union return or yield type whose members have brackets or dots, such as `dict[str, int] | None`, instead of keeping the whole line as the description
- Google: Avoid regex backtracking when parsing parameter types
- Google: Parse docstrings that open with a section title (thanks to @HardMax71)
- Google: Compose a return with no type as just its description, instead of prefixing it with a colon that grew on every round trip
- Google: Keep relative indents and blank lines in a description, so literal blocks and nested admonitions survive
- Google: Parse a param type wrapped over three or more lines, as two lines already were, instead of keeping the whole declaration as the param name
- Google: Join an item head wrapped over several lines with spaces, instead of gluing words together as in `moreThe value`
- Google: End a param's type at its matching parenthesis
- Google: Keep every section when a title appears twice, instead of only the last one
- Google: Keep the words after a param's type, as in `x (int) more:`, as its new `extra`, instead of dropping them
- Google: Keep the text after a section, such as an example or an unknown section, in the long description instead of dropping it
- Google: Read a `Raises:` item that is a type alone, such as `ValueError`, and a `Raises:` section of plain prose as one raises with no type, instead of raising `ParseError`
- Google: Compose blank lines inside a section such as Examples without trailing spaces
- Google: Compose sections in the order of the docstring's items, and each return or yield in a section of its own, instead of in a fixed order with all returns in one, so a docstring with Raises before Returns, or with two Returns sections, reads back the same
- Google: Compose an empty Returns section as its title alone, and a raises with an empty description with a colon after its type, instead of text that reads back as a `:` description or none
- Google: Strip every space between an item's colon and its description, instead of keeping all but the first
- Numpydoc: Fix the type of `NumpydocParser`'s `sections` argument, which takes a list of sections
- Numpydoc: Compose sections such as See Also with their own titles and underlines, instead of e.g. `Seealso`
- Numpydoc: Stop adding a blank line on every round trip of a docstring without a long description
- Numpydoc: End a section at an underlined heading that no section declares, such as `See also` or `Options`, instead of reading the heading and its text as the section's items; the heading becomes a text meta with its `title`, which compose writes back
- Numpydoc: Stop ending a composed docstring with a blank line
- Numpydoc: Compose a blank line between the deprecation block and the long description, and no trailing spaces on its blank lines
- Numpydoc: End a deprecation directive at its indented body, so a long description written after it is no longer part of the deprecation
- Numpydoc: Parse examples sections in linear time instead of quadratic
- Numpydoc: Compose an optional param with no type as `x : optional`, which no longer reads back as a param named `x, optional`
- Numpydoc: Rebuild the reused default parser also when a section in `DEFAULT_SECTIONS` has its title changed in place
- Numpydoc: Compose raises written with another key, such as ReST's `:raise:` and `:except:`, instead of dropping them
- Numpydoc: Keep indented text before a section's first item in the long description instead of dropping it
- Numpydoc: Split a `Raises` or `Warns` item's head such as `ValueError : if bad.` after its type, taking `if bad.` as the start of the description, instead of making the whole line the type
- Numpydoc: Compose sections, examples and deprecations in the order of the docstring's items, instead of in a fixed order, so a docstring with Notes before Examples or a deprecation after its sections reads back the same, and compose every deprecation instead of only the first
- Numpydoc: Compose the blank lines after the short and long description as they were read, instead of always one before the first section, and keep the blank line between two examples
- Epydoc: Match fields only at their header, so field-like text in a description no longer replaces it and a header without its colon no longer stalls the parser (thanks to @akshitkhokhani)
- Epydoc: Take a param's key and kind from its `@param`, `@keyword` or `@ivar` field, instead of `type` when its `@type` field comes first
- Epydoc: Give a name described by two fields, such as `@param x:` and `@ivar x:`, an item for each instead of keeping the last
- Epydoc: Find a param's default in its own description also when its `@type` field comes first
- Epydoc: Take a return's key from its `@return` or `@yield` field, not from an `@rtype` or `@ytype` before it
- Epydoc: Read the field names Epydoc gives as synonyms: `@raises`, `@except` and `@exception` for `@raise`, `@returns` for `@return`, `@returntype` for `@rtype`, `@parameter`, `@arg` and `@argument` for `@param`, and `@kwarg` and `@kwparam` for `@keyword`
- Epydoc: Compose a param or return that only a type field gives as that field alone, instead of adding an empty `@param:` field, and keep a return with an empty description instead of dropping it
- Epydoc: Compose params, returns, yields, raises and the type fields of returns with the field name they were read from, such as `@arg`, `@kwarg`, `@returns`, `@raises` or `@returntype`
- ReST, Numpydoc: Read text after the fields of a docstring with no description as its description, instead of a long description that `compose()` starts with an empty line
- ReST, Epydoc: Compose each param with its kind's field name, such as `:keyword:` or `@ivar`, instead of `:param:` or `@param` for all
- ReST, Epydoc: Give each of a name's type fields to its next item, instead of the last overwriting the others
- Google, Numpydoc: Reuse the default parser between `parse()` calls instead of building a new one each time, making parsing about 30–50% faster
- Google, Numpydoc: Compose params of every kind, such as ReST's `:keyword:` or Numpydoc's other params, instead of dropping those with no section of their own
- Google, Numpydoc: Compose ReST's `:ivar:`, `:var:` and `:cvar:` fields as named attributes instead of a nameless section
- Google, Numpydoc: Match custom section titles literally, so titles with characters such as `?`, `+` or `(` work instead of being ignored or raising `re.error`
- Google, Numpydoc: Compose Epydoc's `@ivar`, `@cvar` and `@var` fields as attributes, instead of as params

# 0.18 (2026-04-14)

- General: Allow `parse()` to work with missing `__doc__` (thanks to @jamesbraza)
- General: Officially support Python 3.14 (thanks to @mauvilsa)
- General: Exclude `docstring_parser.tests` from built wheels (thanks to @gvalkov)
- Epydoc: Add missing attribute parsing, which includes the "@ivar", "@cvar" and "@var" syntax (thanks to @Masara)
- Numpydoc: Add support for defaults in type declarations and improve compose behavior (thanks to @jwlodek)

# 0.17 (2025-07-21)

- General: Replace poetry with hatchling (thanks to @LecrisUT)
- General: Drop support for Python 3.6 and 3.7 (thanks to @LecrisUT)
- General: Officially support Python 3.13 (thanks to @mauvilsa)
- General: Publish packages to PyPI with digital attestations (thanks to @mauvilsa)
- Google: Fix multi-line parameter definitions (thanks to @coolbeevip)
- Attrdoc: Remove use of deprecated ast classes (thanks to @fedepell)

# 0.16 (2024-03-15)

- Parser: add a new property, `description`, that combines short and long
  descriptions into a single string (thanks to @pR0Ps)
- General: support Python 3.12 (thanks to @mauvilsa)

# 0.15 (2022-09-05)

- Parser: add a new function, `parse_from_object`, that supports scattered
  docstrings (thanks to @mauvilsa)

# 0.14.1 (2022-04-27)

- Parser: fix autodetection (regression from 0.14)

# 0.14 (2022-04-25)

- Numpydoc: Improved support for Example / Examples section

# 0.13 (2021-11-17)

- Google: Added support for Example / Examples section

# 0.12 (2021-10-15)

- General: Added support for lone `:rtype:` meta information (thanks to @abergou)

# 0.11 (2021-09-30)

- General: Started tracking changes
- General: Added ability to combine function docstrings (thanks to @abergou)
- ReST: Added support for `:type:` and `:rtype:` (thanks to @abergou)
