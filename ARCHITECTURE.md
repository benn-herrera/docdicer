# ARCHITECTURE – docdicer

How this implementation meets SPEC.md. User-visible outcomes are specified there and cited here as `SPEC §N`; they are not restated.

## §1 Build, run, test

Python ≥ 3.9, standard library only; packaging is in `pyproject.toml`.

| Target | Effect |
|---|---|
| `just test` | creates `.venv` if absent, then runs `docdicer/test/test_dicer.py` with the project root on `PYTHONPATH` |
| `just build` | builds the wheel into `dist/` |
| `just format` | black, isort, flake8 over `docdicer` |

## §2 Package map

`__init__` (`__version__`) and `__main__` are in `docdicer/`; every other module is in `docdicer/dicerlib/`. Tests: `docdicer/test/test_dicer.py`, cases in `docdicer/test/data/<case>/` (§8).

| Module | Responsibility |
|---|---|
| `__main__` | Builds the argparse parser, reconfigures stdout and stderr to UTF-8 with `surrogateescape`, reads `DICER_KEEP`, validates root arguments and refuses unreadable files (exit 2), calls one driver, and turns its result into the exit status. The only code that reads environment variables or `sys.argv`. |
| `heads` | `ENTRY_POINT`, `INDEX`, `HEADS` (SPEC §3.2). |
| `textfile` | File I/O (UTF-8, `surrogateescape`, `newline=""`); `\n`-only line splitting (`split_lines`, `terminated_lines`, `join_lines`); `is_blank`; `FenceTracker` / `fence_flags` (SPEC §3.1). |
| `outline` | `plan_sections` turns lines into `Section` records (SPEC §3.1, §3.2); `Outline` gives lookups by number, children, depth and Contents link text. |
| `refactor` | The bold-line classifier and converter (SPEC §9.1), the `list` rows (SPEC §9.2), and the `check_hunks` self-check. |
| `linkrewrite` | The single link/reference scanner `_scan`, the `Linker` built on it, the `LinkMap` and `Tree` records, and the path helpers `rel` and `parent_dir` (SPEC §4, §5). |
| `split` | The write pass: each section's lines through `Linker.forward`, plus `contents_block` (SPEC §3.3), written under the output directory; prints the `refs linked` line. |
| `reassemble` | The inverse of the write pass (SPEC §8.1). |
| `linkcheck` | `check_links` (SPEC §8.2), `check_markdown_links` (SPEC §8.4), the GitHub anchor functions (SPEC §4.4), `prose_links`, `markdown_files`. |
| `treecheck` | `check_trees` (SPEC §8.5). |
| `dicedoc` | `dice_doc` (SPEC §6) and `verify` (SPEC §8.3); each reports duplicate section numbers once, after planning. |
| `manifest` | `dice_docs` (SPEC §7): manifest reading, refactor calls, link-map rows, group indexes, the entry point, the written-files check. |

## §3 Dependency direction

A module imports only from lower layers.

| Layer | Modules |
|---|---|
| 0 | `heads`, `textfile` |
| 1 | `outline`, `refactor` |
| 2 | `linkrewrite` |
| 3 | `split`, `reassemble`, `linkcheck` |
| 4 | `treecheck`, `dicedoc` |
| 5 | `manifest` |
| 6 | `__main__` |

Exception: `linkrewrite._anchor_homes` imports `linkcheck.heading_anchor_list` inside the function, because `linkcheck` imports `linkrewrite`.

## §4 Key data structures

| Type | Module | Role |
|---|---|---|
| `Section` | `outline` | One planned file: `id`, `parent`, `kind` (`E` entry point, `I` index, `L` leaf), `path` relative to the output directory, `first`/`last` source lines (1-based, inclusive), `number`, `level`, `title`. |
| `Outline` | `outline` | Indexes over `Section`s: `children`, `depth`, `by_number` (last duplicate wins, SPEC §3.2), `duplicate_numbers`. |
| `LinkMap` | `linkrewrite` | `documents: target -> path` and `headings: (target, heading) -> path`, loaded from the TSV (SPEC §5). |
| `Tree` | `linkrewrite` | One output tree: `out` as given (prefix of reported paths), `outabs` (real path), `root` (the run directory), and the `LinkMap`. |
| `Linker` | `linkrewrite` | Holds `Outline`, `Tree`, the anchor-home table, and the `resolved` / `dangling` counters. Methods `forward`, `rebase_only`, `revert`. |
| `Anchor` | `linkcheck` | `base` and repeat-suffixed `name` of one heading. |
| `_Volume`, `_Entry` | `manifest` | One diced manifest row (the document actually diced, its output directory, label, `file` key); the `entry` row. |
| `_Hunk` | `refactor` | A merged changed region: start line, old lines, new lines. |

## §5 Data flow per command

### `dice-doc` (SPEC §6)

`dice_doc` creates the output directory, then runs `read_lines` → `plan_sections` → `makedirs` per section directory → `write_tree` → `check_reassembly` → `check_links`, and returns 1 at the first failure. Planning reports every collision but stops at the first empty slug; any planning failure writes nothing.

### `verify` (SPEC §8.3)

Per pair: plan again from the monolith (expected paths come from this plan, never from the tree on disk); run `check_reassembly` with `err=stdout`; run `check_links` into a `StringIO` whose lines are printed again, indented.

### `dice-docs` (SPEC §7)

