"""Tests for numpydoc-style docstring routines."""

import pytest

from docstring_parser import numpydoc
from docstring_parser.numpydoc import (
    DEFAULT_SECTIONS,
    PARAM_DEFAULT_REGEX,
    PARAM_DEFAULT_REGEX_IN_DESC,
    PARAM_KEY_REGEX,
    PARAM_OPTIONAL_REGEX,
    NumpydocParser,
    Section,
    compose,
    parse,
)


@pytest.mark.parametrize(
    "input_str, expected_name, expected_type",
    [
        ("arg_name", "arg_name", None),
        ("arg_name : type", "arg_name", "type"),
        ("arg_name : type, optional", "arg_name", "type, optional"),
        ("arg_name : type, default=10", "arg_name", "type, default=10"),
    ],
)
def test_param_key_regex(input_str, expected_name, expected_type):
    """Test parsing parameter keys."""
    match = PARAM_KEY_REGEX.match(input_str)
    assert match is not None
    assert match.group("name") == expected_name
    assert match.group("type") == expected_type


@pytest.mark.parametrize(
    "input_str, expected_match",
    [
        ("", False),
        ("type", False),
        ("type, optional", True),
    ],
)
def test_param_optional_regex(input_str, expected_match):
    """Test parsing parameter optionality."""
    match = PARAM_OPTIONAL_REGEX.match(input_str)
    if expected_match:
        assert match is not None
    else:
        assert match is None


@pytest.mark.parametrize(
    "input_str, expected_match, default_value",
    [
        ("", False, None),
        ("type", False, None),
        ("type, default=10", True, "10"),
        ("type, default='hello'", True, "'hello'"),
        ('type, default="world"', True, '"world"'),
        ("type, default: 1.5", True, "1.5"),
        ("type, default 1.5", True, "1.5"),
    ],
)
def test_param_default_regex(input_str, expected_match, default_value):
    """Test parsing parameter default values."""
    match = PARAM_DEFAULT_REGEX.match(input_str)
    if expected_match:
        assert match is not None
        assert match.group("type") == "type"
        assert match.group("value") == default_value
    else:
        assert match is None


@pytest.mark.parametrize(
    "input_str, expected_match, default_value",
    [
        ("", False, None),
        ("description without default", False, None),
        ("description with default, default=10", True, "10"),
        ("description with default, Default: 'hello'", True, "'hello'"),
        ("description with default, defaults to 'world'", True, "'world'"),
        ("description with default, defaults to 1.5", True, "1.5"),
        ("description with default, default is 1.5", True, "1.5"),
    ],
)
def test_param_default_regex_in_desc(input_str, expected_match, default_value):
    """Test parsing parameter default values in descriptions."""
    match = PARAM_DEFAULT_REGEX_IN_DESC.search(input_str)
    if expected_match:
        assert match is not None
        assert match.group("value") == default_value
    else:
        assert match is None


