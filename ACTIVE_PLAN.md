# ACTIVE PLAN – a testing regime that protects logic

Base commit: the kickoff commit (recorded in Status when committed). It carries this plan, the
CONVENTIONS.md "Testing", "Dependencies", "Document size" and "Plan & Execute" sections, the README.md
document-size paragraph, and justfile's `test` recipe with `--basetemp` (F16).

## Outcome

The suite follows CONVENTIONS.md "Testing" and is pytest-native: every requirement in the coverage
checklist has a unit test, in the test file the Unit test rules assign it, that would fail if the
requirement stopped holding; end-to-end cases assert exit status, the files written, and the values
messages carry — never message wording. No `unittest` remains in the suite.
No production code changes.

## Facts

Commands run from docdicer's root.

| # | Fact | Command → answer |
|---|---|---|
| F1 | The suite today is one file of three `unittest.TestCase` classes: `GoldenCases` (every case under `data/`, comparing stdout, stderr, exit and tree byte for byte), `RoundTrip`, and one unit test, `HunkCheck`. | `grep -n "^class " docdicer/test/test_dicer.py` → `61:class GoldenCases(unittest.TestCase):`, `77:class RoundTrip(unittest.TestCase):`, `101:class HunkCheck(unittest.TestCase):` |
| F2 | 44 cases. | `command ls docdicer/test/data \| wc -l` → `44` |
| F3 | SPEC makes values contract, not wording; `list` rows are contract. | SPEC.md line 5: "File names, the files a command writes and their content, exit statuses, the stream each message goes to, and output SPEC gives as a row format (§9.2) are contract. Message wording is not: the messages below give current wording. What is contract is which fault or result each message reports, the values it carries, shown in `<angle brackets>` (a file, a line, a heading, a count), and the remedy it names." |
| F4 | The owner functions in the coverage checklist below exist. | `grep -n "^def \|^class \|^    def [a-z]" docdicer/dicerlib/*.py` → lists every owner below, e.g. `textfile.py:27:def split_lines`, `outline.py:130:    def link_text`, `linkrewrite.py:157:    def forward`, `linkrewrite.py:172:    def restore`, `dicedoc.py:110:def _all_reproduced`, `reassemble.py:11:def contents_cut`, `refactor.py:44:def _classify`, `refactor.py:184:def check_hunks` |
| F5 | Tests are written for pytest. CONVENTIONS.md lines 14–16: "Tests are written for pytest: plain `assert`, `@pytest.mark.parametrize` for a rule's table of inputs and results, and `tmp_path` instead of a hand-managed directory. A function that takes its output stream gets an `io.StringIO`; `capsys` is for output printed to the process streams." `just test` runs pytest (floor 8.4) on the venv's Python 3.9.6. Consequence: no syntax newer than Python 3.9 (no `X \| None` annotations, no `match`), no pytest feature newer than 8.4. | F16; `grep -n 'pytest>=' justfile` → `55:    {{VENV_PYTHON}} -m pip install "pytest>=8.4" "isort>=6.1" "black>=25.11" "flake8>=7.3"`; `grep -n '^version' .venv/pyvenv.cfg` → `3:version = 3.9.6`; `command ls .venv/lib/python3.9/site-packages \| grep -i '^pytest-'` → `pytest-8.4.2.dist-info`; `grep -n python pyproject.toml` → `9:requires-python = ">=3.9"` |
| F6 | Two cases hold a root-absolute link, which no message may report. | `grep -rl '](/' docdicer/test/data/*/input` → `docdicer/test/data/check-links-skipped/input/doc.md`, `docdicer/test/data/dice-dead-link/input/doc.md` |
| F7 | Two cases run `list`. | `grep -l '^list$' docdicer/test/data/*/args` → `docdicer/test/data/list-missing/args`, `docdicer/test/data/list-runins/args` |
| F8 | Files referencing the three classes WP1 removes. | `git grep -l 'HunkCheck' -- '*.py' '*.md' ':!ACTIVE_PLAN.md'` → `ARCHITECTURE.md`, `docdicer/test/test_dicer.py`; the same for `GoldenCases` and for `RoundTrip` → the same two files |
| F9 | The harness WP1 converts manages its own scratch directories under `docdicer/test/temp/`, which holds nothing tracked and is git-ignored. `just test` makes the same directory pytest's base temp (F16), so every `tmp_path` lands there. Consequence: once both harness tests use `tmp_path`, `SCRATCH_DIR`, `_scratch_root` and the `tempfile` use are dead; the directory and its `.gitignore` line stay, and ARCHITECTURE.md line 153's scratch-directory clause changes to describe `tmp_path`. | `git grep -n 'test/temp\|_scratch_root\|SCRATCH_DIR' -- ':!ACTIVE_PLAN.md' \| cut -d: -f1,2` → `.gitignore:13`, `ARCHITECTURE.md:153`, `docdicer/test/test_dicer.py:26`, `docdicer/test/test_dicer.py:44`, `docdicer/test/test_dicer.py:45`, `docdicer/test/test_dicer.py:46`, `docdicer/test/test_dicer.py:66`, `docdicer/test/test_dicer.py:88`; `grep -n 'tempfile' docdicer/test/test_dicer.py \| cut -d: -f1` → `18`, `66`, `88`; `git ls-files docdicer/test/temp \| grep -c .` → `0` |
| F10 | The child `python -m docdicer` finds the package only through `PYTHONPATH`, which `just test` sets and the harness passes on by building the child's environment from `os.environ`. The package is not installed in the venv, and the child runs with its cwd in the case's run directory. Consequence: the converted harness keeps building the child's environment from `os.environ` (dropping only `DICER_KEEP`, adding the case's `env` lines); it never builds a fresh environment, never removes `PYTHONPATH`, and never makes the run directory the parent's cwd. | `git grep -n PYTHONPATH -- justfile docdicer/test` → `justfile:7:DD_PYTHON := "PYTHONPATH=\"" + PROJECT_ROOT + "\" " + VENV_PYTHON` (no line in `docdicer/test`); `grep -n 'os.environ' docdicer/test/test_dicer.py` → `35:    env = {k: v for k, v in os.environ.items() if k != "DICER_KEEP"}`; `command ls .venv/lib/python3.9/site-packages \| grep -ci docdicer` → `0` |
| F11 | `docdicer/test/` holds one test file and no `conftest.py` or `__init__.py`. | `git ls-files docdicer/test \| grep -v '/data/'` → `docdicer/test/test_dicer.py` |
| F12 | No production code writes to the process streams; every owner writes to the `out` / `err` it is given. Consequence: unit tests pass an `io.StringIO`, as CONVENTIONS.md "Testing" directs (F5: "A function that takes its output stream gets an `io.StringIO`; `capsys` is for output printed to the process streams."); `capsys` has no use in WP2a or WP2b. | `grep -n "sys\.std" docdicer/dicerlib/*.py \| wc -l` → `0`; ARCHITECTURE.md line 133: "Passes are functions of their arguments and write only to the `out` / `err` streams they are given (drivers take `stdout` / `stderr`). Nothing below `__main__` touches `sys.stdout`, …" |
| F13 | `test_dicer.py` symbols WP1 removes: `GoldenCases`, `RoundTrip` in step 2; the rest in step 4. | `grep -n "^class \|^import unittest\|^from docdicer\|unittest.main\|^if __name__" docdicer/test/test_dicer.py` → `19:import unittest`, `22:from docdicer.dicerlib.refactor import check_hunks`, `61:class GoldenCases(unittest.TestCase):`, `77:class RoundTrip(unittest.TestCase):`, `101:class HunkCheck(unittest.TestCase):`, `108:if __name__ == "__main__":`, `109:    unittest.main()` |
| F14 | `justfile` line 9 is the `test` recipe's doc, which names only the golden tests. | `sed -n 9p justfile` → `[doc("run the docdicer's golden tests")]` |
| F15 | Every SPEC requirement must have a test that would fail if it stopped holding, at the lowest level that observes it; tests follow the code, not SPEC's layout. CONVENTIONS.md lines 8–11: "Every SPEC requirement is tested to hold: if it stopped holding, a test would fail. Test it at the lowest level that can observe it — a unit test where a function owns the logic, an end-to-end case where only a command's behaviour shows it. Tests are organized by the code they exercise, not by SPEC's structure." | `sed -n 8,11p CONVENTIONS.md` → the four lines quoted |
| F16 | `just test` runs pytest with its base temp at `docdicer/test/temp`; every `tmp_path` is created under it. | `grep -n -A1 "^test" justfile` → `10:test: _venv` / `11-  {{DD_PYTHON}} -m pytest --basetemp="{{PROJECT_ROOT}}/docdicer/test/temp" docdicer` |