`dice_docs` runs SPEC §7.2's steps in order: `_read_manifest`, with `refactor` where flagged, into `_Volume` / `_Entry`; `_link_map_rows` (which calls `plan_sections` per volume) into `links.tsv`; `_remove`; for each volume, `dice_doc` with both streams sent to a `StringIO`, dropping the `dead link` lines; `_write_group_indexes`, `_write_entry_point`; `verify`; `_check_written`.

The map is written before dicing because volumes link to each other. Dicing therefore reports links into trees not yet built as dead, so `dice_doc`'s status is ignored and `verify` judges every tree again. Group-index lines go after the parent's Contents block, outside reassembly's cut (§6).

### `refactor` and `list` (SPEC §9)

`_walk` is one pass over the lines, used in two modes: `converting=True` yields the output lines and the long-title notes (`convert_runins`); `converting=False` yields the TSV rows (`list_runins`). The classifier `_classify` is shared, so the `list` classes and the conversion decisions cannot drift. `refactor()` then runs `check_hunks` on the input text and the joined output.

### `check-links`, `check-tree` (SPEC §8.4, §8.5)

Both walk files with `markdown_files` and read links with `prose_links` (§6). `check_trees` maps each file to the real paths it links to, checks that each file's parent links to it, then walks breadth-first from the root's entry point.

## §6 Mechanisms

### Link scanning is shared

`linkrewrite._scan` is the only scanner of a line. It skips code spans, finds `[text](target)` per SPEC §4.1, and, given an `on_ref` callback, finds `§N` references. Callers differ by callback:

| Caller | Callbacks | Used by |
|---|---|---|
| `Linker.forward` | rebaser + reference linker | write pass |
| `Linker.rebase_only` | rebaser | reassembly (expected side) |
| `Linker.revert` | un-linker | reassembly (actual side) |
| `link_targets` | collector | `prose_links` |

`revert` recognises a link as forward-made when its text starts with `§<digit>`, names a known number (and child name if present), and its target equals the path `forward` would compute; any other link is left as is.

### Rebasing

`_rebase` joins a target, or its link-map destination, onto `Tree.root` and takes `rel` from `outabs/<leaf dir>`. `rel` is purely lexical over `/`-split strings.

### Anchor homes

`_anchor_homes` maps each monolith heading anchor to `(file, anchor within file)`. It numbers headings per owning section (`per_file`), so repeat suffixes follow the file the heading lands in (SPEC §4.4), and marks the heading that opens a non-entry file as needing no fragment. The owner of a source line is found by a line-to-section table built from `Section.first` / `last`.

### Contents blocks and the cut

`contents_block` is appended last, so `check_reassembly` cuts at the last line equal to `Contents:`. This drops lines appended after it (group lines) and ignores any earlier `Contents:` line from the source.

### Planning

`plan_sections` makes two passes. The first collects splittable headings outside fences. The second assigns parents using a stack of open headings, names and paths each section, and finds collisions with a path-to-line dict.

### Refactor self-check

`check_hunks` diffs `terminated_lines` of input and output with `difflib.SequenceMatcher(autojunk=False)`, merges changed regions separated by up to three blank unchanged lines, and compares each merged hunk's new side with `_expected(old)`, which derives the conversion separately from `_walk` / `_classify`, sharing only the `_BOLD_ITEM` / `_BOLD_RUNIN` patterns. A divergence between the two derivations is reported as `BAD`.

## §7 Invariants

- Head-file names are spelled only in `heads.py`; every other module imports them.
- Fenced code is defined only by `FenceTracker`; `outline`, `split`, `reassemble`, `linkcheck` and `refactor` use it.
- Only `textfile` opens files for text; passes use its readers and writers.
- Passes are functions of their arguments and write only to the `out` / `err` streams they are given (drivers take `stdout` / `stderr`). Nothing below `__main__` touches `sys.stdout`, which is what lets `manifest` capture a volume's output in a `StringIO`. Drivers own filesystem layout and exit statuses.
- `Section` lists are in document order with `id == index`; `sections[0]` is always the entry point.
- Sections' `first`..`last` ranges partition `1..len(lines)`.
- The file-name slug (`outline.slug`) and the heading anchor (`linkcheck.github_anchor`) are separate functions and never substituted for each other.

## §8 Test harness

`docdicer/test/test_dicer.py` has two `unittest` classes.

`GoldenCases.test_cases` enumerates the directories under `data/`; each is a subtest. A case holds:

| Path | Content |
|---|---|
| `input/` | the working tree the command runs in (symlinks copied as symlinks) |
| `args` | the command-line arguments, one per line |
| `env` | optional `KEY=VALUE` lines; `DICER_KEEP` is removed from the inherited environment otherwise |
| `expected/stdout`, `expected/stderr` | exact bytes |
| `expected/exit` | the status and a newline |
| `expected/tree/` | every file of the working tree after the run, inputs included |

The harness copies `input/` to a scratch directory under `docdicer/test/temp/` (git-ignored), runs `sys.executable -m docdicer <args>` there as a subprocess, and compares stdout, stderr, the exit status and a `{relative path: bytes}` map of all files. Only files are compared, so empty directories are not asserted.

`HunkCheck` calls `check_hunks` directly to assert that an edit beyond a conversion is reported `BAD`.

## §9 Extension points

- *A new command*: add a parser in `__main__._parser`, a driver in the layer that owns its inputs, and a golden case; exit statuses follow SPEC §2.
- *A new link form*: change `_scan` and `Linker` only (§6).
- *A new split level*: `outline._DEEPEST_SPLIT_LEVEL`; the heading-width test in `plan_sections` bounds what is a heading at all.
- *Head-file names*: fixed, not an extension point.
