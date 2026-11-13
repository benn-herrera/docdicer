"""Unit tests for the kanban board model: the columns, cards, separators and notices a project's files
give, the moves of a ticket between ROADMAP.md and the active design and their guards."""

import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import pytest

from docdicer.dicerlib.linkcheck import prose_links
from docdicer.dicerlib.textfile import split_lines
from docdicer.kanban import board as board_module
from docdicer.kanban.board import (
    INSTRUCTION,
    PLAN_COLUMNS,
    DesignCard,
    MoveRefused,
    MoveWriteFailed,
    ParkedCard,
    RoadmapCard,
    move_to_design,
    move_to_roadmap,
    read_board,
)
from docdicer.kanban.planform import DRAFTED

_PLAN = (
    "# Plan\n\nRelease: 9.9.9\n\n## Status\n\n| Package | Lifetime | Rating | State |\n|---|---|---|---|\n"
    "| P1 | shipped | expert | |\n| P2 | scratch | mechanical | dispatchable |\n"
    "| P3 | shipped | expert | in progress: a note |\n| P4 | shipped | expert | landed |\n"
    "| P5 | shipped | expert | done |\n|  | shipped | expert | landed |\n"
)
# The ticket to move is the last of its category, so dropping it back on that category restores it.
_ROADMAP = (
    "# Roadmap\n\n## Next\n\n### Alpha\n\nFirst.\n\n### Search index\n\nBuild an index from\n"
    "[x](ROADMAP_DESIGNS/x.md#goals).\n\n## Later\n\n### Other\n"
)
_BODY = "### Search index\n\nBuild an index from\n[x](ROADMAP_DESIGNS/x.md#goals).\n"  # the ticket's lines
_MONOLITH = {"ACTIVE_DESIGN.md": "# Design\n\n## Goals\n\n### Fast\n\nkeep\n\n## Drafts\n"}
_DICED = {
    "ACTIVE_DESIGN/entry-point.md": "# Design\n\nContents:\n\n- [Goals](goals.md)\n",
    "ACTIVE_DESIGN/goals.md": "## Goals\n\n### Fast\n\nkeep\n",
}


def _project(root: Path, files: dict[str, str]) -> str:
    (root / ".git").mkdir()
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return str(root)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tree(root: Path) -> dict[str, str]:
    """Every file under root but `.git`, relative path to text."""
    return {
        str(p.relative_to(root)): _read(p) for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.parts
    }


def _card(root: str, title: str) -> dict:
    """The card or separator titled title, as the server serves it."""
    board = read_board(root)
    return asdict(next(c for c in [*board.roadmap, *board.parked, *board.design] if c.title == title))


def _to_design(root: str, title: str) -> list[str]:
    return move_to_design(root, _card(root, title), read=read_board(root).sha256)


def _to_roadmap(root: str, title: str, target: Optional[str] = None) -> list[str]:
    """Move the design card titled title, target naming the roadmap separator the page sends."""
    board = read_board(root)
    card = asdict(next(c for c in board.design if c.title == title))
    dropped_on = _card(root, target) if target else None
    return move_to_roadmap(root, card, target=dropped_on, read=board.sha256)


@pytest.mark.parametrize(
    "plan, packages",
    [
        pytest.param(
            _PLAN,
            [("P1", DRAFTED, "shipped", "expert"), ("P2", "dispatchable", "scratch", "mechanical")]
            + [("P3", "in progress", "shipped", "expert"), ("P4", "landed", "shipped", "expert")]
            + [("P5", DRAFTED, "shipped", "expert")],
            id="each-state-in-its-column-with-lifetime-and-rating",
        ),
        pytest.param(
            "# Plan\n\n## Status\n\n| Package | State |\n|---|---|\n| P1 | landed |\n",
            [("P1", "landed", None, None)],
            id="no-lifetime-or-rating-column",
        ),
    ],
)
def test_plan_columns(tmp_path, plan, packages):
    board = read_board(_project(tmp_path, {"ACTIVE_PLAN.md": plan}))
    assert [(p.id, p.state, p.lifetime, p.rating) for p in board.packages] == packages
    assert all(p.state in PLAN_COLUMNS for p in board.packages)


@pytest.mark.parametrize(
    "files, release, hardening",
    [
        pytest.param({"ACTIVE_PLAN.md": "# Plan\n\nRelease: 1.2.3\n"}, "1.2.3", False, id="release"),
        pytest.param(
            {"ACTIVE_PLAN.md": "# Release hardening for 1.2\n\nRelease: 1.2.0\n"}, "1.2.0", True, id="hardening"
        ),
        pytest.param(
            {"ACTIVE_PLAN/entry-point.md": "# Release hardening\n\nRelease:  2.0 \n"}, "2.0", True, id="diced-plan"
        ),
        pytest.param({}, None, False, id="no-active-plan"),
    ],
)
def test_header(tmp_path, files, release, hardening):
    board = read_board(_project(tmp_path, files))
    assert (board.release, board.hardening) == (release, hardening)


@pytest.mark.parametrize(
    "files, cards",
    [
        pytest.param(
            {"ACTIVE_DESIGN.md": "# Cache design\n\nIntro.\n\n## Goals\n\nFast.\n\n### Detail\n\nMore.\n\n## Risks\n"},
            [("category", "Goals", "", "ACTIVE_DESIGN.md"), ("ticket", "Detail", "More.", "ACTIVE_DESIGN.md")]
            + [("category", "Risks", "", "ACTIVE_DESIGN.md")],
            id="monolith",
        ),
        pytest.param(
            {
                "ACTIVE_DESIGN/entry-point.md": "# Cache design\n\n## Overview\n\n### All\n\nAll.\n\nContents:\n\n"
                "- [Goals](goals.md)\n",
                "ACTIVE_DESIGN/goals.md": "## Goals\n\n### Fast\n\nFast.\n",
                "ACTIVE_DESIGN/risks.md": "## Risks\n",
            },
            [("category", "Overview", "", "ACTIVE_DESIGN/entry-point.md")]
            + [("ticket", "All", "All.", "ACTIVE_DESIGN/entry-point.md")]
            + [
                ("category", "Goals", "", "ACTIVE_DESIGN/goals.md"),
                ("ticket", "Fast", "Fast.", "ACTIVE_DESIGN/goals.md"),
            ]
            + [("category", "Risks", "", "ACTIVE_DESIGN/risks.md")],
            id="diced-across-leaves-contents-block-excluded",
        ),
        pytest.param(
            {
                "ACTIVE_DESIGN.md": "```\n# not the title\n## not a category\n### not a ticket\n```\n\n# Title\n\n## Kept\n"
            },
            [("category", "Kept", "", "ACTIVE_DESIGN.md")],
            id="fenced-headings-skipped",
        ),
        pytest.param({}, [], id="no-design"),
    ],
)
def test_design_cards(tmp_path, files, cards):
    board = read_board(_project(tmp_path, files))
    assert [(c.kind, c.title, c.text, c.path) for c in board.design] == cards
    assert all(c.parked is None for c in board.design)


