# Unreleased

- Google: Parse PEP 604 union types (e.g. `int | str`) in return sections (thanks to @binggao1230)
- Google: Avoid regex backtracking when parsing parameter types
- Google: Parse docstrings that open with a section title (thanks to @HardMax71)
- Google: `compose()` writes a return with no type as just its description, instead of prefixing it with a colon that grew on every round trip
- Google: Keep the indent of a description's continuation lines relative to each other, and the blank lines between them, so literal blocks and nested admonitions survive; `compose()` starts such a description on its own line
- Google: Parse a param type wrapped over three or more lines, as two lines already were, instead of keeping the whole declaration as the param name
- Google: Join an item head wrapped over several lines with spaces, instead of gluing words together as in `moreThe value`, and end a param's type at its matching parenthesis
- Google: Keep every section when a title appears twice, instead of only the last one
- ReST: Stop the last field from absorbing text after the field list; that text now goes to the long description (thanks to @apoorvdarshan)
- ReST: Raise `ParseError` instead of `IndexError` for a field with no name
- ReST: `compose()` indents continuation lines in compact mode, so one starting with a role such as `:class:` is no longer read back as a new field
- ReST: `compose()` writes a type with a space or a colon in it, such as `float or tuple`, as a `:type:` or `:rtype:` field of its own, instead of a field name that fails to parse
- ReST: End a `:type:` or `:rtype:` field at the next unindented line, which goes to the long description instead of into the type
- ReST: Keep the blank lines and relative indents in a field's description, so its paragraphs and literal blocks survive; `compose()` starts such a description on its own line
- Epydoc: Match fields only at their header, so field-like text in a description no longer replaces it and a header missing its colon no longer stalls the parser (thanks to @akshitkhokhani)
- Epydoc: Take a param's kind in `args[0]` from its `@param`, `@keyword` or `@ivar` field, instead of `type` when its `@type` field comes first
- Google, Numpydoc: Reuse the default parser between `parse()` calls instead of building a new one each time, making parsing about 30–50% faster
- General: Parse docstrings with `\r\n` or `\r` line endings the same as with `\n`, on every Python version
- General: Strip the short description, which kept leading spaces when a later line was indented less than it
- General: Auto-detection parses a docstring with no fields or sections once instead of four times, making it about 47% faster
- General: Snapshot-test the parsers on 1100 docstrings from real projects, kept as text case files
- General: Replace pylint, black and isort with ruff, and pre-commit with prek
- General: Check commit messages for a `scope: description` subject and the 50/72 rule
- General: Replace pip, venv and hatchling with uv; development dependencies are now dependency groups instead of extras
- General: Add a justfile for common development tasks
- General: Type-check with ty
- General: `compose()` raises `ValueError` instead of `KeyError` when the docstring has no style and none is given
- Numpydoc: Fix the type of `NumpydocParser`'s `sections` argument, which takes a list of sections
- Numpydoc: `compose()` writes sections such as See Also with their own titles and underlines, instead of e.g. `Seealso`
- Numpydoc: `compose()` no longer adds a blank line on every round trip of a docstring without a long description
- Numpydoc: `compose()` no longer ends the docstring with a blank line
- Numpydoc: `compose()` separates the deprecation block from the long description with a blank line, and no longer leaves trailing spaces on its blank lines
- Numpydoc: A deprecation directive ends at its indented body, so a long description written after it is no longer parsed as part of the deprecation
- Google, Numpydoc: `compose()` keeps params of every kind, such as ReST's `:keyword:` or Numpydoc's other params, instead of dropping those it has no section for
- Google, Numpydoc: `compose()` writes ReST's `:ivar:`, `:var:` and `:cvar:` fields as named attributes instead of a nameless section
- Numpydoc: Parse examples sections in linear time instead of quadratic
- Numpydoc: Read a default from the description only after `default is`, `default:`, `default=` or `defaults to`, instead of taking the word after any `default`, as in `the default engine` or `by default only`
- Numpydoc: Take `optional` out of a param's type also when it comes before the default, as in `int, optional, default 1`, instead of keeping it in the type and composing it twice
- Google, Numpydoc: Match custom section titles literally, so titles with characters such as `?`, `+` or `(` work instead of being ignored or raising `re.error`

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
