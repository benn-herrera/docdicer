"""Unit tests for refactor: bold-line classification, run-in conversion, the keep list, long titles
and the self-check."""

import re

import pytest

from docdicer.dicerlib.refactor import _classify, check_hunks, convert_runins, list_runins


def _numbers(line: str) -> list[str]:
    """The line's standalone numbers in order: not part of a word or a dotted number."""
    return re.findall(r"(?<![\w.-])\d+(?![\w.-])", line)


NINE_WORDS = "one two three four five six seven eight nine"
EIGHT_WORDS = "one two three four five six seven eight"


@pytest.mark.parametrize(
    "line, prev_blank, cls",
    [
        pytest.param("plain text", True, "", id="not-bold"),
        pytest.param("*em* text", True, "", id="single-star"),
        pytest.param("****x text", True, "", id="star-after-bold-marker"),
        pytest.param("***x*** text", True, "LABEL", id="star-bullet-then-bold"),
        pytest.param("- **T.** body", True, "ITEM", id="item-dot"),
        pytest.param("- **T:** body", False, "ITEM", id="item-before-mid"),
        pytest.param("- **T** body", True, "LIST", id="item-without-mark"),
        pytest.param("- **a*b.** body", True, "LIST", id="item-title-with-star"),
        pytest.param("  **T.** body", True, "LIST", id="space-indented"),
        pytest.param("\t**T.** body", True, "LIST", id="tab-indented"),
        pytest.param("  **T.** body", False, "LIST", id="list-before-mid"),
        pytest.param("+ **T.** body", True, "LIST", id="plus-bullet"),
        pytest.param("1. **T.** body", True, "LIST", id="numbered-dot"),
        pytest.param("1) **T.** body", True, "LIST", id="numbered-paren"),
        pytest.param("**T.** body", False, "MID", id="mid"),
        pytest.param("**T.** body", True, "RUNIN", id="runin-dot"),
        pytest.param("**T:** body", True, "RUNIN", id="runin-colon"),
        pytest.param("**Whole line**", True, "RUNIN", id="runin-whole-line"),
        pytest.param("**Note** that", True, "LABEL", id="label-not-runin"),
        pytest.param("**Title**.", True, "LABEL", id="mark-outside-bold"),
        pytest.param("* **T.** body", True, "LABEL", id="star-bullet"),
        pytest.param("-**T.** body", True, "LABEL", id="dash-without-space"),
    ],
)
def test_classify(line: str, prev_blank: bool, cls: str) -> None:
    assert _classify(line, prev_blank=prev_blank)[0] == cls


@pytest.mark.parametrize(
    "line, title",
    [
        pytest.param("**T.** body", "T", id="dot-stripped"),
        pytest.param("**T:** body", "T", id="colon-stripped"),
        pytest.param("**Whole line**", "Whole line", id="whole-line"),
        pytest.param("**T..** body", "T.", id="one-mark-stripped"),
        pytest.param("**a.b.** body", "a.b", id="inner-dot-kept"),
        pytest.param("- **Item:** body", "Item", id="item"),
    ],
)
def test_runin_title(line: str, title: str) -> None:
    assert _classify(line, prev_blank=True)[1] == title


@pytest.mark.parametrize(
    "lines, items, keep, converted, notes",
    [
        pytest.param(["## S", "", "**T.**   body"], False, [], ["## S", "", "### T", "", "body"], [], id="runin"),
        pytest.param(["## S", "", "**T:** body"], False, [], ["## S", "", "### T", "", "body"], [], id="runin-colon"),
        pytest.param(
            ["## S", "", "**Whole title**", "", "x"],
            False,
            [],
            ["## S", "", "### Whole title", "", "x"],
            [],
            id="whole-line-no-text",
        ),
        pytest.param(["### S", "", "**T.** b"], False, [], ["### S", "", "#### T", "", "b"], [], id="level-plus-one"),
        pytest.param(
            ["###### S", "", "**T.** b"], False, [], ["###### S", "", "###### T", "", "b"], [], id="capped-at-six"
        ),
        pytest.param(
            ["## A", "### B", "## C", "", "**T.** b"],
            False,
            [],
            ["## A", "### B", "## C", "", "### T", "", "b"],
            [],
            id="last-heading-encloses",
        ),
        pytest.param(["**T.** b"], False, [], ["**T.** b"], [], id="before-any-heading"),
        pytest.param(["# D", "", "**T.** b"], False, [], ["# D", "", "**T.** b"], [], id="under-level-one"),
        pytest.param(["## S", "text", "**T.** b"], False, [], ["## S", "text", "**T.** b"], [], id="mid"),
        pytest.param(["## S", "**T.** b"], False, [], ["## S", "**T.** b"], [], id="after-heading-is-mid"),
        pytest.param(
            ["## S", "", "```", "**T.** b", "```"], False, [], ["## S", "", "```", "**T.** b", "```"], [], id="fenced"
        ),
        pytest.param(
            ["## S", "", "- **T.** a", "  b"], False, [], ["## S", "", "- **T.** a", "  b"], [], id="item-without-items"
        ),
        pytest.param(
            ["## S", "", "- **T.** a", "  b", "", "    c", "  **U.** v", " d"],
            True,
            [],
            ["## S", "", "### T", "", "a", "b", "", "  c", "**U.** v", " d"],
            [],
            id="item-continuation-dedented",
        ),
        pytest.param(
            ["## S", "", "- **T:**", "x"], True, [], ["## S", "", "### T", "", "x"], [], id="item-blank-without-text"
        ),
        pytest.param(["## S", "", "**T.** b"], False, ["T"], ["## S", "", "**T.** b"], [], id="keep"),
        pytest.param(
            ["## S", "", "**T.** b"], False, ["t"], ["## S", "", "### T", "", "b"], [], id="keep-case-sensitive"
        ),
        pytest.param(["## S", "", "**T.** b"], False, ["T b"], ["## S", "", "### T", "", "b"], [], id="keep-exact"),
        pytest.param(
            ["## S", "", "- **T.** a", "  b"], True, ["T"], ["## S", "", "- **T.** a", "  b"], [], id="keep-item"
        ),
        pytest.param(
            ["## S", "", f"**{NINE_WORDS}.** b"],
            False,
            [],
            ["## S", "", f"**{NINE_WORDS}.** b"],
            [f"skipped long: line 3: {NINE_WORDS}"],
            id="long-title",
        ),
        pytest.param(
            ["## S", "", f"**{EIGHT_WORDS}.** b"],
            False,
            [],
            ["## S", "", f"### {EIGHT_WORDS}", "", "b"],
            [],
            id="eight-words-converted",
        ),
        pytest.param(
            ["## S", "", "**one\ttwo three four five six seven eight nine**"],
            False,
            [],
            ["## S", "", "**one\ttwo three four five six seven eight nine**"],
            ["skipped long: line 3: one\ttwo three four five six seven eight nine"],
            id="tab-separates-words",
        ),
        pytest.param(
            ["## S", "", "x", "", f"- **{NINE_WORDS}:** b"],
            True,
            [],
            ["## S", "", "x", "", f"- **{NINE_WORDS}:** b"],
            [f"skipped long: line 5: {NINE_WORDS}"],
            id="long-item",
        ),
    ],
)
def test_convert_runins(lines: list[str], items: bool, keep: list[str], converted: list[str], notes: list[str]) -> None:
    assert convert_runins(lines, items=items, keep=keep) == (converted, notes)


