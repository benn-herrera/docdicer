"""The kanban board's model: a project's roadmap, active design and active plan as columns of cards;
and the board's only writes to documents, the moves of an entry between `ROADMAP.md` and the active
design.

A document is a list of lines and its structure line ranges: a move splices lines out of one file
and into another. Plain data over the project's files: nothing here serves, keeps UI state or reads
git.
"""

import hashlib
import os
import posixpath
import re
from dataclasses import asdict, dataclass
from typing import Any, Optional

from ..dicerlib.heads import CONTENTS, ENTRY_POINT, HEADS
from ..dicerlib.linkcheck import markdown_files, prose_links
from ..dicerlib.linkrewrite import link_targets, never_rebased, rel, scan
from ..dicerlib.outline import section_name
from ..dicerlib.reassemble import contents_cut
from ..dicerlib.textfile import fence_flags, is_blank, read_text, replace_lines, split_lines
from .planform import (
    ACTIVE_DESIGN,
    ACTIVE_PLAN,
    DELTA,
    DELTA_HEADINGS,
    DRAFTED,
    ENTRY,
    HEADING,
    ROADMAP,
    SECTION,
    STATE_WORDS,
    DesignPart,
    WorkPackage,
    active_document,
    design_files,
    design_from_files,
    parked_entries,
    read_plan,
)

# The plan columns, left to right; a work package's card is in the column its state names.
PLAN_COLUMNS = (DRAFTED, *STATE_WORDS)
TITLE_LENGTH = 60  # a roadmap title taken from a first sentence is cut to this many characters
INSTRUCTION = "complete and update this design"
CREATED_DESIGN_HEADING = "# ACTIVE DESIGN"

_ITEM = re.compile(r"(?:[-*]|[0-9]+\.)[ \t]+")
_LIST_LINE = re.compile(r"[ \t]*(?:[-*]|[0-9]+\.)[ \t]")
_BOLD_LEAD = re.compile(r"\*\*(.+?)\*\*")
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_GONE = "the card is no longer on the board"


@dataclass
class RoadmapCard:
    title: str
    group: str  # the `##` heading above the item; "" where there is none
    text: str  # the item's lines as written, newline-joined
    parked: list[str]  # the parked entries the item links, relative to the project root


@dataclass
class ParkedCard:
    title: str  # the entry's file name, or a diced entry's directory name, without `.md`
    path: str  # relative to the project root


@dataclass
class DesignCard:
    title: str  # the part's heading; an entry's with each link reduced to its text
    text: str  # the lines below its heading, blank lines at either end dropped; "" for a delta
    path: str  # the file holding the part, relative to the project root
    parked: Optional[str]  # the parked entry's path where the section is its link section; else None
    kind: str  # the DesignPart's: SECTION, DELTA (drawn as a separator) or ENTRY


@dataclass
class Board:
    release: Optional[str]  # the active plan's; None where it names none or there is no active plan
    hardening: bool
    roadmap: list[RoadmapCard]
    parked: list[ParkedCard]  # parked entries neither linked nor in the design, below the roadmap cards
    design: list[DesignCard]  # one per part of the design: sections, separators and entries, in document order
    packages: list[WorkPackage]  # the active plan's work packages, each in the column its state names
    sha256: dict[str, Optional[str]]  # each file a move may write, relative to the root: its digest, None if absent


class MoveRefused(Exception):
    """A move between Roadmap and Design was refused and nothing was written; the message says why."""


class MoveWriteFailed(Exception):
    """A move's write failed at the file system: `path` could not be written, after `written`."""

    def __init__(self, path: str, written: list[str]) -> None:
        super().__init__(f"cannot write: {path}")
        self.path = path
        self.written = written


@dataclass
class _Item:
    card: RoadmapCard
    group_line: Optional[int]  # 0-based line of the item's `##` heading
    first: int  # 0-based, inclusive
    last: int
    marker: str  # the list marker with the whitespace after it


@dataclass
class _Section:
    card: DesignCard
    path: str  # the file holding it, as active_document and design_files name it
    first: int  # 0-based line of its heading
    end: int  # 0-based, exclusive