Coverage checklist (F4, F15): the requirements WP2a and WP2b must leave covered by unit tests, and
the function(s) that own each. A row is a list of requirements, not a list of tests.

| SPEC | Requirements | Owner |
|---|---|---|
| §2 Text | `\n`-only splitting, final newline | `textfile.split_lines`, `join_lines` |
| §3.1 | fenced code | `textfile.FenceTracker`, `fence_flags` |
| §3.1, §3.2 | split levels, extra level-1, numbers, slugs, names, paths, collisions, empty slug | `outline.slug`, `split_number`, `plan_sections` |
| §3.3 | Contents block, link text | `split.contents_block`, `outline.Outline.link_text` |
| §4, §4.1 | what is a link, code spans | `linkrewrite.link_targets` |
| §4.2 | other-document reference, dangling reference, linked reference, named child | `linkrewrite.Linker.forward` |
| §4.3 | target classification, rebasing | `linkrewrite.Linker.forward`, `rel` |
| §4.4 | anchors, repeats | `linkcheck.github_anchor`, `heading_anchor_list` |
| §6.1 | link restoration, would be re-diced, opens no section, not reproduced | `linkrewrite.Linker.restore`, `dicedoc._all_reproduced` |
| §8.1 | Contents cut | `reassemble.contents_cut` |
| §9.1 | run-in classification, conversion, keep list, long titles, self-check | `refactor._classify`, `convert_runins`, `list_runins`, `check_hunks` |