_DELTA_MONOLITH = {
    "ACTIVE_DESIGN.md": "# D\n\n## Intro\n\n### Why\n\nBecause.\n\n## SPEC delta\n\nstray\n\n"
    "### [§11.2](SPEC.md#x)\n\nNew row.\n\n## Code delta\n\n### board.py\n\nKind.\n"
}
# The leaves' names sort against document order: the Contents block puts SPEC delta first.
_DELTA_DICED = {
    "ACTIVE_DESIGN/entry-point.md": "# D\n\n## Intro\n\n### Why\n\nBecause.\n\nContents:\n\n"
    "- [SPEC delta](spec-delta.md)\n- [Code delta](code-delta.md)\n",
    "ACTIVE_DESIGN/spec-delta.md": "## SPEC delta\n\nstray\n\n### [§11.2](../SPEC.md#x)\n\nNew row.\n",
    "ACTIVE_DESIGN/code-delta.md": "## Code delta\n\n### board.py\n\nKind.\n",
}


@pytest.mark.parametrize(
    "files, paths",
    [
        pytest.param(_DELTA_MONOLITH, ["ACTIVE_DESIGN.md"] * 6, id="monolith"),
        pytest.param(
            _DELTA_DICED,
            ["ACTIVE_DESIGN/entry-point.md"] * 2
            + ["ACTIVE_DESIGN/spec-delta.md"] * 2
            + ["ACTIVE_DESIGN/code-delta.md"] * 2,
            id="diced-in-document-order",
        ),
    ],
)
def test_deltas_are_separators_over_entry_cards(tmp_path, files, paths):
    board = read_board(_project(tmp_path, files))
    assert [(c.kind, c.title, c.text) for c in board.design] == [
        ("category", "Intro", ""),
        ("ticket", "Why", "Because."),
        ("delta", "SPEC delta", ""),
        ("entry", "§11.2", "New row."),
        ("delta", "Code delta", ""),
        ("entry", "board.py", "Kind."),
    ]
    assert [c.path for c in board.design] == paths


@pytest.mark.parametrize("kind", ["entry", "delta", "category"])
def test_an_entry_card_or_separator_is_refused_on_roadmap(tmp_path, kind):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **_DELTA_MONOLITH})
    before = _tree(tmp_path)
    board = read_board(root)
    card = next(c for c in board.design if c.kind == kind)
    with pytest.raises(MoveRefused):
        move_to_roadmap(root, asdict(card), target=None, read=board.sha256)
    assert _tree(tmp_path) == before


def test_a_roadmap_separator_is_refused_on_design(tmp_path):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **_MONOLITH})
    before = _tree(tmp_path)
    with pytest.raises(MoveRefused):
        _to_design(root, "Next")
    assert _tree(tmp_path) == before


def test_a_ticket_moves_both_ways_in_a_design_with_deltas(tmp_path):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, "ROADMAP_DESIGNS/x.md": "# X\n", **_DELTA_MONOLITH})
    before = _tree(tmp_path)

    _to_design(root, "Search index")
    assert [c.kind for c in read_board(root).design if c.title == "Search index"] == ["ticket"]
    _to_roadmap(root, "Search index", target="Next")

    # the `## Drafts` the move added stays: a removed ticket's category heading stays
    assert _tree(tmp_path) == {**before, "ACTIVE_DESIGN.md": before["ACTIVE_DESIGN.md"] + "\n## Drafts\n"}


def test_design_read_for_its_headings_only(tmp_path):
    design = "# Design\n\nRelease: 1.0\n\n## Status\n\n| Package | State |\n|---|---|\n| X1 | landed |\n"
    board = read_board(_project(tmp_path, {"ACTIVE_DESIGN.md": design}))
    assert [c.title for c in board.design] == ["Status"]
    assert (board.release, board.packages) == (None, [])


@pytest.mark.parametrize(
    "roadmap, cards",
    [
        pytest.param(
            "# Roadmap\n\nIntro.\n\n## Next\n\nAbout next.\n\n### Search index\n\nBuild an index.\n\n### Cache\n\n"
            "Keep answers\nacross runs.\n\n## Later\n\n### Third\n",
            [("category", "Next", ""), ("ticket", "Search index", "Build an index.")]
            + [("ticket", "Cache", "Keep answers\nacross runs."), ("category", "Later", ""), ("ticket", "Third", "")],
            id="categories-as-separators-over-tickets",
        ),
        pytest.param(
            "## Next\n\n### See [x](y.md)\n\nz\n",
            [("category", "Next", ""), ("ticket", "See x", "z")],
            id="link-in-title",
        ),
        pytest.param(
            "## Next\n\n### T\n\n\nA.\n\n#### Sub\n\nB.\n\n\n## Later\n",
            [("category", "Next", ""), ("ticket", "T", "A.\n\n#### Sub\n\nB."), ("category", "Later", "")],
            id="text-without-heading-or-outer-blank-lines-deeper-heading-kept",
        ),
        pytest.param(
            "## Next\n\n```\n### not a ticket\n## not a category\n```\n\n### Real\n",
            [("category", "Next", ""), ("ticket", "Real", "")],
            id="fenced-ignored",
        ),
        pytest.param("##\tSoon\n\n### Item\n", [], id="tab-after-hashes-is-no-heading"),
    ],
)
def test_roadmap_cards(tmp_path, roadmap, cards):
    board = read_board(_project(tmp_path, {"ROADMAP.md": roadmap}))
    assert [(c.kind, c.title, c.text) for c in board.roadmap] == cards


def test_parked_cards(tmp_path):
    roadmap = (
        "See [above](ROADMAP_DESIGNS/above.md).\n\n## Next\n\nSee [loose](ROADMAP_DESIGNS/loose.md).\n\n"
        "### Linked\n\nsee [plan](ROADMAP_DESIGNS/linked.md) and\n[tree](ROADMAP_DESIGNS/tree/entry-point.md#goals)\n"
        "and [search](ROADMAP_DESIGNS/SEARCH_PLAN.md).\n"
    )
    files = {
        "ROADMAP.md": roadmap,
        "ROADMAP_DESIGNS/README.md": "# Parked plans\n",
        "ROADMAP_DESIGNS/above.md": "# Above\n",
        "ROADMAP_DESIGNS/linked.md": "# Linked\n",
        "ROADMAP_DESIGNS/tree/entry-point.md": "# Tree\n",
        "ROADMAP_DESIGNS/SEARCH_DESIGN.md": "# Search\n",
        "ROADMAP_DESIGNS/SEARCH_PLAN.md": "# Search plan\n",
        "ROADMAP_DESIGNS/CACHE_PLAN/entry-point.md": "# Cache plan\n",
        "ROADMAP_DESIGNS/CACHE_DESIGN.md": "# Cache\n",
        "ROADMAP_DESIGNS/unlinked.md": "# Unlinked\n\nSee [appendix](appendix.md).\n",
        "ROADMAP_DESIGNS/appendix.md": "# Appendix\n",
        "ROADMAP_DESIGNS/loose.md": "# Loose\n",
    }
    board = read_board(_project(tmp_path, files))
    # a link to one file of a grouped piece names all its files
    assert [c.parked for c in board.roadmap if c.kind == "ticket"] == [
        ["ROADMAP_DESIGNS/linked.md", "ROADMAP_DESIGNS/tree/entry-point.md"]
        + ["ROADMAP_DESIGNS/SEARCH_DESIGN.md", "ROADMAP_DESIGNS/SEARCH_PLAN.md"]
    ]
    assert board.parked == [
        _parked("CACHE", ["ROADMAP_DESIGNS/CACHE_DESIGN.md", "ROADMAP_DESIGNS/CACHE_PLAN/entry-point.md"]),
        _parked("above", ["ROADMAP_DESIGNS/above.md"]),
        _parked("appendix", ["ROADMAP_DESIGNS/appendix.md"]),
        _parked("loose", ["ROADMAP_DESIGNS/loose.md"]),
        _parked("unlinked", ["ROADMAP_DESIGNS/unlinked.md"]),
    ]


