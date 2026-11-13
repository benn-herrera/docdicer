"""The layout, roadmap, plan-form and design-form reader: a document's categories and tickets in the
ticket layout, a development plan's title, release and work packages as its status table and
headings record them, a design's categories, deltas, tickets and entries, every breach of each form
met on the way, and where a project keeps its roadmap, plan and design files.

A plan or design is a monolith, or a diced tree given by its `entry-point.md`; a tree's files are
read as one document, the entry point first. Headings and tables inside fenced code are not part of
the form.
"""

import os
import re
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional

from ..dicerlib.anchors import heading_anchor_list
from ..dicerlib.heads import ENTRY_POINT, HEADS
from ..dicerlib.linkcheck import markdown_files
from ..dicerlib.linkrewrite import never_rebased
from ..dicerlib.linkscan import link_targets, plain_text
from ..dicerlib.reassemble import own_end
from ..dicerlib.textfile import fence_flags, is_blank, read_text, split_lines

ACTIVE_DESIGN = "ACTIVE_DESIGN.md"
ACTIVE_PLAN = "ACTIVE_PLAN.md"
PARKED_DESIGNS = "ROADMAP_DESIGNS"
_TOPIC_SUFFIXES = ("_DESIGN", "_PLAN", "_PLAN_REVIEW")  # a parked name `<topic><suffix>` makes a topic
ROADMAP = "ROADMAP.md"

DRAFTED = "drafted"
STATE_WORDS = ("dispatchable", "in progress", "landed")
RATING_WORDS = ("mechanical", "expert")
HARDENING = "Release hardening"
_RELEASE = "Release:"
_REVIEW = "Post-plan review"
_BURNDOWN = "Post-plan burndown"
DELTA_HEADINGS = ("SPEC delta", "ARCHITECTURE delta", "Code delta")  # in the order a design holds them
_DELTA_LIST = ", ".join(f"`## {d}`" for d in DELTA_HEADINGS)
# The kinds of a Part; plain strings, as the board's payload carries them.
CATEGORY = "category"
TICKET = "ticket"
DELTA = "delta"  # a design's delta: a category headed by one of DELTA_HEADINGS
ENTRY = "entry"  # a ticket of a delta

HEADING = re.compile(r"(#{1,6}) ")  # group 1 is the `#` run
_OLD_FORM_ITEM = re.compile(r"(?:[-*+]|[0-9]+[.)]) \*\*")
_STATE = re.compile("(" + "|".join(STATE_WORDS) + r")(?!\w)")
_RATING = re.compile("(" + "|".join(RATING_WORDS) + r")(?!\w)")
_RATING_FORM = (
    "`mechanical` where the package's own text enumerates every edit and needs no design choice and no"
    " debugging, else `expert`, which is also the rating wherever its text does not settle it; lowercase and"
    " without markup; any text after the word is a note"
)
# What may sit between an ID and its title, or a state or rating word and its note.
_SEPARATOR = re.compile(r"[\s:.,;|/)\]\-–—]*")
# An ID ends where no word character, nor a `.` or `-` joined to one, follows it.
_ID_END = r"(?!\w|[.-]\w)"
_DELIMITER_ROW = re.compile(r"\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*")
_CELL_BORDER = re.compile(r"(?<!\\)\|")


class BreachKind(Enum):
    ID_REPEATED = "id-repeated"
    ID_SPACE = "id-space"
    STATE_WORD = "state-word"
    RELEASE_MISPLACED = "release-misplaced"
    RELEASE_EMPTY = "release-empty"
    RATING_MISSING = "rating-missing"
    RATING_WORD = "rating-word"
    REVIEW_UNPAIRED = "review-unpaired"
    BURNDOWN_UNPAIRED = "burndown-unpaired"
    DELTA_MISSPELLED = "delta-misspelled"
    NOT_A_DELTA = "not-a-delta"
    DELTA_REPEATED = "delta-repeated"
    DELTA_ORDER = "delta-order"
    NO_DELTA = "no-delta"
    DELTA_CONTENT = "delta-content"
    TICKET_OUTSIDE = "ticket-outside"
    OLD_FORM_ITEM = "old-form-item"
    TICKET_EMPTY = "ticket-empty"
    NO_CATEGORY = "no-category"


