"""The kanban board's model: a project's roadmap, active design and active plan as columns of cards;
and the board's only writes to documents, the moves of a ticket between `ROADMAP.md` and the active
design, a monolith or a diced tree.

A document is a list of lines and its parts line ranges, as `planform` reads them in the ticket
layout: a move splices a ticket's lines out of one file and into another, rebasing their relative
links between the two files' directories; in a diced design it may add a leaf or delete one, with
its Contents lines. Plain data over the project's files: nothing here serves, keeps UI state or
reads git.
"""

import hashlib
import os
import posixpath
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any, Optional, TypeVar, Union
from urllib.parse import quote

from ..dicerlib.heads import CONTENTS, ENTRY_POINT, HEADS, INDEX, contents_line
from ..dicerlib.linkcheck import markdown_files, prose_links
from ..dicerlib.linkrewrite import never_rebased, rel
from ..dicerlib.linkscan import link_targets, scan
from ..dicerlib.outline import contents_text, section_name, split_number
from ..dicerlib.reassemble import contents_cut
from ..dicerlib.textfile import fence_flags, is_blank, read_text, replace_lines
from .planform import (
    ACTIVE_DESIGN,
    ACTIVE_PLAN,
    CATEGORY,
    DELTA,
    DRAFTED,
    HEADING,
    LAYOUT_BREACHES,
    ROADMAP,
    STATE_WORDS,
    TICKET,
    Breach,
    ParkedWork,
    Part,
    WorkPackage,
    active_document,
    design_files,
    design_from_files,
    document_paths,
    parked_work,
    read_file,
    read_plan,
    roadmap_file,
    roadmap_from_file,
)

# The plan columns, left to right; a work package's card is in the column its state names.
PLAN_COLUMNS = (DRAFTED, *STATE_WORDS)
INSTRUCTION = "complete and update this design"
CREATED_DESIGN_HEADING = "# ACTIVE DESIGN"
CREATED_ROADMAP_HEADING = "# ROADMAP"
GENERAL_HEADING = "## General"
DRAFTS = "Drafts"  # the heading text of the design's category that a move to Design adds to
DRAFTS_DIRECTORY = "drafts"  # made beside a diced design's entry point for a `## Drafts` it lacks

_GONE = "the card is no longer on the board"
_ITEM = re.compile(r" *[-*+] ")  # a list item, as a Contents block's lines are

# A file a move writes, as (path, lines); lines is None for a leaf the move deletes.
_Change = tuple[str, Optional[list[str]]]


@dataclass
class RoadmapCard:
    title: str  # the Part's
    text: str  # the lines below its heading, blank lines at either end dropped; "" for a separator
    href: Optional[str]  # the URL path of the file holding its heading, then `#` and its anchor; None for a separator
    parked: list[str]  # the files of the parked work the ticket links, relative to the project root
    kind: str  # the Part's: CATEGORY (drawn as a separator) or TICKET
    occurrence: int  # the number of cards before it in Board.roadmap equal to it in every other field


@dataclass
class ParkedCard:
    title: str  # the piece of parked work's parked name
    paths: list[str]  # its files, relative to the project root
    hrefs: list[str]  # the URL path of each of paths, in the same order


@dataclass
class DesignCard:
    title: str  # the Part's
    text: str  # as RoadmapCard's
    path: str  # the file holding the part, relative to the project root
    href: Optional[str]  # as RoadmapCard's
    parked: Optional[list[str]]  # the parked work's files where the ticket is its link ticket; else None
    parked_hrefs: Optional[list[str]]  # the URL path of each of parked, in the same order; None where it is
    kind: str  # the Part's: CATEGORY or DELTA (drawn as separators), TICKET or ENTRY
    occurrence: int  # as RoadmapCard's, in Board.design


@dataclass
class PackageCard(WorkPackage):
    """A work package's fields, flat, and its card's link."""

    href: str  # as RoadmapCard's, to its heading; untitled, the URL path of the file holding its row