@pytest.mark.parametrize(
    "source, expected, expected_num_metas",
    [
        ("", "", 0),
        ("\n", "", 0),
        ("Short description", "Short description", 0),
        ("\nShort description\n", "Short description", 0),
        ("\n   Short description\n", "Short description", 0),
        (
            "Short description\n\nLong description",
            "Short description\n\nLong description",
            0,
        ),
        (
            """
            Short description

            Long description
            """,
            "Short description\n\nLong description",
            0,
        ),
        (
            """
            Short description

            Long description
            Second line
            """,
            "Short description\n\nLong description\nSecond line",
            0,
        ),
        (
            "Short description\nLong description",
            "Short description\nLong description",
            0,
        ),
        (
            """
            Short description
            Long description
            """,
            "Short description\nLong description",
            0,
        ),
        (
            "\nShort description\nLong description\n",
            "Short description\nLong description",
            0,
        ),
        (
            """
            Short description
            Long description
            Second line
            """,
            "Short description\nLong description\nSecond line",
            0,
        ),
        (
            """
            Short description
            Meta
            ----
            asd
            """,
            "Short description\nMeta\n----\nasd",
            1,
        ),
        (
            """
            Short description
            Long description
            Meta
            ----
            asd
            """,
            "Short description\nLong description\nMeta\n----\nasd",
            1,
        ),
        (
            """
            Short description
            First line
                Second line
            Meta
            ----
            asd
            """,
            "Short description\nFirst line\n    Second line\nMeta\n----\nasd",
            1,
        ),
        (
            """
            Short description

            First line
                Second line
            Meta
            ----
            asd
            """,
            "Short description\n"
            "\n"
            "First line\n"
            "    Second line\n"
            "Meta\n"
            "----\n"
            "asd",
            1,
        ),
        (
            """
            Short description

            First line
                Second line
            Meta
            ----
            asd
            """,
            "Short description\n"
            "\n"
            "First line\n"
            "    Second line\n"
            "Meta\n"
            "----\n"
            "asd",
            1,
        ),
        (
            """
            Short description

            Meta
            ----
            asd
                1
                    2
                3
            """,
            "Short description\n\nMeta\n----\nasd\n    1\n        2\n    3",
            1,
        ),
        (
            """
            Short description

            Meta1
            -----
            asd
            1
                2
            3
            Meta2
            -----
            herp
            Meta3
            -----
            derp
            """,
            "Short description\n\n"
            "Meta1\n"
            "-----\n"
            "asd\n"
            "1\n"
            "    2\n"
            "3\n\n"
            "Meta2\n"
            "-----\n"
            "herp\n\n"
            "Meta3\n"
            "-----\n"
            "derp",
            3,
        ),
        (
            """
            Short description

            Parameters
            ----------
            name
                description 1
            priority: int
                description 2
            sender: str, optional
                description 3
            message: str, optional
                description 4, defaults to 'hello'
            multiline: str, optional
                long description 5,
                    defaults to 'bye'
            default_arg: str, default=10
                description 6, defaults to 10
            """,
            "Short description\n\n"
            "Parameters\n"
            "----------\n"
            "name\n"
            "    description 1\n"
            "priority : int\n"
            "    description 2\n"
            "sender : str, optional\n"
            "    description 3\n"
            "message : str, optional\n"
            "    description 4, defaults to 'hello'\n"
            "multiline : str, optional\n"
            "    long description 5,\n"
            "        defaults to 'bye'\n"
            "default_arg : str, default=10\n"
            "    description 6, defaults to 10",
            6,
        ),
        (
            """
            Short description
            Raises
            ------
            ValueError
                description
            """,
            "Short description\nRaises\n------\nValueError\n    description",
            1,
        ),
        (
            """
            Description
            Examples
            --------
            >>> test1a
            >>> test1b
            desc1a
            desc1b
            >>> test2a
            >>> test2b
            desc2a
            desc2b
            """,
            "Description\n"
            "Examples\n"
            "--------\n"
            ">>> test1a\n"
            ">>> test1b\n"
            "desc1a\n"
            "desc1b\n"
            ">>> test2a\n"
            ">>> test2b\n"
            "desc2a\n"
            "desc2b",
            4,
        ),
    ],
)
def test_compose(source: str, expected: str, expected_num_metas: int) -> None:
    """Test compose in default mode."""

    # Test cases use `Meta` and `Meta#`, which aren't included in the defaults.
    addtl_sections = [Section(f"Meta{i}", f"meta{i}") for i in range(1, 4)] + [
        Section("Meta", "meta")
    ]
    parser_w_meta_section = NumpydocParser(
        sections=(DEFAULT_SECTIONS + addtl_sections)
    )
    docstring = parser_w_meta_section.parse(source)

    # We want to make sure that parse is correctly parsing the docstring and
    # not returning the whole thing as a description.
    assert len(docstring.meta) == expected_num_metas

    assert compose(docstring) == expected


def test_parse_reuses_default_parser() -> None:
    """Test that parse builds the default parser once."""
    numpydoc.parse("Short.")
    parser = numpydoc._default_parser
    numpydoc.parse("Short.\n\nParameters\n----------\na\n    A.")
    assert numpydoc._default_parser is parser


