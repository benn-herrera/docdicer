"""Unit tests for the plan-form reader: a plan's packages, title and release, the breaches of the plan
form it reports, and the project's root and plan-file locations."""

from pathlib import Path

import pytest

from docdicer.kanban import planform
from docdicer.kanban.planform import (
    ACTIVE_DESIGN,
    ACTIVE_PLAN,
    BreachKind,
    active_document,
    find_project_root,
    parked_entries,
    read_plan,
)

_TABLE = "| Package | State |\n|---|---|\n"
_RATED = "| Package | State | Rating |\n|---|---|---|\n"


def _write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")


def _read(tmp_path: Path, text: str):
    _write(tmp_path, {"plan.md": text})
    return read_plan(str(tmp_path / "plan.md"))


def _breaches(plan, root: Path) -> list[tuple[BreachKind, str, int, str]]:
    return [(b.kind, str(Path(b.path).relative_to(root)), b.line, b.found) for b in plan.breaches]


@pytest.mark.parametrize(
    "text, packages",
    [
        pytest.param(
            "# Plan\n\n## Status\n\n" + _TABLE + "|  | landed |\n| P1 | landed |\n",
            [("P1", "", "landed", "")],
            id="empty-package-cell-is-not-a-package",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n"
            + _TABLE
            + "| P1 | |\n| P2 | |\n| P3 | |\n| P4 | |\n\n"
            + "## P1 — Alpha\n\n### P2: Beta\n\n#### P3. Gamma\n\n###### P4 Delta\n",
            [("P1", "Alpha", "drafted", ""), ("P2", "Beta", "drafted", ""), ("P3", "Gamma", "drafted", "")]
            + [("P4", "Delta", "drafted", "")],
            id="heading-at-any-level-with-any-separator",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n" + _TABLE + "| P1 | |\n\n## P10 Ten\n\n## P1.2 Sub\n\n## P1 — One\n",
            [("P1", "One", "drafted", "")],
            id="heading-matched-by-whole-id",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n" + _TABLE + "| P1 | |\n\n## P1 — The reader (`coder`, expert)\n",
            [("P1", "The reader (`coder`, expert)", "drafted", "")],
            id="only-the-title-taken-from-the-heading",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n" + _TABLE + "| P1 | |\n",
            [("P1", "", "drafted", "")],
            id="no-heading-no-title",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n" + _TABLE + "| P3 | |\n\n## Network usage (P3)\n",
            [("P3", "", "drafted", "")],
            id="heading-mentioning-id-gives-no-title",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n"
            + _TABLE
            + "| A | |\n| B | dispatchable |\n| C | in progress: a note |\n| D | landed (abc123) |\n"
            + "| E | done |\n| F | not started |\n| G | Landed |\n| H | landedness |\n",
            [
                ("A", "", "drafted", ""),
                ("B", "", "dispatchable", ""),
                ("C", "", "in progress", "a note"),
                ("D", "", "landed", "(abc123)"),
                ("E", "", "drafted", "done"),
                ("F", "", "drafted", "not started"),
                ("G", "", "drafted", "Landed"),
                ("H", "", "drafted", "landedness"),
            ],
            id="state-word-and-note-other-words-drafted",
        ),
        pytest.param(
            "# Plan\n\n## Before\n\n"
            + _TABLE
            + "| X | |\n\n## Status\n\n| Piece | State |\n|---|---|\n| Y | landed |\n\n"
            + _TABLE
            + "| P1 | landed |\n\n"
            + _TABLE
            + "| Z | landed |\n\n## After\n\n"
            + _TABLE
            + "| W | |\n",
            [("P1", "", "landed", "")],
            id="first-table-with-package-and-state-under-status",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n| package | STATE |\n|---|---|\n| P1 | landed |\n",
            [("P1", "", "landed", "")],
            id="headers-case-insensitive",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n### Packages\n\n" + _TABLE + "| P1 | landed |\n",
            [("P1", "", "landed", "")],
            id="table-under-a-status-subheading",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\nNone yet.\n\n## Other\n\n" + _TABLE + "| P1 | landed |\n",
            [],
            id="status-section-ends-at-next-level-2-heading",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n```text\n" + _TABLE + "| X | landed |\n```\n\n" + _TABLE + "| P1 | landed |\n",
            [("P1", "", "landed", "")],
            id="fenced-table-ignored",
        ),
        pytest.param(
            "# Plan\n\n```\n## Status\n\n" + _TABLE + "| X | landed |\n```\n",
            [],
            id="fenced-status-heading-ignored",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n" + _TABLE + "| P1 | |\n\n~~~\n## P1 — Fenced\n~~~\n",
            [("P1", "", "drafted", "")],
            id="fenced-heading-ignored",
        ),
        pytest.param("# Plan\n\nNo status.\n", [], id="no-status-table"),
    ],
)
def test_packages(tmp_path, text, packages):
    plan = _read(tmp_path, text)
    assert [(p.id, p.title, p.state, p.note) for p in plan.packages] == packages