_Card = TypeVar("_Card", RoadmapCard, DesignCard)


@dataclass
class Notice:
    """A breach of `ROADMAP.md`, or of the active design's layout, as the page shows it."""

    column: str  # the Board field whose cards it heads: "roadmap" or "design"
    path: str  # relative to the project root
    line: int  # 1-based
    found: str
    accepted: str


@dataclass
class Board:
    release: Optional[str]  # the active plan's; None where it names none or there is no active plan
    hardening: bool
    roadmap: list[RoadmapCard]  # one per part of ROADMAP.md, separators included, in document order
    parked: list[ParkedCard]  # parked work neither linked nor in the design, below the roadmap cards
    design: list[DesignCard]  # one per part of the design, separators included, in document order
    packages: list[PackageCard]  # the active plan's work packages, each in the column its state names
    notices: list[Notice]  # the breaches of ROADMAP.md, then the layout breaches of the design
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
class _Read:
    """One read of the roadmap and the active design: their parts, the card of each part, and the
    lines a move splices."""

    roadmap: list[str]  # ROADMAP.md's lines; [] where it is absent
    roadmap_parts: list[Part]
    roadmap_cards: list[RoadmapCard]  # one per roadmap part, in the same order
    parked: list[ParkedCard]
    design: Optional[str]  # the active design's file: the monolith or the tree's entry point
    diced: bool  # the active design is a diced tree
    lines: dict[str, list[str]]  # each design file's lines, in design_files order
    design_parts: list[Part]
    design_cards: list[DesignCard]  # one per design part, in the same order
    notices: list[Notice]
    sha256: dict[str, Optional[str]]


def read_board(root: str) -> Board:
    """The board of the project at root. Raises OSError where a file it reads cannot be read."""
    now = _read(root)
    plan_path = active_document(root, ACTIVE_PLAN)
    plan = read_plan(plan_path) if plan_path else None
    return Board(
        release=plan.release if plan else None,
        hardening=plan.hardening if plan else False,
        roadmap=now.roadmap_cards,
        parked=now.parked,
        design=now.design_cards,
        packages=[_package_card(root, p) for p in plan.packages] if plan else [],
        notices=now.notices,
        sha256=now.sha256,
    )


def watched_files(root: str) -> list[str]:
    """Every file the board reads, or would read were it there, so that its creation is seen too;
    each path normalized."""
    paths = [os.path.join(root, name) for name in (ROADMAP, ACTIVE_DESIGN, ACTIVE_PLAN)]
    for monolith in (ACTIVE_DESIGN, ACTIVE_PLAN):
        tree = os.path.join(root, os.path.splitext(monolith)[0])
        if os.path.isdir(tree):
            paths.extend(markdown_files([tree]))
    paths.extend(f for work in parked_work(root) for f in work.files)
    return [os.path.normpath(p) for p in paths]


def served_files(root: str) -> list[str]:
    """The files the board reads, sorted, each relative to root and `/`-separated: `ROADMAP.md`,
    the active design's and the active plan's files in the form read, and the parked work's files.
    Reads none of them."""
    paths = [p for p in [roadmap_file(root)] if p is not None]
    for monolith in (ACTIVE_DESIGN, ACTIVE_PLAN):
        document = active_document(root, monolith)
        if document:
            paths += document_paths(document)
    paths += [f for work in parked_work(root) for f in work.files]
    return sorted({root_relative(root, p) for p in paths})


