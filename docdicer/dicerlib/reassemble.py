"""The reassembly check: the leaves, read in order with their Contents blocks dropped and section
links reverted, reproduce the monolith line for line (outside links compared in rebased form)."""

import os
from typing import TextIO

from .heads import CONTENTS, HEADS
from .linkrewrite import Linker, Tree, parent_dir
from .outline import Outline, Section
from .textfile import FenceTracker, fence_flags, read_lines


def contents_cut(lines: list[str]) -> int:
    """Index of a head's Contents block: its last line that is exactly `Contents:`; -1 if none."""
    cut = len(lines) - 1
    while cut >= 0 and lines[cut] != CONTENTS:
        cut -= 1
    return cut


def own_end(path: str, lines: list[str]) -> int:
    """Where the lines of the tree file at path end as its own: at a head file's Contents block,
    else at the file's end."""
    cut = contents_cut(lines) if os.path.basename(path) in HEADS else -1
    return cut if cut >= 0 else len(lines)


def check_reassembly(sections: list[Section], lines: list[str], tree: Tree, *, out: TextIO, err: TextIO) -> bool:
    linker = Linker(Outline(sections), tree, lines)
    fenced = fence_flags(lines)
    k = 0
    for s in sections:
        path = f"{tree.out}/{s.path}"
        try:
            leaf = read_lines(path)
        except OSError:
            print(f"reassemble: cannot read {path}", file=err)
            return False
        if s.kind != "L":
            cut = contents_cut(leaf)
            if cut < 0:
                print(f"reassemble: no Contents block in {path}", file=err)
                return False
            leaf = leaf[:cut]
        leaf_dir = parent_dir(s.path)
        fence = FenceTracker()
        for line in leaf:
            got = line if fence.inside(line) else linker.revert(line, leaf_dir)
            want = ""
            if k < len(lines):
                next_line = lines[k + 1] if k + 1 < len(lines) else ""
                want = lines[k] if fenced[k] else linker.rebase_only(lines[k], leaf_dir, next_line)
            k += 1
            if got != want:
                print(
                    f"reassemble: first difference at monolith line {k} ({path})\n  want: {want}\n  got:  {got}",
                    file=err,
                )
                return False
    if k != len(lines):
        print(f"reassemble: leaves hold {k} lines, monolith {len(lines)}", file=err)
        return False
    print(f"reassemble ok: {k} lines", file=out)
    return True