@dataclass
class _Read:
    """One read of the roadmap and the active design: their cards and the line ranges a move splices."""

    roadmap: list[str]
    items: list[_Item]
    eof_group: Optional[int]  # the `##` heading line in effect at the end of ROADMAP.md
    parked: list[ParkedCard]
    design: Optional[str]  # the active design's file: the monolith or the tree's entry point
    diced: bool  # the active design is a diced tree
    lines: dict[str, list[str]]  # each design file's lines
    sections: list[_Section]
    sha256: dict[str, Optional[str]]


def read_board(root: str) -> Board:
    """The board of the project at root. Raises OSError where a file it reads cannot be read."""
    now = _read(root)
    plan_path = active_document(root, ACTIVE_PLAN)
    plan = read_plan(plan_path) if plan_path else None
    return Board(
        release=plan.release if plan else None,
        hardening=plan.hardening if plan else False,
        roadmap=[item.card for item in now.items],
        parked=now.parked,
        design=[s.card for s in now.sections],
        packages=plan.packages if plan else [],
        sha256=now.sha256,
    )


def watched_files(root: str) -> list[str]:
    """Every file the board reads, or would read were it there, so that its creation is seen too;
    each path normalized."""
    paths = [os.path.join(root, name) for name in (ROADMAP, ACTIVE_DESIGN, ACTIVE_PLAN)]
    paths.append(os.path.join(root, os.path.splitext(ACTIVE_DESIGN)[0], ENTRY_POINT))
    for monolith in (ACTIVE_DESIGN, ACTIVE_PLAN):
        tree = os.path.join(root, os.path.splitext(monolith)[0])
        if os.path.isdir(tree):
            paths.extend(markdown_files([tree]))
    paths.extend(parked_entries(root))
    return [os.path.normpath(p) for p in paths]


def move_to_design(root: str, card: dict[str, Any], *, read: dict[str, Optional[str]]) -> list[str]:
    """Move the entry of card, a roadmap or parked card as served, into the active design as a `##`
    section headed by its title: a roadmap item leaves `ROADMAP.md`, a parked entry gets a link
    section. Returns the files written, relative to root, in the order written, the addition first.

    read is the `Board.sha256` the move is made against. Raises MoveRefused, writing nothing, where
    card's title is a delta heading's text, no card of a fresh read of the files equals card, a file
    to write differs from read, or a diced design's new leaf has no name or already exists;
    MoveWriteFailed where a write fails. Raises OSError where a file the move reads cannot be read.
    """
    if card.get("title") in DELTA_HEADINGS:
        raise MoveRefused(f"{card['title']!r} is a delta heading: a section headed by it would be a delta, not a card")
    now = _read(root)
    item = next((i for i in now.items if asdict(i.card) == card), None)
    parked = next((p for p in now.parked if asdict(p) == card), None)
    if item is None and parked is None:
        raise MoveRefused(_GONE)
    here = _directory(root, now.design) if now.design else ""
    if item is not None:
        title = item.card.title
        first, *rest = now.roadmap[item.first : item.last + 1]
        body = _rebased([first[len(item.marker) :], *rest], "", here)
    else:
        title = parked.title
        body = _link_body(parked.path, here)
    section = [f"## {title}", "", *body]
    changes: list[tuple[str, Optional[list[str]]]] = []
    if now.design is None:
        changes.append((os.path.join(root, ACTIVE_DESIGN), [CREATED_DESIGN_HEADING, "", *section]))
    elif not now.diced:
        lines = now.lines[now.design]
        changes.append((now.design, [*lines, *([""] if lines and not is_blank(lines[-1]) else []), *section]))
    else:
        name = section_name(title)
        if not name:
            raise MoveRefused(
                f"no leaf name for {title!r}: a title without a number needs an ASCII letter or digit to name"
                " the design's new leaf"
            )
        leaf = os.path.join(os.path.dirname(now.design), f"{name}.md")
        if os.path.lexists(leaf):
            raise MoveRefused(f"{root_relative(root, leaf)} already exists")
        contents_line = f"- [{title}]({name}.md)"
        changes += [(leaf, section), (now.design, _with_contents_line(now.lines[now.design], contents_line))]
    if item is not None:
        changes.append((os.path.join(root, ROADMAP), now.roadmap[: item.first] + now.roadmap[item.last + 1 :]))
    return _write(root, changes, read)