# The breaches of the ticket layout, which read_layout reports.
LAYOUT_BREACHES = frozenset({BreachKind.TICKET_OUTSIDE, BreachKind.OLD_FORM_ITEM, BreachKind.TICKET_EMPTY})


@dataclass
class Breach:
    kind: BreachKind
    path: str
    line: int  # 1-based, in path
    found: str  # the text as the plan or design holds it
    accepted: str  # the form the rule accepts there


@dataclass
class WorkPackage:
    id: str
    title: str  # from the heading opening with the ID; "" where none does
    state: str  # DRAFTED or one of STATE_WORDS
    note: str  # the State cell after its state word; the whole cell where it has none
    lifetime: Optional[str]  # None where the status table has no Lifetime column
    rating: Optional[str]  # one of RATING_WORDS; None where unrated
    rating_note: str  # the Rating cell after its rating word; the whole cell where it has none
    path: str  # the file holding the package's status row
    line: int
    heading: Optional["Heading"]  # the heading its title is read from; None where untitled


@dataclass
class Plan:
    title: str  # the H1 heading's text; "" where there is none
    release: Optional[str]  # None where the plan names no release
    hardening: bool
    packages: list[WorkPackage] = field(default_factory=list)
    breaches: list[Breach] = field(default_factory=list)


@dataclass
class Part:
    kind: str  # CATEGORY (to its first ticket) or TICKET; a delta's category and tickets are DELTA and ENTRY
    heading: str  # the heading's text as written, links unreduced
    title: str  # a ticket's: its heading's plain text; else the heading
    anchor: str  # as its Heading's
    path: str
    first: int  # 0-based, the heading's line
    # 0-based, the last non-blank line before the next heading of level 3 or less, or before a head file's
    # Contents cut where read_layout cuts
    last: int
    # A category's first line of text above its first ticket, in its file or a later one, as (path, 1-based
    # line): non-blank, outside fenced code and no layout breach; None for a ticket or a category without one.
    first_text: Optional[tuple[str, int]]
    # A ticket's: its text continues into a later file, a non-blank line there coming before any heading
    # of level 3 or less.
    runs_on: bool = False


@dataclass
class Layout:
    parts: list[Part] = field(default_factory=list)  # in document order
    breaches: list[Breach] = field(default_factory=list)


@dataclass
class Design:
    parts: list[Part] = field(default_factory=list)  # in document order
    breaches: list[Breach] = field(default_factory=list)  # the layout's among them


@dataclass
class Heading:
    path: str
    line: int  # 1-based, in path
    level: int
    text: str  # after the `#` run, surrounding spaces removed
    anchor: str  # its GitHub anchor in its file, repeats suffixed


@dataclass
class ParkedWork:
    name: str  # its parked name: the topic's, else its one parked file's or tree's
    files: list[str]  # its parked files and its parked trees' entry points, sorted


@dataclass
class PlanFile:
    path: str
    text: str  # the file's text as read, from which lines are split
    lines: list[str]
    fenced: list[bool]  # per line: inside fenced code


def read_file(path: str) -> PlanFile:
    """The one file at path, as read. Raises OSError where it cannot be read."""
    text = read_text(path)
    lines = split_lines(text)
    return PlanFile(path, text, lines, fence_flags(lines))


def plan_files(path: str) -> list[PlanFile]:
    """The files of the document at path, read, in document_paths order. Raises OSError where one
    cannot be read."""
    return [read_file(p) for p in document_paths(path)]


def document_paths(path: str) -> list[str]:
    """The paths of the files of the document at path, in reading order, none of them read: a
    monolith alone, or a diced tree's entry point and then every other `.md` beneath its directory."""
    if os.path.basename(path) != ENTRY_POINT:
        return [path]
    leaves = [p for p in markdown_files([os.path.dirname(path) or "."]) if not os.path.samefile(p, path)]
    return [path, *leaves]


