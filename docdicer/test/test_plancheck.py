"""Unit tests for check_plan, check_design and check_roadmap: which document each checks with no
argument, their exit statuses, and the values each breach message carries."""

import errno
import io
import os
from pathlib import Path

import pytest

from docdicer.kanban import plancheck, planform
from docdicer.kanban.plancheck import check_design, check_plan, check_roadmap
from docdicer.kanban.planform import BreachKind, read_design, read_plan, read_roadmap

_TABLE = "| Package | State | Rating |\n|---|---|---|\n"
_CONFORMING = "# Plan\n\n## Status\n\n" + _TABLE + "| P1 | landed | expert |\n"
_BREACHING = "# Plan\n\n## Status\n\n" + _TABLE + "| P1 | done | expert |\n"


def _write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")


def _run(plan, start: str = "") -> tuple[int, str, str]:
    """check_plan's status, stdout and stderr, run from start."""
    out, err = io.StringIO(), io.StringIO()
    status = check_plan(plan, start=start, stdout=out, stderr=err)
    return status, out.getvalue(), err.getvalue()


@pytest.mark.parametrize(
    "files, checked, status",
    [
        pytest.param({"ACTIVE_PLAN.md": _BREACHING}, "ACTIVE_PLAN.md", 1, id="monolith"),
        pytest.param({"ACTIVE_PLAN/entry-point.md": _BREACHING}, "ACTIVE_PLAN/entry-point.md", 1, id="tree"),
        pytest.param(
            {"ACTIVE_PLAN.md": _BREACHING, "ACTIVE_PLAN/entry-point.md": _CONFORMING},
            "ACTIVE_PLAN.md",
            1,
            id="both-monolith-read",
        ),
    ],
)
def test_default_is_the_active_plan(tmp_path, files, checked, status):
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    (project / "sub").mkdir()
    _write(project, files)

    got, out, err = _run(None, start=str(project / "sub"))

    assert got == status
    assert str(project / checked) in out
    assert str(project / checked) in err


def test_no_active_plan_passes(tmp_path):
    (tmp_path / ".git").mkdir()
    _write(tmp_path, {"ACTIVE_DESIGN.md": _BREACHING, "ACTIVE_PLAN/status.md": _BREACHING})

    status, out, err = _run(None, start=str(tmp_path))

    assert (status, err) == (0, "")
    assert str(tmp_path) in out


def test_no_project_root_is_refused(tmp_path, monkeypatch):
    _write(tmp_path, {"ACTIVE_PLAN.md": _BREACHING})
    monkeypatch.setattr(planform.os.path, "lexists", lambda path: False)

    status, out, err = _run(None, start=str(tmp_path))

    assert (status, out) == (2, "")
    assert str(tmp_path) in err


@pytest.mark.parametrize(
    "text, kind",
    [
        pytest.param(
            "## Status\n\n" + _TABLE + "| P1 | | expert |\n| P1 | | expert |\n",
            BreachKind.ID_REPEATED,
            id="id-repeated",
        ),
        pytest.param("## Status\n\n" + _TABLE + "| P 1 | | expert |\n", BreachKind.ID_SPACE, id="id-space"),
        pytest.param("## Status\n\n" + _TABLE + "| P1 | Landed | expert |\n", BreachKind.STATE_WORD, id="state-word"),
        pytest.param("# Plan\n\nIntro.\n\nRelease: 1\n", BreachKind.RELEASE_MISPLACED, id="release-misplaced"),
        pytest.param("# Plan\n\nRelease:\n", BreachKind.RELEASE_EMPTY, id="release-empty"),
        pytest.param(
            "## Status\n\n| Package | State |\n|---|---|\n| P1 | landed |\n",
            BreachKind.RATING_MISSING,
            id="rating-missing",
        ),
        pytest.param("## Status\n\n" + _TABLE + "| P1 | | high |\n", BreachKind.RATING_WORD, id="rating-word"),
        pytest.param(
            "## Status\n\n" + _TABLE + "| P1 | | expert |\n\n## P1 — Post-plan review\n",
            BreachKind.REVIEW_UNPAIRED,
            id="review-unpaired",
        ),
        pytest.param(
            "## Status\n\n" + _TABLE + "| P1 | | expert |\n\n## P1 — Post-plan burndown\n",
            BreachKind.BURNDOWN_UNPAIRED,
            id="burndown-unpaired",
        ),
    ],
)
def test_breach_message_carries_file_line_found_and_accepted(tmp_path, text, kind):
    _write(tmp_path, {"plan.md": text})
    plan = str(tmp_path / "plan.md")
    (breach,) = read_plan(plan).breaches
    assert breach.kind == kind

    status, out, err = _run(plan)

    assert status == 1
    (line,) = err.splitlines()
    assert f"{plan}:{breach.line}" in line
    assert breach.found in line
    assert breach.accepted in line
    assert plan in out