def move_to_design(root: str, card: dict[str, Any], *, read: dict[str, Optional[str]]) -> list[str]:
    """Move the ticket of card, a roadmap ticket's or a parked card as served, to the end of the
    active design's `## Drafts` category: a roadmap ticket's lines leave `ROADMAP.md`, a parked card's
    work gets a link ticket. In a diced design whose `## Drafts` opens an `index.md`, or that has
    none, the ticket is a new leaf, listed in the Contents blocks that list its directory. Returns the
    files written, relative to root, in the order written, the addition first.

    read is the `Board.sha256` the move is made against. Raises MoveRefused, writing nothing, where
    no card of a fresh read of the files equals card, a leaf to add has no name, a file to create
    exists, or a file to write differs from read; MoveWriteFailed where a write fails. Raises OSError
    where a file the move reads cannot be read.
    """
    now = _read(root)
    at = _ticket_at(now.roadmap_cards, card)
    parked = next((p for p in now.parked if asdict(p) == card), None)
    if at is None and parked is None:
        raise MoveRefused(_GONE)
    title = now.roadmap_parts[at].title if at is not None else parked.title

    def ticket(path: str) -> list[str]:
        """The ticket's lines for the file at path."""
        here = _directory(root, path)
        if at is None:
            return _link_ticket(parked.title, parked.paths, here)
        part = now.roadmap_parts[at]
        return _rebased(now.roadmap[part.first : part.last + 1], "", here)

    drafts = f"## {DRAFTS}"
    head = next((k for k, p in enumerate(now.design_parts) if p.kind == CATEGORY and p.heading == DRAFTS), None)
    changes: list[_Change]
    if now.design is None:
        created = os.path.join(root, ACTIVE_DESIGN)
        changes = [(created, _appended([CREATED_DESIGN_HEADING], drafts, ticket(created)))]
    elif head is not None and not _opens_an_index(now, head):
        path = now.design_parts[head].path
        changes = [(path, _added(now.lines[path], _category(now.design_parts, head), ticket(path)))]
    elif now.diced:
        changes = _new_leaf(root, now, head, title, ticket)
    else:
        changes = [(now.design, _appended(now.lines[now.design], drafts, ticket(now.design)))]
    if at is not None:
        changes.append((os.path.join(root, ROADMAP), _removed(now.roadmap, now.roadmap_parts[at])))
    return _write(root, changes, read)


def move_to_roadmap(
    root: str,
    card: dict[str, Any],
    *,
    target: Optional[dict[str, Any]],
    read: dict[str, Optional[str]],
) -> list[str]:
    """Move the ticket of card, a design ticket's card as served, out of the active design and,
    unless it is a link ticket, into `ROADMAP.md` at the end of the category of target, the roadmap
    separator the drop selected as served, else of the first category; where `ROADMAP.md` has no
    category, under a `## General` appended to it. A diced design's leaf holding only the ticket is
    deleted, its lines in the Contents blocks that list it removed first. Returns and fails as
    move_to_design does; raises MoveRefused, writing nothing, where card is not a ticket's (before
    any read), no card of a fresh read equals card, the ticket runs on past its file, a leaf to
    delete is not listed by its directory's head, or a file to write differs from read.
    """
    if card.get("kind") != TICKET:
        raise MoveRefused("an entry card or a separator does not move to Roadmap; only a design ticket's card does")
    now = _read(root)
    at = _ticket_at(now.design_cards, card)
    if at is None:
        raise MoveRefused(_GONE)
    part = now.design_parts[at]
    lines = now.lines[part.path]
    if part.runs_on:
        raise MoveRefused(
            f"the ticket {part.title} runs on past {root_relative(root, part.path)} into the next file of the"
            " design; move it with its continuation into one file first"
        )
    changes: list[_Change] = []
    if now.design_cards[at].parked is None:
        ticket = _rebased(lines[part.first : part.last + 1], _directory(root, part.path), "")
        heads = [k for k, c in enumerate(now.roadmap_cards) if c.kind == CATEGORY]
        if now.sha256[ROADMAP] is None:
            added = _appended([CREATED_ROADMAP_HEADING], GENERAL_HEADING, ticket)
        elif not heads:
            added = _appended(now.roadmap, GENERAL_HEADING, ticket)
        else:
            head = next((k for k in heads if asdict(now.roadmap_cards[k]) == target), heads[0])
            added = _added(now.roadmap, _category(now.roadmap_parts, head), ticket)
        changes.append((os.path.join(root, ROADMAP), added))
    changes += _ticket_removed(root, now, part)
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
    digests: dict[str, Optional[str]] = {ROADMAP: None}
    notices: list[Notice] = []
    roadmap_path = roadmap_file(root)
    roadmap: list[str] = []
    roadmap_parts: list[Part] = []
    if roadmap_path is not None:
        f = read_file(roadmap_path)
        layout = roadmap_from_file(f)
        roadmap, roadmap_parts, digests[ROADMAP] = f.lines, layout.parts, sha256(f.text)
        notices += [_notice(root, b, "roadmap") for b in layout.breaches]
    work = [ParkedWork(w.name, [root_relative(root, f) for f in w.files]) for w in parked_work(root)]
    pieces = {os.path.normpath(os.path.join(root, f)): w for w in work for f in w.files}
    links = list(prose_links(roadmap))
    roadmap_cards = _told_apart([_roadmap_card(root, part, roadmap, links, pieces) for part in roadmap_parts])
    linked = {path for card in roadmap_cards for path in card.parked}
    unlinked = [w for w in work if not linked.intersection(w.files)]

    design = active_document(root, ACTIVE_DESIGN)
    files = design_files(design) if design else []
    if not files:
        digests[ACTIVE_DESIGN] = None
    for f in files:
        digests[root_relative(root, f.path)] = sha256(f.text)
    lines = {f.path: f.lines for f in files}
    design_parts: list[Part] = []
    if files:
        read = design_from_files(files)
        design_parts = read.parts
        notices += [_notice(root, b, "design") for b in read.breaches if b.kind in LAYOUT_BREACHES]
    design_cards = _told_apart([_design_card(root, part, lines[part.path], unlinked) for part in design_parts])
    in_design = [card.parked for card in design_cards]
    return _Read(
        roadmap=roadmap,
        roadmap_parts=roadmap_parts,
        roadmap_cards=roadmap_cards,
        parked=[ParkedCard(w.name, w.files, _file_hrefs(root, w.files)) for w in unlinked if w.files not in in_design],
        design=design,
        diced=design is not None and os.path.basename(design) == ENTRY_POINT,
        lines=lines,
        design_parts=design_parts,
        design_cards=design_cards,
        notices=notices,
        sha256=digests,
    )


