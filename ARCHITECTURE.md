# ARCHITECTURE – docdicer

How this implementation meets SPEC.md. User-visible outcomes are specified there and cited here as `SPEC §N`; they are not restated.

## §1 Build, run, test

Python 3.9 or later, standard library only (`pyproject.toml`: `requires-python = ">=3.9"`, `dependencies = []`). Setuptools builds the wheel; the version is read from `docdicer.__version__`; the console script `docdicer` is `docdicer.__main__:main`; the test package is excluded from the wheel.

| Target | Effect |
|---|---|
| `just test` | creates `.venv` if absent, then runs `docdicer/test/test_dicer.py` with the project root on `PYTHONPATH` |
| `just build` | builds the wheel into `dist/` |
| `just format` | black (line length 120), isort, flake8 over `docdicer` |

Without `just`, `python3 -m docdicer <command>` with the project root on `PYTHONPATH` is the same program. Tool versions in the venv are pinned on the `_venv` install line.

## §2 Package map

```text
docdicer/
  __init__.py          __version__
  __main__.py          argument parsing, DICER_KEEP, dispatch to drivers
  dicerlib/
    heads.py           head-file names
    textfile.py        text I/O, line splitting, fence tracking
    outline.py         heading pass: sections, names, paths, lookups
    refactor.py        run-in classification, conversion, hunk self-check
    linkrewrite.py     link scanner, Linker, LinkMap, Tree, rel()
    split.py           write pass: section files and Contents blocks
    reassemble.py      reassembly check (SPEC §8.1)
    linkcheck.py       link check (SPEC §8.2), check-links (SPEC §8.4), anchors
    treecheck.py       check-tree (SPEC §8.5)
    dicedoc.py         dice_doc and verify drivers
    manifest.py        dice_docs driver
  test/
    test_dicer.py      golden harness
    data/<case>/       golden cases
```

| Module | Responsibility |
|---|---|
| `__main__` | Builds the argparse parser, reconfigures stdout and stderr to UTF-8 with `surrogateescape`, reads `DICER_KEEP`, validates root arguments (usage errors, exit 2), calls one driver, and turns its result into the exit status. The only code that reads the environment or `sys.argv`. |
| `heads` | `ENTRY_POINT`, `INDEX`, `HEADS`: the only place the head-file names are spelled (SPEC §3.2). |
| `textfile` | The one place files are opened: UTF-8, `surrogateescape`, `newline=""`. Line splitting on `\n` only (`split_lines`, `terminated_lines`, `join_lines`), `is_blank`, and `FenceTracker` / `fence_flags`, the one definition of fenced code (SPEC §3.1). |
| `outline` | `plan_sections` turns lines into `Section` records (SPEC §3.1, §3.2); `Outline` gives lookups by number, children, depth and Contents link text; `load_outline` adds the duplicate-number warning. |
| `refactor` | The bold-line classifier and converter (SPEC §9.1), the `list` rows (SPEC §9.2), and the `check_hunks` self-check. Depends on nothing but `textfile`. |
| `linkrewrite` | The single link/reference scanner `_scan`, the `Linker` built on it, the `LinkMap` and `Tree` records, and the path helpers `rel` and `parent_dir` (SPEC §4, §5). |
| `split` | The write pass: each section's lines through `Linker.forward`, plus `contents_block` (SPEC §3.3), written under the output directory; prints the `refs linked` line. |
| `reassemble` | The inverse of the write pass (SPEC §8.1). |
| `linkcheck` | `check_links` (SPEC §8.2), `check_markdown_links` (SPEC §8.4), the GitHub anchor functions (SPEC §4.4), `prose_links`, `markdown_files`. |
| `treecheck` | `check_trees` (SPEC §8.5). |
| `dicedoc` | `dice_doc` (SPEC §6) and `verify` (SPEC §8.3). |
| `manifest` | `dice_docs` (SPEC §7): manifest reading, refactor calls, link-map rows, group indexes, the entry point, the written-files check. |

## §3 Dependency direction

Imports point down this list; a module imports only from rows above its own.

| Layer | Modules |
|---|---|
| 0 | `heads`, `textfile` |
| 1 | `outline`, `refactor` |
| 2 | `linkrewrite` |
| 3 | `split`, `reassemble`, `linkcheck` |
| 4 | `treecheck`, `dicedoc` |
| 5 | `manifest` |
| 6 | `__main__` |

One upward edge exists: `linkrewrite._anchor_homes` needs `linkcheck.heading_anchor_list`, and `linkcheck` imports `linkrewrite`. The cycle is broken by importing inside the function. `treecheck` reaches into `linkcheck` (`markdown_files`, `prose_links`) and `linkrewrite` (`URL_SCHEME`) rather than keeping its own copies.

