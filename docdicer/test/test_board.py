"""Unit tests for the kanban board model: the columns and cards a project's files give, the moves of
an entry between ROADMAP.md and the active design and their guards."""

import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import pytest

from docdicer.dicerlib.heads import CONTENTS
from docdicer.dicerlib.linkcheck import prose_links
from docdicer.dicerlib.textfile import split_lines
from docdicer.kanban import board as board_module
from docdicer.kanban.board import (
    INSTRUCTION,
    PLAN_COLUMNS,
    TITLE_LENGTH,
    DesignCard,
    MoveRefused,
    MoveWriteFailed,
    ParkedCard,
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
# The item to move is the last of its group, so dropping it back on the group's other card restores it.
_ROADMAP = (
    "# Roadmap\n\n## Next\n\n1. **Alpha.** First.\n2. **Search index.** Build an index from\n"
    "   [x](ROADMAP_DESIGNS/x.md#goals).\n\n## Later\n\n- Other\n"
)
_BODY = ["**Search index.** Build an index from", "   [x](ROADMAP_DESIGNS/x.md#goals)."]
_MONOLITH = {"ACTIVE_DESIGN.md": "# Design\n\n## Goals\n\nkeep\n"}
_DICED = {
    "ACTIVE_DESIGN/entry-point.md": "# Design\n\nContents:\n\n- [Goals](goals.md)\n",
    "ACTIVE_DESIGN/goals.md": "## Goals\n\nkeep\n",
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
    """The card titled title, as the server serves it."""
    board = read_board(root)
    return asdict(next(c for c in [*board.roadmap, *board.parked, *board.design] if c.title == title))


def _to_design(root: str, title: str) -> list[str]:
    return move_to_design(root, _card(root, title), read=read_board(root).sha256)


def _to_roadmap(root: str, title: str, target: Optional[str] = None) -> list[str]:
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
            [("Goals", "Fast.\n\n### Detail\n\nMore.", "ACTIVE_DESIGN.md"), ("Risks", "", "ACTIVE_DESIGN.md")],
            id="monolith",
        ),
        pytest.param(
            {
                "ACTIVE_DESIGN/entry-point.md": "# Cache design\n\n## Overview\n\nAll.\n\nContents:\n\n- [Goals](goals.md)\n",
                "ACTIVE_DESIGN/goals.md": "## Goals\n\nFast.\n",
                "ACTIVE_DESIGN/risks.md": "## Risks\n",
            },
            [("Overview", "All.", "ACTIVE_DESIGN/entry-point.md"), ("Goals", "Fast.", "ACTIVE_DESIGN/goals.md")]
            + [("Risks", "", "ACTIVE_DESIGN/risks.md")],
            id="diced-across-leaves-contents-block-excluded",
        ),
        pytest.param(
            {"ACTIVE_DESIGN.md": "```\n# not the title\n## not a section\n```\n\n# Title\n\n## Kept\n"},
            [("Kept", "", "ACTIVE_DESIGN.md")],
            id="fenced-headings-skipped",
        ),
        pytest.param({}, [], id="no-design"),
    ],
)
def test_design_cards(tmp_path, files, cards):
    board = read_board(_project(tmp_path, files))
    assert [(c.title, c.text, c.path) for c in board.design] == cards
    assert all(c.parked is None for c in board.design)


_DELTA_MONOLITH = {
    "ACTIVE_DESIGN.md": "# D\n\n## Intro\n\nWhy.\n\n## SPEC delta\n\nstray\n\n### [§11.2](SPEC.md#x)\n\nNew row.\n\n"
    "## Code delta\n\n### board.py\n\nKind.\n"
}
# The leaves' names sort against document order: the Contents block puts SPEC delta first.
_DELTA_DICED = {
    "ACTIVE_DESIGN/entry-point.md": "# D\n\n## Intro\n\nWhy.\n\nContents:\n\n- [SPEC delta](spec-delta.md)\n"
    "- [Code delta](code-delta.md)\n",
    "ACTIVE_DESIGN/spec-delta.md": "## SPEC delta\n\nstray\n\n### [§11.2](../SPEC.md#x)\n\nNew row.\n",
    "ACTIVE_DESIGN/code-delta.md": "## Code delta\n\n### board.py\n\nKind.\n",
}


