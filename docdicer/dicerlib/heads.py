"""The head-file names of a diced tree, fixed by convention and never configurable: a reader moving
between projects relies on finding them.

A tree's root, and each diced volume, opens at ENTRY_POINT; every other directory opens at INDEX.
A head's Contents block opens at its last line that is exactly CONTENTS; contents_line spells each
line it lists.
"""

ENTRY_POINT = "entry-point.md"
INDEX = "index.md"
HEADS = (ENTRY_POINT, INDEX)
CONTENTS = "Contents:"


def contents_line(indent: str, *, text: str, path: str) -> str:
    """The one spelling of a Contents block's line: indent, then a list item linking path as text."""
    return f"{indent}- [{text}]({path})"
