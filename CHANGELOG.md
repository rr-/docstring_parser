# Unreleased

- Google: Parse PEP 604 union types (e.g. `int | str`) in return sections (thanks to @binggao1230)
- Google: Avoid regex backtracking when parsing parameter types
- Google: Parse docstrings that open with a section title (thanks to @HardMax71)
- ReST: Stop the last field from absorbing text after the field list; that text now goes to the long description (thanks to @apoorvdarshan)
- Epydoc: Match fields only at their header, so field-like text in a description no longer replaces it and a header missing its colon no longer stalls the parser (thanks to @akshitkhokhani)
- General: Replace pylint, black and isort with ruff, and pre-commit with prek
- General: Check commit messages for a `scope: description` subject and the 50/72 rule
- General: Replace pip, venv and hatchling with uv; development dependencies are now dependency groups instead of extras
- General: Add a justfile for common development tasks
- General: Type-check with ty
- General: `compose()` raises `ValueError` instead of `KeyError` when the docstring has no style and none is given
- Numpydoc: Fix the type of `NumpydocParser`'s `sections` argument, which takes a list of sections
- Google, Numpydoc: `compose()` keeps params of every kind, such as ReST's `:keyword:` or Numpydoc's other params, instead of dropping those it has no section for
- Google, Numpydoc: `compose()` writes ReST's `:ivar:`, `:var:` and `:cvar:` fields as named attributes instead of a nameless section

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