@pytest.mark.parametrize(
    "text, lifetimes",
    [
        pytest.param(
            "## Status\n\n| Package | Lifetime | State |\n|---|---|---|\n| P1 | shipped | |\n| P2 | | |\n",
            ["shipped", ""],
            id="lifetime-column",
        ),
        pytest.param("## Status\n\n" + _TABLE + "| P1 | |\n", [None], id="no-lifetime-column"),
    ],
)
def test_lifetime(tmp_path, text, lifetimes):
    assert [p.lifetime for p in _read(tmp_path, text).packages] == lifetimes


@pytest.mark.parametrize(
    "text, ratings",
    [
        pytest.param(
            "## Status\n\n| Package | Rating | State |\n|---|---|---|\n"
            + "| A | expert | |\n| B | mechanical | |\n| C | expert: makes D1 | |\n| D | mechanical (step-down) | |\n"
            + "| E | | |\n| F | Expert | |\n| G | **expert** | |\n| H | expertise | |\n| I | trivial | |\n",
            [("expert", ""), ("mechanical", ""), ("expert", "makes D1"), ("mechanical", "(step-down)")]
            + [(None, ""), (None, "Expert"), (None, "**expert**"), (None, "expertise"), (None, "trivial")],
            id="rating-word-and-note-other-words-unrated",
        ),
        pytest.param(
            "## Status\n\n| package | RATING | state |\n|---|---|---|\n| P1 | mechanical | |\n",
            [("mechanical", "")],
            id="rating-header-any-case",
        ),
        pytest.param("## Status\n\n" + _TABLE + "| P1 | |\n", [(None, "")], id="no-rating-column-unrated"),
    ],
)
def test_rating(tmp_path, text, ratings):
    assert [(p.rating, p.rating_note) for p in _read(tmp_path, text).packages] == ratings


def test_package_row_location(tmp_path):
    plan = _read(tmp_path, "# Plan\n\n## Status\n\n" + _TABLE + "| P1 | |\n| P2 | |\n")
    assert [(Path(p.path).name, p.line) for p in plan.packages] == [("plan.md", 7), ("plan.md", 8)]


@pytest.mark.parametrize(
    "text, title, release, hardening",
    [
        pytest.param("# A plan\n\nRelease: 1.2.3\n", "A plan", "1.2.3", False, id="release-line"),
        pytest.param("# A plan\n\nRelease:   1.2.3  \n", "A plan", "1.2.3", False, id="release-spaces-removed"),
        pytest.param("# A plan\n", "A plan", None, False, id="no-release"),
        pytest.param(
            "# Release hardening for 2.0\n\nRelease: 2.0.0\n",
            "Release hardening for 2.0",
            "2.0.0",
            True,
            id="hardening-release-only-from-release-line",
        ),
        pytest.param("# Release hardening\n", "Release hardening", None, True, id="hardening-without-release"),
        pytest.param("# Release hardened\n", "Release hardened", None, False, id="not-the-hardening-prefix"),
        pytest.param("# A plan\n\nIntro.\n\nRelease: 1.0\n", "A plan", None, False, id="release-not-first-line"),
        pytest.param("# A plan\n\n```\nRelease: 1.0\n```\n", "A plan", None, False, id="fenced-release"),
        pytest.param("```\n# Fenced\n```\n\n# A plan\n", "A plan", None, False, id="fenced-h1-ignored"),
        pytest.param("Text only.\n", "", None, False, id="no-h1"),
    ],
)
def test_title_and_release(tmp_path, text, title, release, hardening):
    plan = _read(tmp_path, text)
    assert (plan.title, plan.release, plan.hardening) == (title, release, hardening)


