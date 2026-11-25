"""Parameter precedence follows the metadata precedence."""

from docstring_parser import parse
from docstring_parser.util import combine_docstrings


def test_wrapped_and_rightmost_parameter_descriptions_win():
    def first(value, fallback):
        """:param value: first value
        :param fallback: first fallback
        """

    def second(value, fallback):
        """:param value: second value
        :param fallback: second fallback
        """

    @combine_docstrings(first, second)
    def wrapped(value, fallback):
        """:param value: wrapped value"""

    params = parse(wrapped.__doc__).params_by_name
    assert params["value"].description == "wrapped value"
    assert params["fallback"].description == "second fallback"
