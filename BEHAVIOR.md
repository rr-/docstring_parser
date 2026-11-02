# Parsing behavior with `legacy=False`

`docstring_parser` has two parsing modes. Pass `legacy=False` to `parse`,
`parse_from_object`, `combine_docstrings`, the per style `parse` functions or
`GoogleParser.parse` / `NumpydocParser.parse` to get the behavior described
here:

```python
from docstring_parser import parse

docstring = parse(text, legacy=False)
```

- **`legacy=True` (the default)** keeps the behavior of previous versions
  exactly. It is pinned by golden tests over a corpus of 3,180 real
  docstrings and changes only with deliberate fixes, so upgrading is safe.
- **`legacy=False`** uses a parser in which all styles share one set of
  rules. The rules are listed below. It requires Python 3.10 or newer, and
  raises `RuntimeError` on older versions. This will become the default in
  the next major version, and the legacy parsers will then be removed.

The data model doesn't change: you get the same `Docstring`,
`DocstringParam` and other classes, with the same attributes. What changes is
how text maps to them. Docstrings parsed with `legacy=False` have
`docstring.legacy == False`. That flag changes two things: `params` no longer
includes attributes, and `compose` renders the docstring with the new
composers.

## Guarantees

- **No text is silently dropped.** Text that is not part of a recognized
  section ends up in the descriptions.
- **Malformed docstrings don't raise.** You always get a result rather than a
  `ParseError`, keeping as much structure as can be recognized.
- **Composing round-trips.** `parse(compose(d), style, legacy=False)` gives
  back the same docstring as `d` for any docstring that was parsed in that
  style, in all rendering styles. This holds for every docstring in the corpus
  and is checked with property-based tests.

## Rules common to all styles

### Descriptions

- `short_description` is the **first paragraph**, meaning every line up to
  the first blank line. A summary wrapped over two lines is no longer cut in
  half. `long_description` is the rest of the free text.
- Free text after the sections is appended to `long_description` as a new
  paragraph. Examples are a `.. versionadded::` block after a field list, or
  a paragraph after a Google section. If there is no text before the
  sections, that text becomes the description.
- `blank_after_short_description` and `blank_after_long_description` tell
  whether a blank line separates that part from the next one. They are False
  when nothing follows.
- A missing description is `None`, never `""`.
- `\r\n` and `\r` line endings are treated as `\n`.

### Items

- The text of an item is its first line plus the following lines, dedented
  as a block, so relative indentation (code blocks, lists) is kept. Leading
  and trailing blank lines are removed. Empty text is `None`.
- `args[0]` is a **canonical key**, the same in every style:

  | Key | Class | Comes from |
  | --- | --- | --- |
  | `param` | `DocstringParam` | `:param:`, `:parameter:`, `:arg:`, `:key:`, `Args:`, `Parameters`, `@param`... |
  | `keyword` | `DocstringParam` | `:keyword:`, `:kwarg:`, `Keyword Args:`, `@keyword` |
  | `other_param` | `DocstringParam` | `Other Parameters` |
  | `receives` | `DocstringParam` | `Receives` |
  | `attribute` | `DocstringParam` | `:ivar:`, `:var:`, `:cvar:`, `Attributes`, `@ivar`... |
  | `returns` / `yields` | `DocstringReturns` | `:returns:`, `Returns:`, `@return`... |
  | `raises` / `warns` | `DocstringRaises` | `:raises:`, `Raises:`, `Warns`, `@raise`... |
  | `examples` | `DocstringExample` | `Examples` sections |
  | `deprecation` | `DocstringDeprecated` | `.. deprecated::`, `@deprecated` |

  Other sections and fields keep their own key, for example `notes`,
  `see_also` or `meta`.
- `args[1:]` holds the parameter's name, or the exception type, never raw
  header text: `["param", "x"]` instead of `["param", "x (int)"]`.
