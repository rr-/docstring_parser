"""Tests for the behavior of ``legacy=False``, as documented in BEHAVIOR.md.

Most rules apply to every style, so tests are parametrized over equivalent
docstrings written in each style.
"""

import typing as T

import pytest

from docstring_parser import (
    Docstring,
    DocstringDeprecated,
    DocstringParam,
    DocstringStyle,
    ParseError,
    RenderingStyle,
    compose,
    google,
    parse,
    parse_from_object,
)
from docstring_parser.common import DocstringExample, DocstringMeta
from docstring_parser.google import GoogleParser, Section, SectionType
from docstring_parser.numpydoc import NumpydocParser
from docstring_parser.numpydoc import Section as NumpySection
from docstring_parser.tests._serialize import docstring_to_dict
from docstring_parser.util import combine_docstrings

REST = DocstringStyle.REST
GOOGLE = DocstringStyle.GOOGLE
NUMPYDOC = DocstringStyle.NUMPYDOC
EPYDOC = DocstringStyle.EPYDOC


def new(text: str, style: DocstringStyle = DocstringStyle.AUTO) -> Docstring:
    """Parse without legacy behavior."""
    return parse(text, style, legacy=False)


def meta_summary(docstring: Docstring) -> T.List[T.Tuple[T.Any, ...]]:
    """Summarize items as (class name, args, description)."""
    return [
        (type(item).__name__, item.args, item.description)
        for item in docstring.meta
    ]


# Descriptions

SUMMARY_DOCSTRINGS = {
    REST: """
        Summary that is
        wrapped.

        Long description.

        :param x: Value.
        """,
    GOOGLE: """
        Summary that is
        wrapped.

        Long description.

        Args:
            x: Value.
        """,
    NUMPYDOC: """
        Summary that is
        wrapped.

        Long description.

        Parameters
        ----------
        x
            Value.
        """,
    EPYDOC: """
        Summary that is
        wrapped.

        Long description.

        @param x: Value.
        """,
}


@pytest.mark.parametrize("style", list(SUMMARY_DOCSTRINGS))
def test_summary_is_first_paragraph(style: DocstringStyle) -> None:
    """The short description is the whole first paragraph."""
    docstring = new(SUMMARY_DOCSTRINGS[style], style)
    assert docstring.short_description == "Summary that is\nwrapped."
    assert docstring.long_description == "Long description."
    assert docstring.blank_after_short_description
    assert docstring.blank_after_long_description
    assert docstring.description == (
        "Summary that is\nwrapped.\n\nLong description."
    )
    assert docstring.params[0].description == "Value."


@pytest.mark.parametrize("style", list(SUMMARY_DOCSTRINGS))
def test_empty_docstring(style: DocstringStyle) -> None:
    """Missing parts are None and flags are False."""
    for text in (None, "", "   \n  "):
        docstring = new(text, style)  # type: ignore
        assert docstring.short_description is None
        assert docstring.long_description is None
        assert not docstring.blank_after_short_description
        assert not docstring.blank_after_long_description
        assert not docstring.meta
        assert not docstring.legacy


def test_flags_without_meta() -> None:
    """Blank flags only tell what separates parts that exist."""
    docstring = new("Short.\n\nLong.\n\n")
    assert docstring.blank_after_short_description
    assert not docstring.blank_after_long_description
    assert not new("Short.").blank_after_short_description


TRAILING_TEXT = {
    REST: """
        Summary.

        :param x: Value.

        .. versionadded:: 1.0
        """,
    GOOGLE: """
        Summary.

        Args:
            x: Value.

        .. versionadded:: 1.0
        """,
    EPYDOC: """
        Summary.

        @param x: Value.

        .. versionadded:: 1.0
        """,
}


@pytest.mark.parametrize("style", list(TRAILING_TEXT))
def test_text_after_sections_is_kept(style: DocstringStyle) -> None:
    """Free text after the sections ends them and joins the description."""
    docstring = new(TRAILING_TEXT[style], style)
    assert docstring.short_description == "Summary."
    assert docstring.long_description == ".. versionadded:: 1.0"
    assert len(docstring.params) == 1
    assert docstring.params[0].description == "Value."


def test_text_after_sections_without_description() -> None:
    """Free text after the sections makes up a missing description."""
    docstring = new("Args:\n    x: Value.\n\nSummary.\n\nLong.", GOOGLE)
    assert docstring.short_description == "Summary."
    assert docstring.long_description == "Long."


# Types, optional and defaults