def _parked(title, paths):
    """The parked card of title over paths, each an ASCII path with no character a URL quotes."""
    return ParkedCard(title, paths, ["/" + p for p in paths])


def test_parked_file_urls_are_percent_quoted(tmp_path):
    board = read_board(_project(tmp_path, {"ROADMAP_DESIGNS/a b é.md": "# A\n"}))
    assert [c.hrefs for c in board.parked] == [["/ROADMAP_DESIGNS/a%20b%20%C3%A9.md"]]


@pytest.mark.parametrize(
    "files, hrefs",
    [
        pytest.param(
            {"ROADMAP.md": "## Next\n\n### Search index\n"},
            [None, "/ROADMAP.md#search-index"],
            id="roadmap-ticket",
        ),
        pytest.param(
            {"ROADMAP.md": "## A\n\n### Same\n\n## B\n\n### Same\n"},
            [None, "/ROADMAP.md#same", None, "/ROADMAP.md#same-1"],
            id="repeated-heading-suffixed",
        ),
        pytest.param(_DICED, [None, "/ACTIVE_DESIGN/goals.md#fast"], id="design-ticket-in-a-diced-leaf"),
        pytest.param(
            {"ACTIVE_DESIGN/entry-point.md": "# D\n", "ACTIVE_DESIGN/a b%.md": "## Goals\n\n### Fast path\n"},
            [None, "/ACTIVE_DESIGN/a%20b%25.md#fast-path"],
            id="leaf-name-quoted",
        ),
        pytest.param(
            _DELTA_MONOLITH,
            [None, "/ACTIVE_DESIGN.md#why", None, "/ACTIVE_DESIGN.md#112", None, "/ACTIVE_DESIGN.md#boardpy"],
            id="separators-none-entries-linked",
        ),
    ],
)
def test_card_hrefs(tmp_path, files, hrefs):
    board = read_board(_project(tmp_path, files))
    assert [c.href for c in [*board.roadmap, *board.design]] == hrefs


@pytest.mark.parametrize(
    "files, hrefs",
    [
        pytest.param(
            {
                "ACTIVE_PLAN.md": "# Plan\n\n## Status\n\n| Package | State |\n|---|---|\n| P1 | |\n| P2 | |\n\n## P1: First\n"
            },
            ["/ACTIVE_PLAN.md#p1-first", "/ACTIVE_PLAN.md"],
            id="monolith-titled-and-untitled",
        ),
        pytest.param(
            {
                "ACTIVE_PLAN/entry-point.md": "# Plan\n\n## Status\n\n| Package | State |\n|---|---|\n| P1 | |\n",
                "ACTIVE_PLAN/p1.md": "## P1: First\n",
            },
            ["/ACTIVE_PLAN/p1.md#p1-first"],
            id="heading-in-a-leaf",
        ),
    ],
)
def test_package_hrefs(tmp_path, files, hrefs):
    board = read_board(_project(tmp_path, files))
    assert [p.href for p in board.packages] == hrefs


def test_served_files(tmp_path):
    root = _project(
        tmp_path,
        {
            "ROADMAP.md": "## Next\n",
            "README.md": "# Readme\n",
            "SPEC.md": "# Spec\n",
            "ACTIVE_DESIGN.md": "# Design\n",
            "ACTIVE_DESIGN/entry-point.md": "# Not read: the monolith is\n",
            "ACTIVE_PLAN/entry-point.md": "# Plan\n",
            "ACTIVE_PLAN/p1.md": "## P1\n",
            "ROADMAP_DESIGNS/README.md": "# Parked\n",
            "ROADMAP_DESIGNS/X_DESIGN.md": "# X\n",
            "ROADMAP_DESIGNS/tree/entry-point.md": "# Tree\n",
            "ROADMAP_DESIGNS/tree/leaf.md": "## Leaf\n",
        },
    )
    assert board_module.served_files(root) == [
        "ACTIVE_DESIGN.md",
        "ACTIVE_PLAN/entry-point.md",
        "ACTIVE_PLAN/p1.md",
        "ROADMAP.md",
        "ROADMAP_DESIGNS/X_DESIGN.md",
        "ROADMAP_DESIGNS/tree/entry-point.md",
    ]


def test_served_files_lists_an_unreadable_design_leaf(tmp_path):
    root = _project(tmp_path, {**_DICED, "ACTIVE_DESIGN/later.md": "## Later\n"})
    leaf = tmp_path / "ACTIVE_DESIGN/later.md"
    leaf.chmod(0)
    try:
        try:
            leaf.read_text(encoding="utf-8")
            pytest.skip("chmod denies this user no read")
        except PermissionError:
            pass
        assert board_module.served_files(root) == [
            "ACTIVE_DESIGN/entry-point.md",
            "ACTIVE_DESIGN/goals.md",
            "ACTIVE_DESIGN/later.md",
        ]
    finally:
        leaf.chmod(0o644)


def test_an_href_quotes_a_byte_of_a_name_that_is_not_utf_8_as_that_byte(tmp_path):
    root = str(tmp_path)
    assert board_module._href(root, os.path.join(root, "a\udcff.md"), "") == "/a%FF.md"


@pytest.mark.parametrize(
    "files, notices",
    [
        pytest.param(
            {
                "ROADMAP.md": "# Roadmap\n\n### Outside\n\n## Next\n\n- **Old** item\n\n### \n",
                "ACTIVE_DESIGN/entry-point.md": "# D\n\nContents:\n\n- [Leaf](leaf.md)\n",
                "ACTIVE_DESIGN/leaf.md": "### Stray\n\n## Goals\n\n### Fast\n",
            },
            [("roadmap", "ROADMAP.md", 3, "### Outside"), ("roadmap", "ROADMAP.md", 7, "- **Old** item")]
            + [("roadmap", "ROADMAP.md", 9, "### "), ("design", "ACTIVE_DESIGN/leaf.md", 1, "### Stray")],
            id="layout-breaches-in-each-column-design-form-breaches-not-shown",
        ),
        pytest.param(
            {"ROADMAP.md": "# Roadmap\n\nText.\n"}, [("roadmap", "ROADMAP.md", 1, "# Roadmap")], id="no-category"
        ),
        pytest.param({"ROADMAP.md": _ROADMAP, **_MONOLITH}, [], id="none"),
    ],
)
def test_notices(tmp_path, files, notices):
    board = read_board(_project(tmp_path, files))
    assert [(n.column, n.path, n.line, n.found) for n in board.notices] == notices
    assert all(n.accepted for n in board.notices)


