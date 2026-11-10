"""The plan check: every breach of the plan form a plan holds, each reported with its file, line, the
text found there and the form accepted in its place, so that the fix can be made from the message.
"""

import re
from typing import Optional, TextIO

from .planform import ACTIVE_PLAN, Breach, BreachKind, active_document, find_project_root, read_plan

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
}


def _found(text: str) -> str:
    """The found text as a message gives it: in a code span that holds its own backticks."""
    if not text:
        return "found an empty cell"
    fence = "`" * (max((len(run) for run in re.findall("`+", text)), default=0) + 1)
    return f"found {fence} {text} {fence}"


def _message(breach: Breach) -> str:
    return f"{breach.path}:{breach.line}: {_PROBLEMS[breach.kind]}: {_found(breach.found)}; accepted: {breach.accepted}"


def check_plan(plan: Optional[str], *, start: str, stdout: TextIO, stderr: TextIO) -> int:
    """Check the plan at plan, or with None the active plan of the project the directory start is
    in; 0 when it holds no breach or there is no active plan, 1 on any breach, 2 when the project
    root is not found or a file of the plan cannot be read."""
    if plan is None:
        root = find_project_root(start)
        if root is None:
            print(
                f"no project root: neither {start} nor any directory above it holds .git;"
                " run docdicer check-plan inside a project, or name the plan to check: docdicer check-plan <plan>",
                file=stderr,
            )
            return 2
        plan = active_document(root, ACTIVE_PLAN)
        if plan is None:
            print(f"no active plan in {root}", file=stdout)
            return 0
    try:
        read = read_plan(plan)
    except OSError as e:
        print(f"cannot read: {e.filename if e.filename is not None else plan}", file=stderr)
        return 2
    for breach in read.breaches:
        print(_message(breach), file=stderr)
    print(f"plan checked: {plan}, work packages: {len(read.packages)}, problems: {len(read.breaches)}", file=stdout)
    return 1 if read.breaches else 0
