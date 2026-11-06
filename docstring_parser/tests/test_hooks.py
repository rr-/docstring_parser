"""Tests for the ways a style's parsing can be customised by overriding."""

import re
import typing as T

from docstring_parser import google, numpydoc
from docstring_parser.common import DocstringMeta, DocstringParam


def test_numpydoc_section_parse_override() -> None:
    """A section that parses its own text gets the section body."""
    seen = []

    class Shout(numpydoc.Section):
        def parse(self, text: str) -> T.Iterable[DocstringMeta]:
            seen.append(text)
            yield DocstringMeta(text.upper(), key=self.key)

    parser = numpydoc.NumpydocParser(
        [*numpydoc.DEFAULT_SECTIONS, Shout("Shout", "shout")]
    )
    docstring = parser.parse("Summary.\n\nShout\n-----\nhello\nthere\n")
    assert seen == ["\nhello\nthere"]
    assert [m.key for m in docstring.meta] == ["shout"]
    assert docstring.meta[0].description == "\nHELLO\nTHERE"


def test_numpydoc_kv_section_parse_item_override() -> None:
    """A key-value section that builds its own items gets key and value."""

    class Options(numpydoc._KVSection):
        def _parse_item(self, key: str, value: str) -> DocstringMeta:
            return DocstringMeta(value + "!", key=self.key, name=key)

    parser = numpydoc.NumpydocParser(
        [*numpydoc.DEFAULT_SECTIONS, Options("Options", "option")]
    )
    docstring = parser.parse(
        "Summary.\n\nOptions\n-------\nfast\n    Go fast.\nslow\n    Not.\n"
    )
    assert [(m.key, m.description) for m in docstring.meta] == [
        ("option", "Go fast.!"),
        ("option", "Not.!"),
    ]
    assert [m.name for m in docstring.meta] == ["fast", "slow"]


def test_numpydoc_param_section_parse_item_override() -> None:
    """A built-in section's item parsing can be overridden."""

    class Params(numpydoc.ParamSection):
        def _parse_item(self, key: str, value: str) -> DocstringParam:
            param = super()._parse_item(key, value)
            param.arg_name = param.arg_name.upper()
            return param

    parser = numpydoc.NumpydocParser([Params("Parameters", "param")])
    docstring = parser.parse(
        "Summary.\n\nParameters\n----------\nx : int\n    The x.\n"
    )
    (param,) = docstring.params
    assert param.arg_name == "X"
    assert param.type_name == "int"
    assert param.description == "The x."


def test_google_build_meta_override() -> None:
    """A parser that builds its own items gets each item's text and title."""
    seen = []

    class Parser(google.GoogleParser):
        def _build_meta(self, text: str, title: str) -> DocstringMeta:
            seen.append((text, title))
            return super()._build_meta(text, title)

    docstring = Parser().parse(
        "Summary.\n\nArgs:\n    x (int): The x.\n    y: The\n        y.\n"
    )
    assert seen == [
        ("x (int): The x.", "Args"),
        ("y: The\n        y.", "Args"),
    ]
    assert [p.arg_name for p in docstring.params] == ["x", "y"]


def test_google_titles_re_override() -> None:
    """A parser can recognise titles with its own pattern."""

    class Parser(google.GoogleParser):
        def _setup(self) -> None:
            self.titles_re = re.compile(
                r"^(" + "|".join(map(re.escape, self.sections)) + r") ?:\s*$",
                flags=re.M,
            )

    docstring = Parser().parse("Summary.\n\nArgs :\n    x: The x.\n")
    assert [p.arg_name for p in docstring.params] == ["x"]


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