SPEC_DOCSTRINGS = {
    REST: ":param x: Value.\n:type x: {spec}",
    GOOGLE: "Args:\n    x ({spec}): Value.",
    NUMPYDOC: "Parameters\n----------\nx : {spec}\n    Value.",
    EPYDOC: "@param x: Value.\n@type x: {spec}",
}

SPECS = [
    ("int", ("int", False, None)),
    ("int, optional", ("int", True, None)),
    ("int, Optional", ("int", True, None)),
    ("int?", ("int", True, None)),
    ("int (optional)", ("int", True, None)),
    ("`int`, *optional*", ("`int`", True, None)),
    ("int, **optional**", ("int", True, None)),
    ("optional", (None, True, None)),
    ("int, default 3", ("int", True, "3")),
    ("int, default=3", ("int", True, "3")),
    ("int, default: 3", ("int", True, "3")),
    ("int, defaults None", ("int", True, "None")),
    ("`int`, *optional*, defaults to 42", ("`int`", True, "42")),
    ("`bool`, defaults to `True`", ("`bool`", True, "True")),
    ("int, optional, default: 3", ("int", True, "3")),
    ("{'a', 'b'}, default='a'", ("{'a', 'b'}", True, "'a'")),
    ("Dict[str, int], optional", ("Dict[str, int]", True, None)),
    ("int or None, default ``None``", ("int or None", True, "None")),
]


@pytest.mark.parametrize("style", list(SPEC_DOCSTRINGS))
@pytest.mark.parametrize("spec,expected", SPECS)
def test_type_spec(
    style: DocstringStyle,
    spec: str,
    expected: T.Tuple[T.Optional[str], bool, T.Optional[str]],
) -> None:
    """Type specifications are understood the same way in every style."""
    param = new(SPEC_DOCSTRINGS[style].format(spec=spec), style).params[0]
    assert (param.type_name, param.is_optional, param.default) == expected


DESCRIPTION_DOCSTRINGS = {
    REST: ":param x: {desc}",
    GOOGLE: "Args:\n    x: {desc}",
    NUMPYDOC: "Parameters\n----------\nx\n    {desc}",
    EPYDOC: "@param x: {desc}",
}

DESCRIPTIONS = [
    ("Value.", None),
    ("Value. Defaults to 3.", "3"),
    ("Value. defaults to 0.5.", "0.5"),
    ("Value (default: 3).", "3"),
    ("Value, default=``True``.", "True"),
    ("Value. Default is 'utf-8'.", "'utf-8'"),
    ("Value. The default value is [1, 2].", "[1, 2]"),
    ("Value. Defaults to `None`, meaning all.", "None"),
    ("Value. Defaults to os.getcwd().", "os.getcwd()"),
    ("Value. Defaults to 3 if unset.", "3"),
    ("Value. Defaults to 'a b'.", "'a b'"),
    ("Defaults to 3.", "3"),
    ("Value. The default is to use all of them.", None),
    ("Value. Defaults to the current directory.", None),
    ("Value. By default, nothing.", None),
]


@pytest.mark.parametrize("style", list(DESCRIPTION_DOCSTRINGS))
@pytest.mark.parametrize("desc,default", DESCRIPTIONS)
def test_default_in_description(
    style: DocstringStyle, desc: str, default: T.Optional[str]
) -> None:
    """Defaults stated in descriptions are found the same way everywhere."""
    param = new(DESCRIPTION_DOCSTRINGS[style].format(desc=desc), style)
    param = param.params[0]
    assert param.default == default
    assert param.is_optional is (default is not None)
    assert param.description == desc


def test_default_in_spec_wins() -> None:
    """A default in the type specification wins over the description."""
    param = new(
        "x : int, default 1\n    Defaults to 2.".join(
            ["Parameters\n----------\n", ""]
        ),
        NUMPYDOC,
    ).params[0]
    assert param.default == "1"


# Names and keys


def test_several_names_give_several_params() -> None:
    """``x, y`` documents two parameters with the same type and text."""
    for text, style in [
        ("Parameters\n----------\nx, y : int\n    Coordinates.", NUMPYDOC),
        ("Args:\n    x, y (int): Coordinates.", GOOGLE),
    ]:
        params = new(text, style).params
        assert [p.arg_name for p in params] == ["x", "y"]
        assert all(p.type_name == "int" for p in params)
        assert all(p.description == "Coordinates." for p in params)


