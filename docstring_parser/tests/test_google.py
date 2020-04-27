import typing as T

import pytest
from docstring_parser.common import ParseError
from docstring_parser.google import GoogleParser, Section, SectionType, parse


def test_google_parser():
    parser = GoogleParser()
    docstring = parse(
        """
        Unknown:
            spam: a
        """
    )
    assert docstring.short_description == "Unknown:"
    assert docstring.long_description == "spam: a"
    assert len(docstring.meta) == 0

    parser = GoogleParser(
        [
            Section("DESCRIPTION", "desc", SectionType.SINGULAR),
            Section("ARGUMENTS", "param", SectionType.MULTIPLE),
            Section("ATTRIBUTES", "attribute", SectionType.MULTIPLE),
            Section("EXAMPLES", "examples", SectionType.SINGULAR),
        ],
        title_colon=False,
    )
    docstring = parser.parse(
        """
        DESCRIPTION
            This is the description.

        ARGUMENTS
            arg1: first arg
            arg2: second arg

        ATTRIBUTES
            attr1: first attribute
            attr2: second attribute

        EXAMPLES
            Many examples
            More examples
        """
    )

    assert docstring.short_description is None
    assert docstring.long_description is None
    assert len(docstring.meta) == 6
    assert docstring.meta[0].args == ["desc"]
    assert docstring.meta[0].description == "This is the description."
    assert docstring.meta[1].args == ["param", "arg1"]
    assert docstring.meta[1].description == "first arg"
    assert docstring.meta[2].args == ["param", "arg2"]
    assert docstring.meta[2].description == "second arg"
    assert docstring.meta[3].args == ["attribute", "attr1"]
    assert docstring.meta[3].description == "first attribute"
    assert docstring.meta[4].args == ["attribute", "attr2"]
    assert docstring.meta[4].description == "second attribute"
    assert docstring.meta[5].args == ["examples"]
    assert docstring.meta[5].description == "Many examples\nMore examples"

    parser.add_section(Section("Note", "note", SectionType.SINGULAR))
    docstring = parser.parse(
        """
        short description

        Note:
            a note
        """
    )
    assert docstring.short_description == "short description"
    assert docstring.long_description == "Note:\n    a note"

    docstring = parser.parse(
        """
        short description

        Note a note
        """
    )
    assert docstring.short_description == "short description"
    assert docstring.long_description == "Note a note"

    docstring = parser.parse(
        """
        short description

        Note
            a note
        """
    )
    assert len(docstring.meta) == 1
    assert docstring.meta[0].args == ["note"]
    assert docstring.meta[0].description == "a note"


@pytest.mark.parametrize(
    "source, expected",
    [
        ("", None),
        ("\n", None),
        ("Short description", "Short description"),
        ("\nShort description\n", "Short description"),
        ("\n   Short description\n", "Short description"),
    ],
)
def test_short_description(source: str, expected: str) -> None:
    docstring = parse(source)
    assert docstring.short_description == expected
    assert docstring.long_description is None
    assert docstring.meta == []


@pytest.mark.parametrize(
    "source, expected_short_desc, expected_long_desc, expected_blank",
    [
        (
            "Short description\n\nLong description",
            "Short description",
            "Long description",
            True,
        ),
        (
            """
            Short description

            Long description
            """,
            "Short description",
            "Long description",
            True,
        ),
        (
            """
            Short description

            Long description
            Second line
            """,
            "Short description",
            "Long description\nSecond line",
            True,
        ),
        (
            "Short description\nLong description",
            "Short description",
            "Long description",
            False,
        ),
        (
            """
            Short description
            Long description
            """,
            "Short description",
            "Long description",
            False,
        ),
        (
            "\nShort description\nLong description\n",
            "Short description",
            "Long description",
            False,
        ),
        (
            """
            Short description
            Long description
            Second line
            """,
            "Short description",
            "Long description\nSecond line",
            False,
        ),
    ],
)
def test_long_description(
    source: str,
    expected_short_desc: str,
    expected_long_desc: str,
    expected_blank: bool,
) -> None:
    docstring = parse(source)
    assert docstring.short_description == expected_short_desc
    assert docstring.long_description == expected_long_desc
    assert docstring.blank_after_short_description == expected_blank
    assert docstring.meta == []


