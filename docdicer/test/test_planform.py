"""Unit tests for the layout, roadmap, plan-form and design-form reader: a plan's packages, title and
release, a design's files and parts, a document's categories and tickets, the breaches of each form
it reports, and the project's root and plan-file locations."""

from pathlib import Path

import pytest

from docdicer.kanban import planform
from docdicer.kanban.planform import (
    ACTIVE_DESIGN,
    ACTIVE_PLAN,
    PARKED_DESIGNS,
    BreachKind,
    active_document,
    design_files,
    find_project_root,
    parked_work,
    read_design,
    read_file,
    read_layout,
    read_plan,
    read_roadmap,
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
    "files, order",
    [
        pytest.param(
            {
                "d/entry-point.md": "# D\n\nContents:\n\n- [z](z.md)\n- [a](a/index.md)\n",
                "d/a/index.md": "## A\n\nContents:\n\n- [b](b.md)\n",
                "d/a/b.md": "### B\n",
                "d/z.md": "## Z\n",
            },
            ["d/entry-point.md", "d/z.md", "d/a/index.md", "d/a/b.md"],
            id="link-order-against-name-order",
        ),
        pytest.param(
            {
                "d/entry-point.md": "# D\n\nContents:\n\n- [z](z.md)\n",
                "d/m.md": "## M\n",
                "d/z.md": "## Z\n",
                "d/a/x.md": "## X\n",
            },
            ["d/entry-point.md", "d/z.md", "d/m.md", "d/a/x.md"],
            id="unlinked-files-after-in-reading-order",
        ),
        pytest.param(
            {
                "d/entry-point.md": "# D\n\nContents:\n\n- [a](a/index.md)\n- [z](z.md#top)\n",
                "d/a/index.md": "## A\n\nContents:\n\n- [z](../z.md)\n- [b](b.md)\n",
                "d/a/b.md": "### B\n",
                "d/z.md": "## Z\n",
            },
            ["d/entry-point.md", "d/a/index.md", "d/z.md", "d/a/b.md"],
            id="linked-twice-read-at-its-first-link",
        ),
        pytest.param(
            {"d/entry-point.md": "# D\n\n- [a](a.md)\n\nContents:\n\n- [z](z.md)\n", "d/a.md": "", "d/z.md": ""},
            ["d/entry-point.md", "d/z.md", "d/a.md"],
            id="only-links-from-the-last-contents-line-on",
        ),
        pytest.param({"d.md": "# D\n\nContents:\n\n- [z](z.md)\n", "z.md": ""}, ["d.md"], id="monolith-alone"),
        pytest.param(
            {
                "d/entry-point.md": "# D\n\nContents:\n\n- [x](../x.md)\n- [p](p.txt)\n- [z](z.md)\n",
                "x.md": "## X\n",
                "d/p.txt": "## P\n",
                "d/z.md": "## Z\n",
            },
            ["d/entry-point.md", "d/z.md"],
            id="links-outside-the-directory-or-to-other-files-ignored",
        ),
    ],
)
def test_design_files_are_in_document_order(tmp_path, files, order):
    _write(tmp_path, files)
    opening = order[0]
    assert [str(Path(f.path).relative_to(tmp_path)) for f in design_files(str(tmp_path / opening))] == order


def _design(tmp_path: Path, text: str):
    _write(tmp_path, {"design.md": text})
    return read_design(str(tmp_path / "design.md"))