def test_board_digests_every_file_a_move_may_write(tmp_path):
    board = read_board(_project(tmp_path, {**_DICED, "ROADMAP_DESIGNS/later.md": "# Later\n"}))
    assert sorted(board.sha256) == ["ACTIVE_DESIGN/entry-point.md", "ACTIVE_DESIGN/goals.md", "ROADMAP.md"]
    assert board.sha256["ROADMAP.md"] is None


@pytest.mark.parametrize(
    "design, expected",
    [
        pytest.param(_MONOLITH, _MONOLITH["ACTIVE_DESIGN.md"] + "\n" + _BODY, id="monolith"),
        pytest.param({}, "# ACTIVE DESIGN\n\n## Drafts\n\n" + _BODY, id="created"),
    ],
)
def test_roadmap_card_moves_to_design(tmp_path, design, expected):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, "ROADMAP_DESIGNS/x.md": "# X\n", **design})
    assert _to_design(root, "Search index") == ["ACTIVE_DESIGN.md", "ROADMAP.md"]

    assert _read(tmp_path / "ACTIVE_DESIGN.md") == expected
    assert _read(tmp_path / "ROADMAP.md") == "# Roadmap\n\n## Next\n\n### Alpha\n\nFirst.\n\n## Later\n\n### Other\n"
    board = read_board(root)
    [card] = [c for c in board.design if c.title == "Search index"]
    assert (card.kind, card.path, card.parked) == ("ticket", "ACTIVE_DESIGN.md", None)


_TICKET = "### Search index\n\nBuild.\n"


@pytest.mark.parametrize(
    "design, expected",
    [
        pytest.param(
            "# D\n\n## Goals\n\n### Fast\n\nkeep\n",
            "# D\n\n## Goals\n\n### Fast\n\nkeep\n\n## Drafts\n\n" + _TICKET,
            id="no-drafts",
        ),
        pytest.param("# D\n\n", "# D\n\n## Drafts\n\n" + _TICKET, id="no-drafts-last-line-blank"),
        pytest.param("", "## Drafts\n\n" + _TICKET, id="no-drafts-empty-file"),
        pytest.param(
            "## Drafts\n### A\na\n## Goals\n",
            "## Drafts\n### A\na\n\n" + _TICKET + "\n## Goals\n",
            id="heading-follows",
        ),
        pytest.param(
            "## Drafts\n\nTo do.\n\n## Drafts\n",
            "## Drafts\n\nTo do.\n\n" + _TICKET + "\n## Drafts\n",
            id="first-drafts",
        ),
    ],
)
def test_a_ticket_moved_to_design_is_added_at_the_end_of_drafts(tmp_path, design, expected):
    root = _project(tmp_path, {"ROADMAP.md": "## Next\n\n" + _TICKET, "ACTIVE_DESIGN.md": design})
    _to_design(root, "Search index")
    assert _read(tmp_path / "ACTIVE_DESIGN.md") == expected
    assert _read(tmp_path / "ROADMAP.md") == "## Next\n"


_GONE_CARD = {"title": "Gone", "text": "", "parked": [], "kind": "category"}
_PLACEMENT_ROADMAP = "## Next\n\n### One\n\nA.\n\n## Later\n\n### Other\n"


@pytest.mark.parametrize(
    "target, expected",
    [
        pytest.param("Next", "## Next\n\n### One\n\nA.\n\n### Note\n\nText.\n\n## Later\n\n### Other\n", id="next"),
        pytest.param("Later", "## Next\n\n### One\n\nA.\n\n## Later\n\n### Other\n\n### Note\n\nText.\n", id="later"),
        pytest.param(None, "## Next\n\n### One\n\nA.\n\n### Note\n\nText.\n\n## Later\n\n### Other\n", id="none-first"),
        pytest.param(
            _GONE_CARD, "## Next\n\n### One\n\nA.\n\n### Note\n\nText.\n\n## Later\n\n### Other\n", id="stale-first"
        ),
        pytest.param(
            "Other",
            "## Next\n\n### One\n\nA.\n\n### Note\n\nText.\n\n## Later\n\n### Other\n",
            id="not-a-separator-first",
        ),
    ],
)
def test_a_ticket_moved_to_roadmap_ends_the_category_dropped_under(tmp_path, target, expected):
    files = {"ROADMAP.md": _PLACEMENT_ROADMAP, "ACTIVE_DESIGN.md": "# Design\n\n## Drafts\n\n### Note\n\nText.\n"}
    root = _project(tmp_path, files)
    board = read_board(root)
    dropped_on = _card(root, target) if isinstance(target, str) else target
    card = next(c for c in board.design if c.title == "Note")
    move_to_roadmap(root, asdict(card), target=dropped_on, read=board.sha256)
    assert _read(tmp_path / "ROADMAP.md") == expected


@pytest.mark.parametrize(
    "roadmap, target, expected",
    [
        pytest.param(
            "## Next\n### One\nA.\n## Later\n",
            "Next",
            "## Next\n### One\nA.\n\n### Note\n\nText.\n\n## Later\n",
            id="heading-follows",
        ),
        pytest.param(
            "## Next\n\nAbout.\n\n## Later\n",
            "Next",
            "## Next\n\nAbout.\n\n### Note\n\nText.\n\n## Later\n",
            id="no-ticket-yet",
        ),
        pytest.param("## Next\n", "Next", "## Next\n\n### Note\n\nText.\n", id="heading-only"),
        pytest.param(
            "# Roadmap\n\nIntro.\n", None, "# Roadmap\n\nIntro.\n\n## General\n\n### Note\n\nText.\n", id="no-category"
        ),
        pytest.param(
            "# Roadmap\n\n", None, "# Roadmap\n\n## General\n\n### Note\n\nText.\n", id="no-category-last-line-blank"
        ),
        pytest.param("", None, "## General\n\n### Note\n\nText.\n", id="empty"),
    ],
)
def test_a_ticket_added_at_the_end_of_a_category(tmp_path, roadmap, target, expected):
    root = _project(tmp_path, {"ROADMAP.md": roadmap, "ACTIVE_DESIGN.md": "# D\n\n## Drafts\n\n### Note\n\nText.\n"})
    _to_roadmap(root, "Note", target=target)
    assert _read(tmp_path / "ROADMAP.md") == expected


@pytest.mark.parametrize(
    "design, expected",
    [
        pytest.param("# D\n\n## Drafts\n\n### Note\n\nText.\n\n\n", "# D\n\n## Drafts\n\n\n", id="last-ticket"),
        pytest.param(
            "# D\n\n## Drafts\n\n### A\n\na\n\n\n### Note\n\nText.\n\n### B\n\nb\n",
            "# D\n\n## Drafts\n\n### A\n\na\n\n### B\n\nb\n",
            id="between-tickets",
        ),
    ],
)
def test_a_removed_ticket_takes_the_blank_lines_above_it(tmp_path, design, expected):
    root = _project(tmp_path, {"ROADMAP.md": "## Next\n", "ACTIVE_DESIGN.md": design})
    _to_roadmap(root, "Note")
    assert _read(tmp_path / "ACTIVE_DESIGN.md") == expected