@pytest.mark.parametrize(
    "source, expected_short_desc, expected_long_desc, "
    "expected_blank_short_desc, expected_blank_long_desc",
    [
        (
            """
            Short description
            Args:
                asd:
            """,
            "Short description",
            None,
            False,
            False,
        ),
        (
            """
            Short description
            Long description
            Args:
                asd:
            """,
            "Short description",
            "Long description",
            False,
            False,
        ),
        (
            """
            Short description
            First line
                Second line
            Args:
                asd:
            """,
            "Short description",
            "First line\n    Second line",
            False,
            False,
        ),
        (
            """
            Short description

            First line
                Second line
            Args:
                asd:
            """,
            "Short description",
            "First line\n    Second line",
            True,
            False,
        ),
        (
            """
            Short description

            First line
                Second line

            Args:
                asd:
            """,
            "Short description",
            "First line\n    Second line",
            True,
            True,
        ),
        (
            """
            Args:
                asd:
            """,
            None,
            None,
            False,
            False,
        ),
    ],
)
def test_meta_newlines(
    source: str,
    expected_short_desc: T.Optional[str],
    expected_long_desc: T.Optional[str],
    expected_blank_short_desc: bool,
    expected_blank_long_desc: bool,
) -> None:
    docstring = parse(source)
    assert docstring.short_description == expected_short_desc
    assert docstring.long_description == expected_long_desc
    assert docstring.blank_after_short_description == expected_blank_short_desc
    assert docstring.blank_after_long_description == expected_blank_long_desc
    assert len(docstring.meta) == 1


def test_meta_with_multiline_description() -> None:
    docstring = parse(
        """
        Short description

        Args:
            spam: asd
                1
                    2
                3
        """
    )
    assert docstring.short_description == "Short description"
    assert len(docstring.meta) == 1
    assert docstring.meta[0].args == ["param", "spam"]
    assert docstring.meta[0].arg_name == "spam"
    assert docstring.meta[0].description == "asd\n1\n    2\n3"


def test_default_args():
    docstring = parse(
        """A sample function

    A function the demonstrates docstrings
    
    Args:
        arg1 (int): The firsty arg
        arg2 (str): The second arg
        arg3 (float, optional): The third arg. Defaults to 1.0.
        arg4 (Optional[Dict[str, Any]], optional): The fourth arg. Defaults to None.
        arg5 (str, optional): The fifth arg. Defaults to DEFAULT_ARG5.
    
    Returns:
        Mapping[str, Any]: The args packed in a mapping
    """
    )
    assert docstring is not None
    assert len(docstring.params) == 5

    arg4 = docstring.params[3]
    assert arg4.arg_name == "arg4"
    assert arg4.is_optional
    assert arg4.type_name == "Optional[Dict[str, Any]]"
    assert arg4.default == "None"
    assert arg4.description == "The fourth arg. Defaults to None."


def test_multiple_meta() -> None:
    docstring = parse(
        """
        Short description

        Args:
            spam: asd
                1
                    2
                3

        Raises:
            bla: herp
            yay: derp
        """
    )
    assert docstring.short_description == "Short description"
    assert len(docstring.meta) == 3
    assert docstring.meta[0].args == ["param", "spam"]
    assert docstring.meta[0].arg_name == "spam"
    assert docstring.meta[0].description == "asd\n1\n    2\n3"
    assert docstring.meta[1].args == ["raises", "bla"]
    assert docstring.meta[1].type_name == "bla"
    assert docstring.meta[1].description == "herp"
    assert docstring.meta[2].args == ["raises", "yay"]
    assert docstring.meta[2].type_name == "yay"
    assert docstring.meta[2].description == "derp"


def test_params() -> None:
    docstring = parse("Short description")
    assert len(docstring.params) == 0

    docstring = parse(
        """
        Short description

        Args:
            name: description 1
            priority (int): description 2
            sender (str?): description 3
            ratio (Optional[float], optional): description 4
        """
    )
    assert len(docstring.params) == 4
    assert docstring.params[0].arg_name == "name"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].description == "description 1"
    assert not docstring.params[0].is_optional
    assert docstring.params[1].arg_name == "priority"
    assert docstring.params[1].type_name == "int"
    assert docstring.params[1].description == "description 2"
    assert not docstring.params[1].is_optional
    assert docstring.params[2].arg_name == "sender"
    assert docstring.params[2].type_name == "str"
    assert docstring.params[2].description == "description 3"
    assert docstring.params[2].is_optional
    assert docstring.params[3].arg_name == "ratio"
    assert docstring.params[3].type_name == "Optional[float]"
    assert docstring.params[3].description == "description 4"
    assert docstring.params[3].is_optional

    docstring = parse(
        """
        Short description

        Args:
            name: description 1
                with multi-line text
            priority (int): description 2
        """
    )
    assert len(docstring.params) == 2
    assert docstring.params[0].arg_name == "name"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].description == (
        "description 1\n" "with multi-line text"
    )
    assert docstring.params[1].arg_name == "priority"
    assert docstring.params[1].type_name == "int"
    assert docstring.params[1].description == "description 2"


