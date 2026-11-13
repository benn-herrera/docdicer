"""Unit tests for undice's stray-file check: which `.md` files under a tree are reported, and as what.

Each report is identified by the tree paths it carries: a file read as another section names it and
the path it would be re-diced as, a file that opens no section names it alone, an unread file names
it and the tree's entry point.
"""

import io
import re
from pathlib import Path
from typing import Optional

import pytest

from docdicer.dicerlib.dicedoc import _all_reproduced
from docdicer.dicerlib.outline import DEEPEST_SPLIT_LEVEL, plan_sections

# Planned as entry-point.md (line 1), alpha.md (lines 2-3), beta.md (line 4).
MONOLITH = ["# Doc", "## Alpha", "text", "## Beta"]
ASSIGNED = ["entry-point.md", "alpha.md", "beta.md"]


@pytest.mark.parametrize(
    "extra, reads, reports",
    [
        pytest.param([], [("alpha.md", 2), ("beta.md", 4)], [], id="all-assigned"),
        pytest.param(
            ["old.md"], [("old.md", 2), ("beta.md", 4)], [["old.md", "alpha.md"]], id="read-as-another-section"
        ),
        pytest.param(
            ["dup.md"], [("dup.md", 2), ("dup.md", 4)], [["dup.md", "alpha.md"]], id="read-twice-first-section-wins"
        ),
        pytest.param(
            ["dup.md"], [("dup.md", 3), ("dup.md", 4)], [["dup.md", "beta.md"]], id="read-twice-first-opening-wins"
        ),
        pytest.param(["extra.md"], [("alpha.md", 2), ("extra.md", 3)], [["extra.md"]], id="read-mid-section"),
        pytest.param(["empty.md"], [("empty.md", None)], [["empty.md"]], id="read-empty"),
        pytest.param(["stray.md"], [], [["stray.md", "entry-point.md"]], id="not-read"),
        pytest.param(
            ["a.md", "b.md"], [], [["a.md", "entry-point.md"], ["b.md", "entry-point.md"]], id="each-stray-reported"
        ),
        pytest.param(["sub/y.md"], [], [["sub/y.md", "entry-point.md"]], id="subdirectory-without-entry-point"),
        pytest.param(["vol/entry-point.md", "vol/x.md", "vol/sub/y.md"], [], [], id="nested-volume-exempt"),
        pytest.param(["img.png"], [], [], id="not-markdown"),
    ],
)
def test_all_reproduced(
    tmp_path: Path, extra: list[str], reads: list[tuple[str, Optional[int]]], reports: list[list[str]]
) -> None:
    out = tmp_path / "out"
    for name in ASSIGNED + extra:
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_text("x\n", encoding="utf-8")
    sections, ok = plan_sections(MONOLITH, err=io.StringIO())
    assert ok
    err = io.StringIO()

    passed = _all_reproduced(str(out), sections, reads, err=err, deepest=DEEPEST_SPLIT_LEVEL)

    assert passed == (not reports)
    reported = [re.findall(r"\S+\.md\b", line) for line in err.getvalue().splitlines()]
    assert sorted(reported) == sorted([f"{out}/{path}" for path in report] for report in reports)
