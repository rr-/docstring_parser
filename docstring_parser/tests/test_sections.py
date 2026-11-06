"""Tests for declaring sections with SectionSpec."""

import typing as T

import pytest

from docstring_parser import (
    DocstringMeta,
    DocstringParam,
    DocstringStyle,
    ParseError,
    RenderingStyle,
    compose,
    parse,
)
from docstring_parser.sections import (
    Kind,
    Layout,
    SectionSpec,
    default_sections,
)
from docstring_parser.tests.cases import CASES_DIR, dump, read_case

STYLES = [
    DocstringStyle.REST,
    DocstringStyle.GOOGLE,
    DocstringStyle.NUMPYDOC,
    DocstringStyle.EPYDOC,
]
INPUTS = [read_case(p).input for p in sorted(CASES_DIR.rglob("*.txt"))]


def _result(text: str, style: DocstringStyle, **kwargs: T.Any) -> str:
    try:
        return dump(parse(text, style, **kwargs))
    except ParseError as ex:
        return f"ParseError: {ex}"


@pytest.mark.parametrize("style", STYLES, ids=lambda s: s.name.lower())
def test_default_sections_parse_as_no_sections(style: DocstringStyle) -> None:
    """Test that a style's default sections, given, change nothing."""
    sections = default_sections(style)
    for text in INPUTS:
        assert _result(text, style, sections=sections) == _result(text, style)


def test_default_sections_of_auto() -> None:
    """Test that auto mode has no sections of its own."""
    with pytest.raises(ValueError, match="no sections"):
        default_sections(DocstringStyle.AUTO)


def test_spec_defaults() -> None:
    """Test the key and layout a spec gets when given none."""
    spec = SectionSpec("Inputs", Kind.PARAM)
    assert (spec.titles, spec.key, spec.layout) == (
        ("Inputs",),
        "param",
        Layout.ITEMS,
    )
    spec = SectionSpec(["Returns", "Return"], Kind.RETURNS)
    assert (spec.titles, spec.key, spec.layout) == (
        ("Returns", "Return"),
        "returns",
        Layout.ITEM_OR_BLOCK,
    )
    spec = SectionSpec("See Also", Kind.TEXT)
    assert (spec.key, spec.layout) == ("see_also", Layout.BLOCK)
    with pytest.raises(ValueError, match="title"):
        SectionSpec([], Kind.TEXT)


def test_google_spec_section() -> None:
    """Test a Google section with several titles and its own kind."""
    sections = [
        *default_sections(DocstringStyle.GOOGLE),
        SectionSpec(("Keyword Args", "Kwargs"), Kind.OTHER_PARAM),
    ]
    docstring = parse(
        "Short.\n\nKwargs:\n    x (int): The x.\n",
        DocstringStyle.GOOGLE,
        sections=sections,
    )
    (param,) = docstring.params
    assert param.key == "other_param"
    assert (param.arg_name, param.type_name) == ("x", "int")


def test_google_sections_replace_defaults() -> None:
    """Test that sections not given are not recognised."""
    sections = [SectionSpec("Args", Kind.PARAM)]
    docstring = parse(
        "Short.\n\nRaises:\n    ValueError: Bad.\n",
        DocstringStyle.GOOGLE,
        sections=sections,
    )
    assert docstring.meta == []
    assert docstring.long_description == "Raises:\n    ValueError: Bad."


def test_google_bare_title() -> None:
    """Test a Google title that has no colon after it."""
    sections = [
        *default_sections(DocstringStyle.GOOGLE),
        SectionSpec("Todo", Kind.TEXT, bare=True),
    ]
    docstring = parse(
        "Short.\n\nTodo\n    Write it.\n\nArgs:\n    x: The x.\n",
        DocstringStyle.GOOGLE,
        sections=sections,
    )
    assert [(m.key, m.description) for m in docstring.meta] == [
        ("todo", "Write it."),
        ("param", "The x."),
    ]
    assert docstring.params[0].arg_name == "x"


def test_numpydoc_bare_title() -> None:
    """Test a Numpydoc title that has no underline, written its own way."""
    sections = [
        *default_sections(DocstringStyle.NUMPYDOC),
        SectionSpec("**Stars**", Kind.TEXT, key="stars", bare=True),
    ]
    docstring = parse(
        "Short.\n\n**Stars**\nfive", DocstringStyle.NUMPYDOC, sections=sections
    )
    assert [(m.key, m.description) for m in docstring.meta] == [
        ("stars", "five")
    ]


def test_numpydoc_spec_section() -> None:
    """Test a Numpydoc section with its own kind and key."""
    sections = [
        *default_sections(DocstringStyle.NUMPYDOC),
        SectionSpec("Options", Kind.KEYWORD, key="option"),
    ]
    docstring = parse(
        "Short.\n\nOptions\n-------\nfast : bool\n    Go fast.\n",
        DocstringStyle.NUMPYDOC,
        sections=sections,
    )
    (param,) = docstring.params
    assert param.key == "option"
    assert param.arg_name == "fast"
    assert (param.type_name, param.description) == ("bool", "Go fast.")