@pytest.mark.parametrize(
    "text, breaches",
    [
        pytest.param(
            "# Plan\n\nRelease: 1.0\n\n## Status\n\n"
            + _RATED
            + "| P1 | landed: ok | expert |\n| P2 | | mechanical: a note |\n|  | stray | |\n\n"
            + "## P1 — One\n\n## P2 — Two (after P1)\n",
            [],
            id="conforming-plan",
        ),
        pytest.param(
            "## Status\n\n" + _RATED + "| P1 | | expert |\n| P2 | | expert |\n| P1 | landed | expert |\n",
            [(BreachKind.ID_REPEATED, 7, "P1 (first row: line 5)")],
            id="id-repeated",
        ),
        pytest.param(
            "## Status\n\n" + _RATED + "| P1 Correction texts | | expert |\n",
            [(BreachKind.ID_SPACE, 5, "P1 Correction texts")],
            id="id-holds-a-space",
        ),
        pytest.param(
            "## Status\n\n" + _RATED + "| P3 | | expert |\n\n## Network usage (P3)\n",
            [],
            id="heading-mentioning-id-is-no-breach",
        ),
        pytest.param(
            "## Status\n\n" + _TABLE + "| P1 | |\n| P2 | |\n",
            [(BreachKind.RATING_MISSING, 3, "| Package | State |")],
            id="no-rating-column-one-breach-at-the-header",
        ),
        pytest.param(
            "## Status\n\n" + _TABLE,
            [(BreachKind.RATING_MISSING, 3, "| Package | State |")],
            id="no-rating-column-in-a-table-without-rows",
        ),
        pytest.param(
            "## Status\n\n"
            + _RATED
            + "| A | | |\n| B | | Expert |\n| C | | **expert** |\n| D | | trivial: one line |\n",
            [
                (BreachKind.RATING_WORD, 5, ""),
                (BreachKind.RATING_WORD, 6, "Expert"),
                (BreachKind.RATING_WORD, 7, "**expert**"),
                (BreachKind.RATING_WORD, 8, "trivial: one line"),
            ],
            id="rating-cell-opening-with-neither-word",
        ),
        pytest.param(
            "## Status\n\n"
            + _RATED
            + "| A | done | expert |\n| B | not started | expert |\n| C | Landed | expert |\n"
            + "| D | **landed** | expert |\n",
            [
                (BreachKind.STATE_WORD, 5, "done"),
                (BreachKind.STATE_WORD, 6, "not started"),
                (BreachKind.STATE_WORD, 7, "Landed"),
                (BreachKind.STATE_WORD, 8, "**landed**"),
            ],
            id="state-cell-opening-with-another-word",
        ),
        pytest.param(
            "# Plan\n\nIntro.\n\nRelease: 1.0\n",
            [(BreachKind.RELEASE_MISPLACED, 5, "Release: 1.0")],
            id="release-not-first-non-blank-after-h1",
        ),
        pytest.param(
            "# Plan\n\nRelease:\n",
            [(BreachKind.RELEASE_EMPTY, 3, "Release:")],
            id="release-without-version",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n```\n"
            + _TABLE
            + "| P1 | done |\n| P1 | done |\n```\n\n```\n## X P2\nRelease: 1\n```\n",
            [],
            id="fenced-content-not-checked",
        ),
        pytest.param(
            "## Status\n\n" + _RATED + "| P1 | | expert |\n| P2 | | expert |\n\n## P1 — Post-plan review\n",
            [(BreachKind.REVIEW_UNPAIRED, 5, "P1 Post-plan review")],
            id="review-without-burndown",
        ),
        pytest.param(
            "## Status\n\n" + _RATED + "| P1 | | expert |\n\n## P1: Post-plan burndown of the review\n",
            [(BreachKind.BURNDOWN_UNPAIRED, 5, "P1 Post-plan burndown of the review")],
            id="burndown-without-review",
        ),
        pytest.param(
            "## Status\n\n"
            + _RATED
            + "| P1 | | expert |\n| P2 | | expert |\n\n## P1 — Post-plan review\n\n## P2 — Post-plan review again\n",
            [
                (BreachKind.REVIEW_UNPAIRED, 5, "P1 Post-plan review"),
                (BreachKind.REVIEW_UNPAIRED, 6, "P2 Post-plan review again"),
            ],
            id="each-unpaired-package-reported",
        ),
        pytest.param(
            "## Status\n\n"
            + _RATED
            + "| P1 | | expert |\n| P2 | | expert |\n\n## P2 — Post-plan burndown\n\n## P1 — Post-plan review\n",
            [],
            id="review-and-burndown-paired",
        ),
        pytest.param(
            "## Status\n\n" + _RATED + "| P1 | | expert |\n| P2 | done | expert |\n\n## P1 — Post-plan review\n",
            [(BreachKind.REVIEW_UNPAIRED, 5, "P1 Post-plan review"), (BreachKind.STATE_WORD, 6, "done")],
            id="pairing-breach-in-reading-order",
        ),
    ],
)
def test_breaches(tmp_path, text, breaches):
    plan = _read(tmp_path, text)
    assert _breaches(plan, tmp_path) == [(kind, "plan.md", line, found) for kind, line, found in breaches]