def move_to_roadmap(
    root: str,
    card: dict[str, Any],
    *,
    target: Optional[dict[str, Any]],
    read: dict[str, Optional[str]],
) -> list[str]:
    """Move the section of card, a design card as served, out of the active design and, unless it
    is a link section, into `ROADMAP.md` as a top-level item at the end of the `##` group of target,
    the roadmap card dropped on as served, else at the end of the file. An unchanged section returns
    as the item it was; any other gives its heading as the item's bold lead. Returns, refuses and
    fails as move_to_design does; refuses too where card is not a section's, before any read, and
    where the Contents line of a leaf to delete is not found.
    """
    if card.get("kind") != SECTION:
        raise MoveRefused("an entry card or a delta's separator does not move to Roadmap; only a design section does")
    now = _read(root)
    section = next((s for s in now.sections if asdict(s.card) == card), None)
    if section is None:
        raise MoveRefused(_GONE)
    lines = now.lines[section.path]
    changes: list[tuple[str, Optional[list[str]]]] = []
    if section.card.parked is None:
        body = _rebased(_trimmed(lines[section.first + 1 : section.end]), _directory(root, section.path), "")
        target_item = next((i for i in now.items if asdict(i.card) == target), None) if target is not None else None
        changes.append((os.path.join(root, ROADMAP), _roadmap_with(now, section.card.title, body, target_item)))
    if now.diced and _is_whole_leaf(section, lines, now.design):
        entry_lines = _without_contents_line(now.lines[now.design], os.path.basename(section.path))
        if entry_lines is None:
            raise MoveRefused(
                f"{root_relative(root, now.design)} has no Contents line linking {root_relative(root, section.path)}"
            )
        changes += [(now.design, entry_lines), (section.path, None)]
    else:
        remaining = lines[: section.first] + lines[section.end :]
        if section.end == len(lines) and remaining and is_blank(remaining[-1]):
            remaining.pop()
        changes.append((section.path, remaining))
    return _write(root, changes, read)


def sha256(text: str) -> str:
    """The hex SHA-256 of text as the file holding it stores it: UTF-8, surrogateescape."""
    return hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()


def root_relative(root: str, path: str) -> str:
    """path relative to root, `/`-separated."""
    return os.path.relpath(path, root).replace(os.sep, "/")


def _directory(root: str, path: str) -> str:
    """The directory holding path, relative to root; "" for root itself."""
    here = root_relative(root, os.path.dirname(path))
    return "" if here == "." else here


def _read(root: str) -> _Read:
    digests: dict[str, Optional[str]] = {}
    roadmap_path = os.path.join(root, ROADMAP)
    roadmap: list[str] = []
    digests[ROADMAP] = None
    if os.path.isfile(roadmap_path):
        text = read_text(roadmap_path)
        roadmap, digests[ROADMAP] = split_lines(text), sha256(text)
    entries = {os.path.normpath(e): root_relative(root, e) for e in parked_entries(root)}
    items, eof_group = _roadmap_items(root, roadmap, entries)
    linked = {path for item in items for path in item.card.parked}
    unlinked = [path for path in entries.values() if path not in linked]

    design = active_document(root, ACTIVE_DESIGN)
    files = design_files(design) if design else []
    if not files:
        digests[ACTIVE_DESIGN] = None
    for f in files:
        digests[root_relative(root, f.path)] = sha256(f.text)
    lines = {f.path: f.lines for f in files}
    parts = design_from_files(files).parts if files else []
    sections = [_design_section(root, part, lines[part.path], unlinked) for part in parts]
    in_design = {s.card.parked for s in sections}
    return _Read(
        roadmap=roadmap,
        items=items,
        eof_group=eof_group,
        parked=[ParkedCard(_entry_name(path), path) for path in unlinked if path not in in_design],
        design=design,
        diced=design is not None and os.path.basename(design) == ENTRY_POINT,
        lines=lines,
        sections=sections,
        sha256=digests,
    )


def _design_section(root: str, part: DesignPart, lines: list[str], unlinked: list[str]) -> _Section:
    """The card and line range of one part of the design, lines being its file's."""
    body = [] if part.kind == DELTA else _trimmed(lines[part.first + 1 : part.end])
    parked = None
    if part.kind == SECTION and lines[part.first] == f"## {part.heading}":
        here = _directory(root, part.path)
        parked = next((p for p in unlinked if part.heading == _entry_name(p) and body == _link_body(p, here)), None)
    title = _link_texts(part.heading) if part.kind == ENTRY else part.heading
    card = DesignCard(title, "\n".join(body), root_relative(root, part.path), parked, part.kind)
    return _Section(card, part.path, part.first, part.end)