def test_rest_spec_field() -> None:
    """Test a ReST field of a kind of its own."""
    sections = [
        *default_sections(DocstringStyle.REST),
        SectionSpec(("input", "in"), Kind.PARAM),
        SectionSpec("warns", Kind.WARNS),
    ]
    docstring = parse(
        "Short.\n\n:in int x: The x.\n:warns UserWarning: Careful.\n",
        DocstringStyle.REST,
        sections=sections,
    )
    param, warning = docstring.meta
    assert isinstance(param, DocstringParam)
    assert (param.key, param.arg_name, param.type_name) == (
        "in",
        "x",
        "int",
    )
    assert (warning.key, docstring.raises[0].type_name) == (
        "warns",
        "UserWarning",
    )


def test_rest_field_left_out() -> None:
    """Test that a ReST field not given is plain meta."""
    docstring = parse(
        "Short.\n\n:raises ValueError: Bad.\n",
        DocstringStyle.REST,
        sections=[SectionSpec("param", Kind.PARAM)],
    )
    assert docstring.raises == []
    assert docstring.meta[0].key == "raises"
    assert docstring.meta[0].name == "ValueError"


def test_rest_attribute_directive_left_out() -> None:
    """Test that an attribute directive is text without an attribute field."""
    docstring = parse(
        "Short.\n\n.. attribute:: x\n   The x.\n\n:param a: A.\n",
        DocstringStyle.REST,
        sections=[SectionSpec("param", Kind.PARAM)],
    )
    assert docstring.long_description == ".. attribute:: x\n   The x."
    assert docstring.params[0].arg_name == "a"


def test_rest_attribute_directive_parse_item() -> None:
    """Test that an attribute directive goes through its spec's hook."""
    sections = [
        SectionSpec(
            "attribute",
            Kind.ATTRIBUTE,
            parse_item=lambda meta: setattr(meta, "description", "Seen."),
        )
    ]
    docstring = parse(
        "Short.\n\n.. attribute:: x\n   The x.\n",
        DocstringStyle.REST,
        sections=sections,
    )
    assert docstring.attrs[0].arg_name == "x"
    assert docstring.attrs[0].description == "Seen."


def test_epydoc_spec_field() -> None:
    """Test an Epydoc field of a kind of its own, with its type."""
    sections = [
        *default_sections(DocstringStyle.EPYDOC),
        SectionSpec("arg", Kind.PARAM),
        SectionSpec("since", Kind.DEPRECATION),
    ]
    docstring = parse(
        "Short.\n\n@arg x: The x.\n@type x: int\n@since: 2.0\n",
        DocstringStyle.EPYDOC,
        sections=sections,
    )
    (param,) = docstring.params
    assert (param.key, param.type_name) == ("arg", "int")
    assert param.arg_name == "x"
    assert docstring.deprecation is not None
    assert docstring.deprecation.key == "since"


def test_parse_item_changes_item() -> None:
    """Test that parse_item gets each meta, already split, to change."""
    seen = []

    def parse_item(meta: DocstringMeta) -> T.Optional[DocstringMeta]:
        assert isinstance(meta, DocstringParam)
        seen.append(
            (meta.kind, meta.arg_name, meta.type_name, meta.description)
        )
        meta.arg_name = meta.arg_name.upper()
        return None

    sections = [SectionSpec("Args", Kind.PARAM, parse_item=parse_item)]
    docstring = parse(
        "Short.\n\nArgs:\n    x (int): The x.\n",
        DocstringStyle.GOOGLE,
        sections=sections,
    )
    assert seen == [(Kind.PARAM, "x", "int", "The x.")]
    assert docstring.params[0].arg_name == "X"


def test_parse_item_returns_meta() -> None:
    """Test that the meta parse_item returns is used as it is."""
    meta = DocstringMeta("Replaced.", key="custom")
    sections = [SectionSpec("param", Kind.PARAM, parse_item=lambda _i: meta)]
    docstring = parse("Short.\n\n:param x: The x.\n", sections=sections)
    assert docstring.meta == [meta]


def test_auto_with_sections() -> None:
    """Test that every style recognises the sections in auto mode."""
    sections = [SectionSpec("Inputs", Kind.PARAM, bare=True)]
    docstring = parse("Short.\n\nInputs\n    x: The x.\n", sections=sections)
    assert docstring.style == DocstringStyle.GOOGLE
    assert [p.arg_name for p in docstring.params] == ["x"]


@pytest.mark.parametrize("style", STYLES, ids=lambda s: s.name.lower())
@pytest.mark.parametrize("kind", list(Kind), ids=lambda k: k.name.lower())
def test_compose_any_kind_with_own_key(
    style: DocstringStyle, kind: Kind
) -> None:
    """Test that items of every kind compose in every style, whatever key.

    A section of its own with an unusual key used to make some styles
    raise or drop the item.
    """
    sections = [
        *default_sections(DocstringStyle.GOOGLE),
        SectionSpec("Custom", kind, key="custom", layout=Layout.ITEMS),
    ]
    docstring = parse(
        "Short.\n\nCustom:\n    x (int): The x.\n",
        DocstringStyle.GOOGLE,
        sections=sections,
    )
    assert len(docstring.meta) == 1
    for rendering in RenderingStyle:
        text = compose(docstring, style, rendering)
        assert "The x." in text