def test_a_ticket_moved_to_roadmap_creates_it(tmp_path):
    root = _project(tmp_path, {"ACTIVE_DESIGN.md": "# D\n\n## Drafts\n\n### Note\n\nText.\n"})
    assert _to_roadmap(root, "Note") == ["ROADMAP.md", "ACTIVE_DESIGN.md"]
    assert _read(tmp_path / "ROADMAP.md") == "# ROADMAP\n\n## General\n\n### Note\n\nText.\n"
    assert _read(tmp_path / "ACTIVE_DESIGN.md") == "# D\n\n## Drafts\n"


def test_a_drop_under_the_second_of_two_alike_categories_ends_it(tmp_path):
    roadmap = "## A\n\n### One\n\n## B\n\n### Two\n\n## A\n\n### Three\n"
    root = _project(tmp_path, {"ROADMAP.md": roadmap, "ACTIVE_DESIGN.md": "# D\n\n## Drafts\n\n### Note\n\nText.\n"})
    board = read_board(root)
    second_a = [c for c in board.roadmap if c.title == "A"][1]
    card = next(c for c in board.design if c.title == "Note")
    move_to_roadmap(root, asdict(card), target=asdict(second_a), read=board.sha256)
    assert _read(tmp_path / "ROADMAP.md") == roadmap + "\n### Note\n\nText.\n"


def test_the_second_of_two_alike_tickets_moves_alone(tmp_path):
    root = _project(tmp_path, {"ROADMAP.md": "## A\n\n### Same\n\nText.\n\n## B\n\n### Same\n\nText.\n", **_MONOLITH})
    board = read_board(root)
    second = [c for c in board.roadmap if c.title == "Same"][1]
    move_to_design(root, asdict(second), read=board.sha256)
    assert _read(tmp_path / "ROADMAP.md") == "## A\n\n### Same\n\nText.\n\n## B\n"


_DEEP_TICKET = "### Deep\n\nIntro.\n\n#### Detail\n\nBelow.\n"
_FENCED_TICKET = "### Fenced\n\n```\n## not a category\n### not a ticket\n```\n"


@pytest.mark.parametrize(
    "title, ticket, category",
    [
        pytest.param("Deep", _DEEP_TICKET, "A", id="deeper-heading"),
        pytest.param("Fenced", _FENCED_TICKET, "B", id="fenced-code"),
    ],
)
def test_a_ticket_with_a_deeper_heading_or_fenced_code_moves_whole(tmp_path, title, ticket, category):
    roadmap = f"## A\n\n{_DEEP_TICKET}\n## B\n\n{_FENCED_TICKET}"
    root = _project(tmp_path, {"ROADMAP.md": roadmap, **_MONOLITH})

    _to_design(root, title)
    assert _read(tmp_path / "ACTIVE_DESIGN.md").endswith("\n" + ticket)
    _to_roadmap(root, title, target=category)
    assert _read(tmp_path / "ROADMAP.md") == roadmap


def _in_design(files: dict[str, str]) -> dict[str, str]:
    """files, each path made relative to the project root from the diced design's directory."""
    return {f"ACTIVE_DESIGN/{name}": text for name, text in files.items()}


_ROADMAP_AFTER = "# Roadmap\n\n## Next\n\n### Alpha\n\nFirst.\n\n## Later\n\n### Other\n"  # _ROADMAP without _BODY
_LEAF = "### Search index\n\nBuild an index from\n[x](../../ROADMAP_DESIGNS/x.md#goals).\n"  # _BODY in drafts/
_FULL_LISTING = (
    "# D\n\nContents:\n\n- [Goals](goals/index.md)\n  - [Fast](goals/fast.md)\n- [Drafts](drafts/index.md)\n"
    "  - [Old](drafts/old.md)\n- [Notes](notes.md)\n"
)


@pytest.mark.parametrize(
    "design, changed, written",
    [
        pytest.param(
            {
                "entry-point.md": _FULL_LISTING,
                "goals/index.md": "## Goals\n\nContents:\n\n- [Fast](fast.md)\n",
                "goals/fast.md": "### Fast\n\nkeep\n",
                "drafts/index.md": "## Drafts\n\nContents:\n\n- [Old](old.md)\n",
                "drafts/old.md": "### Old\n\nold\n",
                "notes.md": "## Notes\n",
            },
            {
                "drafts/search-index.md": _LEAF,
                "drafts/index.md": "## Drafts\n\nContents:\n\n- [Old](old.md)\n- [Search index](search-index.md)\n",
                "entry-point.md": _FULL_LISTING.replace(
                    "  - [Old](drafts/old.md)\n",
                    "  - [Old](drafts/old.md)\n  - [Search index](drafts/search-index.md)\n",
                ),
            },
            ["drafts/search-index.md", "drafts/index.md", "entry-point.md"],
            id="drafts-opens-an-index-listed-below-its-head",
        ),
        pytest.param(
            {
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals/index.md)\n  - [Fast](goals/fast.md)\n",
                "goals/index.md": "## Goals\n\nContents:\n\n- [Fast](fast.md)\n",
                "goals/fast.md": "### Fast\n\nkeep\n",
                "drafts/index.md": "## Drafts\n\nContents:\n\n",
            },
            {
                "drafts/search-index.md": _LEAF,
                "drafts/index.md": "## Drafts\n\nContents:\n\n- [Search index](search-index.md)\n",
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals/index.md)\n  - [Fast](goals/fast.md)\n"
                "  - [Search index](drafts/search-index.md)\n",
            },
            ["drafts/search-index.md", "drafts/index.md", "entry-point.md"],
            id="drafts-opens-an-index-its-head-unlisted",
        ),
        pytest.param(
            {
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals.md)\n",
                "goals.md": "## Goals\n",
                "drafts/index.md": "## Drafts\n\nContents:\n\n",
            },
            {
                "drafts/search-index.md": _LEAF,
                "drafts/index.md": "## Drafts\n\nContents:\n\n- [Search index](search-index.md)\n",
            },
            ["drafts/search-index.md", "drafts/index.md"],
            id="drafts-opens-an-index-no-full-listing",
        ),
        pytest.param(
            {
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals.md)\n",
                "goals.md": "## Goals\n\n### Fast\n\nkeep\n",
            },
            {
                "drafts/search-index.md": _LEAF,
                "drafts/index.md": "## Drafts\n\nContents:\n\n- [Search index](search-index.md)\n",
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals.md)\n- [Drafts](drafts/index.md)\n"
                "  - [Search index](drafts/search-index.md)\n",
            },
            ["drafts/search-index.md", "drafts/index.md", "entry-point.md"],
            id="no-drafts",
        ),
        pytest.param(
            {"entry-point.md": "# D\n", "goals.md": "## Goals\n\n### Fast\n\nkeep\n"},
            {
                "drafts/search-index.md": _LEAF,
                "drafts/index.md": "## Drafts\n\nContents:\n\n- [Search index](search-index.md)\n",
                "entry-point.md": "# D\n\nContents:\n\n- [Drafts](drafts/index.md)\n"
                "  - [Search index](drafts/search-index.md)\n",
            },
            ["drafts/search-index.md", "drafts/index.md", "entry-point.md"],
            id="no-drafts-no-contents-block",
        ),
        pytest.param(
            {
                "entry-point.md": "# D\n\n## Drafts\n\nContents:\n\n- [Later](later.md)\n",
                "later.md": "### Later\n\nA ticket of Drafts in a later file,\n\nlonger than the entry point's own lines.\n",
            },
            {
                "entry-point.md": "# D\n\n## Drafts\n\n### Search index\n\nBuild an index from\n"
                "[x](../ROADMAP_DESIGNS/x.md#goals).\n\nContents:\n\n- [Later](later.md)\n",
            },
            ["entry-point.md"],
            id="drafts-in-the-entry-point-before-its-contents-block",
        ),
        pytest.param(
            {"entry-point.md": "# D\n\nContents:\n\n- [Drafts](drafts.md)\n", "drafts.md": "## Drafts\n\n### A\n\na\n"},
            {
                "drafts.md": "## Drafts\n\n### A\n\na\n\n### Search index\n\nBuild an index from\n"
                "[x](../ROADMAP_DESIGNS/x.md#goals).\n"
            },
            ["drafts.md"],
            id="drafts-in-a-leaf",
        ),
    ],
)
def test_a_roadmap_card_moves_to_a_diced_design(tmp_path, design, changed, written):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **_in_design(design)})
    before = _tree(tmp_path)

    assert _to_design(root, "Search index") == [*(f"ACTIVE_DESIGN/{name}" for name in written), "ROADMAP.md"]

    assert _tree(tmp_path) == {**before, **_in_design(changed), "ROADMAP.md": _ROADMAP_AFTER}
    [card] = [c for c in read_board(root).design if c.title == "Search index"]
    assert card.path == f"ACTIVE_DESIGN/{written[0]}"