def _notice(root: str, breach: Breach, column: str) -> Notice:
    return Notice(column, root_relative(root, breach.path), breach.line, breach.found, breach.accepted)


def _told_apart(cards: list[_Card]) -> list[_Card]:
    """cards, each one's occurrence set to the number of cards before it equal to it in every other
    field."""
    for k, card in enumerate(cards):
        card.occurrence = sum(replace(c, occurrence=0) == card for c in cards[:k])
    return cards


def _text(part: Part, lines: list[str]) -> str:
    """A ticket's text: its lines below the heading, blank lines at either end dropped."""
    return "\n".join(_trimmed(lines[part.first + 1 : part.last + 1]))


def _roadmap_card(
    root: str, part: Part, lines: list[str], links: list[tuple[int, str]], pieces: dict[str, ParkedWork]
) -> RoadmapCard:
    """The card, or for a category the separator, of one part of the roadmap, lines being its lines
    and links their prose_links; pieces maps each parked file's normalized path to its piece of
    parked work, files relative to root. Its occurrence is left 0."""
    if part.kind != TICKET:
        return RoadmapCard(part.title, "", None, [], part.kind, 0)
    parked: list[str] = []
    for no, target in links:
        work = pieces.get(os.path.normpath(os.path.join(root, target.partition("#")[0])))
        if part.first < no <= part.last + 1 and work:
            parked += [f for f in work.files if f not in parked]
    return RoadmapCard(part.title, _text(part, lines), _href(root, part.path, part.anchor), parked, TICKET, 0)