def test_ellipsis_is_a_name() -> None:
    """``arg1, arg2, ...`` gives an item per name, ``...`` included."""
    for text, style in [
        ("Parameters\n----------\narg1, arg2, ... : int\n    Args.", NUMPYDOC),
        ("Args:\n    arg1, arg2, ... (int): Args.", GOOGLE),
    ]:
        params = new(text, style).params
        assert [p.arg_name for p in params] == ["arg1", "arg2", "..."]
    assert not new("Args:\n    x: X.\n    ...", GOOGLE).params[1:]


ESCAPED_DOCSTRINGS = {
    REST: ":param \\*args: A.\n:param \\*\\*kwargs: B.\n:param class\\_: C.",
    GOOGLE: "Args:\n    \\*args: A.\n    \\*\\*kwargs: B.\n    class\\_: C.",
    NUMPYDOC: (
        "Parameters\n----------\n\\*args\n    A.\n\\*\\*kwargs\n    B.\n"
        "class\\_\n    C."
    ),
    EPYDOC: "@param \\*args: A.\n@param \\*\\*kwargs: B.\n@param class\\_: C.",
}


@pytest.mark.parametrize("style", list(ESCAPED_DOCSTRINGS))
def test_escaped_names(style: DocstringStyle) -> None:
    """Backslashes escaping reST markup are removed from names."""
    params = new(ESCAPED_DOCSTRINGS[style], style).params
    assert [p.arg_name for p in params] == ["*args", "**kwargs", "class_"]


def test_rest_compose_escapes_names() -> None:
    """Composed reST escapes what docutils would read as markup in names."""
    docstring = new(ESCAPED_DOCSTRINGS[REST], REST)
    assert compose(docstring) == ESCAPED_DOCSTRINGS[REST]


CANONICAL = {
    REST: """
        :param x: X.
        :parameter y: Y.
        :keyword z: Z.
        :ivar a: A.
        :returns: R.
        :raise ValueError: E.
        """,
    GOOGLE: """
        Args:
            x: X.

        Arguments:
            y: Y.

        Keyword Args:
            z: Z.

        Attributes:
            a: A.

        Returns:
            R.

        Raises:
            ValueError: E.
        """,
    EPYDOC: """
        @param x: X.
        @arg y: Y.
        @keyword z: Z.
        @ivar a: A.
        @return: R.
        @raise ValueError: E.
        """,
}


@pytest.mark.parametrize("style", list(CANONICAL))
def test_canonical_keys(style: DocstringStyle) -> None:
    """``args`` holds a canonical key followed by the item's name or type."""
    assert [item.args for item in new(CANONICAL[style], style).meta] == [
        ["param", "x"],
        ["param", "y"],
        ["keyword", "z"],
        ["attribute", "a"],
        ["returns"],
        ["raises", "ValueError"],
    ]


@pytest.mark.parametrize("style", list(CANONICAL))
def test_attributes_are_not_params(style: DocstringStyle) -> None:
    """Attributes are in ``attributes`` and not in ``params``."""
    docstring = new(CANONICAL[style], style)
    assert [p.arg_name for p in docstring.params] == ["x", "y", "z"]
    assert [a.arg_name for a in docstring.attributes] == ["a"]
    assert docstring.attributes[0].is_attribute


def test_numpydoc_attributes_are_not_params() -> None:
    """Attributes are in ``attributes`` and not in ``params``."""
    docstring = new(
        "Parameters\n----------\nx\n    X.\n\nAttributes\n----------\na\n"
        "    A.",
        NUMPYDOC,
    )
    assert [p.arg_name for p in docstring.params] == ["x"]
    assert [a.arg_name for a in docstring.attributes] == ["a"]


def test_legacy_params_include_attributes() -> None:
    """In legacy mode attributes are still part of ``params``."""
    docstring = parse(CANONICAL[GOOGLE], GOOGLE)
    assert [p.arg_name for p in docstring.params] == ["x", "y", "a"]
    assert [a.arg_name for a in docstring.attributes] == ["a"]


# Deprecation and examples

DEPRECATED = {
    REST: "Summary.\n\n.. deprecated:: 1.2\n    Use g.\n\n:param x: X.",
    GOOGLE: "Summary.\n\n.. deprecated:: 1.2\n    Use g.\n\nArgs:\n    x: X.",
    NUMPYDOC: (
        "Summary.\n\n.. deprecated:: 1.2\n    Use g.\n\n"
        "Parameters\n----------\nx\n    X."
    ),
    EPYDOC: "Summary.\n\n@deprecated: 1.2 Use g.\n@param x: X.",
}


