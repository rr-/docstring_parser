"""Tests for Google-style docstring routines."""

import subprocess
import sys

import pytest

from docstring_parser import DocstringRaises, google
from docstring_parser.google import (
    GoogleParser,
    Section,
    SectionType,
    compose,
    parse,
)


def test_google_parser_unknown_section() -> None:
    """Test parsing an unknown section with default GoogleParser
    configuration.
    """
    parser = GoogleParser()
    docstring = parser.parse(
        """
        Unknown:
            spam: a
        """
    )
    assert docstring.short_description == "Unknown:"
    assert docstring.long_description == "spam: a"
    assert len(docstring.meta) == 0


def test_google_parser_multi_line_parameter_type() -> None:
    """Test parsing a multi-line parameter type with default GoogleParser"""
    parser = GoogleParser()
    docstring = parser.parse(
        """Description of the function.

        Args:
            output_type (Literal["searchResults", "sourcedAnswer",
                "structured"]): The type of output.
                This can be one of the following:
                - "searchResults": Represents the search results.
                - "sourcedAnswer": Represents a sourced answer.
                - "structured": Represents a structured output format.

        Returns:
            bool: Indicates success or failure.

        """
    )
    assert docstring.params[0].arg_name == "output_type"


def test_google_parser_custom_sections() -> None:
    """Test parsing an unknown section with custom GoogleParser
    configuration.
    """
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
    assert docstring.meta[0].key == "desc"
    assert docstring.meta[0].description == "This is the description."
    assert docstring.meta[1].key == "param"
    assert docstring.meta[1].arg_name == "arg1"
    assert docstring.meta[1].description == "first arg"
    assert docstring.meta[2].key == "param"
    assert docstring.meta[2].arg_name == "arg2"
    assert docstring.meta[2].description == "second arg"
    assert docstring.meta[3].key == "attribute"
    assert docstring.meta[3].arg_name == "attr1"
    assert docstring.meta[3].description == "first attribute"
    assert docstring.meta[4].key == "attribute"
    assert docstring.meta[4].arg_name == "attr2"
    assert docstring.meta[4].description == "second attribute"
    assert docstring.meta[5].key == "examples"
    assert docstring.meta[5].description == "Many examples\nMore examples"


def test_google_parser_custom_sections_after() -> None:
    """Test parsing an unknown section with custom GoogleParser configuration
    that was set at a runtime.
    """
    parser = GoogleParser(title_colon=False)
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
    assert docstring.meta[0].key == "note"
    assert docstring.meta[0].description == "a note"


def test_google_incomplete_type_finishes_promptly():
    """A bounded malformed declaration must not stall schema extraction."""
    code = """
from docstring_parser import parse, parse_from_object
name = 'a(' * 2048
doc = 'Summary.\\n\\nArgs:\\n    ' + name + ': description'
def tool():
    pass
tool.__doc__ = doc
for result in (parse(doc), parse_from_object(tool)):
    assert result.params[0].arg_name == name
    assert result.params[0].type_name is None
"""
    subprocess.run([sys.executable, "-c", code], check=True, timeout=5)


def test_google_long_union_return_finishes_promptly():
    """A long union return type, or a near miss, must parse in one pass."""
    code = """
from docstring_parser import parse
union = ' | '.join(['dict[str, list[int]]'] * 20000)
for head, type_name in ((union, union), (union + ' x', None)):
    doc = 'Summary.\\n\\nReturns:\\n    ' + head + ': description'
    assert parse(doc, 'google').returns.type_name == type_name
near = '[' * 20000 + ' | x'
doc = 'Summary.\\n\\nReturns:\\n    ' + near + ': description'
assert parse(doc, 'google').returns.type_name is None
"""
    subprocess.run([sys.executable, "-c", code], check=True, timeout=5)


def test_parse_reuses_default_parser() -> None:
    """Test that parse builds the default parser once."""
    google.parse("Short.")
    parsers = google._parsers.parsers()
    google.parse("Short.\n\nArgs:\n    a: A.")
    assert google._parsers.parsers() == parsers


def test_parse_follows_default_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that parse picks up changes to DEFAULT_SECTIONS."""
    text = "Short.\n\nNotes:\n    Mind the gap."
    assert parse(text).meta == []
    monkeypatch.setattr(
        google,
        "DEFAULT_SECTIONS",
        [
            *google.DEFAULT_SECTIONS,
            Section("Notes", "notes", SectionType.SINGULAR),
        ],
    )
    assert parse(text).meta[0].key == "notes"


@pytest.mark.parametrize("title", ["Notes?", "C++ Notes", "Args (old)"])
def test_section_title_is_literal(title: str) -> None:
    """Test that regex characters in a section title match literally."""
    parser = GoogleParser(
        [Section(title, "custom", SectionType.SINGULAR)], title_colon=True
    )
    docstring = parser.parse(f"Short.\n\n{title}:\n    text")
    assert [(m.key, m.description) for m in docstring.meta] == [
        ("custom", "text")
    ]


def test_raises_without_type_among_typed() -> None:
    """Test that a raises with no type composes among typed ones and reads
    back the same."""
    docstring = google.parse("Short.\n\nRaises:\n    ValueError: Bad.\n")
    docstring.raises[0].type_name = None
    docstring.meta.append(
        DocstringRaises(description="Worse.", type_name="KeyError")
    )
    text = google.compose(docstring)
    assert text == "Short.\n\nRaises:\n    : Bad.\n    KeyError: Worse."
    again = google.parse(text)
    assert again.raises[0].type_name is None
    assert again.raises[0].description == "Bad."
    assert again.raises[1].type_name == "KeyError"
    assert again.raises[1].description == "Worse."


def test_raises_sphinx_type_head() -> None:
    """Test that a type marked as Sphinx does it is a raises head."""
    docstring = google.parse(
        "Short.\n\nRaises:\n    ~pkg.Error:\n        If it fails.\n"
    )
    assert docstring.raises[0].type_name == "~pkg.Error"
    assert docstring.raises[0].description == "If it fails."


def test_examples_split_as_doctest_reads_them() -> None:
    """Test that each example is its text, then its snippet and output."""
    text = (
        "Short.\n\n"
        "Examples:\n"
        "    To print a number:\n\n"
        "    >>> for i in range(1):\n"
        "    ...     print(i)\n"
        "    0\n\n"
        "    Then more.\n"
    )
    docstring = parse(text)
    assert len(docstring.examples) == 2
    assert docstring.examples[0].description == "To print a number:"
    assert docstring.examples[0].snippet == (
        ">>> for i in range(1):\n...     print(i)\n0"
    )
    assert docstring.examples[1].description == "Then more."
    assert docstring.examples[1].snippet is None
    assert compose(docstring) == text.rstrip("\n")
