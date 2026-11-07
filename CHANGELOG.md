# Unreleased

- General: **Breaking:** Remove `DocstringMeta.args`; use the new `key`, `name` and `kind`
- General: **Breaking:** Read the `common` keyword sets once on import; pass `sections` instead
- General: **Breaking:** Make `DocstringStyle` values the style names, such as `"google"`
- General: **Breaking:** Move attributes from `Docstring.params` to the new `Docstring.attrs`
- General: **Breaking:** Move yields from `returns` and `many_returns` to `yields` and `many_yields`
- General: **Breaking:** Make a parsed param's `is_optional` always a bool
- General: **Breaking:** Give an item with no description `None`, never `""`
- General: **Breaking:** Read the whole first paragraph as the short description
- Google, Numpydoc: **Breaking:** Remove customising by overriding internals; use `SectionSpec` instead
- Google, Numpydoc: **Breaking:** Split examples as doctest does, into `description` and `snippet`
- General: Parse `\r\n` and `\r` line endings the same as `\n`
- General: Dedent docstrings and their items the same on every Python version
- General: Strip leading spaces from the short description
- General: Quote at most 60 characters of the text a `ParseError` points at
- General: Auto-detect docstrings with no fields or sections about 47% faster
- General: Raise `ValueError`, not `KeyError`, from `compose()` when no style is known
- General: Stop `combine_docstrings` from taking a same-named attribute as a param
- General: Give every meta a `kind` that tells what it documents
- General: Compose items by `kind`, so hand-made metas may need `kind=`
- General: Add `docstring_parser.sections`, whose `SectionSpec` declares sections for any style
- General: Add `SectionSpec(bare=True)` for a title with no colon or underline
- General: Add `SectionSpec(parse_item=...)` to change or replace each parsed item
- General: Add a `Parser` to each style module and `auto`, taking `sections` once
- General: Keep `GoogleParser` and `NumpydocParser` as aliases of the new parsers
- General: Accept a style name, such as `"google"`, or a parser in `parse()` and `compose()`
- General: Add `try_parse()`, which returns the docstring and its problems instead of raising
- General: Give `ParseError` all the docstring's `problems` and the partial `result`
- General: Show only the fields that are set in a docstring's or meta's `repr()`
- General: Read optional marks and defaults in types by one rule in every style
- General: Take a default stated in a param's description, and make the param optional
- General: Add `raw_type_name` to params, the type as written
- General: Keep class attributes named like a param in `parse_from_object()`
- General: Handle built-ins and a non-string `__doc__` in `parse_from_object()` without raising
- General: Keep the long description's first-line indent, so indented blocks keep their shape
- General: Treat a line of only a tab or form feed at either end as blank
- General: Compose a param's type as written, such as `int, optional`
- General: Compose docstrings so they parse back the same
- General: Unescape names in every style, such as `\*\*kwargs` or `class\_`
- General: Make each run of whitespace in a type one space
- General: Clean attribute docstrings in `parse_from_object()` as other docstrings
- ReST: Stop the last field from absorbing text after the field list (thanks to @apoorvdarshan)
- ReST: Raise `ParseError`, not `IndexError`, for a field with no name
- ReST: Indent compact continuation lines so a leading role isn't read as a field
- ReST: Compose a type such as `float or tuple` so it parses back
- ReST: End a `:type:` or `:rtype:` field at the next unindented line
- ReST: Keep blank lines and relative indents in field descriptions
- ReST: Keep `:type x:` and `:rtype name:` fields that describe nothing else
- ReST: Read `:ivar:`, `:var:` and `:cvar:` as attributes typed by `:vartype:`
- ReST: Read an empty `:type x:` as no type
- ReST: Compose and read a return's name through `:rtype name:`
- ReST: Read and compose `:ytype:` as the type of the yields
- ReST: Parse `.. attribute::` directives, with `:type:` and `:value:`, as attributes
- ReST: Read types with spaces in field heads, such as `:param int or None x:`
- ReST: Read a line starting with a role, such as `:meth:`, as text
- ReST: Keep every line of a `:deprecated:` field that starts with a version
- ReST: Keep a type field for a param or return that already has a type
- ReST: Compose type fields, field names, versions and attribute values that read back
- ReST: Compose raises as `:raises ValueError:`, with no space before the colon (thanks to @RavSinghChandan)
- ReST: Read `:param \*\*kwargs:` as `**kwargs`, and escape names on compose
- ReST: Unescape types and `.. attribute::` names, and escape a trailing `_`
- ReST: Read `:key:` as a param, and `:kwarg:` and `:kwparam:` as keywords
- ReST: Ignore an empty `:rtype:` or `:ytype:` instead of giving an empty type
- Google: Parse union return and yield types such as `dict[str, int] | None` (thanks to @binggao1230)
- Google: Parse param types without slow regex backtracking
- Google: Parse docstrings that open with a section title (thanks to @HardMax71)
- Google: Compose an untyped return without a colon that grew each round trip
- Google: Keep relative indents and blank lines in descriptions
- Google: Parse param types wrapped over three or more lines
- Google: Join wrapped item heads with spaces instead of gluing words together
- Google: End a param's type at its matching parenthesis
- Google: Keep every section when a title appears twice
- Google: Keep the words after a param's type, as in `x (int) more:`, as `extra`
- Google: Keep text after a section in the long description
- Google: Read a type-only or prose `Raises:` item instead of raising `ParseError`
- Google: Compose blank lines in sections such as Examples without trailing spaces
- Google: Strip every space between an item's colon and its description
- Google: Compose sections in the items' order, one per return
- Google: Make a param optional when its type says `(optional)` or a default
- Google: Read bare param names, unindented wrapped lines and colons in types
- Google: Read a short return type, such as `list of str:`, as the type
- Google: Read a return's `name (type): text` head as its name and type
- Numpydoc: Fix the type hint of `NumpydocParser`'s `sections` argument
- Numpydoc: Compose sections such as See Also with their own titles
- Numpydoc: Stop adding a blank line each round trip without a long description
- Numpydoc: End a section at an unknown underlined heading, kept as titled text
- Numpydoc: Stop ending a composed docstring with a blank line
- Numpydoc: Compose a blank line after the deprecation block, without trailing spaces
- Numpydoc: End a deprecation directive at its indented body
- Numpydoc: Parse examples sections in linear time instead of quadratic
- Numpydoc: Compose an untyped optional param as `x : optional`, which reads back
- Numpydoc: Rebuild the default parser when a `DEFAULT_SECTIONS` title changes in place
- Numpydoc: Compose raises written as ReST's `:raise:` or `:except:` instead of dropping them
- Numpydoc: Keep indented text before a section's first item in the long description
- Numpydoc: Split a `Raises` or `Warns` head such as `ValueError : if bad.` after its type
- Numpydoc: Compose sections and deprecations in the items' order
- Numpydoc: Accept a title underline of `-` or `=` signs, at least 3 by default
- Numpydoc: Report a short underline as `bad-underline`; set `min_underline` or `exact_underline`
- Numpydoc: Keep text before a section's first item apart from the summary when read back
- Epydoc: Match fields only at line starts, and stop hanging on colonless headers (thanks to @akshitkhokhani)
- Epydoc: Take a param's key and kind from its own field, not an earlier `@type`
- Epydoc: Give a name described by two fields an item for each
- Epydoc: Find a param's default in its description when `@type` comes first
- Epydoc: Take a return's key from `@return` or `@yield`, not an earlier `@rtype`
- Epydoc: Read Epydoc's synonym field names, such as `@raises`, `@arg` and `@kwarg`
- Epydoc: Keep the indent of a field's first continuation line
- Epydoc: Compose type fields and field names, such as `@arg`, that read back
- Epydoc: Read `@deprecated` as a deprecation, and compose it with its version
- Epydoc: Keep blank lines in a field's description
- ReST, Numpydoc: Read text after the fields as the description when there is none
- ReST, Epydoc: Compose each param with its kind's field, such as `:keyword:` or `@ivar`
- ReST, Epydoc: Give each of a name's repeated type fields to its next item
- Google, Numpydoc: Reuse the default parser between `parse()` calls, about 30–50% faster
- Google, Numpydoc: Compose params of every kind instead of dropping those without a section
- Google, Numpydoc: Compose ReST's `:ivar:` and Epydoc's `@ivar` fields as attributes
- Google, Numpydoc: Match custom section titles literally, so `?`, `+` or `(` work
- Google, Numpydoc: Match section titles in any case, such as `ARGS:`
- Google, Numpydoc: Read napoleon's other sections, such as `Keyword Args` and `Todo` (thanks to @BrianPugh)
- Google, Numpydoc: Give each name in `x, y : int` its own param
- Google, Numpydoc: Read `...` as a name, as in `arg1, arg2, ...`

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
- Google: Read and compose `.. deprecated::` directives with their version

# 0.12 (2021-10-15)

- General: Added support for lone `:rtype:` meta information (thanks to @abergou)

# 0.11 (2021-09-30)

- General: Started tracking changes
- General: Added ability to combine function docstrings (thanks to @abergou)
- ReST: Added support for `:type:` and `:rtype:` (thanks to @abergou)
- ReST: Read and compose `.. deprecated::` directives with their version