@pytest.mark.parametrize(
    "text, breaches",
    [
        pytest.param(
            "# D\n\n## SPEC delta\n\n### a\n\n## architecture  Delta\n",
            [(BreachKind.DELTA_MISSPELLED, 7, "## architecture  Delta")],
            id="misspelled",
        ),
        pytest.param(
            "# D\n\n## Background\n\n## Code delta\n",
            [(BreachKind.NOT_A_DELTA, 3, "## Background")],
            id="not-a-delta",
        ),
        pytest.param(
            "# D\n\n## SPEC delta\n\n### a\n\n## SPEC delta\n",
            [(BreachKind.DELTA_REPEATED, 7, "## SPEC delta")],
            id="repeated",
        ),
        pytest.param(
            "# D\n\n## Code delta\n\n## ARCHITECTURE delta\n\n## SPEC delta\n",
            [(BreachKind.DELTA_ORDER, 5, "## ARCHITECTURE delta"), (BreachKind.DELTA_ORDER, 7, "## SPEC delta")],
            id="out-of-order",
        ),
        pytest.param("Intro\n\n# D\n\nText.\n", [(BreachKind.NO_DELTA, 3, "# D")], id="no-delta-at-the-h1"),
        pytest.param(
            "Intro\n\n### a\n",
            [(BreachKind.NO_DELTA, 1, "Intro"), (BreachKind.TICKET_OUTSIDE, 3, "### a")],
            id="no-delta-no-h1",
        ),
        pytest.param(
            "# D\n\n## SPEC delta\n\nStray.\n\n#### Deeper\n\n### a\n\nBody.\n",
            [(BreachKind.DELTA_CONTENT, 5, "Stray.")],
            id="content-before-first-entry-once",
        ),
        pytest.param(
            "# D\n\n## SPEC delta\n\n### \n\n### [](x.md)\n\n### [x]()\n",
            [(BreachKind.TICKET_EMPTY, 5, "### "), (BreachKind.TICKET_EMPTY, 7, "### [](x.md)")],
            id="entry-names-nothing",
        ),
        pytest.param(
            "# D\n\n## SPEC delta\n\n### [](x) [](y)\n\n### ![](x)\n",
            [(BreachKind.TICKET_EMPTY, 5, "### [](x) [](y)")],
            id="entry-empty-once-links-reduced",
        ),
        pytest.param(
            "# D\n\n## SPEC delta\n\n- **Old** item\n\n### a\n",
            [(BreachKind.OLD_FORM_ITEM, 5, "- **Old** item")],
            id="old-form-item-before-the-first-entry-is-the-layouts-breach-only",
        ),
    ],
)
def test_design_breaches(tmp_path, text, breaches):
    design = _design(tmp_path, text)
    assert _breaches(design, tmp_path) == [(kind, "design.md", line, found) for kind, line, found in breaches]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("# D\n\n## SPEC delta\n\n## ARCHITECTURE delta\n\n### a\n", id="delta-with-no-entries"),
        pytest.param("# D\n\n## Code delta\n\n### docdicer/x.py\n", id="only-a-code-delta"),
        pytest.param(
            "# D\n\n```\n## Background\n```\n\n## SPEC delta\n\n~~~\nfenced\n~~~\n\n### a\n",
            id="fenced-headings-and-lines-ignored",
        ),
        pytest.param(
            "# D\n\n## SPEC delta\n\n### free\n\n### a\n\n# Appendix\n\nFree again.\n", id="level-1-ends-a-delta"
        ),
    ],
)
def test_conforming_design(tmp_path, text):
    assert _design(tmp_path, text).breaches == []


def _parts(document, root: Path) -> list[tuple[str, str, str, str, int, int]]:
    """(kind, heading, title, path from root, first, last) of each part."""
    return [(p.kind, p.heading, p.title, str(Path(p.path).relative_to(root)), p.first, p.last) for p in document.parts]


def test_design_parts_of_a_monolith(tmp_path):
    text = (
        "# D\n\nFree.\n\n## Background\n\n### free\n\n## SPEC delta\n\n### [§1](SPEC.md)\n\nBody.\n\n#### Deeper\n\n"
        "## Code delta\n\n### x.py\n"
    )
    design = _design(tmp_path, text)
    assert _parts(design, tmp_path) == [
        ("category", "Background", "Background", "design.md", 4, 4),
        ("ticket", "free", "free", "design.md", 6, 6),
        ("delta", "SPEC delta", "SPEC delta", "design.md", 8, 8),
        ("entry", "[§1](SPEC.md)", "§1", "design.md", 10, 14),
        ("delta", "Code delta", "Code delta", "design.md", 16, 16),
        ("entry", "x.py", "x.py", "design.md", 18, 18),
    ]


def test_design_parts_of_a_diced_design(tmp_path):
    _write(
        tmp_path,
        {
            "d/entry-point.md": "# D\n\n## SPEC delta\n\nContents:\n\n- [a](a.md)\n",
            "d/a.md": "### a\n\nBody.\n",
        },
    )
    design = read_design(str(tmp_path / "d/entry-point.md"))
    assert design.breaches == []
    assert _parts(design, tmp_path) == [
        ("delta", "SPEC delta", "SPEC delta", "d/entry-point.md", 2, 2),
        ("entry", "a", "a", "d/a.md", 0, 2),
    ]


def test_delta_content_in_a_later_file_of_a_diced_design(tmp_path):
    _write(
        tmp_path,
        {
            "d/entry-point.md": "# D\n\n## SPEC delta\n\nContents:\n\n- [a](a.md)\n",
            "d/a.md": "Stray.\n\n### a\n",
        },
    )
    design = read_design(str(tmp_path / "d/entry-point.md"))
    assert _breaches(design, tmp_path) == [(BreachKind.DELTA_CONTENT, "d/a.md", 1, "Stray.")]


def _layout(tmp_path: Path, text: str):
    _write(tmp_path, {"doc.md": text})
    return read_layout([read_file(str(tmp_path / "doc.md"))])