@pytest.mark.parametrize("style", list(DEPRECATED))
def test_deprecation(style: DocstringStyle) -> None:
    """Deprecations are found as directives, or as epydoc fields."""
    docstring = new(DEPRECATED[style], style)
    assert docstring.short_description == "Summary."
    assert docstring.long_description is None
    assert docstring.deprecation is not None
    assert docstring.deprecation.version == "1.2"
    assert docstring.deprecation.description == "Use g."
    assert docstring.deprecation.args == ["deprecation"]


def test_several_deprecations() -> None:
    """Every directive gives an item."""
    docstring = new(".. deprecated:: 1\n    A.\n\n.. deprecated:: 2", REST)
    deprecations = [
        m for m in docstring.meta if isinstance(m, DocstringDeprecated)
    ]
    assert [(d.version, d.description) for d in deprecations] == [
        ("1", "A."),
        ("2", None),
    ]
    assert docstring.short_description is None


EXAMPLES = {
    GOOGLE: "Examples:\n    {body}",
    NUMPYDOC: "Examples\n--------\n{body}",
}

EXAMPLES_BODY = """\
Some text.

>>> f(1,
...   2)
3

More text.
>>> g()
"""


@pytest.mark.parametrize("style", list(EXAMPLES))
def test_examples(style: DocstringStyle) -> None:
    """Examples are the text introducing a snippet and the snippet itself.

    As in doctest, a snippet includes its expected output, which ends at a
    blank line (see #104 and #105).
    """
    indent = "    " if style == GOOGLE else ""
    body = EXAMPLES_BODY.replace("\n", "\n" + indent)
    docstring = new(EXAMPLES[style].format(body=body), style)
    assert [(e.description, e.snippet) for e in docstring.examples] == [
        ("Some text.", ">>> f(1,\n...   2)\n3"),
        ("More text.", ">>> g()"),
    ]


def test_examples_from_issue_105() -> None:
    """Each example gets the text before it and the output after it."""
    docstring = new(
        """
        Short description.

        Examples
        --------
        To print the number 1:

        >>> print(1)
        1

        To print the number 2:

        >>> print(2)
        2

        Closing remark.
        """,
        NUMPYDOC,
    )
    assert [(e.description, e.snippet) for e in docstring.examples] == [
        ("To print the number 1:", ">>> print(1)\n1"),
        ("To print the number 2:", ">>> print(2)\n2"),
        ("Closing remark.", None),
    ]
    text = compose(docstring)
    assert "To print the number 1:\n\n>>> print(1)\n1\n\n" in text
    again = new(text, NUMPYDOC)
    assert [vars(e) for e in again.examples] == [
        vars(e) for e in docstring.examples
    ]


# Google style


def test_google_section_titles() -> None:
    """Titles are case insensitive and include the napoleon sections."""
    docstring = new(
        """
        Summary.

        ARGS:
            x: X.

        Note:
            A note.

        See also:
            Other things.

        Todo:
            More.
        """,
        GOOGLE,
    )
    assert meta_summary(docstring)[1:] == [
        ("DocstringMeta", ["notes"], "A note."),
        ("DocstringMeta", ["see_also"], "Other things."),
        ("DocstringMeta", ["todo"], "More."),
    ]
    assert docstring.long_description is None


def test_google_empty_section_is_text() -> None:
    """A title without indented content is kept as text (see #42)."""
    docstring = new(
        """
        Short description.

        Example:

        .. testcode::

            foo = bar

        Args:
            name: Description.
        """,
        GOOGLE,
    )
    assert docstring.long_description == (
        "Example:\n\n.. testcode::\n\n    foo = bar"
    )
    assert [p.arg_name for p in docstring.params] == ["name"]
    assert not docstring.examples


def test_google_unknown_titles_are_text() -> None:
    """Unrecognized ``Title:`` lines are kept as free text."""
    text = "Summary.\n\nArgs:\n    x: X.\n\nUnknown:\n    Stuff."
    docstring = new(text, GOOGLE)
    assert docstring.long_description == "Unknown:\n    Stuff."
    assert len(docstring.params) == 1


def test_google_title_on_first_line() -> None:
    """A docstring may start with a section title."""
    docstring = new("Args:\n        x: X.\n        y (int): Y.\n    ", GOOGLE)
    assert docstring.short_description is None
    assert [(p.arg_name, p.type_name) for p in docstring.params] == [
        ("x", None),
        ("y", "int"),
    ]
    docstring = new(
        "Args:\n            x: X.\n\n        Returns:\n            int: R.",
        GOOGLE,
    )
    assert [p.arg_name for p in docstring.params] == ["x"]
    assert docstring.returns is not None
    assert docstring.returns.type_name == "int"


