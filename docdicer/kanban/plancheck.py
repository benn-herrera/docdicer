"""The plan, design and roadmap checks: every breach of the plan form a plan holds, of the design
form a design holds, or of the ticket layout a roadmap holds, each reported with its file, line, the
text found there and the form accepted in its place, so that the fix can be made from the message.
"""

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Optional, TextIO

from ..dicerlib.textfile import read_text
from .planform import (
    ACTIVE_DESIGN,
    ACTIVE_PLAN,
    ENTRY,
    TICKET,
    Breach,
    BreachKind,
    Pair,
    active_document,
    document_locations,
    find_project_root,
    read_design,
    read_plan,
    read_roadmap,
    roadmap_file,
)

_PROBLEMS = {
    BreachKind.ID_REPEATED: "package ID repeated in the status table",
    BreachKind.ID_SPACE: "package ID holds a space",
    BreachKind.STATE_WORD: "State cell opens with no state word",
    BreachKind.RELEASE_MISPLACED: "`Release:` line is not the first non-blank line after the H1 heading",
    BreachKind.RELEASE_EMPTY: "`Release:` line names no version",
    BreachKind.RATING_MISSING: "status table has no Rating column",
    BreachKind.RATING_WORD: "Rating cell opens with no rating word",
    BreachKind.REVIEW_UNPAIRED: "post-plan review has no post-plan burndown package",
    BreachKind.BURNDOWN_UNPAIRED: "post-plan burndown has no post-plan review package",
    BreachKind.DELTA_MISSPELLED: "delta heading misspelled",
    BreachKind.NOT_A_DELTA: "section is not a delta",
    BreachKind.DELTA_REPEATED: "delta heading repeated",
    BreachKind.DELTA_ORDER: "delta heading out of order",
    BreachKind.NO_DELTA: "design has no delta",
    BreachKind.DELTA_CONTENT: "delta holds content outside an entry",
    BreachKind.MULTI_LINK: "entry heading carries more than one link",
    BreachKind.PAIR_INCOMPLETE: "pair is incomplete",
    BreachKind.TARGET_UNREADABLE: "target cannot be read",
    BreachKind.FROM_NOT_FOUND: "from not found",
    BreachKind.PAIR_DRIFTED: "pair has drifted",
    BreachKind.PAIR_CONFLICTING: "pair is conflicting",
    BreachKind.TICKET_OUTSIDE: "ticket outside a category",
    BreachKind.OLD_FORM_ITEM: "list item in the old ticket form",
    BreachKind.TICKET_EMPTY: "ticket heading names nothing",
    BreachKind.NO_CATEGORY: "roadmap has no category",
}

# Matching reads each run of whitespace on either side as one space, every other character exact.
_WHITESPACE = re.compile(r"\s+")

# The states a pair's target text gives it, as SPEC §8.7 names them.
PENDING = "pending"
LANDED = "landed"
DRIFTED = "drifted"
CONFLICTING = "conflicting"
UNREADABLE = "unreadable"


def _found(text: str, *, empty: str) -> str:
    """The found text as a message gives it: in a code span that holds its own backticks; an empty
    text as `found an empty <empty>`."""
    if not text:
        return f"found an empty {empty}"
    fence = "`" * (max((len(run) for run in re.findall("`+", text)), default=0) + 1)
    return f"found {fence} {text} {fence}"


def _both_forms_refusal(root: str, monolith: str, noun: str) -> Optional[str]:
    """The message refusing to choose between the two forms of the document named monolith under
    root: its monolith and its diced tree's entry point, where both are files; None where either is
    not a file."""
    path, entry = document_locations(root, monolith)
    if os.path.isfile(path) and os.path.isfile(entry):
        return f"both forms of the active {noun} exist: {path} and {entry}: remove one"
    return None


def _breach_line(breach: Breach, *, empty: str) -> str:
    """One breach's stderr line."""
    return (
        f"{breach.path}:{breach.line}: {_PROBLEMS[breach.kind]}:"
        f" {_found(breach.found, empty=empty)}; accepted: {breach.accepted}"
    )


@dataclass
class _Report:
    """What a check's reader gives the driver: the breaches to print, in document order; the summary
    line; the exit status the check returns; and the stdout lines printed before the summary."""

    breaches: list[Breach]
    summary: str
    status: int
    lines: list[str] = field(default_factory=list)