@pytest.mark.parametrize("marker", ["-", "*", "+", "1.", "1)"])
def test_an_old_form_item_outside_a_ticket_is_a_breach_for_each_list_marker(tmp_path, marker):
    item = f"{marker} **Old** item"
    layout = _layout(tmp_path, f"{item}\n\n## C\n\n{item}\n\n### t\n\n{item}\n")
    assert _breaches(layout, tmp_path) == [
        (BreachKind.OLD_FORM_ITEM, "doc.md", 1, item),
        (BreachKind.OLD_FORM_ITEM, "doc.md", 5, item),
    ]


@pytest.mark.parametrize(
    "text, breaches",
    [
        pytest.param("# R\n\n## C\n\n### t\n\nText.\n", [], id="conforming"),
        pytest.param("Intro.\n\n- a plain item\n\n## C\n", [], id="free-lines-above-the-first-category"),
        pytest.param("### t\n\n## C\n", [(BreachKind.TICKET_OUTSIDE, 1, "### t")], id="ticket-above-every-category"),
        pytest.param(
            "## C\n\n# Next\n\n### t\n", [(BreachKind.TICKET_OUTSIDE, 5, "### t")], id="level-1-ends-a-category"
        ),
        pytest.param(
            "## C\n\n### t\n\n#### Detail\n\n- **x** y\n", [], id="level-4-heading-and-old-form-item-in-a-ticket"
        ),
        pytest.param("```\n### t\n- **x** y\n```\n\n## C\n", [], id="fenced-heading-and-item-free"),
        pytest.param("## C\n\n-**x**\n  - **x**\n- x **y**\n", [], id="not-an-old-form-item"),
        pytest.param(
            "## C\n\n### [](x.md)\n\n###   \n",
            [(BreachKind.TICKET_EMPTY, 3, "### [](x.md)"), (BreachKind.TICKET_EMPTY, 5, "###   ")],
            id="ticket-title-empty-once-links-reduced",
        ),
    ],
)
def test_layout_breaches(tmp_path, text, breaches):
    layout = _layout(tmp_path, text)
    assert _breaches(layout, tmp_path) == [(kind, "doc.md", line, found) for kind, line, found in breaches]


def test_layout_parts(tmp_path):
    text = (
        "# R\n\nIntro.\n\n## Features\n\nAbout.\n\n### [Link](x.md) helper\n\nText.\n\n#### Detail\n\nMore.\n\n\n"
        "## Testing\n"
    )
    assert _parts(_layout(tmp_path, text), tmp_path) == [
        ("category", "Features", "Features", "doc.md", 4, 6),
        ("ticket", "[Link](x.md) helper", "Link helper", "doc.md", 8, 14),
        ("category", "Testing", "Testing", "doc.md", 17, 17),
    ]


@pytest.mark.parametrize("name", ["index.md", "entry-point.md"])
def test_a_roadmap_named_as_a_head_file_is_read_whole(tmp_path, name):
    _write(tmp_path, {name: "# R\n\nContents:\n\n## C\n\n### t\n"})
    roadmap = read_roadmap(str(tmp_path / name))
    assert roadmap.breaches == []
    assert [(p.kind, p.title) for p in roadmap.parts] == [("category", "C"), ("ticket", "t")]


def test_a_category_holds_the_tickets_of_the_files_after_it(tmp_path):
    _write(tmp_path, {"a.md": "## C\n", "b.md": "### t\n"})
    layout = read_layout([read_file(str(tmp_path / name)) for name in ("a.md", "b.md")])
    assert layout.breaches == []
    assert [(p.kind, p.title) for p in layout.parts] == [("category", "C"), ("ticket", "t")]


@pytest.mark.parametrize(
    "first, following, runs_on",
    [
        pytest.param("## C\n\n### t\n\nkeep\n", "#### Detail\n\nmore\n", True, id="next-file-opens-with-deeper-text"),
        pytest.param("## C\n\n### t\n\nkeep\n", "### u\n\nmore\n", False, id="next-file-opens-with-a-ticket"),
        pytest.param("## C\n\n### t\n\nkeep\n", "\n\n", False, id="next-file-all-blank"),
        pytest.param("## C\n\n### t\n\nkeep\n\n## D\n", "more\n", False, id="followed-in-its-file-by-a-category"),
        pytest.param("## C\n\n### t\n\nkeep\n", None, False, id="roadmap"),
    ],
)
def test_a_ticket_runs_on_past_its_file(tmp_path, first, following, runs_on):
    _write(tmp_path, {"a.md": first, **({"b.md": following} if following is not None else {})})
    if following is None:
        layout = read_roadmap(str(tmp_path / "a.md"))
    else:
        layout = read_layout([read_file(str(tmp_path / name)) for name in ("a.md", "b.md")])
    assert [p.runs_on for p in layout.parts if p.title == "t"] == [runs_on]


