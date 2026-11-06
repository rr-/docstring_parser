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
    metas: T.List[DocstringMeta], types: ParamTypes, rtypes: ReturnTypes
) -> None:
    """Give params and returns the types their type fields give.

    A name's metas take its types in order, and the last type goes to any
    metas left, so one type field types every meta of its name. A type no
    meta takes is a meta of its own, where its field is, and types left
    over at one place keep their order.
    """
    if not types and not rtypes:
        return
    taken: T.Dict[T.Any, int] = {}
    for meta in metas:
        if isinstance(meta, DocstringParam):
            name = meta.arg_name
            text = _take(taken, types.get(name, []), (True, name))
            if text is not None and not meta.type_name:
                spec = type_spec(text)
                meta.type_name = spec.type_name
                if spec.is_optional:
                    meta.is_optional = True
                    meta.default = meta.default or spec.default
        elif isinstance(meta, DocstringReturns):
            name = meta.return_name
            text = _take(taken, rtypes.get(name, []), (False, name))
            if text is not None and not meta.type_name:
                meta.type_name = text

    extra: T.List[T.Tuple[int, DocstringMeta]] = []
    for name, found in types.items():
        for text, at in found[taken.get((True, name), 0) :]:
            spec = type_spec(text)
            param = DocstringParam(
                None,
                arg_name=name,
                type_name=spec.type_name,
                is_optional=spec.is_optional,
                default=spec.default,
                key="type",
            )
            extra.append((at, param))
    for rname, found_r in rtypes.items():
        for text, at, kind, key in found_r[taken.get((False, rname), 0) :]:
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
