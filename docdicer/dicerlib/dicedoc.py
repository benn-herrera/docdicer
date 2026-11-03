"""Dicing one document, undicing a tree back into one, and re-checking trees that already exist."""

import io
import os
import posixpath
from typing import Optional, TextIO

from .heads import ENTRY_POINT, HEADS, INDEX
from .linkcheck import check_links, heading_anchor_list, markdown_files
from .linkrewrite import Linker, LinkMap, Tree, link_targets, parent_dir
from .outline import Outline, Section, plan_sections
from .reassemble import check_reassembly, contents_cut
from .split import write_tree
from .textfile import FenceTracker, read_lines, split_lines, write_lines


def _warn_duplicate_numbers(sections: list[Section], *, err: TextIO) -> None:
    for number in Outline(sections).duplicate_numbers:
        print(f"duplicate section number {number}", file=err)


def _tree(out: str, map_path: str) -> Tree:
    """Links in a monolith are relative to the run directory, so it anchors their rebasing."""
    link_map = LinkMap.load(map_path) if map_path and os.path.isfile(map_path) else LinkMap()
    return Tree(out=out, outabs=os.path.realpath(out), root=os.getcwd(), link_map=link_map)


def dice_doc(monolith: str, out: str, map_path: str, *, stdout: TextIO, stderr: TextIO) -> int:
    """Split a monolith into a tree under out (empty or absent), then check that the tree
    reassembles the monolith and that its links resolve. 0 ok, 1 a failed step, 2 bad arguments."""
    if not os.path.isfile(monolith):
        print(f"not a file: {monolith}", file=stderr)
        return 2
    if map_path and not os.path.isfile(map_path):
        print(f"not a file: {map_path}", file=stderr)
        return 2
    if os.path.exists(out) and not os.path.isdir(out):
        print(f"not a directory: {out}", file=stderr)
        return 2
    if os.path.isdir(out) and os.listdir(out):
        print(f"out-dir not empty: {out}", file=stderr)
        return 2
    os.makedirs(out, exist_ok=True)
    tree = _tree(out, map_path)
    lines = read_lines(monolith)
    sections, ok = plan_sections(lines, err=stderr)
    if not ok:
        return 1
    _warn_duplicate_numbers(sections, err=stderr)
    for s in sections:
        os.makedirs(os.path.join(out, posixpath.dirname(s.path)), exist_ok=True)
    write_tree(sections, lines, tree, err=stderr)
    if not check_reassembly(sections, lines, tree, out=stdout, err=stderr):
        return 1
    return 0 if check_links(sections, tree, out=stdout, err=stderr) else 1


def _own_and_contents(out: str, path: str) -> tuple[list[str], list[str]]:
    """A tree file's own lines and, for a head, its Contents block with every line after it."""
    lines = read_lines(os.path.join(out, path))
    is_head = path == ENTRY_POINT or path.endswith(f"/{INDEX}")
    cut = contents_cut(lines) if is_head else -1
    return (lines, []) if cut < 0 else (lines[:cut], lines[cut:])


def _undiced_lines(tree: Tree, *, err: TextIO) -> tuple[list[str], bool, list[tuple[str, Optional[int]]]]:
    """The entry point, then each file its Contents block lists, Contents dropped, links restored;
    whether every listed file could be read (each that could not is reported to err); and, for
    every read in reading order, its normalized path and the 1-based line of the result its own
    lines start at, None when it holds none."""
    entry, contents = _own_and_contents(tree.out, ENTRY_POINT)
    parts = [(ENTRY_POINT, entry)]
    all_read = True
    for line in contents:
        for path in link_targets(line):
            try:
                parts.append((path, _own_and_contents(tree.out, path)[0]))
            except OSError:
                print(f"undice: cannot read {tree.out}/{path}", file=err)
                all_read = False
    # Headings read from the tree hold rewritten links, which change their slugs and anchors; each
    # pass plans from the previous one's output, so a chain of headings citing headings settles one
    # link per pass.
    lines = [line for _, own in parts for line in own]
    for _ in range(len(heading_anchor_list(lines)) + 1):
        restored = _restored(parts, tree, lines)
        if restored == lines:
            break
        lines = restored
    reads = []
    first = 1 + len(entry)
    for path, own in parts[1:]:
        reads.append((posixpath.normpath(path), first if own else None))
        first += len(own)
    return lines, all_read, reads