def _design_card(root: str, part: Part, lines: list[str], unlinked: list[ParkedWork]) -> DesignCard:
    """The card, or for a category the separator, of one part of the design, lines being its file's
    and unlinked the parked work no roadmap ticket links, files relative to root. Its occurrence is
    left 0."""
    path = root_relative(root, part.path)
    if part.kind in (CATEGORY, DELTA):
        return DesignCard(part.title, "", path, None, None, None, part.kind, 0)
    parked = None
    if part.kind == TICKET:
        here = _directory(root, part.path)
        ticket = lines[part.first : part.last + 1]
        parked = next((w.files for w in unlinked if ticket == _link_ticket(w.name, w.files, here)), None)
    href = _href(root, part.path, part.anchor)
    parked_hrefs = None if parked is None else _file_hrefs(root, parked)
    return DesignCard(part.title, _text(part, lines), path, href, parked, parked_hrefs, part.kind, 0)


def _package_card(root: str, package: WorkPackage) -> PackageCard:
    heading = package.heading
    href = _href(root, heading.path, heading.anchor) if heading else _href(root, package.path, "")
    return PackageCard(**vars(package), href=href)


def _href(root: str, path: str, anchor: str) -> str:
    """The URL path of the file at path, its path from root percent-quoted (a byte of a name that is
    not UTF-8 quoted as that byte), then `#` and anchor where there is one; the one builder of a
    served file's URL."""
    url = "/" + quote(root_relative(root, path), errors="surrogateescape")
    return f"{url}#{anchor}" if anchor else url


def _file_hrefs(root: str, files: list[str]) -> list[str]:
    """The URL path of each of files, relative to root, no anchor."""
    return [_href(root, os.path.join(root, f), "") for f in files]


def _ticket_at(cards: Sequence[Union[RoadmapCard, DesignCard]], card: dict[str, Any]) -> Optional[int]:
    """The index of the ticket card among cards that equals card as served; None where none does."""
    return next((k for k, c in enumerate(cards) if c.kind == TICKET and asdict(c) == card), None)


def _opens_an_index(now: _Read, head: int) -> bool:
    """Whether the category part now.design_parts[head] opens an `index.md`: only blank lines above it."""
    part = now.design_parts[head]
    return os.path.basename(part.path) == INDEX and all(is_blank(line) for line in now.lines[part.path][: part.first])


def _new_leaf(
    root: str, now: _Read, head: Optional[int], title: str, ticket: Callable[[str], list[str]]
) -> list[_Change]:
    """The writes adding a ticket titled title to a diced design as a new leaf: beside the `index.md`
    that the `## Drafts` part now.design_parts[head] opens, else, head being None, in a `drafts`
    directory beside the entry point, with its `index.md`. ticket gives its lines for a file's path.
    Its Contents lines' text is the link text dicing gives a section titled title. Raises MoveRefused
    where title has no §3.2 name or a file to create exists."""
    name = section_name(title)
    if not name:
        raise MoveRefused(f"the title {title!r} names no file: give the ticket a title with a letter or digit")
    entry = now.design
    top = os.path.dirname(entry)
    text = contents_text(*split_number(title))
    item = contents_line("", text=text, path=f"{name}.md")
    if head is not None:
        index = now.design_parts[head].path
        leaf = os.path.join(os.path.dirname(index), f"{name}.md")
        created = [leaf]
        changes: list[_Change] = [(leaf, ticket(leaf)), (index, _items_added(now.lines[index], [item]))]
        listed = _listed(now.lines[entry], root_relative(top, leaf), text)
        if listed is not None:
            changes.append((entry, listed))
    else:
        directory = os.path.join(top, DRAFTS_DIRECTORY)
        leaf = os.path.join(directory, f"{name}.md")
        index = os.path.join(directory, INDEX)
        created = [leaf, index]
        listing = [
            contents_line("", text=DRAFTS, path=f"{DRAFTS_DIRECTORY}/{INDEX}"),
            contents_line("  ", text=text, path=f"{DRAFTS_DIRECTORY}/{name}.md"),
        ]
        changes = [
            (leaf, ticket(leaf)),
            (index, [f"## {DRAFTS}", "", CONTENTS, "", item]),
            (entry, _items_added(now.lines[entry], listing)),
        ]
    for path in created:
        if os.path.lexists(path):
            raise MoveRefused(f"{root_relative(root, path)} exists: the move would create it")
    return changes