def test_google_items_and_continuation_lines() -> None:
    """Lines that do not look like an item header continue the item."""
    docstring = new(
        """
        Args:
            x: First line
            continued without indentation.
            y (Callable[[int], str], optional): Second.
                Indented continuation.

                Second paragraph.
            *args: Varargs.
            **kwargs (Any): Keywords.
        """,
        GOOGLE,
    )
    assert [
        (p.arg_name, p.type_name, p.description) for p in docstring.params
    ] == [
        ("x", None, "First line\ncontinued without indentation."),
        (
            "y",
            "Callable[[int], str]",
            "Second.\nIndented continuation.\n\nSecond paragraph.",
        ),
        ("*args", None, "Varargs."),
        ("**kwargs", "Any", "Keywords."),
    ]


def test_google_returns() -> None:
    """Returns have a type only if what precedes the colon looks like one."""
    cases = [
        ("int: The value.", (None, "int", "The value.")),
        ("Dict[str, int]: Map.", (None, "Dict[str, int]", "Map.")),
        ("list of str: Names.", (None, "list of str", "Names.")),
        ("int | None: Maybe.", (None, "int | None", "Maybe.")),
        (":class:`Foo`: A foo.", (None, ":class:`Foo`", "A foo.")),
        ("result (int): The value.", ("result", "int", "The value.")),
        ("The value: a number.", (None, None, "The value: a number.")),
        (
            "True if it worked. See: x.",
            (None, None, "True if it worked. See: x."),
        ),
        ("The value.", (None, None, "The value.")),
    ]
    for body, expected in cases:
        returns = new(f"Returns:\n    {body}", GOOGLE).returns
        assert returns is not None
        assert (
            returns.return_name,
            returns.type_name,
            returns.description,
        ) == expected, body


def test_google_raises() -> None:
    """Raises items are ``Type: text``; a bare type or text also works."""
    docstring = new(
        """
        Raises:
            ValueError: If bad.
            TypeError
            KeyError, IndexError: If missing.
        """,
        GOOGLE,
    )
    assert [(r.type_name, r.description) for r in docstring.raises] == [
        ("ValueError", "If bad."),
        ("TypeError", None),
        ("KeyError, IndexError", "If missing."),
    ]
    docstring = new("Raises:\n    An error if bad.", GOOGLE)
    assert [(r.type_name, r.description) for r in docstring.raises] == [
        (None, "An error if bad.")
    ]


def test_numpydoc_raises_with_text_on_header() -> None:
    """``Type : text`` in numpydoc Raises splits as ``Type: text`` does."""
    docstring = new(
        """
        Raises
        ------
        ValueError : If bad.
            Really bad.
        TypeError
            If wrong.
        """,
        NUMPYDOC,
    )
    assert [(r.type_name, r.description) for r in docstring.raises] == [
        ("ValueError", "If bad.\nReally bad."),
        ("TypeError", "If wrong."),
    ]


@pytest.mark.parametrize(
    "header", ["y (int). Y.", "y (int) Y.", "y (int,\n        optional): Y."]
)
def test_google_incomplete_header_continues_item(header: str) -> None:
    """A header that is not complete on its line continues the last item."""
    params = new(f"Args:\n    x (int): X.\n    {header}", GOOGLE).params
    assert [p.arg_name for p in params] == ["x"]
    assert (params[0].description or "").startswith("X.\ny (int")


def test_google_custom_sections() -> None:
    """Custom sections of GoogleParser are used without legacy behavior."""
    parser = GoogleParser(
        [
            Section("Args", "param", SectionType.MULTIPLE),
            Section("Hooks", "hooks", SectionType.MULTIPLE),
        ]
    )
    docstring = parser.parse(
        "Args:\n    x: X.\n\nHooks:\n    pre: Before.\n\nReturns:\n    R.",
        legacy=False,
    )
    assert meta_summary(docstring) == [
        ("DocstringParam", ["param", "x"], "X."),
        ("DocstringMeta", ["hooks", "pre"], "Before."),
    ]
    assert docstring.short_description == "Returns:\n    R."
    parser = GoogleParser()
    parser.add_section(Section("Hooks", "hooks", SectionType.SINGULAR))
    docstring = parser.parse("Hooks:\n    a\n\nNote:\n    b", legacy=False)
    assert meta_summary(docstring) == [
        ("DocstringMeta", ["hooks"], "a"),
        ("DocstringMeta", ["notes"], "b"),
    ]


# Numpydoc style


