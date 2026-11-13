"""GitHub heading anchors: the anchor of a heading's text, and the anchors of a document's headings."""

import re
from dataclasses import dataclass

from .linkscan import plain_text
from .textfile import FenceTracker

_ATX_HEADING = re.compile(r" {0,3}#{1,6}(?:[ \t]|$)")
_CLOSING_HASHES = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")


def github_anchor(heading: str) -> str:
    """GitHub's anchor for a heading's text: taken as plain text, lowercased, every character but a
    letter, digit, space, hyphen or underscore dropped, spaces made hyphens. Not `outline.slug`,
    which names files."""
    kept = "".join(c for c in plain_text(heading).lower() if c.isalnum() or c in " -_")
    return kept.replace(" ", "-")


@dataclass
class Anchor:
    base: str  # github_anchor of the heading's text
    name: str  # base, or base-N for the document's N-th repeat of it


def heading_anchor_list(lines: list[str]) -> list[tuple[int, Anchor]]:
    """(1-based line, anchor) of a document's ATX headings outside fenced code, in order, a repeat
    taking -1, -2, ..."""
    found = []
    repeats: dict[str, int] = {}
    fence = FenceTracker()
    for no, line in enumerate(lines, 1):
        m = _ATX_HEADING.match(line)
        if fence.inside(line) or not m:
            continue
        base = github_anchor(_CLOSING_HASHES.sub("", line[m.end() :].strip(" \t")))
        n = repeats.get(base, 0)
        found.append((no, Anchor(base, f"{base}-{n}" if n else base)))
        repeats[base] = n + 1
    return found


def heading_anchors(lines: list[str]) -> set[str]:
    """The anchors of a document's ATX headings outside fenced code."""
    return {anchor.name for _, anchor in heading_anchor_list(lines)}
