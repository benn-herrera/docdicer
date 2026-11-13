r"""End-to-end tests for docdicer.

Each case under data/ is one test: the CLI runs as a subprocess in a copy of the case's input/,
made in the test's tmp_path, with the arguments in `args` (one per line). The exit status and
every file of expected/tree/ must match byte for byte. expected/names asserts the values the output
carries, never its wording: each of its lines is an entry `<stream>[\t<name>...]`, <stream> being
stdout or stderr, and each entry stands for one line of that stream. A stream must end in a newline
unless empty, and must have exactly as many lines as it has entries, each entry given a distinct
line it matches; a stream with no entries is empty. An entry with no names matches any line;
otherwise its names are found in the line left to right, each as a whole token (no ASCII letter or
digit beside it, nor a `.` or `-` joined to one), compared as UTF-8 bytes with surrogateescape.

COLUMNS is set wide so that argparse never wraps a usage line. Cases are written from SPEC.md.

Each case that dices without a map and exits 0 is also a round-trip test: its tree, undiced and
then diced again from the same run directory at the case's `--split-level`, comes back byte for
byte.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

MODULE = "docdicer"
HERE = Path(__file__).resolve().parent
TESTDATA = HERE / "data"


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _case_env(case: Path) -> dict[str, str]:
    return {**os.environ, "COLUMNS": "1000"}


def _cases() -> list[Path]:
    return sorted(p for p in TESTDATA.iterdir() if p.is_dir())


def _args(case: Path) -> list[str]:
    return (case / "args").read_text(encoding="utf-8").splitlines()


def _split_level_apart(args: list[str]) -> tuple[list[str], list[str]]:
    """args' `--split-level <level>`, empty where they hold none, and the other args in order."""
    if "--split-level" not in args:
        return [], args
    at = args.index("--split-level")
    return args[at : at + 2], args[:at] + args[at + 2 :]


def _round_trip_cases() -> list[Path]:
    return [
        case
        for case in _cases()
        if _args(case)[0] == "dice-doc"
        and len(_split_level_apart(_args(case))[1]) == 3
        and (case / "expected" / "exit").read_text(encoding="utf-8") == "0\n"
    ]


def _docdicer(run: Path, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([sys.executable, f"-m{MODULE}", *args], cwd=run, env=env, capture_output=True)


def _lines(data: bytes, what: str) -> list[bytes]:
    """data split at newlines after removing its final one; empty data has no lines."""
    if not data:
        return []
    assert data.endswith(b"\n"), f"{what} does not end in a newline:\n{data!r}"
    return data[:-1].split(b"\n")


def _token(name: bytes) -> "re.Pattern[bytes]":
    return re.compile(
        rb"(?<![A-Za-z0-9])(?<![A-Za-z0-9][.-])" + re.escape(name) + rb"(?![A-Za-z0-9])(?![.-][A-Za-z0-9])"
    )


def _entry_matches(names: list[bytes], line: bytes) -> bool:
    pos = 0
    for name in names:
        # search from pos rather than slicing, so the lookbehinds see the bytes before pos
        found = _token(name).search(line, pos)
        if found is None:
            return False
        pos = found.end()
    return True


def _one_to_one(entries: list[list[bytes]], lines: list[bytes]) -> bool:
    """True when each entry can be given a distinct line it matches: bipartite matching by
    augmenting paths, since a first-fit choice can take the only line a later entry matches."""
    holder: dict[int, int] = {}

    def place(entry: int, tried: set[int]) -> bool:
        for line, text in enumerate(lines):
            if line not in tried and _entry_matches(entries[entry], text):
                tried.add(line)
                if line not in holder or place(holder[line], tried):
                    holder[line] = entry
                    return True
        return False

    return all(place(entry, set()) for entry in range(len(entries)))


def _assert_names(names_file: Path, streams: dict[str, bytes]) -> None:
    text = names_file.read_text(encoding="utf-8", errors="surrogateescape")
    expected: dict[bytes, list[list[bytes]]] = {stream.encode(): [] for stream in streams}
    for entry in _lines(text.encode("utf-8", "surrogateescape"), str(names_file)):
        stream, *names = entry.split(b"\t")
        assert stream in expected and all(names), f"malformed names line: {entry!r}"
        expected[stream].append(names)
    for stream, data in streams.items():
        entries, lines = expected[stream.encode()], _lines(data, stream)
        assert len(lines) == len(entries) and _one_to_one(entries, lines), f"{stream} vs {entries!r}:\n{data!r}"


@pytest.mark.parametrize(
    "line, found",
    [(b"x 1", True), (b"x 12", False), (b"x 1.1", False), (b"\xc2\xa71(2)", True), (b"level 1.", True), (b"-1", True)],
)
def test_a_name_matches_as_a_whole_token(line: bytes, found: bool) -> None:
    assert _entry_matches([b"1"], line) is found


def test_names_are_found_left_to_right() -> None:
    assert _entry_matches([b"a", b"b"], b"a then b")
    assert not _entry_matches([b"b", b"a"], b"a then b")


def test_entries_take_distinct_lines_where_first_fit_would_not() -> None:
    assert _one_to_one([[], [b"x"]], [b"x 1", b"y 2"])
    assert not _one_to_one([[b"x"], [b"x"]], [b"x 1", b"y 2"])


def test_cases_exist() -> None:
    assert _cases(), "no cases under data/"


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case.name)
def test_cases(case: Path, tmp_path: Path) -> None:
    run = tmp_path / "run"
    shutil.copytree(case / "input", run, symlinks=True)
    args = _args(case)
    proc = _docdicer(run, args, _case_env(case))
    expected = case / "expected"
    assert f"{proc.returncode}\n" == (expected / "exit").read_text(encoding="utf-8")
    assert _files(run) == _files(expected / "tree")
    _assert_names(expected / "names", {"stdout": proc.stdout, "stderr": proc.stderr})


def test_round_trip_cases_exist() -> None:
    assert _round_trip_cases(), "no case dices without a map and exits 0"


@pytest.mark.parametrize("case", _round_trip_cases(), ids=lambda case: case.name)
def test_undice_then_dice_reproduces_the_tree(case: Path, tmp_path: Path) -> None:
    """A tree the case dices without a map: undiced, then diced again from the same run directory,
    both at the case's split level, it comes back byte for byte, both runs exiting 0."""
    run = tmp_path / "run"
    shutil.copytree(case / "expected" / "tree", run, symlinks=True)
    split_level, args = _split_level_apart(_args(case))
    out, env = args[2], _case_env(case)
    undiced = _docdicer(run, ["undice", *split_level, out, "mono.md"], env)
    assert undiced.returncode == 0, undiced.stderr
    (run / out).rename(run / "diced")
    rediced = _docdicer(run, ["dice-doc", *split_level, "mono.md", out], env)
    assert rediced.returncode == 0, rediced.stderr
    assert _files(run / out) == _files(run / "diced")