def test_numpydoc_headers() -> None:
    """Underlines just need three dashes; titles are case insensitive."""
    docstring = new(
        """
        Summary.

        Parameters
        ---
        x : int
            X.

        See also
        ========
        g : Other.
        """,
        NUMPYDOC,
    )
    assert meta_summary(docstring) == [
        ("DocstringParam", ["param", "x"], "X."),
        ("DocstringMeta", ["see_also"], "g : Other."),
    ]


def test_numpydoc_unknown_sections() -> None:
    """Unknown sections end the previous one once sections started."""
    docstring = new(
        """
        Summary.

        Title
        -----
        Part of the description.

        Parameters
        ----------
        x : int
            X.

        Custom Title
        ------------
        Not a parameter.
        """,
        NUMPYDOC,
    )
    assert docstring.long_description == (
        "Title\n-----\nPart of the description."
    )
    assert meta_summary(docstring) == [
        ("DocstringParam", ["param", "x"], "X."),
        ("DocstringMeta", ["custom_title"], "Not a parameter."),
    ]


def test_numpydoc_returns() -> None:
    """Returns are ``name : type`` or ``type``; roles are not split."""
    docstring = new(
        """
        Returns
        -------
        out : ndarray
            Result.
        :class:`numpy.ndarray`
            Other.
        list of str
        """,
        NUMPYDOC,
    )
    assert [
        (r.return_name, r.type_name, r.description)
        for r in docstring.many_returns
    ] == [
        ("out", "ndarray", "Result."),
        (None, ":class:`numpy.ndarray`", "Other."),
        (None, "list of str", None),
    ]


def test_numpydoc_methods() -> None:
    """Methods sections give one item per method (see #62)."""
    docstring = new(
        """
        A photo.

        Methods
        -------
        colorspace(c='rgb')
            Represent the photo in the given colorspace.
        gamma(n=1.0)
            Change the photo's gamma exposure.
        """,
        NUMPYDOC,
    )
    assert meta_summary(docstring) == [
        (
            "DocstringMeta",
            ["methods", "colorspace(c='rgb')"],
            "Represent the photo in the given colorspace.",
        ),
        (
            "DocstringMeta",
            ["methods", "gamma(n=1.0)"],
            "Change the photo's gamma exposure.",
        ),
    ]
    again = new(compose(docstring), NUMPYDOC)
    assert meta_summary(again) == meta_summary(docstring)
    assert not parse(compose(docstring), NUMPYDOC).meta  # legacy: unknown


def test_numpydoc_custom_section() -> None:
    """Custom section classes are parsed by their own ``parse`` method."""

    class Upper(NumpySection):
        """A section whose text is upper-cased."""

        def parse(self, text: str) -> T.Iterable[DocstringMeta]:
            yield DocstringMeta([self.key], text.upper())

    parser = NumpydocParser()
    parser.add_section(Upper("Shout", "shout"))
    docstring = parser.parse("Shout\n-----\nhello", legacy=False)
    assert meta_summary(docstring) == [("DocstringMeta", ["shout"], "HELLO")]


# ReST and epydoc styles


def test_rest_roles_are_not_fields() -> None:
    """A line starting with a role is text, not a field."""
    docstring = new(
        "Calls\n:meth:`run` when done.\n\n:param x: X.\n:returns: Y.", REST
    )
    assert docstring.short_description == "Calls\n:meth:`run` when done."
    assert meta_summary(docstring) == [
        ("DocstringParam", ["param", "x"], "X."),
        ("DocstringReturns", ["returns"], "Y."),
    ]


def test_rest_fields() -> None:
    """Types with spaces, type fields without param and several raises."""
    docstring = new(
        """
        :param Dict[str, int] mapping: Map.
        :type other: str
        :ivar a: A.
        :vartype a: int
        :raises ValueError, TypeError: Bad.
        :rtype:
        :returns: Result.
        :rtype: bool
        :meta private:
        """,
        REST,
    )
    assert [
        (p.args, p.type_name, p.description)
        for p in docstring.meta
        if isinstance(p, DocstringParam)
    ] == [
        (["param", "mapping"], "Dict[str, int]", "Map."),
        (["param", "other"], "str", None),
        (["attribute", "a"], "int", "A."),
    ]
    assert docstring.raises[0].type_name == "ValueError, TypeError"
    assert len(docstring.many_returns) == 1
    assert docstring.many_returns[0].type_name == "bool"
    assert docstring.meta[-1].args == ["meta", "private"]


