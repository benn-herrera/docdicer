# Commands

Every command's arguments, options and exit statuses. The messages and faults behind them are
[SPEC](../SPEC.md)'s, whose §2 table sends each command to the section that states them. For what a
check proves, see [Checks](checks.md); for how a document is diced, [Dicing](dicing.md); for the
board, [The board](kanban.md). [README](../README.md) gives one line per command.

One CLI, `python3 -m docdicer <command> ...` with this repository's root (the directory holding
the `docdicer` package) on `PYTHONPATH`; installed with pip, the same CLI is the `docdicer`
command. `python3 -m docdicer --version` prints the version; `-h`, on its own or after a command,
prints help. Exit status is 0 on success, 1 when a check or step fails, 2 on bad arguments.

## `dice-doc`

`dice-doc [--split-level <level>] <monolith.md> <out-dir> [map.tsv]` dices one document and runs
the reassembly and link checks ([Checks](checks.md)). `out-dir` must be absent or empty.
`--split-level` (`2`, `3` or `4`, default `4`) is the deepest heading level that splits (see
[Heading convention](dicing.md#heading-convention)). `map.tsv`, where given, is the link map
(see [Link rewriting and the map](dicing.md#link-rewriting-and-the-map)).

## `undice`

`undice [--split-level <level>] <tree-dir> <monolith.md>` writes a diced tree back out as one
document: section links return to `§N`, links to a heading's file return to `#anchor`, other
relative links are rebased to the run directory. It then checks that dicing the result reproduces
the tree, Contents blocks aside, reporting any `.md` the tree holds that it would not write,
naming the rename, heading edit, Contents edit or removal that fixes it. `monolith.md` must not
exist. Give it the `--split-level` the tree was diced at.

The result need not equal the original source; a title holding `]` or unbalanced brackets, for
one, yields a malformed Contents link that `undice` reports as not reproduced (SPEC §10).

## `dice-docs`

`dice-docs <manifest.tsv> <src-dir> <work-dir>` drives several documents, each diced at the
default split level (`4`): link map, dice each, group indexes and entry point, verify. The link
map `links.tsv` goes to `<work-dir>`; output directories not nested in another output are removed
first. A manifest row flagged anything but `entry` ends the command, exit 2, before the tree or the
link map is written; `<work-dir>` is created before the rows are read, so it may be left behind,
empty. See [The manifest](dicing.md#manifest-dice-docs) for its columns, and
[Worked example](development.md#worked-example) for one in use.

## `verify`

`verify [--split-level <level>] <map|-> <monolith> <out-dir> ...` re-runs the checks on built
trees, diced at that split level, once every tree a link points into exists. `<map|->` is a link
map path, or `-` for none. Exit 1 if any check fails.

## `check-links`

`check-links <root>...` checks markdown files that need not come from a dicing: a directory root
is walked for every `.md`, a file root is checked alone. It prints `file:line: target: missing
file` or `missing anchor` to stderr per broken link, then the count; exit 1 if any is broken, 2 on
bad arguments, a missing root or an unreadable file. What it checks, and what an anchor is:
[Checks: `check-links`](checks.md#check-links).

## `check-tree`

`check-tree <root>...` checks a diced tree's structure, which no link check sees. Exit 1 on any
problem, 2 on bad arguments, a root that is not a directory, or an unreadable `.md` under one.
What it checks: [Checks: `check-tree`](checks.md#check-tree).

## `check-plan`

`check-plan [<plan>]` checks that a development plan is in the form a program can read. `<plan>`
is a monolith or a diced plan's `entry-point.md`; without it the active plan is checked,
`ACTIVE_PLAN.md` else `ACTIVE_PLAN/entry-point.md` under the nearest ancestor directory holding
`.git`. Absence is valid: no status table, or no active plan, exits 0. Prints
`file:line: problem: found <text>; accepted: form` to stderr per breach, in reading order, `<text>`
being the text found in a code span (`` found `text` ``), or `an empty cell`; then
`plan checked: <plan>, work packages: <N>, problems: <P>`; exit 1 on any breach, 2 on a `<plan>`
that is not a file, no project root, or an unreadable plan file. The form:
[Checks: `check-plan`](checks.md#check-plan).

## `check-design`

`check-design [<design>]` checks that a design is in its final form, ready to plan from; a design
still in progress fails it. `<design>` is a monolith or a diced design's `entry-point.md`; without
it the active design is checked, `ACTIVE_DESIGN.md` else `ACTIVE_DESIGN/entry-point.md` under the
nearest ancestor directory holding `.git`. It prints
`file:line: problem: found <text>; accepted: form` to stderr per breach, in document order, then
`design checked: <design>, entries: <N>, problems: <P>` to stdout; exit 1 on any breach, 2 on a
`<design>` that is not a file, no project root, or an unreadable file of the design. No active
design prints `no active design in <root>` and exits 0. The final form:
[Checks: `check-design`](checks.md#check-design).

## `check-roadmap`

`check-roadmap [<roadmap>]` checks that `ROADMAP.md` is in the ticket layout the board reads.
`<roadmap>` is one file, whatever its name; without it `ROADMAP.md` under the nearest ancestor
directory holding `.git` is checked, and none there prints `no roadmap in <root>` and exits 0.
Prints `file:line: problem: found <text>; accepted: form` to stderr per breach, in line order, then
`roadmap checked: <roadmap>, tickets: <N>, problems: <P>` to stdout; exit 1 on any breach, 2 on a
`<roadmap>` that is not a file, no project root, or an unreadable roadmap. The layout, with a
roadmap in it: [Checks: `check-roadmap`](checks.md#check-roadmap).

## `kanban`

`kanban [<project-dir>]` serves a live board of a project's development-process files on
`127.0.0.1`: it prints `http://127.0.0.1:<port>/` on stdout. `<project-dir>` is any directory
inside the project; without it the project is the one the current directory is in. Exit 2 on a
directory that does not exist, no project root, an unreadable file at start, or a port that cannot
be bound. Columns, cards, links, moves and refusals: [The board](kanban.md).

## See also

- [Checks](checks.md) — what each check proves
- [Dicing](dicing.md) — headings, head files, link rewriting, the manifest
- [The board](kanban.md) — `kanban`'s page and its moves
- [Development](development.md) — build, test, module map, worked example
