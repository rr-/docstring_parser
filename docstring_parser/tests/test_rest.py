import typing as T

import pytest
from docstring_parser.common import ParseError
from docstring_parser.rest import parse


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
            :meta: asd
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
            :meta: asd
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
            :meta: asd
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
            :meta: asd
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

            :meta: asd
            """,
            "Short description",
            "First line\n    Second line",
            True,
            True,
        ),
        (
            """
            :meta: asd
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

        :meta: asd
            1
                2
            3
        """
    )
    assert docstring.short_description == "Short description"
    assert len(docstring.meta) == 1
    assert docstring.meta[0].args == ["meta"]
    assert docstring.meta[0].description == "asd\n1\n    2\n3"


def test_multiple_meta() -> None:
    docstring = parse(
        """
        Short description

        :meta1: asd
            1
                2
            3
        :meta2: herp
        :meta3: derp
        """
    )
    assert docstring.short_description == "Short description"
    assert len(docstring.meta) == 3
    assert docstring.meta[0].args == ["meta1"]
    assert docstring.meta[0].description == "asd\n1\n    2\n3"
    assert docstring.meta[1].args == ["meta2"]
    assert docstring.meta[1].description == "herp"
    assert docstring.meta[2].args == ["meta3"]
    assert docstring.meta[2].description == "derp"


def test_meta_with_args() -> None:
    docstring = parse(
        """
        Short description

        :meta ene due rabe: asd
        """
    )
    assert docstring.short_description == "Short description"
    assert len(docstring.meta) == 1
    assert docstring.meta[0].args == ["meta", "ene", "due", "rabe"]
    assert docstring.meta[0].description == "asd"


def test_params() -> None:
    docstring = parse("Short description")
    assert len(docstring.params) == 0

    docstring = parse(
        """
        Short description

        :param name: description 1
        :param int priority: description 2
        :param str? sender: description 3
        :param str? message: description 4, defaults to 'hello'
        :param str? multiline: long description 5,
        defaults to 'bye'
        """
    )
    assert len(docstring.params) == 5
    assert docstring.params[0].arg_name == "name"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].description == "description 1"
    assert docstring.params[0].default is None
    assert not docstring.params[0].is_optional
    assert docstring.params[1].arg_name == "priority"
    assert docstring.params[1].type_name == "int"
    assert docstring.params[1].description == "description 2"
    assert not docstring.params[1].is_optional
    assert docstring.params[1].default is None
    assert docstring.params[2].arg_name == "sender"
    assert docstring.params[2].type_name == "str"
    assert docstring.params[2].description == "description 3"
    assert docstring.params[2].is_optional
    assert docstring.params[2].default is None
    assert docstring.params[3].arg_name == "message"
    assert docstring.params[3].type_name == "str"
    assert (
        docstring.params[3].description == "description 4, defaults to 'hello'"
    )
    assert docstring.params[3].is_optional
    assert docstring.params[3].default == "'hello'"
    assert docstring.params[4].arg_name == "multiline"
    assert docstring.params[4].type_name == "str"
    assert (
        docstring.params[4].description
        == "long description 5,\ndefaults to 'bye'"
    )
    assert docstring.params[4].is_optional
    assert docstring.params[4].default == "'bye'"


def test_returns() -> None:
    docstring = parse(
        """
        Short description
        """
    )
    assert docstring.returns is None
    assert docstring.many_returns is not None
    assert len(docstring.many_returns) == 0

    docstring = parse(
        """
        Short description
        :returns: description
        """
    )
    assert docstring.returns is not None
    assert docstring.returns.type_name is None
    assert docstring.returns.description == "description"
    assert not docstring.returns.is_generator
    assert docstring.many_returns is not None
    assert len(docstring.many_returns) == 1
    assert docstring.many_returns[0] == docstring.returns

    docstring = parse(
        """
        Short description
        :returns int: description
        """
    )
    assert docstring.returns is not None
    assert docstring.returns.type_name == "int"
    assert docstring.returns.description == "description"
    assert not docstring.returns.is_generator
    assert docstring.many_returns is not None
    assert len(docstring.many_returns) == 1
    assert docstring.many_returns[0] == docstring.returns


def test_yields() -> None:
    docstring = parse(
        """
        Short description
        """
    )
    assert docstring.returns is None
    assert docstring.many_returns is not None
    assert len(docstring.many_returns) == 0

    docstring = parse(
        """
        Short description
        :yields: description
        """
    )
    assert docstring.returns is not None
    assert docstring.returns.type_name is None
    assert docstring.returns.description == "description"
    assert docstring.returns.is_generator
    assert docstring.many_returns is not None
    assert len(docstring.many_returns) == 1
    assert docstring.many_returns[0] == docstring.returns

    docstring = parse(
        """
        Short description
        :yields int: description
        """
    )
    assert docstring.returns is not None
    assert docstring.returns.type_name == "int"
    assert docstring.returns.description == "description"
    assert docstring.returns.is_generator
    assert docstring.many_returns is not None
    assert len(docstring.many_returns) == 1
    assert docstring.many_returns[0] == docstring.returns


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
        :raises: description
        """
    )
    assert len(docstring.raises) == 1
    assert docstring.raises[0].type_name is None
    assert docstring.raises[0].description == "description"

    docstring = parse(
        """
        Short description
        :raises ValueError: description
        """
    )
    assert len(docstring.raises) == 1
    assert docstring.raises[0].type_name == "ValueError"
    assert docstring.raises[0].description == "description"


def test_broken_meta() -> None:
    with pytest.raises(ParseError):
        parse(":")

    with pytest.raises(ParseError):
        parse(":param herp derp")

    with pytest.raises(ParseError):
        parse(":param: invalid")

    with pytest.raises(ParseError):
        parse(":param with too many args: desc")

    # these should not raise any errors
    parse(":sthstrange: desc")