def _check(
    document: Optional[str],
    *,
    noun: str,
    find: Callable[[str], Optional[str]],
    absent: str,
    read: Callable[[str], _Report],
    empty: str,
    start: str,
    stdout: TextIO,
    stderr: TextIO,
    monolith: Optional[str] = None,
) -> int:
    """The check driver of check_plan, check_design and check_roadmap: noun names the document kind,
    find gives its default document under a project root or None, absent names the document where
    find gives none, read gives the report the run prints, empty is what an empty found text is, and
    monolith names the document whose two forms a run without a document refuses to choose between,
    None where the document has no such pair."""
    if document is None:
        root = find_project_root(start)
        if root is None:
            print(
                f"no project root: neither {start} nor any directory above it holds .git;"
                f" run docdicer check-{noun} inside a project, or name the {noun} to check:"
                f" docdicer check-{noun} <{noun}>",
                file=stderr,
            )
            return 2
        if monolith is not None:
            refusal = _both_forms_refusal(root, monolith, noun)
            if refusal is not None:
                print(refusal, file=stderr)
                return 2
        document = find(root)
        if document is None:
            print(f"no {absent} in {root}", file=stdout)
            return 0
    try:
        report = read(document)
    except OSError as e:
        print(f"cannot read: {e.filename if e.filename is not None else document}", file=stderr)
        return 2
    for breach in report.breaches:
        print(_breach_line(breach, empty=empty), file=stderr)
        if breach.interference is not None:
            print(breach.interference, file=stderr)
    for line in report.lines:
        print(line, file=stdout)
    print(report.summary, file=stdout)
    return report.status


def _plan_report(path: str) -> _Report:
    plan = read_plan(path)
    return _Report(
        plan.breaches,
        f"plan checked: {path}, work packages: {len(plan.packages)}, problems: {len(plan.breaches)}",
        1 if plan.breaches else 0,
    )


def _roadmap_report(path: str) -> _Report:
    roadmap = read_roadmap(path)
    return _Report(
        roadmap.breaches,
        f"roadmap checked: {path}, tickets: {sum(part.kind == TICKET for part in roadmap.parts)},"
        f" problems: {len(roadmap.breaches)}",
        1 if roadmap.breaches else 0,
    )


def _normalized(text: str) -> str:
    """Text with each run of whitespace read as one space."""
    return _WHITESPACE.sub(" ", text)


def _first_line(text: str) -> str:
    """The first line of text."""
    return text.split("\n", 1)[0]


def _target_text(path: str, cache: dict[str, Optional[str]]) -> Optional[str]:
    """The target's text, read once per path; None where it cannot be read."""
    if path not in cache:
        try:
            cache[path] = read_text(path)
        except OSError:
            cache[path] = None
    return cache[path]


def _pair_state(pair: Pair, target: Optional[str]) -> str:
    """The pair's state against its target's text: pending, landed, drifted or conflicting; unreadable
    where the target cannot be read. A becomes text that contains its from text is an addition: its
    becomes' presence is the applied state, and its absence leaves the from pending while the from
    survives."""
    if target is None:
        return UNREADABLE
    source = _normalized(pair.source)
    becomes = _normalized(pair.becomes)
    text = _normalized(target)
    applied = becomes in text
    if source and source in becomes:
        if applied:
            return LANDED
        return PENDING if source in text else DRIFTED
    survives = bool(source) and source in text
    if survives:
        return CONFLICTING if applied else PENDING
    return LANDED if applied else DRIFTED


def _target_breach(pair: Pair) -> Breach:
    """The breach a pair's unreadable target makes."""
    return Breach(BreachKind.TARGET_UNREADABLE, pair.path, pair.line, pair.target, "a readable target file")


def _from_breach(pair: Pair) -> Breach:
    """The breach a pair's from passage makes where it does not match its target."""
    return Breach(
        BreachKind.FROM_NOT_FOUND, pair.path, pair.line, _first_line(pair.source), f"matching in {pair.target}"
    )


def _state_breaches(breaches: list[Breach], states: list[tuple[Pair, str]]) -> list[Breach]:
    """The design's breaches plus a breach for each drifted, conflicting or unreadable pair, the
    interference line set where a drifted or conflicting pair's target also holds a landed pair's
    becomes."""
    landed_targets = {pair.target for pair, state in states if state == LANDED}
    found = list(breaches)
    for pair, state in states:
        if state == UNREADABLE:
            found.append(_target_breach(pair))
        elif state in (DRIFTED, CONFLICTING):
            kind = BreachKind.PAIR_DRIFTED if state == DRIFTED else BreachKind.PAIR_CONFLICTING
            interference = None
            if pair.target in landed_targets:
                interference = (
                    f"interference: {pair.target} also holds the becomes passage of a landed pair of this design"
                )
            found.append(
                Breach(kind, pair.path, pair.line, _first_line(pair.source), f"matching in {pair.target}", interference)
            )
    return found