- Several names in one header (`x, y : int` or `x, y (int):`) give one item
  per name, with the same type and description. `...` counts as a name, as in
  sphinx.ext.napoleon: `arg1, arg2, ...` gives the items `arg1`, `arg2` and
  `...`.
- Backslashes escaping reST markup are removed from names in every style:
  `\*\*kwargs` becomes `**kwargs` and `class\_` becomes `class_`.

### Parameters and attributes

- Attributes (`args[0] == "attribute"`) are not in `Docstring.params`. Use
  `Docstring.attributes` or `DocstringParam.is_attribute`. Both also work in
  legacy mode, where `params` still includes attributes.
- `parse_from_object` doesn't duplicate attributes that the docstring already
  documents, and it cleans the descriptions of attribute docstrings the same
  way as other docstrings.

### Types, optional and defaults

The type specification is the part in parentheses (Google), after ` : `
(numpydoc), in the field name or in a `:type:` field (reST), or in `@type`
(epydoc). It is split on commas that are not inside brackets or quotes:

- The parts `optional` (case-insensitive, also emphasized as `*optional*`)
  and `(optional)`, and parts ending in `?`, mark the item as optional.
- The parts `default X`, `default=X`, `default: X`, `default is X`,
  `defaults to X` and `defaults X` give the default `X`. Surrounding
  backticks are removed from `X`.
- The remaining parts make up `type_name`, with whitespace normalized:
  `int, optional, default: 3` gives type `int`, optional, default `3`.

If the specification has no default, the description is searched for
`defaults to X`, `default is X`, `default value is X`, `default: X` or
`default=X`, case-insensitively. `X` is only taken when it is a single value:
a literal, a name, or a quoted or bracketed expression. It may be followed by
a condition starting with `if`, `when` or `unless`. Surrounding backticks are
removed.

| Description | `default` |
| --- | --- |
| `Defaults to 3.` | `3` |
| `Value (default: 3).` | `3` |
| ``Defaults to ``None``, meaning all.`` | `None` |
| `Defaults to os.getcwd().` | `os.getcwd()` |
| `Defaults to 3 if unset.` | `3` |
| `The default is to use all of them.` | `None` |
| `By default, nothing.` | `None` |

`is_optional` is True when the item is marked optional or has a default, and
False otherwise. It is never `None`.

### Deprecations

A `.. deprecated:: <version>` directive at the start of a line in the free
text (reST, Google and numpydoc) gives a `DocstringDeprecated` item. The
indented content is its description, and the directive is removed from the
descriptions. Every directive gives an item. In epydoc, `@deprecated: <version>
<text>` does the same.

### Examples

An examples section is split into `DocstringExample` items the way doctest
reads it. Each one holds the text that introduces it (`description`) and a
snippet: the `>>>` lines with their `...` continuations, followed by the
expected output up to a blank line or the next `>>>` line. Text after the
last snippet is an example without a snippet. Google and numpydoc follow the
same rule.

```text
To print the number 1:      <- description

>>> print(1)                <- snippet
1                           <- snippet (output)
```

### Style detection

`DocstringStyle.AUTO` parses with every style and keeps the result with the
most items. Ties go to reST, Google, numpydoc and epydoc, in that order, so
text in which no line could start a field or section is parsed once, as reST.
On the corpus this picks the declared style for 2,304 of the 2,308 docstrings
that have items.

## Style specific rules

### Google

- A section starts with a line at column 0 holding a known title and a colon.
  Titles are case-insensitive. The default titles follow
  `sphinx.ext.napoleon`: `Args`, `Arguments`, `Parameters`, `Params`,
  `Keyword Args`, `Keyword Arguments`, `Other Parameters`, `Receives`,
  `Attributes`, `Raises`, `Exceptions`, `Warns`, `Returns`, `Yields`,
  `Example(s)`, `Methods`, `Note(s)`, `Warning(s)`, `See Also`, `References`,
  `Todo`, `Attention`, `Caution`, `Danger`, `Error`, `Hint`, `Important` and
  `Tip`. Custom `GoogleParser` sections and sections added to
  `DEFAULT_SECTIONS` are honored.
