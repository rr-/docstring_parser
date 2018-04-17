import pytest

from docstring_parser import parse


@pytest.mark.parametrize('source, expected', [
    ('Short description', 'Short description'),
    ('\nShort description\n', 'Short description'),
    ('\n   Short description\n', 'Short description'),
])
def test_short_description(source: str, expected: str) -> None:
    docstring = parse(source)
    assert docstring.short_description == expected
    assert docstring.long_description is None


@pytest.mark.parametrize(
    'source, expected_short_desc, expected_long_desc, expected_nl',
    [
        (
            'Short description\n\nLong description',
            'Short description',
            'Long description',
            True
        ),

        (
            '''
            Short description

            Long description
            ''',
            'Short description',
            'Long description',
            True
        ),

        (
            '''
            Short description

            Long description
            Second line
            ''',
            'Short description',
            'Long description\nSecond line',
            True
        ),

        (
            'Short description\nLong description',
            'Short description',
            'Long description',
            False
        ),

        (
            '''
            Short description
            Long description
            ''',
            'Short description',
            'Long description',
            False
        ),

        (
            '\nShort description\nLong description\n',
            'Short description',
            'Long description',
            False
        ),

        (
            '''
            Short description
            Long description
            Second line
            ''',
            'Short description',
            'Long description\nSecond line',
            False
        ),
    ]
)
def test_long_description(
        source: str,
        expected_short_desc: str,
        expected_long_desc: str,
        expected_nl: bool
) -> None:
    docstring = parse(source)
    assert docstring.short_description == expected_short_desc
    assert docstring.long_description == expected_long_desc
    assert docstring.nl_after_short_description == expected_nl