@pytest.mark.parametrize(
    "row, found",
    [
        pytest.param("| P1 | a`b | expert |", "found `` a`b ``", id="backtick-in-the-text"),
        pytest.param("| P1 | | |", "found an empty cell", id="empty-cell"),
    ],
)
def test_found_text_is_quoted_whole(tmp_path, row, found):
    _write(tmp_path, {"plan.md": "## Status\n\n" + _TABLE + row + "\n"})

    status, _, err = _run(str(tmp_path / "plan.md"))

    assert status == 1
    (line,) = err.splitlines()
    assert found in line


def test_a_read_failure_naming_no_file_names_the_plan(tmp_path, monkeypatch):
    plan = str(tmp_path / "plan.md")
    _write(tmp_path, {"plan.md": _CONFORMING})

    def read_fails(_path):
        raise OSError(errno.EIO, os.strerror(errno.EIO))

    monkeypatch.setattr(plancheck, "read_plan", read_fails)
    status, out, err = _run(plan)

    assert (status, out) == (2, "")
    assert plan in err


_DESIGN_BREACHING = "# Design\n\n## Background\n"


def _run_design(design, start: str = "") -> tuple[int, str, str]:
    """check_design's status, stdout and stderr, run from start."""
    out, err = io.StringIO(), io.StringIO()
    status = check_design(design, start=start, stdout=out, stderr=err)
    return status, out.getvalue(), err.getvalue()


def test_default_is_the_active_design(tmp_path):
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    (project / "sub").mkdir()
    _write(project, {"ACTIVE_DESIGN.md": _DESIGN_BREACHING})

    status, out, err = _run_design(None, start=str(project / "sub"))

    assert status == 1
    assert str(project / "ACTIVE_DESIGN.md") in out
    assert str(project / "ACTIVE_DESIGN.md") in err


def test_no_active_design_passes(tmp_path):
    (tmp_path / ".git").mkdir()
    _write(tmp_path, {"ACTIVE_PLAN.md": _DESIGN_BREACHING, "ACTIVE_DESIGN/leaf.md": _DESIGN_BREACHING})

    status, out, err = _run_design(None, start=str(tmp_path))

    assert (status, err) == (0, "")
    assert str(tmp_path) in out


def test_no_project_root_is_refused_for_a_design(tmp_path, monkeypatch):
    _write(tmp_path, {"ACTIVE_DESIGN.md": _DESIGN_BREACHING})
    monkeypatch.setattr(planform.os.path, "lexists", lambda path: False)

    status, out, err = _run_design(None, start=str(tmp_path))

    assert (status, out) == (2, "")
    assert str(tmp_path) in err


def test_an_unreadable_contents_target_is_refused(tmp_path):
    _write(tmp_path, {"d/entry-point.md": _DESIGN_BREACHING + "\nContents:\n\n- [gone](gone.md)\n"})

    status, out, err = _run_design(str(tmp_path / "d/entry-point.md"))

    assert (status, out) == (2, "")
    assert str(tmp_path / "d/gone.md") in err