Drivers (`dicedoc`, `manifest`) take `stdout` / `stderr` as parameters and pass them down; the passes take `out` / `err` as keyword arguments. Nothing below `__main__` touches `sys.stdout`; `manifest` relies on this to capture a volume's output into a buffer (§5).

## §4 Key data structures

| Type | Module | Role |
|---|---|---|
| `Section` | `outline` | One planned file: `id`, `parent`, `kind` (`E` entry point, `I` index, `L` leaf), `path` relative to the output directory, `first`/`last` source lines (1-based, inclusive), `number`, `level`, `title`. `sections[0]` is the entry point and `sections[i].id == i`. The list is in document order, so reading the files in list order reproduces the source order. |
| `Outline` | `outline` | Indexes over `Section`s: `children`, `depth`, `by_number` (last duplicate wins, SPEC §3.2), `duplicate_numbers`. |
| `LinkMap` | `linkrewrite` | `documents: target -> path` and `headings: (target, heading) -> path`, loaded from the TSV (SPEC §5). |
| `Tree` | `linkrewrite` | One output tree: `out` as given (prefix of reported paths), `outabs` (real path), `root` (the working directory, anchoring rebasing), and the `LinkMap`. |
| `Linker` | `linkrewrite` | Holds `Outline`, `Tree`, the anchor-home table, and the `resolved` / `dangling` counters. Methods `forward`, `rebase_only`, `revert`. |
| `Anchor` | `linkcheck` | `base` and repeat-suffixed `name` of one heading. |
| `_Volume`, `_Entry` | `manifest` | One diced manifest row (the document actually diced, its output directory, label, `file` key); the `entry` row. |
| `_Hunk` | `refactor` | A merged changed region: start line, old lines, new lines. |

## §5 Data flow per command

### `dice-doc` (SPEC §6)

```text
read_lines(monolith)
  -> plan_sections            lines -> [Section]          (outline)
  -> makedirs for each section path
  -> write_tree               Linker.forward per line, contents_block per E/I (split)
  -> check_reassembly         re-reads the leaves, inverts the rewrite (reassemble)
  -> check_links              probes every link in the leaves (linkcheck)
```

`dice_doc` creates the output directory before planning, which is why a planning failure leaves it empty. Each stage returns a bool; the driver stops at the first failure. `plan_sections` always returns the sections planned so far; on an empty slug it stops there, and `dice_doc` does not write them.

### `verify` (SPEC §8.3)

For each pair: `plan_sections` again from the monolith, then `check_reassembly` and `check_links`. The tree on disk is never trusted for its own structure; expected paths come from the re-plan. `check_links` writes into a `StringIO`, whose lines are re-printed indented. Reassembly writes failures to `stdout` here, to `stderr` in `dice_doc`: the `err=` argument is the only difference.

### `dice-docs` (SPEC §7)

```text
read manifest rows -> per row: refactor (if flagged) -> _Volume / _Entry
write_lines(work/links.tsv, _link_map_rows)     plan_sections per volume
remove old outputs
per volume: dice_doc(.., stdout=log, stderr=log) -> filter "dead link" lines -> stdout
_write_group_indexes, _write_entry_point        (append_text / write_text)
verify(map, all volumes)
_check_written(files written above)
```

The link map is built before any volume is diced because documents link to each other; this is also why dicing reports dead links that `verify` later re-evaluates once every tree exists. `dice_doc`'s return value is ignored here by design: a volume that failed to dice has no tree and `verify` fails on it. Group indexes and the entry point are written after dicing, past each parent's Contents block, so `reassemble` (which cuts at the last `Contents:` line) ignores them.

### `refactor` and `list` (SPEC §9)

`_walk` is one pass over the lines, used in two modes: `converting=True` yields the output lines and the long-title notes (`convert_runins`); `converting=False` yields the TSV rows (`list_runins`). The classifier `_classify` is shared, so the `list` classes and the conversion decisions cannot drift. `refactor()` then runs `check_hunks` on the input text and the joined output.

### `check-links`, `check-tree` (SPEC §8.4, §8.5)

Both use `markdown_files` for the walk and `prose_links` for the links. `prose_links` drives `FenceTracker` and `link_targets`, so they recognise exactly the links the write pass rewrites. `check-tree` builds a per-file set of linked real paths and tests the parent rule and a breadth-first reachability walk from the root's entry point.

## §6 Mechanisms

### Link scanning is shared

`linkrewrite._scan` is the only scanner of a line. It skips code spans, finds `[text](target)` per SPEC §4.1, and, given an `on_ref` callback, finds `§N` references. Callers differ by callback:

| Caller | Callbacks | Used by |
|---|---|---|
| `Linker.forward` | rebaser + reference linker | write pass |
| `Linker.rebase_only` | rebaser | reassembly (expected side) |
| `Linker.revert` | un-linker | reassembly (actual side) |
| `link_targets` | collector | `prose_links` |