- The section's content is the indented block that follows. A line at
  column 0 that is not a title ends the section and is free text. Unknown
  titles such as `Usage:` are free text too, and so is a known title with no
  indented content (an `Example:` followed by an unindented
  `.. testcode::`), the way sphinx.ext.napoleon renders it.
- A docstring may start with a section title (`"""Args:`).
- In `Args`-like sections, an item header looks like `name (type): text`. The
  type and the text are optional, and a bare `name` is also an item. A line
  at the item level that doesn't look like a header, such as a wrapped line
  that wasn't indented, continues the previous item instead of becoming a
  bogus parameter.
- A header must be complete on its line: balanced parentheses, and the colon
  if text follows. So `name (type). text`, `name (type) text` or a type that
  wraps onto the next line are not headers; they continue the previous item,
  or give an item without name at the start of a section. No text is lost.
  sphinx.ext.napoleon is more lenient here, but that also makes it take
  wrapped prose, such as `the value (see below) is used`, as parameters.
- `Raises` items are `Type: text`, or just `Type`. A `Raises` section that is
  only prose gives one item without a type.
- `Returns` / `Yields` hold one item: `type: text`, `name (type): text` or
  just text. What precedes the colon is only taken as a type if it looks like
  one: balanced, not a sentence, and at most three words besides `of`, `or`
  and `|`. So `list of str: Names.` has a type and `The value: a number.`
  doesn't.

### Numpydoc

- A section is a title line followed by an underline of at least three `-`
  or `=`. Its length doesn't need to match the title, and titles are
  case-insensitive (`See also`).
- Underlined headings before the first recognized section belong to the
  description. After it, every underlined heading starts a section, and
  unrecognized ones give items keyed by the title (`Custom Title` gives
  `custom_title`) instead of being absorbed into the previous section.
- `Methods` sections are recognized: each method signature at column 0
  gives a `DocstringMeta` with `args == ["methods", "<signature>"]`, as in
  Google style. Custom sections passed to `NumpydocParser` replace this.
- Each line at column 0 in a section starts an item. `name : type` is split
  at the first colon followed by whitespace that is not inside brackets or
  quotes, so roles like `` :class:`numpy.ndarray` `` and `::` are not split.
- In `Raises` and `Warns`, an item header `Type : text` (or `Type: text`)
  gives the type and the start of the description, as in sphinx.ext.napoleon.
  This only applies if what precedes the colon looks like a type.
- Custom `Section` subclasses are parsed with their own `parse` method.

### reST

- A field is a line at column 0 like `:name args: text`. The closing colon
  must be followed by whitespace or the end of the line, as in docutils, so a
  line that starts with a role (`` :meth:`run` does... ``) is text, not a
  field.
- A field's text continues with the indented lines that follow, and with
  unindented lines that are not separated from it by a blank line. A blank
  line followed by unindented text ends the field list.
- `:param Dict[str, int] x:` gives a type with spaces. `:type x:` without
  `:param x:` still creates the parameter. `:ivar:`/`:var:`/`:cvar:` with
  `:vartype:` give attributes. `:raises A, B:` gives the type `A, B`. Empty
  `:type:`/`:rtype:` fields are ignored.

### Epydoc

- Fields are `@name args: text` at the start of a line, never in the middle
  of text.
- `@type` applies to parameters and variables. `@rtype` and `@returntype`
  apply to `@return`. `@raise`/`@raises` give `DocstringRaises` and
  `@return`/`@returns` give `DocstringReturns`.

## Composing

`compose` uses new composers for docstrings parsed with `legacy=False`:

- Items are rendered in their order in `meta`, and consecutive items with the
  same key share a section.
