"""Golden tests for docdicer.

Each case under data/ runs the CLI in a scratch copy of its input/ with the arguments in
`args` (one per line) and the environment in `env` (KEY=VALUE lines; DICER_KEEP is otherwise
unset), and must reproduce expected/: every file of expected/tree/, and stdout, stderr and the
exit status byte for byte. The expected outputs were produced by the shell/awk implementation
this port replaced (its plumbing files and empty directories left out); cases added since are
written by hand from SPEC.md.

Each tree a case dices without a map, successfully, must also survive `undice` and a second dicing
unchanged.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from docdicer.dicerlib.refactor import check_hunks

MODULE = "docdicer"
HERE = Path(__file__).resolve().parent
SCRATCH_DIR = HERE / "temp"
TESTDATA = HERE / "data"


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _case_env(case: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "DICER_KEEP"}
    env_file = case / "env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            env[key] = value
    return env


def _scratch_root() -> Path:
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    return SCRATCH_DIR


def _cases() -> list[Path]:
    return sorted(p for p in TESTDATA.iterdir() if p.is_dir())


def _args(case: Path) -> list[str]:
    return (case / "args").read_text(encoding="utf-8").splitlines()


def _docdicer(run: Path, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([sys.executable, f"-m{MODULE}", *args], cwd=run, env=env, capture_output=True)


class GoldenCases(unittest.TestCase):
    def test_cases(self) -> None:
        cases = _cases()
        self.assertTrue(cases, "no cases under data/")
        for case in cases:
            with self.subTest(case=case.name), tempfile.TemporaryDirectory(dir=_scratch_root()) as scratch:
                run = Path(scratch) / "run"
                shutil.copytree(case / "input", run, symlinks=True)
                proc = _docdicer(run, _args(case), _case_env(case))
                expected = case / "expected"
                self.assertEqual(proc.stdout, (expected / "stdout").read_bytes())
                self.assertEqual(proc.stderr, (expected / "stderr").read_bytes())
                self.assertEqual(f"{proc.returncode}\n", (expected / "exit").read_text(encoding="utf-8"))
                self.assertEqual(_files(run), _files(expected / "tree"))


class RoundTrip(unittest.TestCase):
    def test_undice_then_dice_reproduces_the_tree(self) -> None:
        """Every tree a case dices without a map and successfully: undiced, then diced again from the
        same run directory, it comes back byte for byte, both runs exiting 0."""
        selected = 0
        for case in _cases():
            args = _args(case)
            exit_status = (case / "expected" / "exit").read_text(encoding="utf-8")
            if args[0] != "dice-doc" or len(args) != 3 or exit_status != "0\n":
                continue
            selected += 1
            with self.subTest(case=case.name), tempfile.TemporaryDirectory(dir=_scratch_root()) as scratch:
                run = Path(scratch) / "run"
                shutil.copytree(case / "expected" / "tree", run, symlinks=True)
                out, env = args[2], _case_env(case)
                undiced = _docdicer(run, ["undice", out, "mono.md"], env)
                self.assertEqual(undiced.returncode, 0, undiced.stderr)
                (run / out).rename(run / "diced")
                rediced = _docdicer(run, ["dice-doc", "mono.md", out], env)
                self.assertEqual(rediced.returncode, 0, rediced.stderr)
                self.assertEqual(_files(run / out), _files(run / "diced"))
        self.assertTrue(selected, "no case dices without a map and exits 0")


class HunkCheck(unittest.TestCase):
    def test_edit_beyond_a_conversion_is_bad(self) -> None:
        old = "## S\n\n**T.** body\n\nplain\n"
        new = "## S\n\n### T\n\nbody, edited\n\nplain\n"
        self.assertEqual(check_hunks(old, new), (1, ["BAD merged hunk at old line 3: **T.** body"]))


if __name__ == "__main__":
    unittest.main()