def test_attributes() -> None:
    docstring = parse("Short description")
    assert len(docstring.params) == 0

    docstring = parse(
        """
        Short description

        Attributes:
            name: description 1
            priority (int): description 2
            sender (str?): description 3
            ratio (Optional[float], optional): description 4
        """
    )
    assert len(docstring.params) == 4
    assert docstring.params[0].arg_name == "name"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].description == "description 1"
    assert not docstring.params[0].is_optional
    assert docstring.params[1].arg_name == "priority"
    assert docstring.params[1].type_name == "int"
    assert docstring.params[1].description == "description 2"
    assert not docstring.params[1].is_optional
    assert docstring.params[2].arg_name == "sender"
    assert docstring.params[2].type_name == "str"
    assert docstring.params[2].description == "description 3"
    assert docstring.params[2].is_optional
    assert docstring.params[3].arg_name == "ratio"
    assert docstring.params[3].type_name == "Optional[float]"
    assert docstring.params[3].description == "description 4"
    assert docstring.params[3].is_optional

    docstring = parse(
        """
        Short description

        Attributes:
            name: description 1
                with multi-line text
            priority (int): description 2
        """
    )
    assert len(docstring.params) == 2
    assert docstring.params[0].arg_name == "name"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].description == (
        "description 1\n" "with multi-line text"
    )
    assert docstring.params[1].arg_name == "priority"
    assert docstring.params[1].type_name == "int"
    assert docstring.params[1].description == "description 2"


def test_returns() -> None:
    docstring = parse(
        """
        Short description
        """
    )
    assert docstring.returns is None

    docstring = parse(
        """
        Short description
        Returns:
            description
        """
    )
    assert docstring.returns is not None
    assert docstring.returns.type_name is None
    assert docstring.returns.description == "description"

    docstring = parse(
        """
        Short description
        Returns:
            description with: a colon!
        """
    )
    assert docstring.returns is not None
    assert docstring.returns.type_name is None
    assert docstring.returns.description == "description with: a colon!"

    docstring = parse(
        """
        Short description
        Returns:
            int: description
        """
    )
    assert docstring.returns is not None
    assert docstring.returns.type_name == "int"
    assert docstring.returns.description == "description"

    docstring = parse(
        """
        Returns:
            Optional[Mapping[str, List[int]]]: A description: with a colon
        """
    )
    assert docstring.returns is not None
    assert docstring.returns.type_name == "Optional[Mapping[str, List[int]]]"
    assert docstring.returns.description == "A description: with a colon"

    docstring = parse(
        """
        Short description
        Yields:
            int: description
        """
    )
    assert docstring.returns is not None
    assert docstring.returns.type_name == "int"
    assert docstring.returns.description == "description"

    docstring = parse(
        """
        Short description
        Returns:
            int: description
            with much text

            even some spacing
        """
    )
    assert docstring.returns is not None
    assert docstring.returns.type_name == "int"
    assert docstring.returns.description == (
        "description\n" "with much text\n\n" "even some spacing"
    )


def test_raises() -> None:
    docstring = parse(
        """
        Short description
        """
    )
    assert len(docstring.raises) == 0

    docstring = parse(
        """
        Short description
        Raises:
            ValueError: description
        """
    )
    assert len(docstring.raises) == 1
    assert docstring.raises[0].type_name == "ValueError"
    assert docstring.raises[0].description == "description"


def test_examples() -> None:
    docstring = parse(
        """
        Short description
        Example:
            example: 1
        Examples:
            long example

            more here
        """
    )
    assert len(docstring.meta) == 2
    assert docstring.meta[0].description == "example: 1"
    assert docstring.meta[1].description == "long example\n\nmore here"


def test_broken_meta() -> None:
    with pytest.raises(ParseError):
        parse("Args:")

    with pytest.raises(ParseError):
        parse("Args:\n    herp derp")