@pytest.mark.parametrize(
    "design, changed",
    [
        pytest.param(
            {
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals/index.md)\n- [Drafts](drafts/index.md)\n",
                "goals/index.md": "## Goals\n\nContents:\n\n",
                "drafts/index.md": "## Drafts\n\nContents:\n\n",
            },
            {
                "drafts/2-fast.md": "### 2 Fast\n\nquick\n",
                "drafts/index.md": "## Drafts\n\nContents:\n\n- [§2 Fast](2-fast.md)\n",
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals/index.md)\n- [Drafts](drafts/index.md)\n"
                "  - [§2 Fast](drafts/2-fast.md)\n",
            },
            id="drafts-opens-an-index",
        ),
        pytest.param(
            {"entry-point.md": "# D\n\nContents:\n\n- [Goals](goals.md)\n", "goals.md": "## Goals\n"},
            {
                "drafts/2-fast.md": "### 2 Fast\n\nquick\n",
                "drafts/index.md": "## Drafts\n\nContents:\n\n- [§2 Fast](2-fast.md)\n",
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals.md)\n- [Drafts](drafts/index.md)\n"
                "  - [§2 Fast](drafts/2-fast.md)\n",
            },
            id="no-drafts",
        ),
    ],
)
def test_a_numbered_title_s_new_leaf_is_listed_as_dicing_lists_its_section(tmp_path, design, changed):
    root = _project(tmp_path, {"ROADMAP.md": "## Next\n\n### 2 Fast\n\nquick\n", **_in_design(design)})
    before = _tree(tmp_path)

    _to_design(root, "2 Fast")

    assert _tree(tmp_path) == {**before, **_in_design(changed), "ROADMAP.md": "## Next\n"}


def test_a_parked_card_moves_to_a_new_leaf_and_back(tmp_path):
    root = _project(tmp_path, {"ROADMAP_DESIGNS/later.md": "# Later\n", **_DICED})
    before = _tree(tmp_path)

    _to_design(root, "later")
    [card] = [c for c in read_board(root).design if c.title == "later"]
    assert (card.path, card.parked) == ("ACTIVE_DESIGN/drafts/later.md", ["ROADMAP_DESIGNS/later.md"])
    [(_, target)] = prose_links(split_lines(_read(tmp_path / card.path)))
    assert os.path.samefile((tmp_path / card.path).parent / target, tmp_path / "ROADMAP_DESIGNS/later.md")

    written = _to_roadmap(root, "later")
    assert written == ["ACTIVE_DESIGN/drafts/index.md", "ACTIVE_DESIGN/entry-point.md", "ACTIVE_DESIGN/drafts/later.md"]
    # the leaf goes; the drafts index the move made stays, listing nothing, as a removed ticket's category does
    assert _tree(tmp_path) == {
        **before,
        "ACTIVE_DESIGN/drafts/index.md": "## Drafts\n\nContents:\n\n",
        "ACTIVE_DESIGN/entry-point.md": _DICED["ACTIVE_DESIGN/entry-point.md"] + "- [Drafts](drafts/index.md)\n",
    }


@pytest.mark.parametrize(
    "design, changed, written",
    [
        pytest.param(
            {
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals/index.md)\n  - [Fast](goals/fast.md)\n"
                "  - [Slow](goals/slow.md)\n",
                "goals/index.md": "## Goals\n\nContents:\n\n- [Fast](fast.md)\n- [Slow](slow.md)\n",
                "goals/fast.md": "\n### Fast\n\nkeep\n\n",
                "goals/slow.md": "### Slow\n\nslow\n",
            },
            {
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals/index.md)\n  - [Slow](goals/slow.md)\n",
                "goals/index.md": "## Goals\n\nContents:\n\n- [Slow](slow.md)\n",
                "goals/fast.md": None,
            },
            ["goals/index.md", "entry-point.md", "goals/fast.md"],
            id="leaf-its-head-and-full-listing-lines-removed",
        ),
        pytest.param(
            {
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals.md)\n- [Fast](fast.md)\n- [Sub](sub/index.md)\n",
                "goals.md": "## Goals\n",
                "fast.md": "### Fast\n\nkeep\n",
                "sub/index.md": "## Sub\n\nContents:\n\n",
            },
            {
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals.md)\n- [Sub](sub/index.md)\n",
                "fast.md": None,
            },
            ["entry-point.md", "fast.md"],
            id="leaf-beside-the-entry-point-only-its-line-removed",
        ),
        pytest.param(
            {
                "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals.md)\n",
                "goals.md": "## Goals\n\n### Fast\n\nkeep\n",
            },
            {"goals.md": "## Goals\n"},
            ["goals.md"],
            id="ticket-sharing-its-file",
        ),
    ],
)
def test_a_design_ticket_moves_out_of_a_diced_design(tmp_path, design, changed, written):
    root = _project(tmp_path, {"ROADMAP.md": "## Next\n", **_in_design(design)})
    before = _tree(tmp_path)

    assert _to_roadmap(root, "Fast") == ["ROADMAP.md", *(f"ACTIVE_DESIGN/{name}" for name in written)]

    expected = {**before, **_in_design(changed), "ROADMAP.md": "## Next\n\n### Fast\n\nkeep\n"}
    assert _tree(tmp_path) == {name: text for name, text in expected.items() if text is not None}