@pytest.mark.parametrize(
    "heading, kinds",
    [
        pytest.param("## P1 — Post-plan review of P2\n", [BreachKind.REVIEW_UNPAIRED], id="prefix-then-space"),
        pytest.param("## P1 — Post-plan review: findings\n", [BreachKind.REVIEW_UNPAIRED], id="prefix-then-colon"),
        pytest.param("## P1 — Post-plan reviewer\n", [], id="prefix-then-letter"),
        pytest.param("## P1 — Post-plan review2\n", [], id="prefix-then-digit"),
        pytest.param("## P1 — post-plan review\n", [], id="prefix-is-case-sensitive"),
        pytest.param("## The Post-plan review (P1)\n", [], id="untitled-is-neither-kind"),
    ],
)
def test_post_plan_title_rule(tmp_path, heading, kinds):
    plan = _read(tmp_path, "## Status\n\n" + _RATED + "| P1 | | expert |\n\n" + heading)
    assert [b.kind for b in plan.breaches] == kinds


def test_diced_plan(tmp_path):
    _write(
        tmp_path,
        {
            "plan/entry-point.md": "# Plan\n\nRelease: 0.1\n\nContents:\n\n- [Status](status.md)\n",
            "plan/status.md": "## Status\n\n" + _RATED + "| P1 | landed | expert |\n| P2 | done | expert |\n",
            "plan/p1/index.md": "## P1 — One\n",
            "plan/p1/detail.md": "### P2 — Two\n\nRelease: 9\n",
        },
    )
    plan = read_plan(str(tmp_path / "plan/entry-point.md"))
    assert (plan.title, plan.release) == ("Plan", "0.1")
    assert [(p.id, p.title, p.state, Path(p.path).name, p.line) for p in plan.packages] == [
        ("P1", "One", "landed", "status.md", 5),
        ("P2", "Two", "drafted", "status.md", 6),
    ]
    # reading order: the entry point, then every other `.md` of the tree, a directory's files before its subdirectories
    assert _breaches(plan, tmp_path) == [
        (BreachKind.STATE_WORD, "plan/status.md", 6, "done"),
        (BreachKind.RELEASE_MISPLACED, "plan/p1/detail.md", 3, "Release: 9"),
    ]