Requirements not in this checklist get no new unit tests this sprint; they stay covered by the
end-to-end cases.

## Sequencing

WP2a and WP2b run in parallel. WP1 starts only after both have landed: it converts `test_dicer.py`,
deletes `HunkCheck`, which WP2b replaces, and its docs name WP2a's and WP2b's files. No package
changes production code or a signature.

File ownership; no file has two owners:

| Package | Owns |
|---|---|
| WP1 (after WP2a, WP2b) | `docdicer/test/test_dicer.py`, every `docdicer/test/data/*/expected/`, `justfile` (line 9 only), ARCHITECTURE.md, README.md |
| WP2a | new `docdicer/test/test_textfile.py`, `test_outline.py`, `test_split.py`, `test_linkcheck.py`, `test_reassemble.py` |
| WP2b | new `docdicer/test/test_linkrewrite.py`, `test_undice.py`, `test_refactor.py`, and `docdicer/test/conftest.py` if it creates one |

Shared fixtures: none is planned. The only `Tree` user is `test_linkrewrite.py`, and building
sections is one call to `plan_sections`; a helper one file uses stays in that file. A fixture two or
more of WP2b's files need goes in `docdicer/test/conftest.py`, which only WP2b creates or edits.
Its fixtures are not autouse and it defines no hooks; WP1 and WP2a never name one of its fixtures or
edit it; a helper they would share with another package's file is written in their own file
instead.

## Unit test rules (WP2a, WP2b)

- Test functions, never classes, with plain `assert`.
- Choose tests and their names to fit the code under test (F15); one test may cover several
  checklist requirements, and a requirement may need several tests. One name is fixed:
  `test_self_check` (WP2b), which WP1's precondition greps for.
  - Where a requirement's expected results form a table of inputs and results (slugs, anchors and
    repeats, run-in classes, target classification, …), parametrize with
    `@pytest.mark.parametrize` over the rows, each row a `pytest.param(..., id="<readable id>")`
    whose id says what the row exercises (`backticks-deleted`, `third-repeat`, `label-not-runin`).
  - Where one example shows a requirement, use a single plain, unparametrized test.
- A test covers a requirement when its input makes the requirement matter: without the requirement,
  its expected value would differ. An input the requirement leaves unchanged (an already-lowercase
  title, for lowercasing) covers nothing. Where one requirement bundles several behaviours (e.g.
  slugs: lowercasing, backtick removal, separator runs, edge trimming, non-ASCII as separator), each
  needs some covering input; one parametrized test may hold them all.
- A test lives in `test_<module>.py` for the module of the owner it calls; `dicedoc._all_reproduced`
  goes in `test_undice.py`.
- Expected results come from SPEC's text, never from running the code.
- Where the owner writes to `err` or `out`, pass an `io.StringIO` (F12); assert the return value and
  the values the message carries (a path, a line number, a count), never its wording. Use `capsys`
  only for an owner that prints to the process streams; F12 shows none in this table does.