- Attributes, keyword arguments, other parameters, warnings, deprecations
  (as `.. deprecated::` directives) and example snippets are all rendered.
  The legacy composers drop some of these.
- Optional parameters are written as `, optional` instead of `?`. A default
  is written in the type only when the description doesn't already state it.
- Rendering styles: `EXPANDED` puts item descriptions on their own lines (and
  reST types in `:type:` fields). `COMPACT` and `CLEAN` keep them on the
  header line where that is possible without losing indentation.
- reST parameter names are escaped where docutils would read markup:
  `**kwargs` is written `\*\*kwargs` and `class_` is written `class\_`.

Docstrings created by hand have `legacy == True` and use the legacy
composers. Set `docstring.legacy = False` to use the new ones.

One case can't round-trip: a Google description whose first line is a
section title, as left by a title without content at the start. Composed,
it reads as a section.

## Differences from legacy, at a glance

| Input | Legacy | `legacy=False` |
| --- | --- | --- |
| Summary wrapped over two lines | Cut after the first line | Whole first paragraph |
| Google: unindented text inside `Args:` | Text and later items dropped | Kept in the description |
| Google: `Note:`, `See Also:`, `Keyword Args:`... | Dropped | Items |
| Google: `ARGS:`, `Raises:` with bare `ValueError` | Ignored / `ParseError` | Items |
| Google: `x (int): Defaults to 3.` | No default | `default="3"`, optional |
| Google: `args` of `x (int):` | `["param", "x (int)"]` | `["param", "x"]` |
| reST: line starting with `` :meth:`run` `` | Field `meth`, description cut | Text |
| reST: `:param Dict[str, int] x:` | `ParseError` | Type `Dict[str, int]` |
| reST: `:ivar a:` + `:vartype a:` | Two generic items | One attribute with a type |
| Numpydoc: underline shorter than the title | Section not found | Section |
| Numpydoc: `See also` heading after `Returns` | Fake return items | `see_also` item |
| Numpydoc: `int, optional, default 3` | Type `int, optional` | Type `int` |
| Numpydoc: `By default the value...` | `default="the"` | No default |
| Numpydoc: `x, y : int` | One parameter `"x, y"` | Two parameters |
| Numpydoc: `Attributes` | Included in `params` | Only in `attributes` |
| Examples | Snippet paired with the text after it | Text before the snippet; output is part of the snippet |
| Doctest `...` continuation lines | Moved to the description | Part of the snippet |
| Google: `Example:` with unindented content | Line dropped | Kept as text |
| Numpydoc: `Methods` | Long description text | One item per method |
| Epydoc: `@raises`, `@returns` | Generic items | `DocstringRaises`, `DocstringReturns` |
| `.. deprecated::` in Google/reST | Left in the description | `DocstringDeprecated` |
| `is_optional` without a type | `None` | `False` |
| Empty description | `""` | `None` |

## Testing

- `docstring_parser/tests/corpus/docstrings.json` holds the corpus, built by
  `scripts/build_corpus.py` from numpy, scipy, pandas, scikit-learn,
  matplotlib, jax, keras, rich, absl, google-auth, transformers, PyTorch,
  requests, werkzeug, click, SQLAlchemy, boto3, sphinx, twisted, pydoctor and
  the standard library.
- `test_corpus.py` compares the results of both modes with
  `expected_legacy.json.gz` and `expected.json.gz`. The legacy file
  changes only with a deliberate fix to a legacy parser. To change either
  behavior on purpose, run `uv run python scripts/golden_diff.py` (with
  `--legacy` for the legacy results) to review the differences, then
  `uv run pytest docstring_parser/tests/test_corpus.py --update-golden`.
- `test_new_behavior.py` tests the rules above, mostly parametrized over
  styles.
- `test_properties.py` checks with Hypothesis that only `ParseError` is
  raised, and that composing round-trips. Set `HYPOTHESIS_PROFILE=thorough`
  for a long randomized run.