@pytest.mark.parametrize(
    "files, paths",
    [
        pytest.param(_DELTA_MONOLITH, ["ACTIVE_DESIGN.md"] * 5, id="monolith"),
        pytest.param(
            _DELTA_DICED,
            ["ACTIVE_DESIGN/entry-point.md"]
            + ["ACTIVE_DESIGN/spec-delta.md"] * 2
            + ["ACTIVE_DESIGN/code-delta.md"] * 2,
            id="diced-in-document-order",
        ),
    ],
)
def test_deltas_are_separators_over_entry_cards(tmp_path, files, paths):
    board = read_board(_project(tmp_path, files))
    assert [(c.kind, c.title, c.text) for c in board.design] == [
        ("section", "Intro", "Why."),
        ("delta", "SPEC delta", ""),
        ("entry", "§11.2", "New row."),
        ("delta", "Code delta", ""),
        ("entry", "board.py", "Kind."),
    ]
    assert [c.path for c in board.design] == paths


@pytest.mark.parametrize("kind", ["entry", "delta"])
def test_an_entry_card_or_separator_is_refused_on_roadmap(tmp_path, kind):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **_DELTA_MONOLITH})
    before = _tree(tmp_path)
    board = read_board(root)
    card = next(c for c in board.design if c.kind == kind)
    with pytest.raises(MoveRefused):
        move_to_roadmap(root, asdict(card), target=None, read=board.sha256)
    assert _tree(tmp_path) == before


def test_a_card_titled_by_a_delta_heading_is_refused_on_design(tmp_path):
    root = _project(tmp_path, {"ROADMAP.md": "- **SPEC delta** text\n", **_DELTA_MONOLITH})
    before = _tree(tmp_path)
    with pytest.raises(MoveRefused):
        _to_design(root, "SPEC delta")
    assert _tree(tmp_path) == before


@pytest.mark.parametrize("design", [_DELTA_MONOLITH, _DELTA_DICED], ids=["monolith", "diced"])
def test_a_section_moves_both_ways_in_a_design_with_deltas(tmp_path, design):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, "ROADMAP_DESIGNS/x.md": "# X\n", **design})
    before = _tree(tmp_path)

    _to_design(root, "Search index")
    assert [c.kind for c in read_board(root).design if c.title == "Search index"] == ["section"]
    _to_roadmap(root, "Search index", target="Alpha")

    assert _tree(tmp_path) == before


def test_design_read_for_its_headings_only(tmp_path):
    design = "# Design\n\nRelease: 1.0\n\n## Status\n\n| Package | State |\n|---|---|\n| X1 | landed |\n"
    board = read_board(_project(tmp_path, {"ACTIVE_DESIGN.md": design}))
    assert [c.title for c in board.design] == ["Status"]
    assert (board.release, board.packages) == (None, [])


_LONG = " ".join(["word"] * 20)
_LINKED_ITEM = "Linked design work: see [linked](ROADMAP_DESIGNS/linked.md)"


@pytest.mark.parametrize(
    "roadmap, cards",
    [
        pytest.param(
            "# Roadmap\n\n## Next\n\n1. **Search index.** Build an index.\n2. **Cache:** keep answers\n   across runs.\n",
            [("Next", "Search index", "1. **Search index.** Build an index.")]
            + [("Next", "Cache", "2. **Cache:** keep answers\n   across runs.")],
            id="numbered-bold-titles",
        ),
        pytest.param(
            "## Soon\n\n- Add a flag. It does x.\n* Second item\n  wraps here\n\n## Later\n\n- Third\n  - a sub-item\n",
            [
                ("Soon", "Add a flag", "- Add a flag. It does x."),
                ("Soon", "Second item wraps here", "* Second item\n  wraps here"),
            ]
            + [("Later", "Third", "- Third\n  - a sub-item")],
            id="bullets-under-groups",
        ),
        pytest.param("- Alone\n", [("", "Alone", "- Alone")], id="no-group"),
        pytest.param(
            f"- {_LINKED_ITEM}\n", [("", "Linked design work: see linked", f"- {_LINKED_ITEM}")], id="link-in-sentence"
        ),
        pytest.param("- **See [x](y.md).** z\n", [("", "See x", "- **See [x](y.md).** z")], id="link-in-bold-lead"),
        pytest.param(f"- {_LONG}\n", [("", _LONG[: TITLE_LENGTH - 1] + "…", f"- {_LONG}")], id="long-sentence-cut"),
        pytest.param("- Item\n\nA paragraph.\n", [("", "Item", "- Item")], id="paragraph-ends-item"),
        pytest.param("- Item\n\n  more text\n", [("", "Item", "- Item\n\n  more text")], id="indented-text-continues"),
        pytest.param(
            "```\n- not an item\n## Not a group\n```\n- Real\n", [("", "Real", "- Real")], id="fenced-ignored"
        ),
        pytest.param("##\tSoon\n\n- Item\n", [("", "Item", "- Item")], id="tab-after-hashes-is-no-heading"),
    ],
)
def test_roadmap_cards(tmp_path, roadmap, cards):
    board = read_board(_project(tmp_path, {"ROADMAP.md": roadmap}))
    assert [(c.group, c.title, c.text) for c in board.roadmap] == cards


