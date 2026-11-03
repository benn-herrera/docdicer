"""Unit tests for linkrewrite: what a link is, section references, link targets and their restoration."""

import io
from pathlib import Path
from typing import Optional

import pytest

from docdicer.dicerlib.linkrewrite import Linker, LinkMap, Tree, link_targets, rel
from docdicer.dicerlib.outline import Outline, plan_sections

# Diced as: entry-point.md (1-2), 1-alpha.md (3-5), 2-beta/index.md (6), 2-beta/the-walk-step.md (7),
# 2-beta/another-walk.md (8), 2-beta/2.1-gamma.md (9-10).
DOC = [
    "# Doc Title",
    "##### Top",
    "## 1. Alpha",
    "##### Notes",
    "##### Notes",
    "## 2. Beta",
    "### The `walk` step",
    "### Another `walk`",
    "### 2.1 Gamma",
    "##### Notes",
]

MAP = LinkMap(
    documents={"other.md": "vol/other/entry-point.md"},
    headings={("other.md", "The walk"): "vol/other/2-the-walk.md"},
)


def _linker(tmp_path: Path, link_map: Optional[LinkMap] = None) -> Linker:
    """A Linker for DOC diced into <tmp_path>/out, run from tmp_path."""
    sections, ok = plan_sections(DOC, err=io.StringIO())
    assert ok
    root = tmp_path.resolve()
    tree = Tree(
        out=str(root / "out"),
        outabs=str(root / "out"),
        root=str(root),
        link_map=LinkMap() if link_map is None else link_map,
    )
    return Linker(Outline(sections), tree, DOC)


@pytest.mark.parametrize(
    "line, targets",
    [
        pytest.param("see [a](b.md) here", ["b.md"], id="link"),
        pytest.param("![alt](img.png)", ["img.png"], id="image"),
        pytest.param("[a](b.md) and [c](d.md)", ["b.md", "d.md"], id="two-in-order"),
        pytest.param("[a](b(c).md)", ["b(c"], id="target-ends-at-first-paren"),
        pytest.param('[a](b.md "title")', ['b.md "title"'], id="title-not-interpreted"),
        pytest.param("[a](<b c.md>)", ["<b c.md>"], id="angle-brackets-not-interpreted"),
        pytest.param("\\[a](b.md)", ["b.md"], id="escape-not-interpreted"),
        pytest.param("[a][ref] and [ref]: b.md", [], id="reference-style-not-a-link"),
        pytest.param("<https://e.com/x>", [], id="autolink-not-a-link"),
        pytest.param("[a] (b.md)", [], id="space-before-paren"),
        pytest.param("`[a](b.md)` and [c](d.md)", ["d.md"], id="code-span"),
        pytest.param("``x ` [a](b.md)`` [c](d.md)", ["d.md"], id="code-span-closes-on-same-length-run"),
        pytest.param("x ` [a](b.md)", ["b.md"], id="unmatched-backtick-literal"),
    ],
)
def test_link_targets(line: str, targets: list[str]) -> None:
    assert link_targets(line) == targets


@pytest.mark.parametrize(
    "line, leaf_dir, expected",
    [
        pytest.param("see §1 now", "", "see [§1](1-alpha.md) now", id="linked"),
        pytest.param("see §1", "2-beta", "see [§1](../1-alpha.md)", id="linked-relative-to-file"),
        pytest.param("§2.1. Next", "", "[§2.1](2-beta/2.1-gamma.md). Next", id="maximal-length"),
        pytest.param("§2 `walk` runs", "", "[§2 `walk`](2-beta/the-walk-step.md) runs", id="named-child-first-wins"),
        pytest.param("§2 `walk`", "2-beta", "[§2 `walk`](the-walk-step.md)", id="named-child-from-sibling"),
        pytest.param("§2 `nope`", "", "[§2](2-beta/index.md) `nope`", id="named-child-absent"),
        pytest.param("§2  `walk`", "", "[§2](2-beta/index.md)  `walk`", id="name-not-directly-after"),
        pytest.param("§1 `walk`", "", "[§1](1-alpha.md) `walk`", id="name-of-no-direct-child"),
        pytest.param("SPEC §1", "", "SPEC §1", id="other-document-spec"),
        pytest.param("see ARCHITECTURE.md §1", "", "see ARCHITECTURE.md §1", id="other-document-md"),
        pytest.param("THESIS §2", "", "THESIS §2", id="other-document-thesis"),
        pytest.param("CONVENTIONS.md §2.1", "", "CONVENTIONS.md §2.1", id="other-document-conventions"),
        pytest.param("SPEC, §1", "", "SPEC, [§1](1-alpha.md)", id="other-document-not-adjacent"),
        pytest.param("§9 left", "", "§9 left", id="dangling"),
        pytest.param("`§1` code", "", "`§1` code", id="code-span"),
        pytest.param("[see §1](#nowhere)", "", "[see §1](#nowhere)", id="inside-link-text"),
    ],
)
def test_forward_section_references(tmp_path: Path, line: str, leaf_dir: str, expected: str) -> None:
    assert _linker(tmp_path).forward(line, leaf_dir, "") == expected