def _document_order(files: list[str]) -> Callable[[Breach], tuple[int, int]]:
    """The sort key putting breaches in document order: by file in files' order, then by line."""
    order = {path: k for k, path in enumerate(files)}
    return lambda breach: (order[breach.path], breach.line)


def _design_report(path: str, *, deltas_applied: bool) -> _Report:
    """The report read_design's design gives: without deltas_applied every pair's from must match its
    target; with it every pair must have landed, its state printed in document order and its summary
    counted. Targets are read, never written."""
    design = read_design(path)
    order = _document_order(design.files)
    pairs = [pair for part in design.parts if part.kind == ENTRY for pair in part.pairs]
    targets: dict[str, Optional[str]] = {}
    if not deltas_applied:
        breaches = list(design.breaches)
        for pair in pairs:
            target = _target_text(pair.target, targets)
            if target is None:
                breaches.append(_target_breach(pair))
            elif _normalized(pair.source) not in _normalized(target):
                breaches.append(_from_breach(pair))
        breaches.sort(key=order)
        return _Report(
            breaches,
            f"design checked: {path}, entries: {sum(part.kind == ENTRY for part in design.parts)},"
            f" problems: {len(breaches)}",
            1 if breaches else 0,
        )
    states = [(pair, _pair_state(pair, _target_text(pair.target, targets))) for pair in pairs]
    breaches = _state_breaches(design.breaches, states)
    breaches.sort(key=order)
    counts = {state: sum(1 for _, s in states if s == state) for state in (PENDING, LANDED, DRIFTED, CONFLICTING)}
    summary = (
        f"design checked: {path}, pairs: {len(states)}, landed: {counts[LANDED]},"
        f" pending: {counts[PENDING]}, drifted: {counts[DRIFTED]},"
        f" conflicting: {counts[CONFLICTING]}, problems: {len(breaches)}"
    )
    lines = [f"{pair.path}:{pair.line}: {state}: {pair.target}" for pair, state in states]
    return _Report(breaches, summary, 0 if not breaches and counts[LANDED] == len(states) else 1, lines)


def check_plan(plan: Optional[str], *, start: str, stdout: TextIO, stderr: TextIO) -> int:
    """Check the plan at plan, or with None the active plan of the project the directory start is
    in; 0 when it holds no breach or there is no active plan, 1 on any breach, 2 when the project
    root is not found, both forms of the active plan exist, or a file of the plan cannot be read."""
    return _check(
        plan,
        noun="plan",
        find=lambda root: active_document(root, ACTIVE_PLAN),
        absent="active plan",
        read=_plan_report,
        empty="cell",
        start=start,
        stdout=stdout,
        stderr=stderr,
        monolith=ACTIVE_PLAN,
    )


def check_design(
    design: Optional[str], *, start: str, stdout: TextIO, stderr: TextIO, deltas_applied: bool = False
) -> int:
    """Check the design at design, or with None the active design of the project the directory start
    is in; without deltas_applied every pair's from must match its target, with it every pair must
    have landed. The design's own breaches come from its reader, `read_design`; the breaches of a
    pair's target come from this check, which reads every target's text and reports a target that
    cannot be read, and, without deltas_applied, a from that matches none of it, with it a pair
    drifted or conflicting. 0 when the design passes or there is no active design, 1 on any breach
    or a pair that has not landed, 2 when the project root is not found, both forms of the active
    design exist, or a file of the design cannot be read."""
    return _check(
        design,
        noun="design",
        find=lambda root: active_document(root, ACTIVE_DESIGN),
        absent="active design",
        read=lambda path: _design_report(path, deltas_applied=deltas_applied),
        empty="line",
        start=start,
        stdout=stdout,
        stderr=stderr,
        monolith=ACTIVE_DESIGN,
    )


def check_roadmap(roadmap: Optional[str], *, start: str, stdout: TextIO, stderr: TextIO) -> int:
    """Check the roadmap at roadmap, or with None the `ROADMAP.md` of the project the directory start
    is in; 0 when it holds no breach or there is no `ROADMAP.md`, 1 on any breach, 2 when the project
    root is not found or the roadmap cannot be read."""
    return _check(
        roadmap,
        noun="roadmap",
        find=roadmap_file,
        absent="roadmap",
        read=_roadmap_report,
        empty="line",
        start=start,
        stdout=stdout,
        stderr=stderr,
    )
