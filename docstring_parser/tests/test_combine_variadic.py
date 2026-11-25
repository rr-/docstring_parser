"""Combining docstrings retains the documented variadic names."""

import pytest

from docstring_parser import parse
from docstring_parser.util import combine_docstrings


@pytest.mark.parametrize("prefixes", [("", ""), ("*", "**")])
def test_variadic_parameter_names(prefixes):
    def source(unused, *args, **kwargs):
        pass

    arg_prefix, kw_prefix = prefixes
    source.__doc__ = (
        ":param unused: Not part of the target signature.\n"
        f":param {arg_prefix}args: Positional values.\n"
        f":param {kw_prefix}kwargs: Named values.\n"
    )

    @combine_docstrings(source)
    def wrapped(*args, **kwargs):
        pass

    params = parse(wrapped.__doc__).params
    assert [(param.arg_name, param.description) for param in params] == [
        (arg_prefix + "args", "Positional values."),
        (kw_prefix + "kwargs", "Named values."),
    ]