def test_forward_counts_linked_and_dangling_references(tmp_path: Path) -> None:
    linker = _linker(tmp_path)
    linker.forward("§1 and §9, SPEC §1", "", "")
    linker.forward("§9 then §2.3 and §2", "", "")
    assert linker.resolved == 2
    assert linker.dangling == {"9": 2, "2.3": 1}
    assert list(linker.dangling) == ["9", "2.3"]


@pytest.mark.parametrize(
    "line, leaf_dir, next_line, expected",
    [
        pytest.param("[t](#doc-title)", "", "", "[t](entry-point.md#doc-title)", id="entry-heading-keeps-anchor"),
        pytest.param("[t](#top)", "2-beta", "", "[t](../entry-point.md#top)", id="entry-heading-from-subdir"),
        pytest.param("[t](#1-alpha)", "", "", "[t](1-alpha.md)", id="heading-opening-leaf"),
        pytest.param("[t](#2-beta)", "2-beta", "", "[t](index.md)", id="heading-opening-index"),
        pytest.param("[t](#21-gamma)", "", "", "[t](2-beta/2.1-gamma.md)", id="heading-in-subdir"),
        pytest.param("[t](#notes-1)", "", "", "[t](1-alpha.md#notes-1)", id="repeat-within-file"),
        pytest.param("[t](#notes-2)", "2-beta", "", "[t](2.1-gamma.md#notes)", id="repeat-renumbered-per-file"),
        pytest.param("[t](#notes)", "2-beta", "", "[t](../1-alpha.md#notes)", id="anchor-from-subdir"),
        pytest.param("[t](#missing)", "2-beta", "", "[t](#missing)", id="unknown-fragment"),
        pytest.param("[t]()", "2-beta", "", "[t]()", id="empty"),
        pytest.param("[t](/abs/x.md)", "2-beta", "", "[t](/abs/x.md)", id="root-absolute"),
        pytest.param("[t](https://e.com/x.md)", "2-beta", "", "[t](https://e.com/x.md)", id="url"),
        pytest.param("[t](mailto:a@b.c)", "2-beta", "", "[t](mailto:a@b.c)", id="mailto"),
        pytest.param("[o](other.md)", "", "", "[o](../vol/other/entry-point.md)", id="map-entry-point"),
        pytest.param("[o](other.md#frag)", "", "", "[o](../vol/other/entry-point.md)", id="map-fragment-dropped"),
        pytest.param("[o](other.md)", "2-beta", "", "[o](../../vol/other/entry-point.md)", id="map-from-subdir"),
        pytest.param(
            '[o](other.md), "The walk" x', "", "", '[o](../vol/other/2-the-walk.md), "The walk" x', id="map-heading"
        ),
        pytest.param(
            '[o](other.md) "The walk"', "", "", '[o](../vol/other/2-the-walk.md) "The walk"', id="map-heading-no-comma"
        ),
        pytest.param(
            "[o](other.md),", "", '"The walk" next', "[o](../vol/other/2-the-walk.md),", id="map-heading-next-line"
        ),
        pytest.param(
            "[o](other.md) and", "", '"The walk"', "[o](../vol/other/entry-point.md) and", id="map-next-line-not-read"
        ),
        pytest.param(
            '[o](other.md), "Elsewhere"',
            "",
            "",
            '[o](../vol/other/entry-point.md), "Elsewhere"',
            id="map-heading-not-listed",
        ),
        pytest.param("[o](sub/other.md)", "", "", "[o](../sub/other.md)", id="map-key-must-equal-path"),
        pytest.param("[t](docs/x.md#sec)", "", "", "[t](../docs/x.md#sec)", id="rebased-fragment-kept"),
        pytest.param("[t](docs/x.md)", "2-beta", "", "[t](../../docs/x.md)", id="rebased-from-subdir"),
        pytest.param("[t](../up.md)", "", "", "[t](../../up.md)", id="rebased-parent"),
        pytest.param("![a](img.png)", "", "", "![a](../img.png)", id="image-rebased"),
        pytest.param("`[t](docs/x.md)`", "", "", "`[t](docs/x.md)`", id="code-span"),
    ],
)
def test_forward_link_targets(tmp_path: Path, line: str, leaf_dir: str, next_line: str, expected: str) -> None:
    assert _linker(tmp_path, MAP).forward(line, leaf_dir, next_line) == expected


