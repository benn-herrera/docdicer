"""The head-file names of a diced tree, fixed by convention and never configurable: a reader moving
between projects relies on finding them.

A tree's root, and each diced volume, opens at ENTRY_POINT; every other directory opens at INDEX.
"""

ENTRY_POINT = "entry-point.md"
INDEX = "index.md"
HEADS = (ENTRY_POINT, INDEX)
