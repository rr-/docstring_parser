"""Tests for generic docstring routines."""

import typing as T

import pytest

from docstring_parser.common import Docstring, DocstringStyle, ParseError
from docstring_parser.parser import compose, parse


@pytest.mark.parametrize(
    "source, expected",
    [
        pytest.param(None, None, id="No __doc__"),
        ("", None),
        ("\n", None),
        ("Short description", "Short description"),
        ("\nShort description\n", "Short description"),
        ("\n   Short description\n", "Short description"),
    ],
)
def test_short_description(
    source: T.Optional[str], expected: T.Optional[str]
) -> None:
    """Test parsing short description."""
    docstring = parse(source)
    assert docstring.short_description == expected
    assert docstring.description == expected
    assert docstring.long_description is None
    assert not docstring.meta


def test_rest() -> None:
    """Test ReST-style parser autodetection."""
    docstring = parse(
        """
        Short description

        Long description

        Causing people to indent:

            A lot sometimes

        :param spam: spam desc
        :param int bla: bla desc
        :param str yay:
        :raises ValueError: exc desc
        :returns tuple: ret desc
        """
    )

    assert docstring.style == DocstringStyle.REST
    assert docstring.short_description == "Short description"
    assert docstring.long_description == (
        "Long description\n\nCausing people to indent:\n\n    A lot sometimes"
    )
    assert docstring.description == (
        "Short description\n\n"
        "Long description\n\n"
        "Causing people to indent:\n\n"
        "    A lot sometimes"
    )
    assert len(docstring.params) == 3
    assert docstring.params[0].arg_name == "spam"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].description == "spam desc"
    assert docstring.params[1].arg_name == "bla"
    assert docstring.params[1].type_name == "int"
    assert docstring.params[1].description == "bla desc"
    assert docstring.params[2].arg_name == "yay"
    assert docstring.params[2].type_name == "str"
    assert docstring.params[2].description == ""
    assert len(docstring.raises) == 1
    assert docstring.raises[0].type_name == "ValueError"
    assert docstring.raises[0].description == "exc desc"
    assert docstring.returns is not None
    assert docstring.returns.type_name == "tuple"
    assert docstring.returns.description == "ret desc"
    assert docstring.many_returns is not None
    assert len(docstring.many_returns) == 1
    assert docstring.many_returns[0] == docstring.returns


def test_google() -> None:
    """Test Google-style parser autodetection."""
    docstring = parse(
        """Short description

        Long description

        Causing people to indent:

            A lot sometimes

        Args:
            spam: spam desc
            bla (int): bla desc
            yay (str):

        Raises:
            ValueError: exc desc

        Returns:
            tuple: ret desc
        """
    )

    assert docstring.style == DocstringStyle.GOOGLE
    assert docstring.short_description == "Short description"
    assert docstring.long_description == (
        "Long description\n\nCausing people to indent:\n\n    A lot sometimes"
    )
    assert docstring.description == (
        "Short description\n\n"
        "Long description\n\n"
        "Causing people to indent:\n\n"
        "    A lot sometimes"
    )
    assert len(docstring.params) == 3
    assert docstring.params[0].arg_name == "spam"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].description == "spam desc"
    assert docstring.params[1].arg_name == "bla"
    assert docstring.params[1].type_name == "int"
    assert docstring.params[1].description == "bla desc"
    assert docstring.params[2].arg_name == "yay"
    assert docstring.params[2].type_name == "str"
    assert docstring.params[2].description == ""
    assert len(docstring.raises) == 1
    assert docstring.raises[0].type_name == "ValueError"
    assert docstring.raises[0].description == "exc desc"
    assert docstring.returns is not None
    assert docstring.returns.type_name == "tuple"
    assert docstring.returns.description == "ret desc"
    assert docstring.many_returns is not None
    assert len(docstring.many_returns) == 1
    assert docstring.many_returns[0] == docstring.returns