def test_breaches_are_in_reading_order_by_file_then_line(tmp_path):
    _write(
        tmp_path,
        {
            "plan/entry-point.md": "# Plan\n\n## Status\n\n" + _RATED + "| P1 | done | expert |\n",
            "plan/leaf.md": "Release: 1.0\n",
        },
    )
    plan = read_plan(str(tmp_path / "plan/entry-point.md"))
    assert _breaches(plan, tmp_path) == [
        (BreachKind.STATE_WORD, "plan/entry-point.md", 7, "done"),
        (BreachKind.RELEASE_MISPLACED, "plan/leaf.md", 1, "Release: 1.0"),
    ]


def test_release_after_a_leaf_h1_is_misplaced(tmp_path):
    _write(
        tmp_path,
        {
            "plan/entry-point.md": "# Plan\n\nRelease: 0.1\n",
            "plan/leaf.md": "# Leaf\n\nRelease: 1.0\n",
        },
    )
    plan = read_plan(str(tmp_path / "plan/entry-point.md"))
    assert (plan.title, plan.release) == ("Plan", "0.1")
    assert _breaches(plan, tmp_path) == [(BreachKind.RELEASE_MISPLACED, "plan/leaf.md", 3, "Release: 1.0")]


@pytest.mark.parametrize(
    "git, start, root",
    [
        pytest.param("proj/.git/", "proj/a/b", "proj", id="from-nested-directory"),
        pytest.param("proj/.git/", "proj", "proj", id="from-the-root-itself"),
        pytest.param("proj/.git", "proj/a", "proj", id="git-entry-may-be-a-file"),
    ],
)
def test_find_project_root(tmp_path, git, start, root):
    (tmp_path / start).mkdir(parents=True)
    if git.endswith("/"):
        (tmp_path / git).mkdir(parents=True)
    else:
        _write(tmp_path, {git: "gitdir: elsewhere\n"})
    assert find_project_root(str(tmp_path / start)) == str(tmp_path / root)


def test_find_project_root_without_git(tmp_path, monkeypatch):
    monkeypatch.setattr(planform.os.path, "lexists", lambda path: False)
    assert find_project_root(str(tmp_path)) is None


@pytest.mark.parametrize(
    "files, monolith, expected",
    [
        pytest.param(["ACTIVE_PLAN.md"], ACTIVE_PLAN, "ACTIVE_PLAN.md", id="monolith"),
        pytest.param(["ACTIVE_PLAN/entry-point.md"], ACTIVE_PLAN, "ACTIVE_PLAN/entry-point.md", id="tree"),
        pytest.param(
            ["ACTIVE_DESIGN.md", "ACTIVE_DESIGN/entry-point.md"], ACTIVE_DESIGN, "ACTIVE_DESIGN.md", id="both-monolith"
        ),
        pytest.param(["ACTIVE_PLAN/status.md"], ACTIVE_PLAN, None, id="tree-without-entry-point"),
        pytest.param(["ACTIVE_DESIGN.md"], ACTIVE_PLAN, None, id="neither"),
    ],
)
def test_active_document(tmp_path, files, monolith, expected):
    _write(tmp_path, {name: "# x\n" for name in files})
    assert active_document(str(tmp_path), monolith) == (None if expected is None else str(tmp_path / expected))


@pytest.mark.parametrize(
    "files, entries",
    [
        pytest.param(
            [
                "ROADMAP_PLANS/README.md",
                "ROADMAP_PLANS/b.md",
                "ROADMAP_PLANS/a.md",
                "ROADMAP_PLANS/notes.txt",
                "ROADMAP_PLANS/diced/entry-point.md",
                "ROADMAP_PLANS/diced/leaf.md",
                "ROADMAP_PLANS/loose/leaf.md",
            ],
            ["ROADMAP_PLANS/a.md", "ROADMAP_PLANS/b.md", "ROADMAP_PLANS/diced/entry-point.md"],
            id="readme-excluded-diced-counted-once",
        ),
        pytest.param(["ROADMAP.md"], [], id="no-parked-directory"),
    ],
)
def test_parked_entries(tmp_path, files, entries):
    _write(tmp_path, {name: "# x\n" for name in files})
    assert parked_entries(str(tmp_path)) == [str(tmp_path / e) for e in entries]