@pytest.mark.parametrize(
    "lines, keep, classes",
    [
        pytest.param(["# D", "", "**T.** b"], [], [(3, "RUNIN-OUTSIDE-SECTION")], id="runin-under-level-one"),
        pytest.param(["# D", "", "- **T.** b"], [], [(3, "ITEM-OUTSIDE-SECTION")], id="item-under-level-one"),
        pytest.param(["## S", "", "**T.** b"], [], [(3, "RUNIN")], id="runin"),
        pytest.param(["## S", "", "- **T.** b"], [], [(3, "ITEM")], id="item-listed-without-items"),
        pytest.param(["## S", "", "**T.** b"], ["T"], [(3, "KEEP")], id="keep"),
        pytest.param(["## S", "", "- **T.** b"], ["T"], [(3, "KEEP")], id="keep-item"),
        pytest.param(["## S", "", f"**{NINE_WORDS}.** b"], [], [(3, "RUNIN(long)")], id="long-runin"),
        pytest.param(["## S", "", f"- **{NINE_WORDS}.** b"], [], [(3, "ITEM(long)")], id="long-item"),
        pytest.param(["## S", "", "```", "**T.** b", "```"], [], [], id="fenced"),
        pytest.param(["## **T.**", "", "x"], [], [], id="heading-line"),
        pytest.param(["## S", "", "- **T.** b", "  **U.** c"], [], [(3, "ITEM")], id="item-continuation-unreported"),
        pytest.param(
            ["## S", "", "- **T** b", "", "**N** that", "x", "**M.** y"],
            [],
            [(3, "LIST"), (5, "LABEL"), (7, "MID")],
            id="other-classes",
        ),
    ],
)
def test_list_classes(lines: list[str], keep: list[str], classes: list[tuple[int, str]]) -> None:
    rows = [row.split("\t") for row in list_runins(lines, name="doc.md", keep=keep)]
    assert [(row[0], row[1]) for row in rows] == [(f"doc.md:{no}", cls) for no, cls in classes]


def test_self_check() -> None:
    count, bad = check_hunks("## S\n\n**T.** body\n\nplain\n", "## S\n\n### T\n\nbody, edited\n\nplain\n")
    assert count == 1
    assert len(bad) == 1
    assert _numbers(bad[0]) == ["3"]
    assert "**T.** body" in bad[0]


@pytest.mark.parametrize(
    "old, new, count",
    [
        pytest.param("## S\n\nplain\n", "## S\n\nplain\n", 0, id="unchanged"),
        pytest.param("## S\n\n**T.** body\n\nplain\n", "## S\n\n### T\n\nbody\n\nplain\n", 1, id="runin"),
        pytest.param("## S\n\n- **T.** a\n  b\nx\n", "## S\n\n### T\n\na\nb\nx\n", 1, id="item-with-continuation"),
        pytest.param("## S\n\n**A**\n\n\n\n**B**\n", "## S\n\n### A\n\n\n\n### B\n", 1, id="three-blank-lines-merge"),
        pytest.param(
            "## S\n\n**A**\n\n\n\n\n**B**\n", "## S\n\n### A\n\n\n\n\n### B\n", 2, id="four-blank-lines-split"
        ),
        pytest.param("## S\n\n**A**\n\nx\n\n**B**\n", "## S\n\n### A\n\nx\n\n### B\n", 2, id="text-between-splits"),
    ],
)
def test_self_check_passes_conversions(old: str, new: str, count: int) -> None:
    assert check_hunks(old, new) == (count, [])


def test_self_check_reports_each_bad_hunk_at_its_old_line() -> None:
    count, bad = check_hunks("## S\n\n**A**\n\nx\n\nzeta\n", "## S\n\n### A\n\nx\n\neta\n")
    assert count == 2
    assert len(bad) == 1
    assert _numbers(bad[0]) == ["7"]
    assert "zeta" in bad[0]
