"""The plan-form reader: a development plan's title, release and work packages as its status table
and headings record them, every breach of the plan form met on the way, and where a project keeps
its plan files.

A plan is a monolith, or a diced tree given by its `entry-point.md`; a tree's files are read as one
plan, the entry point first. Headings and tables inside fenced code are not part of the form.
"""

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..dicerlib.heads import ENTRY_POINT
from ..dicerlib.linkcheck import markdown_files
from ..dicerlib.textfile import fence_flags, read_lines

ACTIVE_DESIGN = "ACTIVE_DESIGN.md"
ACTIVE_PLAN = "ACTIVE_PLAN.md"
PARKED_PLANS = "ROADMAP_PLANS"
ROADMAP = "ROADMAP.md"

DRAFTED = "drafted"
STATE_WORDS = ("dispatchable", "in progress", "landed")
RATING_WORDS = ("mechanical", "expert")
HARDENING = "Release hardening"
_RELEASE = "Release:"
_REVIEW = "Post-plan review"
_BURNDOWN = "Post-plan burndown"

HEADING = re.compile(r"(#{1,6}) ")  # group 1 is the `#` run
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


@dataclass
class Breach:
    kind: BreachKind
    path: str
    line: int  # 1-based, in path
    found: str  # the text as the plan holds it
    accepted: str  # the form the plan rule accepts there


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


@dataclass
class Plan:
    title: str  # the H1 heading's text; "" where there is none
    release: Optional[str]  # None where the plan names no release
    hardening: bool
    packages: list[WorkPackage] = field(default_factory=list)
    breaches: list[Breach] = field(default_factory=list)


@dataclass
class Heading:
    path: str
    line: int  # 1-based, in path
    level: int
    text: str  # after the `#` run, surrounding spaces removed


@dataclass
class PlanFile:
    path: str
    lines: list[str]
    fenced: list[bool]  # per line: inside fenced code


def _read(path: str) -> PlanFile:
    lines = read_lines(path)
    return PlanFile(path, lines, fence_flags(lines))


def plan_files(path: str) -> list[PlanFile]:
    """The files of the document at path, in reading order: a monolith alone, or a diced tree's
    entry point and then every other `.md` beneath its directory. Raises OSError where one cannot
    be read."""
    if os.path.basename(path) != ENTRY_POINT:
        return [_read(path)]
    leaves = [p for p in markdown_files([os.path.dirname(path) or "."]) if not os.path.samefile(p, path)]
    return [_read(p) for p in [path, *leaves]]


def file_headings(f: PlanFile) -> list[Heading]:
    """The headings of f outside fenced code, in order."""
    found = []
    for no, (line, fenced) in enumerate(zip(f.lines, f.fenced), 1):
        m = HEADING.match(line)
        if m and not fenced:
            found.append(Heading(f.path, no, len(m.group(1)), line[m.end() :].strip()))
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


def _title(package_id: str, headings: list[Heading]) -> str:
    """The title of the first heading opening with the ID; "" where none does."""
    opening = re.compile(re.escape(package_id) + _ID_END)
    for h in headings:
        m = opening.match(h.text)
        if m:
            return _after_separator(h.text[m.end() :])
    return ""


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
        title = _title(package_id, headings)
        packages.append(
            WorkPackage(package_id, title, word or DRAFTED, note, lifetime, rating, rating_note, table_path, no)
        )
    return packages


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


def parked_entries(root: str) -> list[str]:
    """Each parked entry, sorted: a `.md` file in the parked-plans directory other than `README.md`,
    or the entry point of a subdirectory there holding one."""
    directory = os.path.join(root, PARKED_PLANS)
    if not os.path.isdir(directory):
        return []
    entries = []
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if os.path.isdir(path):
            entry = os.path.join(path, ENTRY_POINT)
            if os.path.isfile(entry):
                entries.append(entry)
        elif name.endswith(".md") and name != "README.md" and os.path.isfile(path):
            entries.append(path)
    return entries