def test_parse_follows_default_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that parse picks up changes to DEFAULT_SECTIONS."""
    text = "Short.\n\nMeta\n----\nasd"
    assert parse(text).meta == []
    monkeypatch.setattr(
        numpydoc,
        "DEFAULT_SECTIONS",
        [*numpydoc.DEFAULT_SECTIONS, Section("Meta", "meta")],
    )
    assert parse(text).meta[0].key == "meta"


def test_parse_follows_section_title_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that parse picks up a section's title changed in place."""
    section = Section("Meta", "meta")
    monkeypatch.setattr(
        numpydoc, "DEFAULT_SECTIONS", [*numpydoc.DEFAULT_SECTIONS, section]
    )
    assert parse("Short.\n\nMeta\n----\nasd").meta[0].key == "meta"
    section.title = "Data"
    assert parse("Short.\n\nData\n----\nasd").meta[0].key == "meta"


def test_compose_deprecation_layout() -> None:
    """Test that a deprecation is set off and has no trailing spaces."""
    docstring = parse(
        "Short.\n\n.. deprecated:: 1.0\n    Use other.\n\n    More."
    )
    docstring.long_description = "Long."
    assert compose(docstring) == (
        "Short.\n\n.. deprecated:: 1.0\n    Use other.\n\n    More.\n\nLong."
    )


def test_compose_does_not_end_with_blank_line() -> None:
    """Test that a blank line after the last block is left out."""
    docstring = parse("Short.\n\nLong.")
    docstring.blank_after_long_description = True
    assert compose(docstring) == "Short.\n\nLong."


def test_examples_section_finishes_promptly() -> None:
    """Parse a long examples section without rescanning its lines."""
    lines = [">>> f()" if i % 2 == 0 else "out" for i in range(100_000)]
    docstring = parse("Short.\n\nExamples\n--------\n" + "\n".join(lines))
    assert len(docstring.examples) == 50_000
    assert docstring.examples[-1].snippet == ">>> f()\nout"
    assert docstring.examples[-1].description is None


@pytest.mark.parametrize("title", ["Notes?", "C++ Notes", "Args (old)"])
def test_section_title_is_literal(title: str) -> None:
    """Test that regex characters in a section title match literally."""
    parser = NumpydocParser([Section(title, "custom")])
    docstring = parser.parse(f"Short.\n\n{title}\n{'-' * len(title)}\ntext")
    assert [(m.key, m.description) for m in docstring.meta] == [
        ("custom", "text")
    ]


def test_examples_split_as_doctest_reads_them() -> None:
    """Test that each example is its text, then its snippet and output."""
    text = (
        "Short.\n\n"
        "Examples\n"
        "--------\n"
        "To print a number:\n\n"
        ">>> for i in range(1):\n"
        "...     print(i)\n"
        "0\n"
        ">>> f()\n\n"
        "Then more."
    )
    docstring = parse(text)
    assert len(docstring.examples) == 3
    assert docstring.examples[0].description == "To print a number:"
    assert docstring.examples[0].snippet == (
        ">>> for i in range(1):\n...     print(i)\n0"
    )
    assert docstring.examples[1].description is None
    assert docstring.examples[1].snippet == ">>> f()"
    assert docstring.examples[2].description == "Then more."
    assert docstring.examples[2].snippet is None
    assert compose(docstring) == text


def test_several_names_give_one_param_each() -> None:
    """Test that a head listing several names gives each the same type and
    description, and composes to text that reads back the same."""
    docstring = parse(
        "Short.\n\n"
        "Parameters\n"
        "----------\n"
        "x, y : int\n"
        "    A point.\n"
        "*args, **kwargs\n"
        "    Rest."
    )
    names = [param.arg_name for param in docstring.params]
    assert names == ["x", "y", "*args", "**kwargs"]
    assert docstring.params[1].type_name == "int"
    assert docstring.params[1].description == "A point."
    assert docstring.params[3].description == "Rest."
    again = parse(compose(docstring))
    assert [param.arg_name for param in again.params] == names
    assert again.params[1].type_name == "int"
