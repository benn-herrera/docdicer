"""The plan and design checks: every breach of the plan form a plan holds, or of the design form a
design holds, each reported with its file, line, the text found there and the form accepted in its
place, so that the fix can be made from the message.
"""

import re
from collections.abc import Callable
from typing import Optional, TextIO

from .planform import (
    ACTIVE_DESIGN,
    ACTIVE_PLAN,
    ENTRY,
    Breach,
    BreachKind,
    active_document,
    find_project_root,
    read_design,
    read_plan,
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
    BreachKind.ENTRY_EMPTY: "entry heading names nothing",
}


def _found(text: str, *, empty: str) -> str:
    """The found text as a message gives it: in a code span that holds its own backticks; an empty
    text as `found an empty <empty>`."""
    if not text:
        return f"found an empty {empty}"
    fence = "`" * (max((len(run) for run in re.findall("`+", text)), default=0) + 1)
    return f"found {fence} {text} {fence}"


def _check(
    document: Optional[str],
    *,
    noun: str,
    monolith: str,
    read: Callable[[str], tuple[list[Breach], int]],
    counted: str,
    empty: str,
    start: str,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """The check driver of check_plan and check_design: noun names the document kind, monolith its
    active document, read gives its breaches and the count the summary names as counted, and empty
    is what an empty found text is."""
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
        document = active_document(root, monolith)
        if document is None:
            print(f"no active {noun} in {root}", file=stdout)
            return 0
    try:
        breaches, count = read(document)
    except OSError as e:
        print(f"cannot read: {e.filename if e.filename is not None else document}", file=stderr)
        return 2
    for b in breaches:
        print(
            f"{b.path}:{b.line}: {_PROBLEMS[b.kind]}: {_found(b.found, empty=empty)}; accepted: {b.accepted}",
            file=stderr,
        )
    print(f"{noun} checked: {document}, {counted}: {count}, problems: {len(breaches)}", file=stdout)
    return 1 if breaches else 0


def _plan_breaches(path: str) -> tuple[list[Breach], int]:
    plan = read_plan(path)
    return plan.breaches, len(plan.packages)


def _design_breaches(path: str) -> tuple[list[Breach], int]:
    design = read_design(path)
    return design.breaches, sum(part.kind == ENTRY for part in design.parts)


def check_plan(plan: Optional[str], *, start: str, stdout: TextIO, stderr: TextIO) -> int:
    """Check the plan at plan, or with None the active plan of the project the directory start is
    in; 0 when it holds no breach or there is no active plan, 1 on any breach, 2 when the project
    root is not found or a file of the plan cannot be read."""
    return _check(
        plan,
        noun="plan",
        monolith=ACTIVE_PLAN,
        read=_plan_breaches,
        counted="work packages",
        empty="cell",
        start=start,
        stdout=stdout,
        stderr=stderr,
    )


def check_design(design: Optional[str], *, start: str, stdout: TextIO, stderr: TextIO) -> int:
    """Check the design at design, or with None the active design of the project the directory start
    is in; 0 when it holds no breach or there is no active design, 1 on any breach, 2 when the
    project root is not found or a file of the design cannot be read."""
    return _check(
        design,
        noun="design",
        monolith=ACTIVE_DESIGN,
        read=_design_breaches,
        counted="entries",
        empty="line",
        start=start,
        stdout=stdout,
        stderr=stderr,
    )