def test_numpydoc() -> None:
    """Test numpydoc-style parser autodetection."""
    docstring = parse(
        """Short description

        Long description

        Causing people to indent:

            A lot sometimes

        Parameters
        ----------
        spam
            spam desc
        bla : int
            bla desc
        yay : str

        Raises
        ------
        ValueError
            exc desc

        Other Parameters
        ----------------
        this_guy : int, optional
            you know him

        Returns
        -------
        tuple
            ret desc

        See Also
        --------
        multiple lines...
        something else?

        Warnings
        --------
        multiple lines...
        none of this is real!
        """
    )

    assert docstring.style == DocstringStyle.NUMPYDOC
    assert docstring.short_description == "Short description"
    assert docstring.long_description == (
        "Long description\n\nCausing people to indent:\n\n    A lot sometimes"
    )
    assert docstring.description == (
        "Short description\n\n"
        "Long description\n\n"
        "Causing people to indent:\n\n"
        "    A lot sometimes"
    )
    assert len(docstring.params) == 4
    assert docstring.params[0].arg_name == "spam"
    assert docstring.params[0].type_name is None
    assert docstring.params[0].description == "spam desc"
    assert docstring.params[1].arg_name == "bla"
    assert docstring.params[1].type_name == "int"
    assert docstring.params[1].description == "bla desc"
    assert docstring.params[2].arg_name == "yay"
    assert docstring.params[2].type_name == "str"
    assert docstring.params[2].description is None
    assert docstring.params[3].arg_name == "this_guy"
    assert docstring.params[3].type_name == "int"
    assert docstring.params[3].is_optional
    assert docstring.params[3].description == "you know him"

    assert len(docstring.raises) == 1
    assert docstring.raises[0].type_name == "ValueError"
    assert docstring.raises[0].description == "exc desc"
    assert docstring.returns is not None
    assert docstring.returns.type_name == "tuple"
    assert docstring.returns.description == "ret desc"
    assert docstring.many_returns is not None
    assert len(docstring.many_returns) == 1
    assert docstring.many_returns[0] == docstring.returns


def test_autodetection_error_detection() -> None:
    """Test autodection for the case where one of the parsers throws an error
    and another one succeeds.
    """
    source = """
    Does something useless

    :param 3 + 3 a: a param
    """

    with pytest.raises(ParseError):
        # assert that one of the parsers does raise
        parse(source, DocstringStyle.REST)

    # assert that autodetection still works
    docstring = parse(source)

    assert docstring
    assert docstring.style == DocstringStyle.GOOGLE


def test_compose_without_style() -> None:
    """Test composing a docstring that has no style to fall back on."""
    with pytest.raises(ValueError):
        compose(Docstring())


def test_google_without_summary_is_detected() -> None:
    """A Google docstring that opens with a section title must not fall
    back to a REST parse with no params.
    """
    docstring = parse(
        """Args:
            spam: description
        """
    )
    assert docstring.style == DocstringStyle.GOOGLE
    assert len(docstring.params) == 1
    assert docstring.params[0].arg_name == "spam"
    assert docstring.params[0].description == "description"


@pytest.mark.parametrize(
    "style, source",
    [
        (
            DocstringStyle.REST,
            """Short.

            Long.

            :param a: first
            :returns: result
            """,
        ),
        (
            DocstringStyle.GOOGLE,
            """Short.

            Args:
                a: first

            Returns:
                result
            """,
        ),
        (
            DocstringStyle.NUMPYDOC,
            """Short.

            Parameters
            ----------
            a
                first

            Returns
            -------
            result
            """,
        ),
        (
            DocstringStyle.EPYDOC,
            """Short.

            @param a: first
            @return: result
            """,
        ),
    ],
)
@pytest.mark.parametrize("line_ending", ["\r\n", "\r"])
def test_line_endings(
    style: DocstringStyle, source: str, line_ending: str
) -> None:
    """Test that other line endings parse the same as newlines."""
    expected = parse(source, style)
    docstring = parse(source.replace("\n", line_ending), style)
    assert len(expected.meta) == 2
    assert docstring.short_description == expected.short_description
    assert docstring.long_description == expected.long_description
    assert [m.args for m in docstring.meta] == [m.args for m in expected.meta]
    assert [m.description for m in docstring.meta] == [
        m.description for m in expected.meta
    ]
