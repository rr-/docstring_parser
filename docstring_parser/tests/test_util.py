"""Test for utility functions."""

from docstring_parser.common import DocstringReturns
from docstring_parser.util import combine_docstrings


def test_combine_docstrings() -> None:
    """Test combine_docstrings wrapper."""

    def fun1(a, b, c, d):
        """short_description: fun1

        :param a: fun1
        :param b: fun1
        :return: fun1
        """

    def fun2(b, c, d, e):
        """short_description: fun2

        long_description: fun2

        :param b: fun2
        :param c: fun2
        :param e: fun2
        """

    @combine_docstrings(fun1, fun2)
    def decorated(a, b, c, d, e, f):
        """
        :param e: decorated
        :param f: decorated
        """

    assert decorated.__doc__ == (
        "short_description: fun2\n"
        "\n"
        "long_description: fun2\n"
        "\n"
        ":param a: fun1\n"
        ":param b: fun1\n"
        ":param c: fun2\n"
        ":param e: fun2\n"
        ":param f: decorated\n"
        ":returns: fun1"
    )

    @combine_docstrings(fun1, fun2, exclude=[DocstringReturns])
    def decorated(a, b, c, d, e, f):
        pass

    assert decorated.__doc__ == (
        "short_description: fun2\n"
        "\n"
        "long_description: fun2\n"
        "\n"
        ":param a: fun1\n"
        ":param b: fun1\n"
        ":param c: fun2\n"
        ":param e: fun2"
    )
