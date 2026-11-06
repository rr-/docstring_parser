"""What the field list styles, ReST and Epydoc, share."""

import typing as T

from ._text import type_spec
from .common import DocstringMeta, DocstringParam, DocstringReturns, Kind

# Each name's type fields, in order: the type, and how many metas had been
# read when the field was.
ParamTypes = T.Dict[str, T.List[T.Tuple[str, int]]]
# The same for return types, with the kind and key of a return that a type
# left over makes.
ReturnTypes = T.Dict[
    T.Optional[str], T.List[T.Tuple[str, int, Kind, T.Optional[str]]]
]

# A position after every meta, for adding a meta at the end.
AFTER_ALL = 1 << 31


def _take(
    taken: T.Dict[T.Any, int],
    found: T.Sequence[T.Tuple[T.Any, ...]],
    name: T.Any,
) -> T.Any:
    """Count a meta of a name, and return the type its turn gives."""
    count = taken[name] = taken.get(name, 0) + 1
    return found[min(count, len(found)) - 1][0] if found else None


def assign_types(
    metas: T.List[DocstringMeta],
    types: ParamTypes,
    rtypes: ReturnTypes,
    ytypes: T.Optional[ReturnTypes] = None,
    vartypes: T.Optional[ParamTypes] = None,
) -> None:
    """Give params and returns the types their type fields give.

    A name's metas take its types in order, and the last type goes to any
    metas left, so one type field types every meta of its name. A type no
    meta takes is a meta of its own, where its field is, and types left
    over at one place keep their order.

    :param ytypes: types that only yields take; a yields of a name with
        none takes from ``rtypes``
    :param vartypes: types that only attributes take, and that a type no
        attribute takes makes one of; an attribute of a name with none
        takes from ``types``
    """
    if not types and not rtypes and not ytypes and not vartypes:
        return
    ytypes = ytypes or {}
    vartypes = vartypes or {}
    taken: T.Dict[T.Any, int] = {}
    for meta in metas:
        # A meta with a type of its own, as in ``:param int x:``, takes no
        # type field, which stays a meta of its own instead of being lost.
        if getattr(meta, "type_name", None):
            continue
        if isinstance(meta, DocstringParam):
            name = meta.arg_name
            if meta.kind is Kind.ATTRIBUTE and name in vartypes:
                text = _take(taken, vartypes[name], ("var", name))
            else:
                text = _take(taken, types.get(name, []), (True, name))
            if text is not None and not meta.type_name:
                spec = type_spec(text)
                meta.type_name = spec.type_name
                meta.raw_type_name = text
                if spec.is_optional:
                    meta.is_optional = True
                    # A default in the type wins over one the description
                    # states, as when both come in one field.
                    meta.default = spec.default or meta.default
        elif isinstance(meta, DocstringReturns):
            name = meta.return_name
            if meta.is_generator and name in ytypes:
                text = _take(taken, ytypes[name], (None, name))
            else:
                text = _take(taken, rtypes.get(name, []), (False, name))
            if text is not None and not meta.type_name:
                meta.type_name = text

    extra: T.List[T.Tuple[int, DocstringMeta]] = []
    for tag, kind, key, table in (
        (True, Kind.PARAM, "type", types),
        ("var", Kind.ATTRIBUTE, "vartype", vartypes),
    ):
        for name, found in table.items():
            for text, at in found[taken.get((tag, name), 0) :]:
                spec = type_spec(text)
                param = DocstringParam(
                    None,
                    arg_name=name,
                    type_name=spec.type_name or None,
                    is_optional=spec.is_optional,
                    default=spec.default,
                    kind=kind,
                    key=key,
                    raw_type_name=text or None,
                )
                extra.append((at, param))
    for tag, table in ((False, rtypes), (None, ytypes)):
        for rname, found_r in table.items():
            for text, at, kind, key in found_r[taken.get((tag, rname), 0) :]:
                returns = DocstringReturns(
                    None, text, kind is Kind.YIELDS, return_name=rname, key=key
                )
                extra.append((at, returns))
    if not extra:
        return
    # Each goes before the meta read after its field, and those of one
    # place keep their fields' order, which the stable sort keeps.
    extra.sort(key=lambda entry: entry[0])
    merged: T.List[DocstringMeta] = []
    k = 0
    for i, meta in enumerate(metas):
        while k < len(extra) and extra[k][0] <= i:
            merged.append(extra[k][1])
            k += 1
        merged.append(meta)
    merged.extend(meta for _at, meta in extra[k:])
    metas[:] = merged