@pytest.mark.parametrize(
    "from_dir, to, expected",
    [
        pytest.param("", "a.md", "a.md", id="root-to-root"),
        pytest.param("a", "a/b.md", "b.md", id="same-dir"),
        pytest.param("a/b", "c.md", "../../c.md", id="up-two"),
        pytest.param("a/b", "a/c/d.md", "../c/d.md", id="sibling-dir"),
        pytest.param("a", "a", "../a", id="file-named-like-the-dir"),
    ],
)
def test_rel(from_dir: str, to: str, expected: str) -> None:
    assert rel(from_dir, to) == expected


@pytest.mark.parametrize(
    "line, leaf_dir, expected",
    [
        pytest.param("[§1](1-alpha.md) x", "", "§1 x", id="section-link"),
        pytest.param("[§1](../1-alpha.md)", "2-beta", "§1", id="section-link-from-subdir"),
        pytest.param("[§2.1](2-beta/2.1-gamma.md).", "", "§2.1.", id="numbered-child-link"),
        pytest.param("[§2 `walk`](2-beta/the-walk-step.md) x", "", "§2 `walk` x", id="named-child-link"),
        pytest.param("[§1](elsewhere.md)", "", "[§1](out/elsewhere.md)", id="section-text-other-target"),
        pytest.param("[t](entry-point.md#doc-title)", "", "[t](#doc-title)", id="entry-heading"),
        pytest.param("[t](../entry-point.md#top)", "2-beta", "[t](#top)", id="entry-heading-from-subdir"),
        pytest.param("[t](1-alpha.md)", "", "[t](#1-alpha)", id="heading-opening-leaf"),
        pytest.param("[t](index.md)", "2-beta", "[t](#2-beta)", id="heading-opening-index"),
        pytest.param("[t](1-alpha.md#notes-1)", "", "[t](#notes-1)", id="repeat-within-file"),
        pytest.param("[t](2.1-gamma.md#notes)", "2-beta", "[t](#notes-2)", id="repeat-counted-over-document"),
        pytest.param("[t](1-alpha.md#nothing)", "", "[t](out/1-alpha.md#nothing)", id="not-a-heading-home"),
        pytest.param("[t](../docs/x.md#sec)", "", "[t](docs/x.md#sec)", id="rebased-fragment-kept"),
        pytest.param("[t](../../docs/x.md)", "2-beta", "[t](docs/x.md)", id="rebased-from-subdir"),
        pytest.param("[t](#frag)", "", "[t](#frag)", id="bare-fragment"),
        pytest.param("[t]()", "", "[t]()", id="empty"),
        pytest.param("[t](/abs.md)", "", "[t](/abs.md)", id="root-absolute"),
        pytest.param("[t](https://e.com)", "", "[t](https://e.com)", id="url"),
        pytest.param("`[§1](1-alpha.md)`", "", "`[§1](1-alpha.md)`", id="code-span"),
    ],
)
def test_restore(tmp_path: Path, line: str, leaf_dir: str, expected: str) -> None:
    assert _linker(tmp_path).restore(line, leaf_dir) == expected