_LINKED = (
    "### Linked\n\n[rel](docs/a.md) [frag](docs/a.md#part) [url](https://x.org/a.md) [anchor](#here)\n"
    "[abs](/top.md) [up](../out.md) ![img](img/p.png) `[code](docs/a.md)`\n\n```\n[fenced](docs/a.md)\n```\n"
)


def test_relative_links_are_rebased_into_a_nested_leaf_and_back(tmp_path):
    project = tmp_path / "project"  # its parent holds out.md, which `../out.md` names
    project.mkdir()
    roadmap = "## Next\n\n" + _LINKED
    root = _project(project, {"ROADMAP.md": roadmap, "docs/a.md": "# A\n", "img/p.png": "", **_DICED})
    (tmp_path / "out.md").write_text("# Out\n", encoding="utf-8")

    _to_design(root, "Linked")
    leaf = project / "ACTIVE_DESIGN/drafts/linked.md"
    lines = split_lines(_read(leaf))
    assert lines[2:4] == [
        "[rel](../../docs/a.md) [frag](../../docs/a.md#part) [url](https://x.org/a.md) [anchor](#here)",
        "[abs](/top.md) [up](../../../out.md) ![img](../../img/p.png) `[code](docs/a.md)`",
    ]
    assert lines[5:] == ["```", "[fenced](docs/a.md)", "```"]
    pairs = zip((t for _, t in prose_links(split_lines(_LINKED))), (t for _, t in prose_links(lines)))
    relative = [(was, now) for was, now in pairs if not was.startswith(("#", "/", "https:"))]
    assert len(relative) == 4
    for was, now in relative:
        assert os.path.samefile(leaf.parent / now.partition("#")[0], project / was.partition("#")[0])

    _to_roadmap(root, "Linked")
    assert _read(project / "ROADMAP.md") == roadmap


@pytest.mark.parametrize(
    "files, title, move",
    [
        pytest.param({"ROADMAP.md": "## Next\n\n### ---\n", **_DICED}, "---", "design", id="title-names-no-file"),
        pytest.param(
            {"ROADMAP.md": _ROADMAP, **_DICED, "ACTIVE_DESIGN/drafts/search-index.md": "x\n"},
            "Search index",
            "design",
            id="leaf-to-create-exists",
        ),
        pytest.param(
            {"ROADMAP.md": _ROADMAP, **_DICED, "ACTIVE_DESIGN/drafts/index.md": "# Other\n"},
            "Search index",
            "design",
            id="drafts-index-to-create-exists",
        ),
        pytest.param(
            {
                "ROADMAP.md": "## Next\n",
                **_in_design(
                    {
                        "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals.md)\n",
                        "goals.md": "## Goals\n",
                        "fast.md": "### Fast\n\nkeep\n",
                    }
                ),
            },
            "Fast",
            "roadmap",
            id="leaf-not-listed-by-its-head",
        ),
        pytest.param(
            {
                "ROADMAP.md": "## Next\n",
                **_in_design(
                    {
                        "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals/index.md)\n",
                        "goals/index.md": "## Goals\n\nContents:\n\n- [Fast](fast.md)\n- [Detail](detail.md)\n",
                        "goals/fast.md": "### Fast\n\nkeep\n",
                        "goals/detail.md": "#### Detail\n\nmore\n",
                    }
                ),
            },
            "Fast",
            "roadmap",
            id="ticket-runs-on-past-its-file",
        ),
        pytest.param(
            {
                "ROADMAP.md": "## Next\n",
                **_in_design(
                    {
                        "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals/index.md)\n",
                        "goals/index.md": "## Goals\n\nContents:\n\n- [Other](other.md)\n\nSee [Fast](fast.md).\n",
                        "goals/other.md": "### Other\n\nother\n",
                        "goals/fast.md": "### Fast\n\nkeep\n",
                    }
                ),
            },
            "Fast",
            "roadmap",
            id="leaf-linked-by-its-head-only-after-its-contents-list",
        ),
    ],
)
def test_a_diced_design_move_is_refused(tmp_path, files, title, move):
    root = _project(tmp_path, files)
    before = _tree(tmp_path)
    with pytest.raises(MoveRefused):
        _to_design(root, title) if move == "design" else _to_roadmap(root, title)
    assert _tree(tmp_path) == before


def test_a_title_holding_a_bracket_moved_into_a_diced_design_cannot_move_back(tmp_path):
    root = _project(tmp_path, {"ROADMAP.md": "## Next\n\n### Foo ] bar\n\nkeep\n", **_DICED})
    _to_design(root, "Foo ] bar")
    moved_in = _tree(tmp_path)
    assert "ACTIVE_DESIGN/drafts/foo-bar.md" in moved_in

    with pytest.raises(MoveRefused):
        _to_roadmap(root, "Foo ] bar")
    assert _tree(tmp_path) == moved_in


def test_a_diced_design_move_is_refused_where_a_file_to_create_appeared_since_the_read(tmp_path):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **_DICED})
    board = read_board(root)
    card = _card(root, "Search index")
    created = tmp_path / "ACTIVE_DESIGN/drafts/index.md"
    created.parent.mkdir()
    created.write_text("## Drafts\n", encoding="utf-8")
    after = _tree(tmp_path)

    with pytest.raises(MoveRefused):
        move_to_design(root, card, read=board.sha256)
    assert _tree(tmp_path) == after


def test_a_leaf_deletion_that_fails_names_the_leaf_and_the_files_written(tmp_path, monkeypatch):
    design = {
        "entry-point.md": "# D\n\nContents:\n\n- [Goals](goals/index.md)\n  - [Fast](goals/fast.md)\n",
        "goals/index.md": "## Goals\n\nContents:\n\n- [Fast](fast.md)\n",
        "goals/fast.md": "### Fast\n\nkeep\n",
    }
    root = _project(tmp_path, {"ROADMAP.md": "## Next\n", **_in_design(design)})
    real = os.remove

    def fail_on_the_leaf(path):
        if os.path.basename(path) == "fast.md":
            raise OSError("read-only")
        real(path)

    monkeypatch.setattr(os, "remove", fail_on_the_leaf)
    with pytest.raises(MoveWriteFailed) as failed:
        _to_roadmap(root, "Fast")

    assert (failed.value.path, failed.value.written) == (
        "ACTIVE_DESIGN/goals/fast.md",
        ["ROADMAP.md", "ACTIVE_DESIGN/goals/index.md", "ACTIVE_DESIGN/entry-point.md"],
    )
    assert (tmp_path / "ACTIVE_DESIGN/goals/fast.md").exists()


def test_making_the_drafts_directory_that_fails_names_the_leaf_it_was_made_for(tmp_path, monkeypatch):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **_DICED})
    before = _tree(tmp_path)

    def fail(path, *args, **kwargs):
        raise OSError("read-only")

    monkeypatch.setattr(os, "makedirs", fail)
    with pytest.raises(MoveWriteFailed) as failed:
        _to_design(root, "Search index")

    assert (failed.value.path, failed.value.written) == ("ACTIVE_DESIGN/drafts/search-index.md", [])
    assert _tree(tmp_path) == before