def _ticket_removed(root: str, now: _Read, part: Part) -> list[_Change]:
    """The writes removing the design ticket of part: a leaf holding only the ticket goes with its
    line in the list of its directory's head's Contents block and, where that head is not the entry
    point, in the full listing; any other ticket through _removed. Raises MoveRefused where that list
    has no line linking the leaf."""
    lines = now.lines[part.path]
    by_path = {os.path.normpath(p): p for p in now.lines}
    heads = [os.path.normpath(os.path.join(os.path.dirname(part.path), name)) for name in HEADS]
    head = next((by_path[p] for p in heads if p in by_path), None)
    whole = all(is_blank(line) for line in lines[: part.first] + lines[part.last + 1 :])
    if not whole or head is None or os.path.basename(part.path) in HEADS:
        return [(part.path, _removed(lines, part))]
    head_lines = now.lines[head]
    leaf = os.path.basename(part.path)
    line = next((k for k in range(*_listing(head_lines)) if _links(head_lines[k], leaf)), None)
    if line is None:
        raise MoveRefused(
            f"{root_relative(root, head)} has no Contents line linking {root_relative(root, part.path)}: the leaf"
            " cannot go with its line"
        )
    changes: list[_Change] = [(head, _without(head_lines, line))]
    entry = now.design
    if head != entry:
        entry_lines = now.lines[entry]
        first, end = _listing(entry_lines)
        from_top = root_relative(os.path.dirname(entry), part.path)
        listed = next((k for k in range(first, end) if _links(entry_lines[k], from_top)), None)
        if listed is not None:
            changes.append((entry, _without(entry_lines, listed)))
    changes.append((part.path, None))
    return changes


def _without(lines: list[str], k: int) -> list[str]:
    return lines[:k] + lines[k + 1 :]


def _links(line: str, path: str) -> bool:
    """Whether a link of line targets path, a `/`-separated relative path, once normalized and its
    fragment dropped."""
    return any(not never_rebased(t) and posixpath.normpath(t.partition("#")[0]) == path for t in link_targets(line))


def _listing(lines: list[str]) -> tuple[int, int]:
    """The list under the last `Contents:` line of a head file's lines, as (first, end): its run of
    list items after any blank lines; first == end where it lists nothing, first then being where a
    first item would go. (len, len) where there is no `Contents:` line."""
    cut = contents_cut(lines)
    if cut < 0:
        return len(lines), len(lines)
    first = next((k for k in range(cut + 1, len(lines)) if not is_blank(lines[k])), len(lines))
    end = next((k for k in range(first, len(lines)) if not _ITEM.match(lines[k])), len(lines))
    return first, end


def _items_added(lines: list[str], items: list[str]) -> list[str]:
    """A head file's lines with items after the last item of the list under its last `Contents:`
    line; where it lists nothing, directly below that line after a blank line; with no `Contents:`
    line, in a Contents block appended to it."""
    cut = contents_cut(lines)
    if cut < 0:
        return _appended(lines, CONTENTS, items)
    first, end = _listing(lines)
    if first < end:
        return [*lines[:end], *items, *lines[end:]]
    return [*lines[: cut + 1], "", *items, *([""] if first < len(lines) else []), *lines[first:]]