def test_parked_cards(tmp_path):
    roadmap = (
        "## Next\n\n- **Linked** see [plan](ROADMAP_DESIGNS/linked.md) and\n"
        "  [tree](ROADMAP_DESIGNS/tree/entry-point.md#goals).\n\nSee [loose](ROADMAP_DESIGNS/loose.md).\n"
    )
    files = {
        "ROADMAP.md": roadmap,
        "ROADMAP_DESIGNS/README.md": "# Parked plans\n",
        "ROADMAP_DESIGNS/linked.md": "# Linked\n",
        "ROADMAP_DESIGNS/tree/entry-point.md": "# Tree\n",
        "ROADMAP_DESIGNS/unlinked.md": "# Unlinked\n\nSee [appendix](appendix.md).\n",
        "ROADMAP_DESIGNS/appendix.md": "# Appendix\n",
        "ROADMAP_DESIGNS/loose.md": "# Loose\n",
    }
    board = read_board(_project(tmp_path, files))
    assert [c.parked for c in board.roadmap] == [["ROADMAP_DESIGNS/linked.md", "ROADMAP_DESIGNS/tree/entry-point.md"]]
    assert board.parked == [
        ParkedCard("appendix", "ROADMAP_DESIGNS/appendix.md"),
        ParkedCard("loose", "ROADMAP_DESIGNS/loose.md"),
        ParkedCard("unlinked", "ROADMAP_DESIGNS/unlinked.md"),
    ]


def test_board_digests_every_file_a_move_may_write(tmp_path):
    board = read_board(_project(tmp_path, {**_DICED, "ROADMAP_DESIGNS/later.md": "# Later\n"}))
    assert sorted(board.sha256) == ["ACTIVE_DESIGN/entry-point.md", "ACTIVE_DESIGN/goals.md", "ROADMAP.md"]
    assert board.sha256["ROADMAP.md"] is None


@pytest.mark.parametrize(
    "design, written, section_file",
    [
        pytest.param(_MONOLITH, ["ACTIVE_DESIGN.md", "ROADMAP.md"], "ACTIVE_DESIGN.md", id="monolith"),
        pytest.param({}, ["ACTIVE_DESIGN.md", "ROADMAP.md"], "ACTIVE_DESIGN.md", id="created"),
        pytest.param(
            _DICED,
            ["ACTIVE_DESIGN/search-index.md", "ACTIVE_DESIGN/entry-point.md", "ROADMAP.md"],
            "ACTIVE_DESIGN/search-index.md",
            id="diced",
        ),
    ],
)
def test_roadmap_card_moves_to_design(tmp_path, design, written, section_file):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, "ROADMAP_DESIGNS/x.md": "# X\n", **design})
    assert _to_design(root, "Search index") == written

    board = read_board(root)
    assert [c.title for c in board.roadmap] == ["Alpha", "Other"]
    assert "Search index" not in _read(tmp_path / "ROADMAP.md")
    [card] = [c for c in board.design if c.title == "Search index"]
    assert (card.path, card.parked) == (section_file, None)
    lines = split_lines(_read(tmp_path / section_file))
    assert lines[lines.index("## Search index") + 2] == _BODY[0]
    [(_, target)] = prose_links(lines[lines.index("## Search index") :])
    assert os.path.samefile(
        (tmp_path / section_file).parent / target.partition("#")[0], tmp_path / "ROADMAP_DESIGNS/x.md"
    )
    if design is _DICED:
        entry = split_lines(_read(tmp_path / "ACTIVE_DESIGN/entry-point.md"))
        assert [t for _, t in prose_links(entry)] == ["goals.md", "search-index.md"]
    if not design:
        assert lines[0] == "# ACTIVE DESIGN"


