"""Tests for the ways Google parsing can be set up."""

from docstring_parser import google


def test_google_title_without_colon() -> None:
    """``title_colon=False`` recognises titles with no colon after them."""
    parser = google.GoogleParser(title_colon=False)
    docstring = parser.parse("Summary.\n\nArgs\n    x: The x.\n")
    assert [p.arg_name for p in docstring.params] == ["x"]


def test_google_custom_section() -> None:
    """A section can be added with a title and key of its own."""
    parser = google.GoogleParser(
        [
            *google.DEFAULT_SECTIONS,
            google.Section("Inputs", "param", google.SectionType.MULTIPLE),
        ]
    )
    docstring = parser.parse("Summary.\n\nInputs:\n    x (int): The x.\n")
    (param,) = docstring.params
    assert (param.key, param.type_name) == ("param", "int")
    assert param.arg_name == "x"