def design_files(path: str) -> list[PlanFile]:
    """The files of the design at path, in document order: a monolith alone; for a diced design's
    entry point, the entry point, then each file linked from a head file's Contents block, depth
    first in link order, each where a link first reaches it; then the files beneath the entry
    point's directory that no such link reaches, in plan_files order. A link to anything but a
    `.md` file beneath that directory is ignored. Raises OSError where one cannot be read. This
    differs from undice's walk of the entry point's Contents block on purpose: a design's parts are
    found in every head's block and in files no link reaches, each file read once."""
    if os.path.basename(path) != ENTRY_POINT:
        return [read_file(path)]
    top = os.path.realpath(os.path.dirname(path) or ".")
    files: list[PlanFile] = []
    seen: set[str] = set()

    def add(p: str) -> Optional[PlanFile]:
        key = os.path.realpath(p)
        if key in seen:
            return None
        seen.add(key)
        files.append(read_file(p))
        return files[-1]

    def beneath(p: str) -> bool:
        return p.endswith(".md") and os.path.realpath(p).startswith(top + os.sep)

    def follow(p: str) -> None:
        f = add(p)
        if f is None or os.path.basename(p) not in HEADS:
            return
        for line in f.lines[own_end(f.path, f.lines) :]:
            for target in link_targets(line):
                if not never_rebased(target):
                    linked = os.path.normpath(os.path.join(os.path.dirname(p), target.split("#", 1)[0]))
                    if beneath(linked):
                        follow(linked)

    follow(path)
    for p in markdown_files([os.path.dirname(path) or "."]):
        add(p)
    return files


def file_headings(f: PlanFile) -> list[Heading]:
    """The headings of f outside fenced code, in order, each with its anchor."""
    # Every HEADING match is an ATX heading, so each finds its anchor, its repeats counted over them all.
    anchors = dict(heading_anchor_list(f.lines))
    found = []
    for no, (line, fenced) in enumerate(zip(f.lines, f.fenced), 1):
        m = HEADING.match(line)
        if m and not fenced:
            found.append(Heading(f.path, no, len(m.group(1)), line[m.end() :].strip(), anchors[no].name))
    return found