@pytest.mark.parametrize(
    "text, breaches",
    [
        pytest.param("# R\n\n## C\n", [], id="a-category"),
        pytest.param(
            "Intro.\n\n# R\n\n### t\n",
            [(BreachKind.NO_CATEGORY, 3, "# R"), (BreachKind.TICKET_OUTSIDE, 5, "### t")],
            id="no-category-at-the-first-level-1-heading",
        ),
        pytest.param("Intro.\n", [(BreachKind.NO_CATEGORY, 1, "Intro.")], id="no-category-no-h1"),
        pytest.param("", [(BreachKind.NO_CATEGORY, 1, "")], id="empty"),
        pytest.param("```\n## C\n```\n", [(BreachKind.NO_CATEGORY, 1, "```")], id="fenced-category-is-none"),
    ],
)
def test_roadmap_breaches(tmp_path, text, breaches):
    _write(tmp_path, {"roadmap.md": text})
    roadmap = read_roadmap(str(tmp_path / "roadmap.md"))
    assert _breaches(roadmap, tmp_path) == [(kind, "roadmap.md", line, found) for kind, line, found in breaches]


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
    "files, work",
    [
        pytest.param(
            ["README.md", "b.md", "a.md", "notes.txt", "diced/entry-point.md", "diced/leaf.md", "loose/leaf.md"],
            [("a", ["a.md"]), ("b", ["b.md"]), ("diced", ["diced/entry-point.md"])],
            id="readme-excluded-diced-counted-once-no-topic-each-alone",
        ),
        pytest.param(["T_DESIGN.md"], [("T", ["T_DESIGN.md"])], id="design-makes-a-topic"),
        pytest.param(["T_PLAN.md"], [("T", ["T_PLAN.md"])], id="plan-makes-a-topic"),
        pytest.param(["T_PLAN_REVIEW.md"], [("T", ["T_PLAN_REVIEW.md"])], id="plan-review-makes-a-topic"),
        pytest.param(["T_DESIGN.md", "T.md"], [("T", ["T.md", "T_DESIGN.md"])], id="name-equal-to-topic-joins"),
        pytest.param(
            ["T_notes.md", "T_PLAN.md", "T_PLAN_REVIEW.md"],
            [("T", ["T_PLAN.md", "T_PLAN_REVIEW.md", "T_notes.md"])],
            id="name-opening-with-topic-joins-in-path-order",
        ),
        pytest.param(
            ["A_DESIGN.md", "A_B_DESIGN.md", "A_B_X.md"],
            [("A", ["A_DESIGN.md"]), ("A_B", ["A_B_DESIGN.md", "A_B_X.md"])],
            id="longest-topic-wins",
        ),
        pytest.param(
            ["T_DESIGN.md", "T_PLAN/entry-point.md"],
            [("T", ["T_DESIGN.md", "T_PLAN/entry-point.md"])],
            id="tree-joins-by-directory-name",
        ),
        pytest.param(["T_DESIGN.md", "Tx.md"], [("T", ["T_DESIGN.md"]), ("Tx", ["Tx.md"])], id="no-topic-alone"),
    ],
)
def test_parked_work(tmp_path, files, work):
    parked = tmp_path / PARKED_DESIGNS
    _write(parked, {name: "# x\n" for name in files})
    assert [
        (w.name, [Path(f).relative_to(parked).as_posix() for f in w.files]) for w in parked_work(str(tmp_path))
    ] == work


def test_no_parked_directory_no_parked_work(tmp_path):
    _write(tmp_path, {"ROADMAP.md": "# x\n"})
    assert parked_work(str(tmp_path)) == []


def test_heading_anchors(tmp_path):
    _write(tmp_path, {"a.md": "# T\n\n## A\n\n```\n## A\n```\n\n   ## A\n\n## A\n"})
    headings = planform.file_headings(read_file(str(tmp_path / "a.md")))
    # the fenced heading is not counted; the indented one is no board heading but counts toward repeats
    assert [(h.line, h.anchor) for h in headings] == [(1, "t"), (3, "a"), (11, "a-2")]


def test_package_heading(tmp_path):
    plan = _read(tmp_path, "# Plan\n\n## Status\n\n" + _TABLE + "| P1 | |\n| P2 | |\n\n### P1 — First\n")
    first, untitled = plan.packages
    assert (first.heading.line, first.heading.level, first.heading.anchor) == (10, 3, "p1--first")
    assert untitled.heading is None
