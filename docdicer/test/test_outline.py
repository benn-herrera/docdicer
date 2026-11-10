import io
import re

import pytest

from docdicer.dicerlib.outline import Outline, plan_sections, section_name, slug, split_number


def _numbers(line):
    """The line's standalone numbers in order: not part of a word, a dotted number or `level-1`."""
    return re.findall(r"(?<![\w.-])\d+(?![\w.-])", line)


def _plan(lines):
    err = io.StringIO()
    sections, ok = plan_sections(lines, err=err)
    return sections, ok, err.getvalue().splitlines()


def _layout(sections):
    """(path, parent path, first, last) of each section."""
    return [(s.path, sections[s.parent].path if s.id else None, s.first, s.last) for s in sections]


@pytest.mark.parametrize(
    "title, expected",
    [
        pytest.param("Hello World", "hello-world", id="ascii-lowered-space-separator"),
        pytest.param("a`b`c", "abc", id="backticks-deleted"),
        pytest.param("a -- b", "a-b", id="separator-run-collapsed"),
        pytest.param("snake_case", "snake-case", id="underscore-is-separator"),
        pytest.param("(Intro)!", "intro", id="edges-trimmed"),
        pytest.param("Rule 42", "rule-42", id="digits-kept"),
        pytest.param("Café au lait", "caf-au-lait", id="non-ascii-is-separator"),
        pytest.param("Kelvin", "elvin", id="kelvin-sign-not-lowered-to-k"),
        pytest.param("***", "", id="all-separators-empty"),
    ],
)
def test_slug(title, expected):
    assert slug(title) == expected


@pytest.mark.parametrize(
    "text, number, title",
    [
        pytest.param("1. Intro", "1", "Intro", id="trailing-dot-dropped"),
        pytest.param("2 Setup", "2", "Setup", id="no-trailing-dot"),
        pytest.param("1.1.1. Deep", "1.1.1", "Deep", id="dotted-groups"),
        pytest.param("4.2 Deep", "4.2", "Deep", id="dotted-groups-no-trailing-dot"),
        pytest.param("1.Intro", "", "1.Intro", id="no-space-unnumbered"),
        pytest.param("2024", "", "2024", id="digits-alone-unnumbered"),
        pytest.param("v1. Intro", "", "v1. Intro", id="letter-first-unnumbered"),
        pytest.param("1..2 X", "", "1..2 X", id="empty-group-unnumbered"),
    ],
)
def test_split_number(text, number, title):
    assert split_number(text) == (number, title)


@pytest.mark.parametrize(
    "text, name",
    [
        pytest.param("1.2. Deep Dive", "1.2-deep-dive", id="numbered"),
        pytest.param("3. ä", "3", id="numbered-empty-slug"),
        pytest.param("Deep Dive", "deep-dive", id="unnumbered"),
        pytest.param("ä", "", id="unnumbered-empty-slug"),
    ],
)
def test_section_name(text, name):
    assert section_name(text) == name


def test_split_levels_and_parents():
    lines = [
        "# Doc",  # 1
        "intro",  # 2
        "## A",  # 3
        "### B",  # 4
        "#### C",  # 5
        "##### D",  # 6
        "###### E",  # 7
        "## F",  # 8
        "#### G",  # 9
        "### H",  # 10
        "#### I",  # 11
        "### J",  # 12
    ]
    sections, ok, err = _plan(lines)
    assert ok and err == []
    assert _layout(sections) == [
        ("entry-point.md", None, 1, 2),
        ("a/index.md", "entry-point.md", 3, 3),
        ("a/b/index.md", "a/index.md", 4, 4),
        ("a/b/c.md", "a/b/index.md", 5, 7),
        ("f/index.md", "entry-point.md", 8, 8),
        ("f/g.md", "f/index.md", 9, 9),
        ("f/h/index.md", "f/index.md", 10, 10),
        ("f/h/i.md", "f/h/index.md", 11, 11),
        ("f/j.md", "f/index.md", 12, 12),
    ]