def _cells(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    return [cell.strip() for cell in _CELL_BORDER.split(text)]


def _tables(f: PlanFile, first: int, last: int) -> list[tuple[int, list[str], list[tuple[int, list[str]]]]]:
    """(header's 1-based line, header cells, [(1-based line, cells)]) of each table in lines
    first..last, 0-based inclusive."""
    tables = []
    i = first
    while i < last:
        header, delimiter = f.lines[i], f.lines[i + 1]
        if f.fenced[i] or f.fenced[i + 1] or "|" not in header or not _DELIMITER_ROW.fullmatch(delimiter):
            i += 1
            continue
        rows = []
        header_line = i + 1
        i += 2
        while i <= last and not f.fenced[i] and "|" in f.lines[i]:
            rows.append((i + 1, _cells(f.lines[i])))
            i += 1
        tables.append((header_line, _cells(header), rows))
    return tables


@dataclass
class _StatusTable:
    path: str
    line: int  # the header's, 1-based
    text: str  # the header line as written
    header: list[str]  # lowercased
    rows: list[tuple[int, list[str]]]


def _status_table(files: list[PlanFile], headings: list[Heading]) -> Optional[_StatusTable]:
    """The first table under a `## Status` heading whose headers include Package and State; None
    where there is none."""
    for f in files:
        own = [h for h in headings if h.path == f.path]
        for k, h in enumerate(own):
            if h.level != 2 or h.text != "Status":
                continue
            end = next((g.line - 1 for g in own[k + 1 :] if g.level <= 2), len(f.lines))
            for line, header, rows in _tables(f, h.line, end - 1):
                header = [cell.lower() for cell in header]
                if "package" in header and "state" in header:
                    return _StatusTable(f.path, line, f.lines[line - 1], header, rows)
    return None


def h1_line(lines: list[str], fenced: list[bool]) -> Optional[int]:
    """The 1-based line of the first `# ` heading outside fenced code; None where there is none."""
    return next((no for no, (line, f) in enumerate(zip(lines, fenced), 1) if not f and line.startswith("# ")), None)


def _release(f: PlanFile, h1: Optional[tuple[str, int]], breaches: list[Breach]) -> Optional[str]:
    """The release f names in the plan's release slot, the first non-blank line after the plan's H1
    heading, h1 being that heading's (path, line) or None where the plan has none; reports misplaced
    and empty `Release:` lines. Only the file that opens the plan holds the plan's H1, so in any
    other file every `Release:` line is misplaced, whatever H1 it holds."""
    slot = None
    if h1 is not None and h1[0] == f.path:
        slot = next((n for n in range(h1[1] + 1, len(f.lines) + 1) if f.lines[n - 1].strip()), None)
    if h1 is None:
        misplaced = f"a `{_RELEASE}` line is read only directly after the plan's H1 heading, and this plan has none"
    else:
        misplaced = (
            f"`{_RELEASE} <version>` only as the first non-blank line after the plan's H1 heading, at"
            f" {h1[0]}:{h1[1]}: move this line there, or delete it where that place already holds the plan's"
            f" `{_RELEASE}` line"
        )
    release = None
    for no, (line, fenced) in enumerate(zip(f.lines, f.fenced), 1):
        if fenced or not line.startswith(_RELEASE):
            continue
        if no != slot:
            breaches.append(Breach(BreachKind.RELEASE_MISPLACED, f.path, no, line, misplaced))
            continue
        release = line[len(_RELEASE) :].strip()
        if not release:
            accepted = (
                f"`{_RELEASE} <version>`; or no `{_RELEASE}` line, which names no release, as this empty one does"
            )
            breaches.append(Breach(BreachKind.RELEASE_EMPTY, f.path, no, line, accepted))
    return release


def _title(package_id: str, headings: list[Heading]) -> tuple[str, Optional[Heading]]:
    """The title of the first heading opening with the ID, and that heading; "" and None where none
    does."""
    opening = re.compile(re.escape(package_id) + _ID_END)
    for h in headings:
        m = opening.match(h.text)
        if m:
            return _after_separator(h.text[m.end() :]), h
    return "", None


def _title_opens_with(title: str, prefix: str) -> bool:
    """Whether title begins with prefix followed by its end or a character that is not a letter or digit."""
    return title.startswith(prefix) and not title[len(prefix) : len(prefix) + 1].isalnum()


def _unpaired_post_plan(packages: list[WorkPackage]) -> list[Breach]:
    """A breach at the row of each post-plan review package where the plan has no post-plan burndown
    package, and of each burndown package where it has no review package."""
    breaches = []
    for own, other, kind in (
        (_REVIEW, _BURNDOWN, BreachKind.REVIEW_UNPAIRED),
        (_BURNDOWN, _REVIEW, BreachKind.BURNDOWN_UNPAIRED),
    ):
        if any(_title_opens_with(p.title, other) for p in packages):
            continue
        accepted = (
            f"a package of its own: a status-table row with an ID no other row uses, and a heading at any level"
            f" opening with that ID and then `{other}`, case as shown, as `## <ID> {other}`; or, only where the"
            f" plan is to hold no {other.lower()}, no {own.lower()} package either"
        )
        breaches += [
            Breach(kind, p.path, p.line, f"{p.id} {p.title}", accepted)
            for p in packages
            if _title_opens_with(p.title, own)
        ]
    return breaches


def _after_separator(text: str) -> str:
    return text[_SEPARATOR.match(text).end() :]


def _opening_word(words: "re.Pattern[str]", cell: str) -> tuple[Optional[str], str]:
    """The word of words that cell opens with and the note after it; (None, cell) where it opens
    with none."""
    m = words.match(cell)
    if not m:
        return None, cell
    return m.group(1), _after_separator(cell[m.end() :])


def read_plan(path: str) -> Plan:
    """The plan at path, a monolith or a diced tree's entry point, read as the plan form directs.

    Raises OSError where a file of the plan cannot be read. The breaches are in reading order: by
    file in the plan's reading order, then by line, those on one line in the order found.
    """
    files = plan_files(path)
    opening = files[0]
    h1 = h1_line(opening.lines, opening.fenced)
    title = opening.lines[h1 - 1][2:].strip() if h1 is not None else ""
    h1_at = (opening.path, h1) if h1 is not None else None
    breaches: list[Breach] = []
    release = _release(opening, h1_at, breaches)
    for f in files[1:]:
        _release(f, h1_at, breaches)
    headings = [h for f in files for h in file_headings(f)]
    table = _status_table(files, headings)
    packages = _packages(table, headings, breaches) if table is not None else []
    breaches += _unpaired_post_plan(packages)
    order = {f.path: k for k, f in enumerate(files)}
    breaches.sort(key=lambda b: (order[b.path], b.line))
    return Plan(title, release, title.startswith(HARDENING), packages, breaches)


def _packages(table: _StatusTable, headings: list[Heading], breaches: list[Breach]) -> list[WorkPackage]:
    """The work packages of the status table's rows, reporting the table's breaches."""
    table_path, header = table.path, table.header
    if "rating" not in header:
        accepted = f"a `Rating` column in the status table's header; in each row, {_RATING_FORM}"
        breaches.append(Breach(BreachKind.RATING_MISSING, table_path, table.line, table.text, accepted))
    package_col, state_col = header.index("package"), header.index("state")
    lifetime_col = header.index("lifetime") if "lifetime" in header else None
    rating_col = header.index("rating") if "rating" in header else None
    first_rows: dict[str, int] = {}
    packages = []
    for no, cells in table.rows:
        cells += [""] * (len(header) - len(cells))
        package_id, cell = cells[package_col], cells[state_col]
        if not package_id:
            continue
        if package_id in first_rows:
            accepted = (
                "each Package ID on one row only; where the two rows are one package, delete one row; where they"
                " are two, give this row a new ID and change this package's heading and each mention of it to match"
            )
            found = f"{package_id} (first row: line {first_rows[package_id]})"
            breaches.append(Breach(BreachKind.ID_REPEATED, table_path, no, found, accepted))
        first_rows.setdefault(package_id, no)
        if " " in package_id:
            accepted = (
                f"a Package ID with no spaces, such as `{package_id.replace(' ', '')}`, where no other row uses it;"
                " change the package's heading and each mention of the ID in the plan to match"
            )
            breaches.append(Breach(BreachKind.ID_SPACE, table_path, no, package_id, accepted))
        word, note = _opening_word(_STATE, cell)
        if cell and word is None:
            accepted = (
                "a State cell opening with the word its text means: `dispatchable` (ready to hand to an agent),"
                " `in progress` (dispatched, not yet landed) or `landed` (accepted and committed), lowercase and"
                " without markup, any other text kept after the word as a note; empty only for a package not yet"
                " ready to dispatch (drafted)"
            )
            breaches.append(Breach(BreachKind.STATE_WORD, table_path, no, cell, accepted))
        lifetime = cells[lifetime_col] if lifetime_col is not None else None
        rating, rating_note = None, ""
        if rating_col is not None:
            rating, rating_note = _opening_word(_RATING, cells[rating_col])
            if rating is None:
                accepted = f"a Rating cell opening with {_RATING_FORM}"
                breaches.append(Breach(BreachKind.RATING_WORD, table_path, no, cells[rating_col], accepted))
        title, heading = _title(package_id, headings)
        packages.append(
            WorkPackage(
                package_id, title, word or DRAFTED, note, lifetime, rating, rating_note, table_path, no, heading
            )
        )
    return packages


def _part(kind: str, h: Heading, following: list[Heading], f: PlanFile, end: int) -> Part:
    """The part of kind headed by h in f, following being the headings of f after h, end the
    0-based exclusive end of f's own lines."""
    first = h.line - 1
    stop = next((g.line - 1 for g in following if g.level <= 3), end)
    last = next(i for i in range(stop - 1, first - 1, -1) if not is_blank(f.lines[i]))
    title = plain_text(h.text) if kind == TICKET else h.text
    return Part(kind, h.text, title, h.anchor, f.path, first, last, None)


def read_layout(files: list[PlanFile], *, cut: bool = False) -> Layout:
    """The parts and breaches of files, already read, in the ticket layout, read as one document in
    the order given: a category in one file holds the tickets of the files after it, up to the next
    heading of level 1 or 2. Each file is read whole; with cut, a head file is read only to its
    Contents cut. A ticket carried into a later file runs on where a non-blank line there comes
    before any heading of level 3 or less. Nothing is read from disk. Parts and breaches are in
    document order."""
    layout = Layout()
    in_category = False
    ticket: Optional[Part] = None  # the ticket whose text the reading is in
    awaiting: Optional[Part] = None  # the category whose first_text is still to be found
    for f in files:
        end = own_end(f.path, f.lines) if cut else len(f.lines)
        headings = [h for h in file_headings(f) if h.line <= end]
        at = {h.line: k for k, h in enumerate(headings)}
        for no in range(1, end + 1):
            line, k = f.lines[no - 1], at.get(no)
            h = headings[k] if k is not None else None
            if ticket is not None and ticket.path != f.path and not is_blank(line) and (h is None or h.level > 3):
                ticket.runs_on = True
            if h is not None and h.level <= 2:
                in_category, ticket, awaiting = h.level == 2, None, None
                if in_category:
                    awaiting = _part(CATEGORY, h, headings[k + 1 :], f, end)
                    layout.parts.append(awaiting)
            elif h is not None and h.level == 3 and not in_category:
                accepted = "`### <title>` only below a `## <category>` heading: move it under a category"
                layout.breaches.append(Breach(BreachKind.TICKET_OUTSIDE, f.path, no, line, accepted))
            elif h is not None and h.level == 3:
                awaiting = None
                ticket = _part(TICKET, h, headings[k + 1 :], f, end)
                if not ticket.title.strip():
                    accepted = "`### <title>`, its text not empty once links are reduced to their text"
                    layout.breaches.append(Breach(BreachKind.TICKET_EMPTY, f.path, no, line, accepted))
                layout.parts.append(ticket)
            elif ticket is None and not f.fenced[no - 1] and _OLD_FORM_ITEM.match(line):
                accepted = (
                    "a ticket as a `### <title>` heading below a `## <category>` heading, its text below the"
                    " heading; a list item only inside a ticket's text"
                )
                layout.breaches.append(Breach(BreachKind.OLD_FORM_ITEM, f.path, no, line, accepted))
            elif awaiting is not None and not (f.fenced[no - 1] or is_blank(line)):
                awaiting.first_text, awaiting = (f.path, no), None
    return layout


def _opening_line(f: PlanFile) -> tuple[int, str]:
    """The 1-based line of f's first level-1 heading, else 1, and its text; "" where f is empty."""
    no = h1_line(f.lines, f.fenced) or 1
    return no, f.lines[no - 1] if f.lines else ""


def read_roadmap(path: str) -> Layout:
    """The roadmap at path, one file whatever its name, as roadmap_from_file reads it. Raises
    OSError where it cannot be read."""
    return roadmap_from_file(read_file(path))


def roadmap_from_file(f: PlanFile) -> Layout:
    """The roadmap f, already read, in the ticket layout, with a NO_CATEGORY breach where it holds no
    category. Breaches are in line order."""
    layout = read_layout([f])
    if not any(p.kind == CATEGORY for p in layout.parts):
        no, found = _opening_line(f)
        accepted = "at least one `## <category>` heading, its tickets below it as `### <title>` headings"
        layout.breaches.append(Breach(BreachKind.NO_CATEGORY, f.path, no, found, accepted))
        layout.breaches.sort(key=lambda b: b.line)
    return layout


def _section_breach(part: Part, line: str) -> Breach:
    """The breach of a level-2 heading that is not a delta heading: misspelled where it equals one
    without regard to case and with each whitespace run read as one space."""
    folded = " ".join(part.heading.split()).casefold()
    meant = next((d for d in DELTA_HEADINGS if d.casefold() == folded), None)
    if meant is not None:
        return Breach(BreachKind.DELTA_MISSPELLED, part.path, part.first + 1, line, f"`## {meant}`, spelled exactly so")
    accepted = f"no level-2 heading but {_DELTA_LIST}: make this a heading of another level, or plain text"
    return Breach(BreachKind.NOT_A_DELTA, part.path, part.first + 1, line, accepted)


def _delta_breach(part: Part, line: str, deltas: dict[str, Part]) -> Optional[Breach]:
    """The breach of the delta headed by part, deltas being the deltas met before it, each first
    occurrence in document order; None where it is in place."""
    earlier = deltas.get(part.heading)
    if earlier is not None:
        accepted = (
            f"each delta heading once: move this delta's entries under `## {part.heading}` at"
            f" {earlier.path}:{earlier.first + 1}, and delete this heading"
        )
        return Breach(BreachKind.DELTA_REPEATED, part.path, part.first + 1, line, accepted)
    order = DELTA_HEADINGS.index
    later = next((d for d in deltas.values() if order(d.heading) > order(part.heading)), None)
    if later is None:
        return None
    accepted = (
        f"the deltas in the order {_DELTA_LIST}: move this delta, heading and entries, above `## {later.heading}`"
        f" at {later.path}:{later.first + 1}"
    )
    return Breach(BreachKind.DELTA_ORDER, part.path, part.first + 1, line, accepted)


def read_design(path: str) -> Design:
    """The design at path, a monolith or a diced tree's entry point, read as the design form
    directs. Raises OSError where a file of the design cannot be read. Parts and breaches are in
    document order (design_files), by line within a file."""
    return design_from_files(design_files(path))


def design_from_files(files: list[PlanFile]) -> Design:
    """The design of files, already read, as design_files gives them (never empty), read as
    read_design reads one: read_layout's parts and breaches, a delta's category made a DELTA part and
    its tickets ENTRY parts, and the breaches of the delta rules. A diced design's head files are read
    to their Contents cut. Nothing is read from disk."""
    layout = read_layout(files, cut=os.path.basename(files[0].path) == ENTRY_POINT)
    design = Design(breaches=list(layout.breaches))
    lines = {f.path: f.lines for f in files}
    deltas: dict[str, Part] = {}
    in_delta = False  # the last CATEGORY part met is a delta
    for part in layout.parts:
        if part.kind == CATEGORY:
            line = lines[part.path][part.first]
            in_delta = part.heading in DELTA_HEADINGS
            if not in_delta:
                design.breaches.append(_section_breach(part, line))
            else:
                breach = _delta_breach(part, line, deltas)
                design.breaches += [breach] if breach is not None else []
                deltas.setdefault(part.heading, part)
                part = replace(part, kind=DELTA)
                if part.first_text is not None:
                    path, no = part.first_text
                    accepted = (
                        "only `### <leaf or section>` entries inside a delta: put this line under an entry's heading,"
                        " or move it out of the delta"
                    )
                    design.breaches.append(Breach(BreachKind.DELTA_CONTENT, path, no, lines[path][no - 1], accepted))
        elif in_delta:
            part = replace(part, kind=ENTRY)
        design.parts.append(part)
    if not deltas:
        opening = files[0]
        no, found = _opening_line(opening)
        accepted = f"at least one delta of {_DELTA_LIST}, in that order, each holding `### <leaf or section>` entries"
        design.breaches.append(Breach(BreachKind.NO_DELTA, opening.path, no, found, accepted))
    order = {f.path: k for k, f in enumerate(files)}
    design.breaches.sort(key=lambda b: (order[b.path], b.line))
    return design


def find_project_root(start: str) -> Optional[str]:
    """The nearest of start and its ancestors holding an entry named `.git`; None where none does."""
    directory = os.path.abspath(start)
    while True:
        if os.path.lexists(os.path.join(directory, ".git")):
            return directory
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def active_document(root: str, monolith: str) -> Optional[str]:
    """The file to read for the project document named monolith (ACTIVE_PLAN, ACTIVE_DESIGN): the
    monolith where it exists, else its diced tree's entry point, else None."""
    path = os.path.join(root, monolith)
    if os.path.isfile(path):
        return path
    entry = os.path.join(root, os.path.splitext(monolith)[0], ENTRY_POINT)
    return entry if os.path.isfile(entry) else None


def roadmap_file(root: str) -> Optional[str]:
    """`ROADMAP.md` under root where it is a file; else None."""
    path = os.path.join(root, ROADMAP)
    return path if os.path.isfile(path) else None


def parked_work(root: str) -> list[ParkedWork]:
    """The pieces of parked work under root, sorted by name, then files. Each parked file, a `.md`
    file in the parked-designs directory other than `README.md`, and each parked tree, a
    subdirectory there holding an entry point, has a parked name: the file's name without `.md`, the
    tree's directory name. A name ending in one of _TOPIC_SUFFIXES makes what comes before it a
    topic; a name that is a topic or opens with `<topic>_` joins the longest such topic, and the
    files of one topic are one piece. Every other parked file or tree is a piece of its own."""
    directory = os.path.join(root, PARKED_DESIGNS)
    if not os.path.isdir(directory):
        return []
    named: list[tuple[str, str]] = []  # (parked name, file)
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if os.path.isdir(path):
            entry = os.path.join(path, ENTRY_POINT)
            if os.path.isfile(entry):
                named.append((name, entry))
        elif name.endswith(".md") and name != "README.md" and os.path.isfile(path):
            named.append((name[: -len(".md")], path))
    topics = {n[: -len(s)] for n, _ in named for s in _TOPIC_SUFFIXES if n.endswith(s) and n != s}
    work: list[ParkedWork] = []
    grouped: dict[str, list[str]] = {}
    for name, path in named:
        joins = [t for t in topics if name == t or name.startswith(t + "_")]
        if joins:
            grouped.setdefault(max(joins, key=len), []).append(path)
        else:
            work.append(ParkedWork(name, [path]))
    work += [ParkedWork(topic, sorted(files)) for topic, files in grouped.items()]
    return sorted(work, key=lambda w: (w.name, w.files))