@pytest.mark.parametrize("design", [_MONOLITH, _DICED], ids=["monolith", "diced"])
def test_round_trip_leaves_both_documents_as_they_were(tmp_path, design):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, "ROADMAP_DESIGNS/x.md": "# X\n", **design})
    before = _tree(tmp_path)

    _to_design(root, "Search index")
    _to_roadmap(root, "Search index", target="Alpha")

    assert _tree(tmp_path) == before


def test_item_titled_by_a_linking_sentence_moves_to_a_diced_design_and_back(tmp_path):
    roadmap = f"## Next\n\n- First.\n- {_LINKED_ITEM}\n"
    root = _project(tmp_path, {"ROADMAP.md": roadmap, "ROADMAP_DESIGNS/linked.md": "# Linked\n", **_DICED})
    before = _tree(tmp_path)

    _to_design(root, "Linked design work: see linked")

    entry = split_lines(_read(tmp_path / "ACTIVE_DESIGN/entry-point.md"))
    assert [t for _, t in prose_links(entry)] == ["goals.md", "linked-design-work-see-linked.md"]
    assert entry[-1] == "- [Linked design work: see linked](linked-design-work-see-linked.md)"
    leaf = split_lines(_read(tmp_path / "ACTIVE_DESIGN/linked-design-work-see-linked.md"))
    assert leaf[0] == "## Linked design work: see linked"

    _to_roadmap(root, "Linked design work: see linked", target="First")
    assert _tree(tmp_path) == before


def test_edited_section_returns_with_its_heading_as_bold_lead(tmp_path):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, "ROADMAP_DESIGNS/x.md": "# X\n", **_MONOLITH})
    _to_design(root, "Search index")
    design = tmp_path / "ACTIVE_DESIGN.md"
    design.write_text(_read(design).replace("**Search index.** Build", "Build"), encoding="utf-8")

    _to_roadmap(root, "Search index", target="Alpha")

    lines = split_lines(_read(tmp_path / "ROADMAP.md"))
    at = lines.index("1. **Alpha.** First.") + 1
    assert lines[at : at + 2] == ["2. **Search index** Build an index from", "      [x](ROADMAP_DESIGNS/x.md#goals)."]
    assert _read(design) == _MONOLITH["ACTIVE_DESIGN.md"]


_GONE_CARD = {"title": "Gone", "group": "Next", "text": "1. Gone.", "parked": []}


@pytest.mark.parametrize(
    "target, expected",
    [
        pytest.param(None, "## Later\n\n- Other\n- **Note** Text.\n", id="no-card-end-of-file"),
        pytest.param("later", "## Later\n\n- Other\n- **Note** Text.\n", id="parked-card-end-of-file"),
        pytest.param(_GONE_CARD, "## Later\n\n- Other\n- **Note** Text.\n", id="card-no-longer-on-the-board"),
    ],
)
def test_returned_item_placement_and_marker(tmp_path, target, expected):
    files = {
        "ROADMAP.md": "## Next\n\n1. One.\n\n## Later\n\n- Other\n",
        "ROADMAP_DESIGNS/later.md": "# Later\n",
        "ACTIVE_DESIGN.md": "# Design\n\n## Note\n\nText.\n",
    }
    root = _project(tmp_path, files)
    board = read_board(root)
    dropped_on = _card(root, target) if isinstance(target, str) else target
    move_to_roadmap(root, asdict(board.design[0]), target=dropped_on, read=board.sha256)
    assert _read(tmp_path / "ROADMAP.md") == "## Next\n\n1. One.\n\n" + expected


def test_returned_item_at_the_end_of_a_numbered_last_group_takes_the_next_number(tmp_path):
    files = {"ROADMAP.md": "## Next\n\n- One.\n\n## Later\n\n1. Other.\n", "ACTIVE_DESIGN.md": "# D\n\n## Note\n"}
    root = _project(tmp_path, files)
    _to_roadmap(root, "Note")
    assert _read(tmp_path / "ROADMAP.md") == "## Next\n\n- One.\n\n## Later\n\n1. Other.\n2. **Note**\n"