- Build inputs in memory. Where the owner reads from disk, or needs real directory paths (a `Tree`,
  `_all_reproduced`'s `out`), use the `tmp_path` fixture; never a hand-managed directory.

## Work packages

### WP1 – end-to-end cases assert values, not wording (python-coder, expert)

Rated expert: it must decide which values each message carries.

Starts after WP2a and WP2b have landed (see Sequencing). Precondition:
`grep -n "def test_self_check" docdicer/test/test_refactor.py` returns a line.

Scope: `docdicer/test/test_dicer.py`; every `docdicer/test/data/*/expected/`; `justfile` (line 9
only); ARCHITECTURE.md; README.md. `docdicer/test/temp/` and its `.gitignore` line stay (F9).

1. **Format.** Every case gets `expected/names`; a case without one fails. Each line is one of:
   - `<stream>\t<name>[\t<name>...]` — some single line of the stream contains every name;
   - `!<stream>\t<name>` — no line of the stream contains the name;
   - `<stream>\tempty` — the stream is empty.

   `<stream>` is `stdout` or `stderr`; any other line fails the case. Matching is on bytes: the
   stream is split on `\n`, and each name is encoded UTF-8 with `surrogateescape`.
2. **Harness, pytest-native.** Replace `GoldenCases` and `RoundTrip` with two module-level test
   functions, keeping their method names:
   - `test_cases`, parametrized over every case directory under `data/`, ids the directory names. It
     keeps comparing exit status and the tree byte for byte, and replaces the stdout and stderr
     comparisons with the `expected/names` assertions. A case whose `args` first line is `list`
     (F7) also keeps `expected/stdout`, compared byte for byte (SPEC §9.2 rows are contract, F3);
     its `expected/names` holds `stderr` lines only. Every other case's `expected/stdout` and
     `expected/stderr` are deleted.
   - `test_undice_then_dice_reproduces_the_tree`, parametrized over the qualifying cases (args
     `dice-doc` with no map, `expected/exit` `0`), ids the case names; its assertions are unchanged.
   - Each run copies into `tmp_path / "run"` (`shutil.copytree` needs an absent destination), not a
     hand-managed directory.
   - Pytest skips a test parametrized over an empty list, so the two emptiness guards the classes
     held ("no cases under data/", "no case dices without a map and exits 0") become two plain test
     functions, `test_cases_exist` and `test_round_trip_cases_exist`, asserting that each case list
     is non-empty.
   - Keep `_docdicer` running `sys.executable -m docdicer` as a subprocess, and `_case_env` building
     the child's environment from `os.environ` (F10).
   - Delete `SCRATCH_DIR`, `_scratch_root`, every `tempfile` use and `import tempfile` (F9). Leave
     `docdicer/test/temp/` and `.gitignore` untouched. Leave `HunkCheck`, its
     import and `import unittest` for step 4.
3. **Convert all 44 cases.** For each message in the old expected streams, one line holding its
   values: paths, line numbers, headings, counts, quoted source lines. A count printed beside other
   counts keeps the label SPEC gives it (`dead: 2`). Where SPEC gives one check several messages,
   the line also holds the phrase that tells which fault it reports, as a name: `missing file` /
   `missing anchor` (§8.4); `would be re-diced` / `opens no section` / `not reproduced` (§6.1);
   `BAD` (§9.1); `DEAD` (§7.2). A message with no values is not asserted. An
   empty stream gets `empty`. Each value is checked against SPEC for the case's input, not copied
   from the old stream. `!` lines (F6):
   - `check-links-skipped`: `!stderr\t/nowhere.md`
   - `dice-dead-link`: `!stderr\t/etc/hosts`
4. **Retire `HunkCheck` and update docs.**
   - `test_dicer.py` (F13): delete the `HunkCheck` class, the `check_hunks` import, `import
     unittest` and the `if __name__ == "__main__":` block. Rewrite the module docstring to describe
     the harness: one test per case directory, each run in its own `tmp_path`; the `expected/names`
     assertions and the `list` stdout byte comparison; the round trip, one test per qualifying case.
     Drop the sentence on where the expected outputs came from; the docstring says cases are
     written from SPEC.md. `grep -n "unittest" docdicer/test/test_dicer.py` then returns nothing.
   - `justfile` line 9 (F14) becomes
     `[doc("run docdicer's tests: the golden cases, the round trip and the per-module unit tests")]`.
   - ARCHITECTURE.md line 18 ("Tests:"): name the per-module unit test files as well.
   - ARCHITECTURE.md §8. Edit §8 from the bottom up; the line numbers are those before any edit.
     - line 140 ("`docdicer/test/test_dicer.py` has three `unittest` classes."): it holds the
       end-to-end harness as pytest functions; the per-module unit test files are named below.
     - line 142: `test_cases` is parametrized over the directories under `data/`, one test per case,
       id the directory name (replacing `GoldenCases.test_cases` and "each is a subtest");
       `test_cases_exist` requires at least one case.
     - line 149: the `expected/stdout`, `expected/stderr` row becomes `expected/names` with its
       syntax, plus `expected/stdout` for `list` cases.
     - line 153: the case's `input/` is copied into the test's pytest `tmp_path`, which `just test`
       places under `docdicer/test/temp/` (git-ignored) through `--basetemp`, which pytest deletes
       and recreates on each run (replacing "a scratch
       directory under `docdicer/test/temp/` (git-ignored)"); the comparison is exit status, tree,
       and the names (and `list` stdout).
     - line 155: `test_undice_then_dice_reproduces_the_tree` is parametrized over the qualifying
       cases and copies into its `tmp_path`; "at least one case to qualify" becomes
       `test_round_trip_cases_exist`.
     - line 157: the `HunkCheck` paragraph is replaced by a sentence naming the per-module unit
       test files: `test_textfile.py`, `test_outline.py`, `test_split.py`, `test_linkcheck.py`,
       `test_reassemble.py`, `test_linkrewrite.py`, `test_undice.py`, `test_refactor.py`.
   - README.md lines 77–78 (the sentence beginning "`just test` runs"): it says it runs one pytest test per golden case
     and per round-tripped case, and the per-module unit tests.

### WP2a – unit tests: text, outline, Contents, anchors (python-coder, expert)

Rated expert: for each rule it must choose the inputs and derive the expected result from SPEC,
which the plan does not settle.

Scope: new files `docdicer/test/test_textfile.py`, `test_outline.py`, `test_split.py`,
`test_linkcheck.py`, `test_reassemble.py`.

Unit tests, under "Unit test rules", covering the checklist rows `§2`, `§3.1`, `§3.1, §3.2`, `§3.3`,
`§4.4` and `§8.1`.

Done when every requirement in those rows has a test that would fail if it stopped holding.

### WP2b – unit tests: links, undice, refactor (python-coder, expert)

Rated expert: for each rule it must choose the inputs and derive the expected result from SPEC,
which the plan does not settle.

Scope: new files `docdicer/test/test_linkrewrite.py`, `test_undice.py`, `test_refactor.py`;
`docdicer/test/conftest.py` only if two or more of WP2b's files need one fixture (see Sequencing).

Unit tests, under "Unit test rules", covering the checklist rows `§4, §4.1`, `§4.2`, `§4.3`, `§6.1` and
`§9.1`.

Done when every requirement in those rows has a test that would fail if it stopped holding.

- `Linker` needs a `Tree` (a dataclass: `out`, `outabs`, `root`, `link_map`): build it over
  `tmp_path`, with an in-memory `LinkMap` unless the test exercises the map file.
- `_all_reproduced` walks the `.md` files under its `out`: write them under `tmp_path`.
- `test_self_check` is a plain function: it calls `check_hunks` with old
  `"## S\n\n**T.** body\n\nplain\n"` and new `"## S\n\n### T\n\nbody, edited\n\nplain\n"`, and
  asserts the count is `1` and that the one report line holds `3`.

Do not edit `test_dicer.py`.

## Stop conditions (all packages)

- A Facts command's answer differs from the one recorded: stop and report both.
- SPEC's text does not settle a rule's expected result: stop and report the rule and the input. Do
  not infer the result from the code.
- A unit test shows behaviour that contradicts SPEC: stop and report the rule, the input and both
  results. Change neither the test nor the code to make them agree.
- A case's exit status or tree no longer matches: stop and report.
- Pytest cannot create `tmp_path`: stop and report the error. Do not fall back to a hand-managed
  directory.
- Any production file under `docdicer/dicerlib/` or `docdicer/__main__.py` would need to change.

## Done-line

`just test` passes; a second `just format` run changes no file and prints no flake8 output.

Report: files added or changed; for WP2a and WP2b, for each checklist row, the `file::function`
tests covering it; any stop condition hit.

## Post-sprint review

Per CONVENTIONS.md "Post-sprint review", against the change since the kickoff commit recorded in
Status. Reviewers judge coverage by CONVENTIONS.md "Testing": could any SPEC requirement stop
holding without a test failing? Test counts, names, and whether tests mirror SPEC's sections are
not findings.

## Status

| Package | State |
|---|---|
| Kickoff commit | not yet committed (record its hash here) |
| WP1, WP2a, WP2b | reviewed and revised; awaiting approval and kickoff commit |
| Review | not started |