def test_parent_is_root_without_a_lower_level_heading():
    sections, ok, _ = _plan(["### X", "text", "## Y"])
    assert ok
    assert [(s.path, s.parent) for s in sections[1:]] == [("x.md", 0), ("y.md", 0)]
    assert (sections[1].first, sections[1].last) == (1, 2)


def test_non_headings_do_not_split():
    lines = [
        "# Doc",
        "####### Seven",
        "##NoSpace",
        "##\tTab",
        "##",
        " ## Indented",
        "```",
        "## Fenced",
        "```",
    ]
    sections, ok, err = _plan(lines)
    assert ok and err == []
    assert _layout(sections) == [("entry-point.md", None, 1, 9)]


def test_extra_level_1_heading_kept_as_text_and_reported():
    lines = ["# Doc", "## A", "text", "text", "text", "# Again", "more"]
    sections, ok, err = _plan(lines)
    assert ok
    assert _layout(sections) == [("entry-point.md", None, 1, 1), ("a.md", "entry-point.md", 2, 7)]
    assert len(err) == 1 and _numbers(err[0]) == ["6"]


def test_first_level_1_heading_is_the_title_wherever_it_sits():
    sections, ok, err = _plan(["preface", "# Doc", "body"])
    assert ok and err == []
    assert _layout(sections) == [("entry-point.md", None, 1, 3)]


def test_numbers_titles_and_names():
    lines = [
        "# Doc",
        "## 1. Intro   ",
        "### 1.1 Scope",
        "## 2 Setup Steps",
        "## 3. ***",
        "## Notes",
        "## 4.1.2. Deep",
    ]
    sections, ok, err = _plan(lines)
    assert ok and err == []
    assert [(s.path, s.number, s.title) for s in sections[1:]] == [
        ("1-intro/index.md", "1", "Intro"),
        ("1-intro/1.1-scope.md", "1.1", "Scope"),
        ("2-setup-steps.md", "2", "Setup Steps"),
        ("3.md", "3", "***"),
        ("notes.md", "", "Notes"),
        ("4.1.2-deep.md", "4.1.2", "Deep"),
    ]


def test_leading_spaces_after_the_hash_run_are_ignored():
    sections, ok, _ = _plan(["# Doc", "##   1. X"])
    assert ok
    assert (sections[1].path, sections[1].number, sections[1].title) == ("1-x.md", "1", "X")


def test_collisions_each_reported_against_previous_holder():
    lines = ["# Doc", "## A", "## a", "text", "## A!"]
    _, ok, err = _plan(lines)
    assert not ok
    assert len(err) == 2
    assert "a.md" in err[0] and _numbers(err[0]) == ["2", "3"]
    assert "a.md" in err[1] and _numbers(err[1]) == ["3", "5"]


def test_empty_slug_reported_for_first_heading_only():
    lines = ["# Doc", "## A", "## ***", "text", "## ???"]
    _, ok, err = _plan(lines)
    assert not ok
    assert len(err) == 1 and _numbers(err[0]) == ["3"]


def test_duplicate_numbers_listed_once_each_in_order_of_first_repeat():
    lines = ["# Doc", "## 2. A", "## 1. B", "## 1. C", "## 2. D", "## 1. E"]
    sections, ok, _ = _plan(lines)
    assert ok
    assert Outline(sections).duplicate_numbers == ["1", "2"]


def test_link_text_takes_nearest_numbered_ancestor():
    lines = [
        "# Doc",
        "## 1. Intro",
        "### Scope",
        "#### Detail",
        "### 1.1 Rules",
        "## Notes",
        "### Aside",
        "### 2. Sub",
    ]
    sections, ok, _ = _plan(lines)
    assert ok
    outline = Outline(sections)
    assert [outline.link_text(s.id) for s in sections[1:]] == [
        "§1 Intro",
        "§1 Scope",
        "§1 Detail",
        "§1.1 Rules",
        "Notes",
        "Aside",
        "§2 Sub",
    ]