def test_epydoc_fields() -> None:
    """Fields must start the line; types are merged."""
    docstring = new(
        """
        Summary mentioning @param x: in the text.

        @param x: X.
        @type x: int
        @return: R.
        @returntype: str
        @raise IOError: Bad.
        @note: Careful.
        """,
        EPYDOC,
    )
    assert docstring.short_description == (
        "Summary mentioning @param x: in the text."
    )
    assert meta_summary(docstring) == [
        ("DocstringParam", ["param", "x"], "X."),
        ("DocstringReturns", ["returns"], "R."),
        ("DocstringRaises", ["raises", "IOError"], "Bad."),
        ("DocstringMeta", ["note"], "Careful."),
    ]
    assert docstring.params[0].type_name == "int"
    assert docstring.returns is not None
    assert docstring.returns.type_name == "str"


def test_lenient_fields() -> None:
    """Fields without a name are kept as items rather than failing."""
    docstring = new(":param: Nameless.", REST)
    assert meta_summary(docstring) == [
        ("DocstringMeta", ["param"], "Nameless.")
    ]


# Detection and composition


@pytest.mark.parametrize(
    "style", [REST, GOOGLE, EPYDOC, NUMPYDOC], ids=lambda s: s.name
)
def test_auto_detection(style: DocstringStyle) -> None:
    """AUTO picks the style with the most items."""
    assert new(DEPRECATED[style]).style == style


def test_auto_detection_without_items() -> None:
    """Without items in any style, the result is the reST one."""
    docstring = new("Just text.\n\nMore text.")
    assert docstring.style == REST
    assert docstring.short_description == "Just text."


ROUND_TRIP = {
    GOOGLE: """
        Summary.

        .. deprecated:: 2.0
            Use g.

        Args:
            x (int): X. Defaults to 3.
            y (str, optional): Y.

        Keyword Args:
            z: Z.

        Attributes:
            a (int): A.

        Returns:
            bool: B.

        Raises:
            ValueError: V.

        Examples:
            >>> f(1)
            True
        """,
    NUMPYDOC: """
        Summary.

        .. deprecated:: 2.0
            Use g.

        Parameters
        ----------
        x : int
            X. Defaults to 3.
        y : str, optional
            Y.

        Attributes
        ----------
        a : int
            A.

        Returns
        -------
        out : bool
            B.

        Examples
        --------
        >>> f(1)
        True
        """,
    REST: """
        Summary.

        .. deprecated:: 2.0
            Use g.

        :param x: X. Defaults to 3.
        :type x: int
        :param str y: Y.
        :type y: str, optional
        :keyword z: Z.
        :ivar a: A.
        :vartype a: int
        :returns: B.
        :rtype: bool
        :raises ValueError: V.
        """,
    EPYDOC: """
        Summary.

        @deprecated: 2.0 Use g.
        @param x: X. Defaults to 3.
        @type x: int
        @param y: Y.
        @type y: str, optional
        @keyword z: Z.
        @ivar a: A.
        @type a: int
        @return: B.
        @rtype: bool
        @raise ValueError: V.
        """,
}


@pytest.mark.parametrize("style", list(ROUND_TRIP), ids=lambda s: s.name)
@pytest.mark.parametrize("rendering", list(RenderingStyle))
def test_compose_round_trip(
    style: DocstringStyle, rendering: RenderingStyle
) -> None:
    """Parsing composed text gives back the same items."""
    docstring = new(ROUND_TRIP[style], style)
    text = compose(docstring, rendering_style=rendering)
    again = new(text, style)
    assert meta_summary(again) == meta_summary(docstring)
    assert [vars(m) for m in again.meta] == [vars(m) for m in docstring.meta]
    assert again.description == docstring.description


def test_compose_google() -> None:
    """The Google composer keeps every kind of item."""
    text = compose(new(ROUND_TRIP[GOOGLE], GOOGLE))
    assert text == (
        "Summary.\n"
        "\n"
        ".. deprecated:: 2.0\n"
        "    Use g.\n"
        "\n"
        "Args:\n"
        "    x (int): X. Defaults to 3.\n"
        "    y (str, optional): Y.\n"
        "\n"
        "Keyword Args:\n"
        "    z: Z.\n"
        "\n"
        "Attributes:\n"
        "    a (int): A.\n"
        "\n"
        "Returns:\n"
        "    bool: B.\n"
        "\n"
        "Raises:\n"
        "    ValueError: V.\n"
        "\n"
        "Examples:\n"
        "    >>> f(1)\n"
        "    True"
    )


