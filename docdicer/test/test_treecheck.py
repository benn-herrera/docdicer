"""Unit tests for check_tree: each document linked from its parent and reachable from the entry point."""

import io
import re
from pathlib import Path

import pytest

from docdicer.dicerlib.treecheck import check_tree


def _tree(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")


def _paths(root: Path, line: str) -> list[str]:
    """The tree paths a report carries, in order, relative to the root."""
    prefix = f"{root}/"
    return [p[len(prefix) :] for p in re.findall(re.escape(prefix) + r"\S+\.md\b", line)]


@pytest.mark.parametrize(
    "files, reports",
    [
        pytest.param(
            {
                "entry-point.md": "[a](a.md) [s](sub/index.md)\n",
                "a.md": "x\n",
                "sub/index.md": "[x](x.md)\n",
                "sub/x.md": "x\n",
            },
            [],
            id="clean",
        ),
        pytest.param({"entry-point.md": "[x](sub/x.md)\n", "sub/x.md": "x\n"}, [["sub/x.md"]], id="no-parent-document"),
        pytest.param(
            {"entry-point.md": "[s](sub/index.md) [x](sub/x.md)\n", "sub/index.md": "none\n", "sub/x.md": "x\n"},
            [["sub/x.md", "sub/index.md"]],
            id="not-linked-from-parent",
        ),
    ],
)
def test_check_tree(tmp_path: Path, files: dict[str, str], reports: list[list[str]]) -> None:
    root = tmp_path / "tree"
    _tree(root, files)
    err = io.StringIO()

    _, problems = check_tree(str(root), err=err)

    assert problems == len(reports)
    assert sorted(_paths(root, line) for line in err.getvalue().splitlines()) == sorted(reports)


def test_unreachable_documents_reported_below_the_unlinked_one(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    _tree(root, {"entry-point.md": "none\n", "sub/index.md": "[x](x.md)\n", "sub/x.md": "x\n"})
    err = io.StringIO()

    _, problems = check_tree(str(root), err=err)

    assert problems == 3
    reported = [(_paths(root, line), "not reachable from" in line) for line in err.getvalue().splitlines()]
    assert sorted(reported) == sorted(
        [
            (["sub/index.md", "entry-point.md"], False),
            (["sub/index.md", "entry-point.md"], True),
            (["sub/x.md", "entry-point.md"], True),
        ]
    )


def test_root_without_entry_point_is_one_problem(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    _tree(root, {"index.md": "[a](a.md)\n", "a.md": "x\n"})
    err = io.StringIO()

    _, problems = check_tree(str(root), err=err)

    assert problems == 1
    lines = err.getvalue().splitlines()
    assert len(lines) == 1 and str(root) in lines[0]