Because write and check share the scanner and `_rebase`, link recognition cannot differ between them. `revert` recognises a link as forward-made when its text starts with `§<digit>`, names a known number (and child name if present), and its target equals the path `forward` would compute; any other link is left as is.

### Rebasing

Monolith links are relative to `Tree.root` (the working directory). `_rebase` resolves the target to `root/<dest>` and calls `rel(here, ...)` from `outabs/<leaf dir>`. `rel` is purely lexical over `/`-split strings. Link-map paths and manifest paths are also relative to the working directory, which is why they are joined onto `Tree.root` too.

### Anchor homes

`_anchor_homes` maps each monolith heading anchor to `(file, anchor within file)`. It numbers headings per owning section (`per_file`), so repeat suffixes follow the file the heading lands in (SPEC §4.4), and marks the heading that opens a non-entry file as needing no fragment. The owner of a source line is found by a line-to-section table built from `Section.first` / `last`.

### Contents blocks and the cut

`contents_block` always starts `Contents:` and is appended last; `check_reassembly` finds the cut by scanning backward for a line equal to `Contents:`, so anything appended after (group lines) is removed too, and a source line `Contents:` earlier in the section is not mistaken for it.

### Planning

`plan_sections` makes two passes: collect splittable headings outside fences (reporting extra level-1 headings); then compute parents with a stack of open headings (pop while the top's level is not lower), and name and path each section. A path-to-line dictionary detects collisions.

### Refactor self-check

`check_hunks` diffs `terminated_lines` of input and output with `difflib.SequenceMatcher(autojunk=False)`, merges changed regions separated by up to three blank unchanged lines, and compares each merged hunk's new side with `_expected(old)`, which re-derives the conversion with regexes independent of `_classify`. A divergence between the two implementations of the rule is thus reported as `BAD`.

### Text fidelity

`surrogateescape` and `newline=""` in `textfile`, and the matching stdout/stderr reconfiguration in `__main__`, carry non-UTF-8 bytes and `\r` through every pass; the `_excerpt` helper in `refactor` truncates in bytes and decodes the same way.

## §7 Invariants

- Head-file names are spelled only in `heads.py`; every other module imports them.
- Fenced code is defined only by `FenceTracker`; `outline`, `split`, `reassemble`, `linkcheck` and `refactor` use it.
- Only `textfile` opens files for text; passes use its readers and writers.
- Each pass is a function of its arguments; drivers own filesystem layout and exit statuses. Passes report through the `out` / `err` streams they are given and return a bool or count.
- `Section` lists are in document order with `id == index`; `sections[0]` is always the entry point.
- Every source line belongs to exactly one section: sections partition `1..len(lines)`; `reassemble` fails if the count differs.
- The file-name slug (`outline.slug`) and the heading anchor (`linkcheck.github_anchor`) are separate functions and never substituted for each other.
- A message's text is a contract (SPEC preamble); the golden cases compare stdout and stderr byte for byte.

## §8 Test harness

`docdicer/test/test_dicer.py` has two `unittest` classes.

`GoldenCases.test_cases` enumerates the directories under `data/`; each is a subtest. A case holds:

| Path | Content |
|---|---|
| `input/` | the working tree the command runs in |
| `args` | the command-line arguments, one per line |
| `env` | optional `KEY=VALUE` lines; `DICER_KEEP` is removed from the inherited environment otherwise |
| `expected/stdout`, `expected/stderr` | exact bytes |
| `expected/exit` | the status and a newline |
| `expected/tree/` | every file of the working tree after the run, inputs included |

The harness copies `input/` to a scratch directory under `docdicer/test/temp/` (git-ignored), runs `sys.executable -m docdicer <args>` there as a subprocess, and compares stdout, stderr, the exit status and a `{relative path: bytes}` map of all files. Only files are compared, so empty directories are not asserted. Running the real entry point exercises argument parsing, stream configuration and exit codes along with the passes.

`HunkCheck` calls `check_hunks` directly to assert that an edit beyond a conversion is reported `BAD`.

The cases cover each command (`dice-*`, `verify-failures`, `refactor-*`, `list-runins`, `check-links-*`, `check-tree-*`), the planning errors (`dice-collision`, `dice-empty-slug`, `dice-dupnum`), the argument fault (`dice-out-not-empty`), the link map (`dice-map`, `dice-docs`), anchors (`dice-anchors`) and dead links (`dice-dead-link`). A behaviour change is made by changing code and the affected `expected/` together.

## §9 Extension points

- *A new command*: add a parser in `__main__._parser`, a driver in the layer that owns its inputs, and a golden case; exit statuses follow SPEC §2.
- *A new link form*: change `_scan` and `Linker` only; the checks follow because they share the scanner (§6).
- *A new split level*: `outline._DEEPEST_SPLIT_LEVEL`; the heading-width test in `plan_sections` bounds what is a heading at all.
- *A new head-file name*: not an extension point (SPEC §3.2).
