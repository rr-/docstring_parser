"""Exclusions apply to all metadata and remain reusable."""

import pytest

from docstring_parser import DocstringParam, DocstringReturns, parse
from docstring_parser.util import combine_docstrings


@pytest.mark.parametrize(
    "excluded",
    [
        (DocstringParam,),
        (DocstringReturns,),
        (DocstringParam, DocstringReturns),
    ],
)
@pytest.mark.parametrize("iterator", [False, True])
def test_excluded_metadata_is_not_reinserted(excluded, iterator):
    def source(value):
        """Source.

        :param value: The value.
        :return: The result.
        """

    decorator = combine_docstrings(
        source, exclude=iter(excluded) if iterator else excluded
    )
    for _ in range(2):

        def wrapped(value):
            pass

        doc = parse(decorator(wrapped).__doc__)
        assert bool(doc.params) == (DocstringParam not in excluded)
        assert bool(doc.many_returns) == (DocstringReturns not in excluded)