def test_compose_to_other_style() -> None:
    """Docstrings can be composed in another style."""
    docstring = new(ROUND_TRIP[GOOGLE], GOOGLE)
    text = compose(docstring, style=REST)
    assert ":param int x: X. Defaults to 3." in text
    assert ":ivar int a: A." in text
    assert ":rtype: bool" in text
    assert new(text, REST).params[1].is_optional


def test_compose_legacy_docstring_unchanged() -> None:
    """Legacy docstrings are still composed by the legacy composers."""
    docstring = parse(ROUND_TRIP[GOOGLE], GOOGLE)
    assert docstring.legacy
    assert "y (str?): Y." in compose(docstring)


# Other entry points


class _WithAttributes:
    """Summary.

    Attributes:
        a (int): Documented in the class docstring.
    """

    a: int = 1
    """Documented next to the attribute."""

    b: str = "x"
    """Documented
    next to the attribute.
    """


def test_parse_from_object() -> None:
    """Attribute docstrings are added once, with cleaned descriptions."""
    docstring = parse_from_object(_WithAttributes, legacy=False)
    assert [(a.arg_name, a.description) for a in docstring.attributes] == [
        ("a", "Documented in the class docstring."),
        ("b", "Documented\nnext to the attribute."),
    ]
    assert not docstring.params


def test_combine_docstrings() -> None:
    """combine_docstrings accepts the legacy flag."""

    def source(x: int, y: int) -> None:
        """Summary.

        Args:
            x (int): X.
            y (int): Y.

        Attributes:
            a: A.
        """

    @combine_docstrings(source, style=GOOGLE, legacy=False)
    def target(x: int) -> None:
        """Other summary."""

    assert target.__doc__ == (
        "Other summary.\n\nArgs:\n    x (int): X.\n\nAttributes:\n    a: A."
    )


def test_never_raises_on_bad_input() -> None:
    """Malformed docstrings give results instead of errors."""
    for text in [": :", "Args:\n    (", "@raise", "Returns\n-------\n:"]:
        for style in (REST, GOOGLE, NUMPYDOC, EPYDOC):
            try:
                new(text, style)
            except ParseError:  # pragma: no cover
                raise AssertionError(f"{style}: {text!r}")


def test_examples_are_docstring_examples() -> None:
    """Examples sections give DocstringExample items."""
    docstring = new("Example:\n    >>> 1", GOOGLE)
    assert isinstance(docstring.meta[0], DocstringExample)


def test_auto_without_fields_keeps_the_mode() -> None:
    """Text without fields is still parsed without legacy behavior."""
    docstring = parse("Summary\nwrapped.\n\nLong.", legacy=False)
    assert docstring.legacy is False
    assert docstring.short_description == "Summary\nwrapped."


def test_auto_finds_equals_underlines() -> None:
    """Underlines of ``=`` are not taken as text without fields."""
    text = "Summary.\n\nParameters\n==========\nx\n    Value."
    docstring = parse(text, legacy=False)
    assert docstring.style == NUMPYDOC
    assert [p.arg_name for p in docstring.params] == ["x"]


LINE_ENDINGS_DOCSTRINGS = {
    REST: """Summary.

        Long.

        :param x: Value.
        """,
    GOOGLE: """Summary.

        Long.

        Args:
            x: Value.
        """,
    NUMPYDOC: """Summary.

        Long.

        Parameters
        ----------
        x
            Value.
        """,
    EPYDOC: """Summary.

        Long.

        @param x: Value.
        """,
}


@pytest.mark.parametrize("style", list(LINE_ENDINGS_DOCSTRINGS))
@pytest.mark.parametrize("line_ending", ["\r\n", "\r"])
def test_line_endings(style: DocstringStyle, line_ending: str) -> None:
    """Other line endings parse the same as newlines."""
    text = LINE_ENDINGS_DOCSTRINGS[style]
    expected = new(text, style)
    docstring = new(text.replace("\n", line_ending), style)
    assert len(expected.params) == 1
    assert docstring_to_dict(docstring) == docstring_to_dict(expected)


def test_google_default_sections_can_be_extended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sections added to DEFAULT_SECTIONS are recognized."""
    section = Section("Usage", "usage", SectionType.SINGULAR)
    monkeypatch.setattr(
        google, "DEFAULT_SECTIONS", [*google.DEFAULT_SECTIONS, section]
    )
    docstring = google.parse("Summary.\n\nUsage:\n    Text.", legacy=False)
    assert [m.args for m in docstring.meta] == [["usage"]]
    docstring = google.parse("Summary.\n\nArgs:\n    x: X.", legacy=False)
    assert [m.args for m in docstring.meta] == [["param", "x"]]