def _write(root: str, changes: list[tuple[str, Optional[list[str]]]], read: dict[str, Optional[str]]) -> list[str]:
    """Check every file changes names against read, then write each in order, None deleting it."""
    for path, _ in changes:
        name = root_relative(root, path)
        if (sha256(read_text(path)) if os.path.isfile(path) else None) != read.get(name):
            raise MoveRefused(f"{name} changed since the board read it")
    written: list[str] = []
    for path, lines in changes:
        try:
            if lines is None:
                os.remove(path)
            else:
                replace_lines(path, lines)
        except OSError as e:
            raise MoveWriteFailed(root_relative(root, path), written) from e
        written.append(root_relative(root, path))
    return written


def _entry_name(path: str) -> str:
    directory, name = os.path.split(path)
    return os.path.basename(directory) if name == ENTRY_POINT else os.path.splitext(name)[0]


def _link_body(parked: str, here: str) -> list[str]:
    """A link section's lines below its heading, in a file in directory here, both relative to root."""
    return [f"[{parked}]({rel(here, parked)})", "", INSTRUCTION]


def _trimmed(lines: list[str]) -> list[str]:
    first = next((i for i, line in enumerate(lines) if not is_blank(line)), len(lines))
    last = next((i for i in range(len(lines) - 1, -1, -1) if not is_blank(lines[i])), -1)
    return lines[first : last + 1]


def _items(lines: list[str]) -> tuple[list[tuple[str, Optional[int], int, int]], Optional[int]]:
    """(group, group's heading line, first, last) of each top-level list item outside fenced code,
    0-based and inclusive, last being its last non-blank line; and the `##` heading line in effect at
    the end. An item ends at the next item or heading, or at a line starting in column 0 after a
    blank line."""
    items: list[tuple[str, Optional[int], int, int]] = []
    group, group_line = "", None
    in_item = after_blank = in_fence = False
    for i, (line, fenced) in enumerate(zip(lines, fence_flags(lines))):
        heading = None if fenced else HEADING.match(line)
        if heading or (not fenced and _ITEM.match(line)):
            in_item = not heading
            if heading and len(heading.group(1)) == 2:
                group, group_line = line[heading.end() :].strip(), i
            if in_item:
                items.append((group, group_line, i, i))
        elif in_item and not is_blank(line):
            if after_blank and not line[:1].isspace() and not in_fence:
                in_item = False
            else:
                items[-1] = (*items[-1][:3], i)
        after_blank, in_fence = is_blank(line), fenced
    return items, group_line


def _roadmap_items(root: str, lines: list[str], entries: dict[str, str]) -> tuple[list[_Item], Optional[int]]:
    """An item per top-level item of the roadmap's lines, and the heading line in effect at its end;
    entries maps each parked entry's normalized path to its path relative to root."""
    links = list(prose_links(lines))
    found, eof_group = _items(lines)
    items = []
    for group, group_line, first, last in found:
        parked: list[str] = []
        for no, target in links:
            entry = entries.get(os.path.normpath(os.path.join(root, target.partition("#")[0])))
            if first < no <= last + 1 and entry and entry not in parked:
                parked.append(entry)
        item = lines[first : last + 1]
        card = RoadmapCard(_roadmap_title(item), group, "\n".join(item), parked)
        items.append(_Item(card, group_line, first, last, _ITEM.match(item[0]).group()))
    return items, eof_group


def _roadmap_title(item: list[str]) -> str:
    """The item's bold lead where it opens with one, else its first sentence, cut to TITLE_LENGTH;
    either without a closing `.` or `:`, and each link in it reduced to its text, so the title can
    head a section and name a Contents line."""
    text = item[0][_ITEM.match(item[0]).end() :]
    bold = _BOLD_LEAD.match(text)
    if bold:
        return _link_texts(bold.group(1)).strip().rstrip(".:")
    paragraph = [text]
    for line in item[1:]:
        if is_blank(line) or _LIST_LINE.match(line):
            break
        paragraph.append(line.strip())
    joined = _link_texts(" ".join(paragraph)).strip()
    end = _SENTENCE_END.search(joined)
    sentence = (joined[: end.end()] if end else joined).rstrip(".:")
    return sentence if len(sentence) <= TITLE_LENGTH else sentence[: TITLE_LENGTH - 1].rstrip() + "…"