def _listed(lines: list[str], leaf: str, text: str) -> Optional[list[str]]:
    """The entry point's lines with the line `- [<text>](<leaf>)` added to its full listing, leaf
    being the path from the entry point's directory: two spaces deeper than the line linking the
    leaf's directory's `index.md`, after it and the lines below it indented deeper; at the listing's
    end, indented two spaces, where no line links that head. None where there is no full listing:
    no list under the last `Contents:` line, or none of its lines linking a file not beside the entry
    point."""
    first, end = _listing(lines)
    if not any(
        "/" in posixpath.normpath(t.partition("#")[0]) for k in range(first, end) for t in link_targets(lines[k])
    ):
        return None
    directory = posixpath.dirname(leaf)
    index = posixpath.join(directory, INDEX)
    at = next((k for k in range(first, end) if directory and _links(lines[k], index)), None)
    if at is None:
        return [*lines[:end], contents_line("  ", text=text, path=leaf), *lines[end:]]
    depth = _indent(lines[at])
    below = next((k for k in range(at + 1, end) if _indent(lines[k]) <= depth), end)
    return [*lines[:below], contents_line(" " * (depth + 2), text=text, path=leaf), *lines[below:]]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _rebased(lines: list[str], source: str, destination: str) -> list[str]:
    """A ticket's lines moved from a file in directory source to one in destination, both relative
    to the root: each relative link target in their prose resolved from source and made relative to
    destination, its fragment kept; lines inside fenced code and code spans unchanged. Between equal
    directories, lines as given."""
    if source == destination:
        return lines

    def rebased(raw: str, text: str, target: str, after: str) -> str:
        if never_rebased(target):
            return raw
        path, mark, fragment = target.partition("#")
        return f"[{text}]({rel(destination, posixpath.normpath(posixpath.join(source, path)))}{mark}{fragment})"

    return [line if fenced else scan(line, rebased) for line, fenced in zip(lines, fence_flags(lines))]


def _category(parts: list[Part], head: int) -> list[Part]:
    """The category whose part is parts[head]: that part and its tickets' parts."""
    end = next((k for k in range(head + 1, len(parts)) if parts[k].kind in (CATEGORY, DELTA)), len(parts))
    return parts[head:end]


def _added(lines: list[str], category: list[Part], ticket: list[str]) -> list[str]:
    """lines, the file holding category's part, with ticket added at the end of category, its part and
    its tickets' parts: after the category's last non-blank line in that file, a blank line before it
    and, where a heading follows directly, a blank line after it. In a diced design's head file the
    category so ends at its Contents cut: its parts there end before it, and its tickets in later
    files are not added after."""
    at = max(p.last for p in category if p.path == category[0].path) + 1
    after = [""] if at < len(lines) and HEADING.match(lines[at]) else []
    return [*lines[:at], "", *ticket, *after, *lines[at:]]


def _appended(lines: list[str], heading: str, ticket: list[str]) -> list[str]:
    """lines with heading and ticket appended, a blank line before each unless the line above is
    blank or there is none."""
    blank = [""] if lines and not is_blank(lines[-1]) else []
    return [*lines, *blank, heading, "", *ticket]


def _removed(lines: list[str], part: Part) -> list[str]:
    """lines without the ticket of part, its first..last, and the blank lines directly above it."""
    first = part.first
    while first > 0 and is_blank(lines[first - 1]):
        first -= 1
    return lines[:first] + lines[part.last + 1 :]


def _write(root: str, changes: list[_Change], read: dict[str, Optional[str]]) -> list[str]:
    """Check every file changes names against read, then write each in order: a file whose lines
    are None is deleted, and a new file's missing directory is made just before it."""
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
                directory = os.path.dirname(path)
                if not os.path.isdir(directory):
                    os.makedirs(directory)
                replace_lines(path, lines)
        except OSError as e:
            raise MoveWriteFailed(root_relative(root, path), written) from e
        written.append(root_relative(root, path))
    return written


def _link_ticket(name: str, files: list[str], here: str) -> list[str]:
    """The lines of the link ticket for the parked work named name, whose files are files, in a file
    in directory here, all relative to root: one link line per file. The one writer of the form and
    the one recogniser of it."""
    return [f"### {name}", "", *(f"[{f}]({rel(here, f)})" for f in files), "", INSTRUCTION]


def _trimmed(lines: list[str]) -> list[str]:
    first = next((i for i, line in enumerate(lines) if not is_blank(line)), len(lines))
    last = next((i for i in range(len(lines) - 1, -1, -1) if not is_blank(lines[i])), -1)
    return lines[first : last + 1]