@pytest.mark.parametrize("design", [_MONOLITH, {}], ids=["monolith", "created"])
def test_parked_card_round_trip(tmp_path, design):
    root = _project(tmp_path, {"ROADMAP_DESIGNS/later.md": "# Later\n", **design})
    before = _tree(tmp_path)

    written = _to_design(root, "later")
    board = read_board(root)
    assert "ROADMAP.md" not in written
    assert board.parked == []
    [card] = [c for c in board.design if c.title == "later"]
    assert (card.kind, card.parked, card.parked_hrefs) == (
        "ticket",
        ["ROADMAP_DESIGNS/later.md"],
        ["/ROADMAP_DESIGNS/later.md"],
    )
    lines = split_lines(_read(tmp_path / card.path))
    at = lines.index("### later")
    assert lines[at:] == ["### later", "", "[ROADMAP_DESIGNS/later.md](ROADMAP_DESIGNS/later.md)", "", INSTRUCTION]
    [(_, target)] = prose_links(lines)
    assert os.path.samefile((tmp_path / card.path).parent / target, tmp_path / "ROADMAP_DESIGNS/later.md")

    assert "ROADMAP.md" not in _to_roadmap(root, "later")
    assert read_board(root).parked == [_parked("later", ["ROADMAP_DESIGNS/later.md"])]
    assert not (tmp_path / "ROADMAP.md").exists()
    if design:
        assert _tree(tmp_path) == before


def test_a_grouped_pieces_link_ticket_links_each_of_its_files(tmp_path):
    files = ["ROADMAP_DESIGNS/X_DESIGN.md", "ROADMAP_DESIGNS/X_PLAN/entry-point.md"]
    root = _project(tmp_path, {**{f: "# X\n" for f in files}, **_MONOLITH})
    before = _tree(tmp_path)

    _to_design(root, "X")
    board = read_board(root)
    assert board.parked == []
    [card] = [c for c in board.design if c.title == "X"]
    assert card.parked == files
    lines = split_lines(_read(tmp_path / "ACTIVE_DESIGN.md"))
    assert lines[lines.index("### X") :] == ["### X", "", *(f"[{f}]({f})" for f in files), "", INSTRUCTION]

    _to_roadmap(root, "X")
    assert read_board(root).parked == [_parked("X", files)]
    assert _tree(tmp_path) == before


def test_an_edited_link_ticket_is_an_ordinary_card(tmp_path):
    root = _project(tmp_path, {"ROADMAP_DESIGNS/later.md": "# Later\n", **_MONOLITH})
    _to_design(root, "later")
    design = tmp_path / "ACTIVE_DESIGN.md"
    design.write_text(_read(design) + "\nDecided: yes.\n", encoding="utf-8")
    board = read_board(root)
    assert [c.parked for c in board.design if c.title == "later"] == [None]
    assert board.parked == [_parked("later", ["ROADMAP_DESIGNS/later.md"])]


def test_a_link_ticket_whose_work_a_roadmap_ticket_links_is_an_ordinary_card(tmp_path):
    root = _project(tmp_path, {"ROADMAP_DESIGNS/later.md": "# Later\n", **_MONOLITH})
    _to_design(root, "later")
    (tmp_path / "ROADMAP.md").write_text("## Next\n\n### Later\n\n[x](ROADMAP_DESIGNS/later.md)\n", encoding="utf-8")
    board = read_board(root)
    assert [c.parked for c in board.design if c.title == "later"] == [None]
    assert [c.parked for c in board.roadmap if c.title == "Later"] == [["ROADMAP_DESIGNS/later.md"]]
    assert board.parked == []


@pytest.mark.parametrize(
    "design, changed",
    [
        pytest.param(_MONOLITH, "ACTIVE_DESIGN.md", id="monolith-design"),
        pytest.param(_MONOLITH, "ROADMAP.md", id="roadmap"),
        pytest.param({}, "ACTIVE_DESIGN.md", id="design-created-since-read"),
    ],
)
def test_move_to_design_refused_where_a_file_changed(tmp_path, design, changed):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **design})
    board = read_board(root)
    card = asdict(next(c for c in board.roadmap if c.title == "Search index"))
    path = tmp_path / changed
    path.write_text((_read(path) if path.exists() else "") + "edited\n", encoding="utf-8")
    after = _tree(tmp_path)

    with pytest.raises(MoveRefused):
        move_to_design(root, card, read=board.sha256)
    assert _tree(tmp_path) == after


@pytest.mark.parametrize("changed", ["ACTIVE_DESIGN.md", "ROADMAP.md"], ids=["design", "roadmap"])
def test_move_to_roadmap_refused_where_a_file_changed(tmp_path, changed):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **_MONOLITH})
    board = read_board(root)
    (tmp_path / changed).write_text(_read(tmp_path / changed) + "edited\n", encoding="utf-8")
    after = _tree(tmp_path)

    card = next(c for c in board.design if c.title == "Fast")
    with pytest.raises(MoveRefused):
        move_to_roadmap(root, asdict(card), target=None, read=board.sha256)
    assert _tree(tmp_path) == after


@pytest.mark.parametrize(
    "card",
    [
        pytest.param(_parked("gone", ["ROADMAP_DESIGNS/gone.md"]), id="parked"),
        pytest.param(RoadmapCard("Gone", "", "/ROADMAP.md#gone", [], "ticket", 0), id="roadmap"),
        pytest.param(
            DesignCard("Gone", "", "ACTIVE_DESIGN.md", "/ACTIVE_DESIGN.md#gone", None, None, "ticket", 0), id="design"
        ),
    ],
)
def test_move_refused_where_the_card_is_gone(tmp_path, card):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **_MONOLITH})
    before = _tree(tmp_path)
    read = read_board(root).sha256
    with pytest.raises(MoveRefused):
        if isinstance(card, DesignCard):
            move_to_roadmap(root, asdict(card), target=None, read=read)
        else:
            move_to_design(root, asdict(card), read=read)
    assert _tree(tmp_path) == before


def test_a_move_does_not_read_the_active_plan(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root reads any file")
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, "ACTIVE_PLAN.md": _PLAN, **_MONOLITH})
    card = _card(root, "Search index")
    read = read_board(root).sha256
    plan = tmp_path / "ACTIVE_PLAN.md"
    plan.chmod(0)
    try:
        assert move_to_design(root, card, read=read) == ["ACTIVE_DESIGN.md", "ROADMAP.md"]
    finally:
        plan.chmod(0o644)


def test_addition_is_written_before_removal(tmp_path, monkeypatch):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **_MONOLITH})
    real = board_module.replace_lines

    def fail_on_roadmap(path, lines):
        if os.path.basename(path) == "ROADMAP.md":
            raise OSError("disk full")
        real(path, lines)

    monkeypatch.setattr(board_module, "replace_lines", fail_on_roadmap)
    with pytest.raises(MoveWriteFailed) as failed:
        _to_design(root, "Search index")

    assert (failed.value.path, failed.value.written) == ("ROADMAP.md", ["ACTIVE_DESIGN.md"])
    assert "### Search index" in _read(tmp_path / "ACTIVE_DESIGN.md")
    assert _read(tmp_path / "ROADMAP.md") == _ROADMAP