def _link_texts(text: str) -> str:
    """text with each link outside code spans replaced by its link text."""
    return scan(text, lambda raw, link_text, target, after: link_text)


def _roadmap_with(now: _Read, title: str, body: list[str], target: Optional[_Item]) -> list[str]:
    """ROADMAP.md's lines with a section headed title, its body lines given, as an item at the end of
    target's group, else at the end of the file, taking the marker of that group's items."""
    group_line = target.group_line if target is not None else None
    at_end = group_line is None
    members = [i for i in now.items if i.group_line == (now.eof_group if at_end else group_line)]
    marker = _next_marker(members[-1].marker) if members else "- "
    item = _returned_item(title, body, marker)
    lines = now.roadmap
    if not at_end:
        at = members[-1].last + 1
    elif members and all(is_blank(line) for line in lines[members[-1].last + 1 :]):
        at = members[-1].last + 1
    else:
        separator = [""] if lines and not is_blank(lines[-1]) else []
        return [*lines, *separator, *item]
    return [*lines[:at], *item, *lines[at:]]


def _next_marker(marker: str) -> str:
    """The marker an item after one marked marker takes: the same bullet, or the next number."""
    word = marker.rstrip()
    if word[0].isdigit():
        return f"{int(word[:-1]) + 1}.{marker[len(word):]}"
    return marker


def _returned_item(title: str, body: list[str], marker: str) -> list[str]:
    """The item a section returns as: the body after marker where that gives title and reads back as
    one item over every body line, else title as its bold lead, the body after it, its later lines
    indented under the marker."""
    if body:
        as_written = [marker + body[0], *body[1:]]
        found, _ = _items(as_written)
        if _roadmap_title(as_written) == title and [(f, last) for _, _, f, last in found] == [(0, len(body) - 1)]:
            return as_written
    lead = f"{marker}**{title}**"
    if not body:
        return [lead]
    indent = " " * len(marker)
    return [f"{lead} {body[0]}", *(line if is_blank(line) else indent + line for line in body[1:])]


def _rebased(lines: list[str], source: str, destination: str) -> list[str]:
    """lines moved from a file in directory source to one in destination, both relative to the root,
    each relative link target outside fenced code and code spans made to reach the same file. Targets
    that mean the same from any directory (empty, `#...`, `/...`, a URL) stay as written."""
    if source == destination:
        return lines

    def rebase(raw: str, link_text: str, target: str, after: str) -> str:
        if never_rebased(target):
            return raw
        path, hash_, fragment = target.partition("#")
        return f"[{link_text}]({rel(destination, posixpath.normpath(posixpath.join(source, path)))}{hash_}{fragment})"

    return [line if fenced else scan(line, rebase) for line, fenced in zip(lines, fence_flags(lines))]


def _is_whole_leaf(section: _Section, lines: list[str], entry: str) -> bool:
    """Whether section is all of a leaf beside a diced design's entry point."""
    return (
        os.path.dirname(section.path) == os.path.dirname(entry)
        and os.path.basename(section.path) not in HEADS
        and all(is_blank(line) for line in lines[: section.first])
        and section.end == len(lines)
    )


def _with_contents_line(lines: list[str], contents_line: str) -> list[str]:
    """lines with contents_line after the last item of the list under the last `Contents:` line,
    or a Contents block holding it appended where there is none."""
    start = contents_cut(lines)
    if start < 0:
        return [*lines, "", CONTENTS, "", contents_line]
    at = start + 1
    for i in range(at, len(lines)):
        if _LIST_LINE.match(lines[i]):
            at = i + 1
        elif not is_blank(lines[i]):
            break
    if at == start + 1:
        return [*lines[:at], "", contents_line, *lines[at:]]
    return [*lines[:at], contents_line, *lines[at:]]


def _without_contents_line(lines: list[str], name: str) -> Optional[list[str]]:
    """lines without the line after the last `Contents:` line that links the leaf name; None where
    there is no Contents block or no line of it does."""
    start = contents_cut(lines)
    if start < 0:
        return None
    for i in range(start + 1, len(lines)):
        if any(posixpath.normpath(t.partition("#")[0]) == name for t in link_targets(lines[i])):
            return lines[:i] + lines[i + 1 :]
    return None