def _restored(parts: list[tuple[str, list[str]]], tree: Tree, lines: list[str]) -> list[str]:
    """The parts' own lines with links restored against the sections and headings of lines."""
    sections, _ = plan_sections(lines, err=io.StringIO())
    linker = Linker(Outline(sections), tree, lines)
    restored = []
    for path, own in parts:
        fence = FenceTracker()
        leaf_dir = parent_dir(path)
        restored += [line if fence.inside(line) else linker.restore(line, leaf_dir) for line in own]
    return restored


def _all_reproduced(out: str, sections: list[Section], reads: list[tuple[str, Optional[int]]], *, err: TextIO) -> bool:
    """Report each `.md` under out that the sections do not write, nested volumes aside, naming the
    remedy: a file read as a section is renamed or its heading edited, a file read that opens none
    gets a heading or is removed, any other is linked or removed.
    reads are the (path, first line) pairs of `_undiced_lines`."""
    assigned = {s.path for s in sections}
    opened_at = {s.first: s for s in sections if s.path != ENTRY_POINT}
    read_as: dict[str, Section] = {}
    read: set[str] = set()
    for path, first in reads:
        read.add(path)
        if first in opened_at:
            read_as.setdefault(path, opened_at[first])
    strays = 0
    for f in markdown_files([out]):
        parts = os.path.relpath(f, out).split(os.sep)
        rel = "/".join(parts)
        nested = any(os.path.isfile(os.path.join(out, *parts[:i], ENTRY_POINT)) for i in range(1, len(parts)))
        if rel in assigned or nested:
            continue
        strays += 1
        if rel in read_as:
            planned = f"{out}/{read_as[rel].path}"
            print(
                f"undice: {f} would be re-diced as {planned}: rename the file or edit its heading to match",
                file=err,
            )
        elif rel in read:
            print(
                f"undice: {f} opens no section: start it with a level 2 to 4 heading, or remove it and its Contents line",
                file=err,
            )
        else:
            print(
                f"undice: not reproduced: {f}: link it from {out}/{ENTRY_POINT}'s Contents, or remove it",
                file=err,
            )
    return not strays


def undice(out: str, monolith: str, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write the document the tree under out holds to monolith, which must not exist, then check
    that dicing it reproduces the tree. 0 ok, 1 a failed check, 2 bad arguments."""
    try:
        read_lines(os.path.join(out, ENTRY_POINT))
    except OSError:
        print(f"not a tree: {out}", file=stderr)
        return 2
    if os.path.lexists(monolith):
        print(f"{monolith} exists: name another output, or move or delete it", file=stderr)
        return 2
    tree = _tree(out, "")
    lines, all_read, reads = _undiced_lines(tree, err=stderr)
    try:
        write_lines(monolith, lines)
    except OSError:
        print(f"cannot write: {monolith}", file=stderr)
        return 2
    sections, planned = plan_sections(lines, err=stderr)
    if not planned:
        return 1
    _warn_duplicate_numbers(sections, err=stderr)
    checks = [
        all_read,
        check_reassembly(sections, lines, tree, out=stdout, err=stderr),
        check_links(sections, tree, out=stdout, err=stderr),
        _all_reproduced(out, sections, reads, err=stderr),
    ]
    return 0 if all(checks) else 1


def _leaf_count(out: str) -> int:
    count = 0
    for _, dirs, files in os.walk(out):
        names = dirs + files
        count += sum(n.endswith(".md") and n not in HEADS for n in names)
    return count


def verify(map_path: str, pairs: list[tuple[str, str]], *, stdout: TextIO, stderr: TextIO) -> int:
    """Re-run the reassembly and link checks on each (monolith, out) tree, once every tree a link
    points into exists. 0 when every check passes, else 1."""
    rc = 0
    for monolith, out in pairs:
        if not os.path.isdir(out):
            print(f"not a directory: {out}", file=stderr)
            rc = 1
            continue
        tree = _tree(out, map_path)
        print(f"=== {monolith} -> {out}", file=stdout)
        try:
            lines = read_lines(monolith)
        except OSError:
            print(f"cannot read: {monolith}", file=stderr)
            rc = 1
            continue
        sections, ok = plan_sections(lines, err=stderr)
        _warn_duplicate_numbers(sections, err=stderr)
        if not ok:
            rc = 1
        if not check_reassembly(sections, lines, tree, out=stdout, err=stdout):
            rc = 1
        log = io.StringIO()
        if not check_links(sections, tree, out=log, err=log):
            rc = 1
        for line in split_lines(log.getvalue()):
            print(f"  {line}", file=stdout)
        print(f"  leaves: {_leaf_count(out)}", file=stdout)
    return rc