def test_section_that_does_not_read_back_as_one_item_returns_in_bold_lead_form(tmp_path):
    # its heading is the title its body gives, but the paragraph after the blank line would end the item
    root = _project(tmp_path, {"ACTIVE_DESIGN.md": "# D\n\n## Alpha\n\nAlpha. More.\n\nA paragraph.\n"})
    _to_roadmap(root, "Alpha")
    [card] = read_board(root).roadmap
    assert card.title == "Alpha"
    assert "A paragraph." in card.text


def test_returned_item_into_numbered_group_takes_the_next_number(tmp_path):
    files = {"ROADMAP.md": "## Next\n\n1. One.\n\n## Later\n\n- Other\n", "ACTIVE_DESIGN.md": "# D\n\n## Note\n"}
    root = _project(tmp_path, files)
    _to_roadmap(root, "Note", target="One")
    assert _read(tmp_path / "ROADMAP.md") == "## Next\n\n1. One.\n2. **Note**\n\n## Later\n\n- Other\n"


def test_returned_item_creates_the_roadmap(tmp_path):
    root = _project(tmp_path, {"ACTIVE_DESIGN.md": "# D\n\n## Note\n\nText.\n"})
    assert _to_roadmap(root, "Note") == ["ROADMAP.md", "ACTIVE_DESIGN.md"]
    assert _read(tmp_path / "ROADMAP.md") == "- **Note** Text.\n"
    assert _read(tmp_path / "ACTIVE_DESIGN.md") == "# D\n"


def test_section_in_entry_point_moves_as_a_monolith_section(tmp_path):
    entry = "# Design\n\n## Intro\n\nHello.\n\nContents:\n\n- [Goals](goals.md)\n"
    root = _project(tmp_path, {"ACTIVE_DESIGN/entry-point.md": entry, "ACTIVE_DESIGN/goals.md": "## Goals\n"})
    assert _to_roadmap(root, "Intro") == ["ROADMAP.md", "ACTIVE_DESIGN/entry-point.md"]
    assert _read(tmp_path / "ACTIVE_DESIGN/entry-point.md") == "# Design\n\nContents:\n\n- [Goals](goals.md)\n"
    assert (tmp_path / "ACTIVE_DESIGN/goals.md").exists()
    assert _read(tmp_path / "ROADMAP.md") == "- **Intro** Hello.\n"


@pytest.mark.parametrize("design", [_MONOLITH, _DICED, {}], ids=["monolith", "diced", "created"])
def test_parked_entry_round_trip(tmp_path, design):
    root = _project(tmp_path, {"ROADMAP_DESIGNS/later.md": "# Later\n", **design})
    before = _tree(tmp_path)

    written = _to_design(root, "later")
    board = read_board(root)
    assert "ROADMAP.md" not in written
    assert board.parked == []
    [card] = [c for c in board.design if c.title == "later"]
    assert card.parked == "ROADMAP_DESIGNS/later.md"
    lines = split_lines(_read(tmp_path / card.path))
    [(_, target)] = prose_links(lines)
    assert os.path.samefile((tmp_path / card.path).parent / target, tmp_path / "ROADMAP_DESIGNS/later.md")
    assert INSTRUCTION in lines

    assert "ROADMAP.md" not in _to_roadmap(root, "later")
    assert read_board(root).parked == [ParkedCard("later", "ROADMAP_DESIGNS/later.md")]
    if design:
        assert _tree(tmp_path) == before


def test_edited_link_section_is_an_ordinary_card(tmp_path):
    root = _project(tmp_path, {"ROADMAP_DESIGNS/later.md": "# Later\n", **_MONOLITH})
    _to_design(root, "later")
    design = tmp_path / "ACTIVE_DESIGN.md"
    design.write_text(_read(design) + "\nDecided: yes.\n", encoding="utf-8")
    board = read_board(root)
    assert [c.parked for c in board.design if c.title == "later"] == [None]
    assert board.parked == [ParkedCard("later", "ROADMAP_DESIGNS/later.md")]


