import typing as T

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
    assert docstring.meta == []


@pytest.mark.parametrize(
    'source, expected_short_desc, expected_long_desc, expected_blank',
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
        expected_blank: bool
) -> None:
    docstring = parse(source)
    assert docstring.short_description == expected_short_desc
    assert docstring.long_description == expected_long_desc
    assert docstring.blank_after_short_description == expected_blank
    assert docstring.meta == []


@pytest.mark.parametrize(
    'source, expected_long_desc, '
    'expected_blank_short_desc, expected_blank_long_desc',
    [
        (
            '''
            Short description
            :param: asd
            ''',
            None, False, False
        ),

        (
            '''
            Short description
            Long description
            :param: asd
            ''',
            'Long description', False, False
        ),

        (
            '''
            Short description
            Long description
                Second line
            :param: asd
            ''',
            'Long description\n    Second line', False, False
        ),

        (
            '''
            Short description

            Long description
                Second line
            :param: asd
            ''',
            'Long description\n    Second line', True, False
        ),

        (
            '''
            Short description

            Long description
                Second line

            :param: asd
            ''',
            'Long description\n    Second line', True, True
        )
    ]
)
def test_meta_newlines(
        source: str,
        expected_long_desc: T.Optional[str],
        expected_blank_short_desc: bool,
        expected_blank_long_desc: bool
) -> None:
    docstring = parse(source)
    assert docstring.short_description == 'Short description'
    assert docstring.long_description == expected_long_desc
    assert docstring.blank_after_short_description == expected_blank_short_desc
    assert docstring.blank_after_long_description == expected_blank_long_desc
    assert len(docstring.meta) == 1


def test_meta_with_multiline_description() -> None:
    docstring = parse(
        '''
        Short description

        :param: asd
            1
                2
            3
        ''')
    assert docstring.short_description == 'Short description'
    assert len(docstring.meta) == 1
    assert docstring.meta[0].args == ['param']
    assert docstring.meta[0].description == 'asd\n1\n    2\n3'


def test_multiple_meta() -> None:
    docstring = parse(
        '''
        Short description

        :param: asd
            1
                2
            3
        :param2: herp
        :param3: derp
        ''')
    assert docstring.short_description == 'Short description'
    assert len(docstring.meta) == 3
    assert docstring.meta[0].args == ['param']
    assert docstring.meta[0].description == 'asd\n1\n    2\n3'
    assert docstring.meta[1].args == ['param2']
    assert docstring.meta[1].description == 'herp'
    assert docstring.meta[2].args == ['param3']
    assert docstring.meta[2].description == 'derp'