def test_design_breach_message_carries_file_line_found_and_accepted(tmp_path):
    _write(tmp_path, {"design.md": "## Background\n\n## SPEC delta\n"})
    design = str(tmp_path / "design.md")
    (breach,) = read_design(design).breaches
    assert set(plancheck._PROBLEMS) == set(BreachKind)

    status, out, err = _run_design(design)

    assert status == 1
    (line,) = err.splitlines()
    assert f"{design}:{breach.line}" in line
    assert breach.found in line
    assert breach.accepted in line
    assert design in out


def test_an_empty_found_line_is_named(tmp_path):
    _write(tmp_path, {"design.md": "\nText.\n"})

    status, _, err = _run_design(str(tmp_path / "design.md"))

    assert status == 1
    (line,) = err.splitlines()
    assert "found an empty line" in line


_ROADMAP_BREACHING = "# Roadmap\n"


def _run_roadmap(roadmap, start: str = "") -> tuple[int, str, str]:
    """check_roadmap's status, stdout and stderr, run from start."""
    out, err = io.StringIO(), io.StringIO()
    status = check_roadmap(roadmap, start=start, stdout=out, stderr=err)
    return status, out.getvalue(), err.getvalue()


def test_default_is_the_projects_roadmap(tmp_path):
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    (project / "sub").mkdir()
    _write(project, {"ROADMAP.md": _ROADMAP_BREACHING})

    status, out, err = _run_roadmap(None, start=str(project / "sub"))

    assert status == 1
    assert str(project / "ROADMAP.md") in out
    assert str(project / "ROADMAP.md") in err


@pytest.mark.parametrize(
    "files",
    [
        pytest.param(
            {"ROADMAP/entry-point.md": _ROADMAP_BREACHING, "ACTIVE_DESIGN.md": _ROADMAP_BREACHING}, id="absent"
        ),
        pytest.param({"ROADMAP.md/entry-point.md": _ROADMAP_BREACHING}, id="a-directory"),
    ],
)
def test_no_roadmap_passes(tmp_path, files):
    (tmp_path / ".git").mkdir()
    _write(tmp_path, files)

    status, out, err = _run_roadmap(None, start=str(tmp_path))

    assert (status, err) == (0, "")
    assert str(tmp_path) in out


def test_no_project_root_is_refused_for_a_roadmap(tmp_path, monkeypatch):
    _write(tmp_path, {"ROADMAP.md": _ROADMAP_BREACHING})
    monkeypatch.setattr(planform.os.path, "lexists", lambda path: False)

    status, out, err = _run_roadmap(None, start=str(tmp_path))

    assert (status, out) == (2, "")
    assert str(tmp_path) in err
    assert "docdicer check-roadmap" in err


def test_a_roadmap_that_cannot_be_read_is_named(tmp_path):
    roadmap = tmp_path / "roadmap.md"
    roadmap.mkdir()

    status, out, err = _run_roadmap(str(roadmap))

    assert (status, out) == (2, "")
    assert str(roadmap) in err


@pytest.mark.parametrize(
    "text, kind",
    [
        pytest.param("### t\n\n## C\n", BreachKind.TICKET_OUTSIDE, id="ticket-outside"),
        pytest.param("## C\n\n- **Old** item\n", BreachKind.OLD_FORM_ITEM, id="old-form-item"),
        pytest.param("## C\n\n### \n", BreachKind.TICKET_EMPTY, id="ticket-empty"),
        pytest.param("# Roadmap\n", BreachKind.NO_CATEGORY, id="no-category"),
    ],
)
def test_roadmap_breach_message_carries_file_line_found_and_accepted(tmp_path, text, kind):
    _write(tmp_path, {"roadmap.md": text})
    roadmap = str(tmp_path / "roadmap.md")
    (breach,) = read_roadmap(roadmap).breaches
    assert breach.kind == kind

    status, out, err = _run_roadmap(roadmap)

    assert status == 1
    (line,) = err.splitlines()
    assert f"{roadmap}:{breach.line}" in line
    assert breach.found in line
    assert breach.accepted in line
    assert roadmap in out
