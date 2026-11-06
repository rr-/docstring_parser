"""Generated docstrings: random lines of every style's syntax.

They find edge cases no docstring written by hand has, and the same seed
gives the same docstrings, for ``tools/parity.py`` and the tests.
"""

import random
import typing as T

# Lines that generated docstrings are made of: titles, underlines, fields
# and items in every style, and the whitespace and punctuation that edge
# cases come from.
PIECES = [
    "Args:",
    "Arguments:",
    "Returns:",
    "Yields:",
    "Raises:",
    "Example:",
    "Examples:",
    "Attributes:",
    "Note:",
    "Parameters",
    "----------",
    "Returns",
    "-------",
    "Raises",
    "------",
    "Notes",
    "-----",
    "Examples",
    "--------",
    ".. deprecated:: 1.0",
    "..",
    "   deprecated::",
    "See Also",
    "x : int",
    "x (int): desc",
    "y: thing",
    "    x (int): desc",
    "    y: more",
    "        continued",
    "  shallow",
    "",
    "",
    "   ",
    "\t",
    "\tx: tabbed",
    "\x0c",
    " \x0c ",
    "\xa0x: nbsp",
    "Args:  ",
    "Args :",
    "Summary.",
    "    a",
    "    b : str, optional",
    "        desc of b",
    "  c",
    ">>> 1 + 1",
    "2",
    "    >>> f()",
    "x",
    "Default is 3.",
    "Args:\t",
    "Returns:\x0b",
    "Methods",
    "Other Parameters",
    "deprecated",
    "..  deprecated  ::",
    "\r\n",
    "Returns\r",
    "C++ Notes:",
    " Lead:",
    " Lead",
    "Trail :",
    "Trail  ",
    "Args (old):",
    "**Stars**",
    ".. versionadded:: 2",
    "Trail ",
    "Stars",
    ":param x: desc",
    ":param int y: desc",
    ":type x: str",
    ":returns: thing",
    ":rtype: int",
    ":raises ValueError: bad",
    ":raises:",
    ":meta:",
    ": no name:",
    ":param x:",
    "    continued field",
    "@param x: desc",
    "@type x: int",
    "@return: thing",
    "@rtype: str",
    "@raise ValueError: bad",
    "@yield: y",
    "@ytype: int",
    "@ivar a: attr",
    "@note: n",
    "@keyword k: kw",
    "x (List[int], optional): desc. Defaults to 3.",
    "y (Dict[str, int]): mapping",
    "    ValueError: if bad",
    "int: the result",
    "    Optional[int]: maybe",
    ":Example:",
]


def generated_inputs(count: int, seed: int = 1) -> T.List[str]:
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        lines = [rng.choice(PIECES) for _ in range(rng.randint(1, 14))]
        indent = rng.choice(["", "    ", "  ", "\t"])
        lines = [lines[0]] + [
            indent + line if line and rng.random() < 0.7 else line
            for line in lines[1:]
        ]
        text = "\n".join(lines)
        if rng.random() < 0.2:
            text = "\n" + text
        if rng.random() < 0.2:
            text = text + "\n" + indent
        out.append(text)
    return out