@pytest.mark.parametrize(
    "design, changed",
    [
        pytest.param(_MONOLITH, "ACTIVE_DESIGN.md", id="monolith-design"),
        pytest.param(_MONOLITH, "ROADMAP.md", id="roadmap"),
        pytest.param(_DICED, "ACTIVE_DESIGN/entry-point.md", id="diced-entry-point"),
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


@pytest.mark.parametrize("changed", ["ACTIVE_DESIGN/goals.md", "ROADMAP.md"], ids=["leaf", "roadmap"])
def test_move_to_roadmap_refused_where_a_file_changed(tmp_path, changed):
    root = _project(tmp_path, {"ROADMAP.md": _ROADMAP, **_DICED})
    board = read_board(root)
    (tmp_path / changed).write_text(_read(tmp_path / changed) + "edited\n", encoding="utf-8")
    after = _tree(tmp_path)

    with pytest.raises(MoveRefused):
        move_to_roadmap(root, asdict(board.design[0]), target=None, read=board.sha256)
    assert _tree(tmp_path) == after


@pytest.mark.parametrize(
    "card",
    [
        pytest.param(ParkedCard("gone", "ROADMAP_DESIGNS/gone.md"), id="parked"),
        pytest.param(DesignCard("Gone", "", "ACTIVE_DESIGN.md", None, "section"), id="design"),
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


@pytest.mark.parametrize(
    "files, title, named",
    [
        pytest.param(
            {"ROADMAP.md": _ROADMAP, "ACTIVE_DESIGN/search-index.md": "## Search index\n\nearlier\n"},
            "Search index",
            "ACTIVE_DESIGN/search-index.md",
            id="leaf-exists",
        ),
        pytest.param({"ROADMAP.md": "- **ä**\n"}, "ä", "ä", id="empty-name"),
    ],
)
def test_move_into_diced_design_refused_without_a_new_leaf(tmp_path, files, title, named):
    root = _project(tmp_path, {**_DICED, **files})
    before = _tree(tmp_path)
    board = read_board(root)
    with pytest.raises(MoveRefused) as refused:
        move_to_design(root, asdict(next(c for c in board.roadmap if c.title == title)), read=board.sha256)
    assert named in str(refused.value)
    assert _tree(tmp_path) == before


@pytest.mark.parametrize(
    "roadmap, title, leaf",
    [
        pytest.param("- **1. Search**\n", "1. Search", "1-search.md", id="numbered"),
        pytest.param("- **2. ä**\n", "2. ä", "2.md", id="numbered-empty-slug"),
    ],
)
def test_a_diced_designs_new_leaf_takes_the_section_name_of_its_title(tmp_path, roadmap, title, leaf):
    root = _project(tmp_path, {"ROADMAP.md": roadmap, **_DICED})
    assert _to_design(root, title)[0] == f"ACTIVE_DESIGN/{leaf}"
    entry = split_lines(_read(tmp_path / "ACTIVE_DESIGN/entry-point.md"))
    assert entry[-1] == f"- [{title}]({leaf})"


def test_a_diced_design_without_a_contents_block_gains_one(tmp_path):
    files = {"ROADMAP.md": _ROADMAP, "ROADMAP_DESIGNS/x.md": "# X\n", "ACTIVE_DESIGN/entry-point.md": "# Design\n"}
    root = _project(tmp_path, files)
    _to_design(root, "Search index")
    entry = split_lines(_read(tmp_path / "ACTIVE_DESIGN/entry-point.md"))
    assert CONTENTS in entry
    assert [t for _, t in prose_links(entry)] == ["search-index.md"]


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param("# Design\n\nContents:\n\n- [Goals](goals.md)\n", id="not-listed"),
        pytest.param("# Design\n", id="no-contents-block"),
    ],
)
def test_a_leaf_whose_contents_line_is_not_found_is_not_moved(tmp_path, entry):
    files = {"ACTIVE_DESIGN/entry-point.md": entry, "ACTIVE_DESIGN/risks.md": "## Risks\n\nText.\n"}
    files["ACTIVE_DESIGN/goals.md"] = "## Goals\n"  # a Contents link is read: one to no file fails the read
    root = _project(tmp_path, files)
    before = _tree(tmp_path)
    with pytest.raises(MoveRefused):
        _to_roadmap(root, "Risks")
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
    assert "## Search index" in _read(tmp_path / "ACTIVE_DESIGN.md")
    assert _read(tmp_path / "ROADMAP.md") == _ROADMAP
