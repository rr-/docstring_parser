"""Docstring parsing and composing without the legacy behavior.

This package implements ``legacy=False``. All styles share the same building
blocks: :mod:`.text` handles lines and descriptions, :mod:`.fields` the
contents of items (types, defaults, names) and :mod:`.build` the creation of
docstring items with canonical keys.

It requires Python 3.10 or newer, while the rest of the package also
supports older versions. The legacy modules import it only when
``legacy=False`` is used, so importing it is where that is enforced.
"""

import sys

if sys.version_info < (3, 10):
    raise RuntimeError("legacy=False requires Python 3.10 or newer")
