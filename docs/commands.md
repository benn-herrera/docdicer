# Commands

Every command's arguments, options, exit statuses, messages and streams. The contract the messages
carry is [SPEC](../SPEC.md)'s: §2 for the exit-status classes and streams, each command's section
for what it names. What a check proves is [Checks](checks.md)'s; how a document is diced,
[Dicing](dicing.md)'s; the board, [The board](kanban.md)'s. [README](../README.md) gives one line per
command.

## Invocation

`docdicer <command> ...`. Running one from its checkout, without installing it, is
`PYTHONPATH=<checkout> python3 -m docdicer <command> ...`, the checkout being the directory holding
the `docdicer` package; every example on this page is written that way.

`--version` prints the version and `-h`, alone or after a command, prints help.

**Exit status.** 0 success; 1 a step or check failed; 2 bad arguments — usage errors and the
per-command argument faults each command's section names.

**Streams.** Results and summaries go to stdout; diagnostics, warnings and failure details go to
stderr, `verify`'s reassembly output excepted.

**Usage errors.** A missing command, a wrong argument count, a `--split-level` outside `2`, `3` and
`4`, a `<plan>`, `<design>` or `<roadmap>` named but not a file, a `<project-dir>` that is not a
directory, and each root fault a section gives: each prints `docdicer: error: <message>` to stderr
and exits 2. What falls outside that list is each section's own.

**Project root.** The `check-plan`, `check-design`, `check-roadmap` and `kanban` sections' "project
root" is the nearest ancestor of the current directory, the directory itself included, that holds an
entry named `.git`; git is not run.

## `dice-doc`

`dice-doc [--split-level <level>] <monolith.md> <out-dir> [map.tsv]` dices one document and runs the
reassembly and link checks ([Checks](checks.md)). `--split-level` (`2`, `3` or `4`, default `4`) is
the deepest heading level that splits (see [Heading convention](dicing.md#heading-convention)).
`map.tsv`, where given, is the link map (see [Link rewriting and the map](dicing.md#link-rewriting-and-the-map)).

| Condition | stderr | stdout | Exit |
|---|---|---|---|
| `<monolith>` is not a file | `not a file: <monolith>` | | 2 |
| `map.tsv` is given and not a file | `not a file: <map>` | | 2 |
| `<out-dir>` exists and is not a directory | `not a directory: <out-dir>` | | 2 |
| `<out-dir>` exists and is not empty | `out-dir not empty: <out-dir>` | | 2 |
| planning fails: an empty slug, or two sections writing one path | the planning message (SPEC §3.2) | | 1 |

Otherwise `<out-dir>` is created if absent, the tree is written, and stderr carries any
`duplicate section number <number>` line (once per number), the `refs linked: <R>; dangling: <D>
distinct:` line and its dangling list, and any `extra level-1 heading at line <N> kept as text`. The
reassembly check then runs; where it fails the command exits 1 without the link check. The link check
follows: its `dead link:` lines go to stderr and its summary to stdout, and any dead link exits 1.
Files already written remain on failure. Planning failure aside, `<out-dir>` is created before the
planning, so a failed run may leave it empty.

## `undice`

`undice [--split-level <level>] <tree-dir> <monolith.md>` writes a diced tree back out as one
document: section links return to `§N`, links to a heading's file return to `#anchor`, other
relative links are rebased to the run directory. It then checks that dicing the result reproduces
the tree, Contents blocks aside. Give it the `--split-level` the tree was diced at.

| Condition | stderr | stdout | Exit |
|---|---|---|---|
| `<tree-dir>/entry-point.md` is not a readable file | `not a tree: <tree-dir>` | | 2 |
| `<monolith.md>` exists, a dangling symlink included | `<monolith> exists: name another output, or move or delete it` | | 2 |
| `<monolith.md>` cannot be written | `cannot write: <monolith>` | | 2 |

The document is then written, and the command exits 1 where any of these fails: a file the tree's
entry point lists cannot be read — `undice: cannot read <tree-dir>/<target>` to stderr, the file left
out; planning the result fails (the §3.2 message); the reassembly or link check fails; or an `.md`
file under `<tree-dir>` is one the dicing would not write:

| The file | stderr |
|---|---|
| was read as a section the dicing places at another path | `undice: <file> would be re-diced as <tree-dir>/<path>: rename the file or edit its heading to match` |
| was read, but opens no section | `undice: <file> opens no section: start it with a level 2 to <level> heading, or remove it and its Contents line` |
| was not read | `undice: not reproduced: <file>: link it from <tree-dir>/entry-point.md's Contents, or remove it` |

A nested volume's files are not reported. stderr also carries the `duplicate section number` and
`refs linked` lines the dicing reports, and the `reassemble:` and `dead link:` lines of the two
checks; the link check's summary goes to stdout. `<monolith.md>` is kept either way.

The result need not equal the original source; a title holding `]` or unbalanced brackets, for one,
yields a malformed Contents link that `undice` reports as not reproduced (SPEC §9).

## `dice-docs`

`dice-docs <manifest.tsv> <src-dir> <work-dir>` drives several documents, each diced at the default
split level (`4`): link map, dice each, group indexes and entry point, verify.

| Condition | stderr | Exit |
|---|---|---|
| `<manifest.tsv>` is not a file | `not a file: <manifest>` | 2 |
| `<src-dir>` is not a directory | `not a directory: <src-dir>` | 2 |
| a row's source is absent | `missing source: <src-dir>/<file>` | 2 |
| a row's `flags` hold anything but `entry` | `unknown flag: <flag> in row for <file> (the only flag is entry)` | 2 |

The fault rows are read in order and end the command before the tree or the link map is written;
`<work-dir>` is created first, so it may be left behind, empty. The link map `links.tsv` goes to
`<work-dir>`; output directories not nested in another output are removed first. A volume's failed
dicing does not stop the others: each volume's output is preceded by `=== <file>` on stdout, with
its stderr merged into stdout and its `dead link:` lines dropped, and steps 7 and 8 of SPEC §7.2
decide the result — exit 0 where every volume verifies and every file written by the script links
only to existing files, else 1. See [The manifest](dicing.md#manifest-dice-docs) for its columns,
and [Worked example](development.md#worked-example) for one in use.

## `verify`

`verify [--split-level <level>] <map|-> (<monolith> <out-dir>) ...` re-runs the checks on built
trees, diced at that split level, once every tree a link points into exists. `<map|->` is a link map
path, or `-` for none; a map path that is not a file is treated as no map. What follows is one
`<monolith> <out-dir>` pair or more, an odd count a usage error
(`verify takes <map|-> followed by <monolith> <out> pairs`).

Per pair, stdout carries `=== <monolith> -> <out-dir>`, then the reassembly check's result, then
each link-check line indented two spaces, then `  leaves: <K>`, the count of `.md` files under
`<out-dir>` other than `entry-point.md` and `index.md`. `<out-dir>` that is not a directory prints
`not a directory: <out-dir>` to stderr and `<monolith>` that cannot be read prints
`cannot read: <monolith>` to stderr, either skipping the rest of that pair. Any failing pair exits
1.

## `check-links`

`check-links <root>...` checks markdown files that need not come from a dicing: a directory root
is walked for every `.md`, a file root is checked alone.

| Condition | stderr | stdout | Exit |
|---|---|---|---|
| a root does not exist | `docdicer: error: no such root: <roots>` | | 2 |
| a markdown file under a root cannot be read | `cannot read: <path>`, before any link is checked | | 2 |
| a link's path part names no existing file | `<file>:<line>: <target>: missing file` | | 1 |
| a `#fragment` names no heading anchor | `<file>:<line>: <target>: missing anchor` | | 1 |

The summary is `links checked: <N>, broken: <B>` on stdout. What it checks, and what an anchor is:
[Checks: `check-links`](checks.md#check-links).

## `check-tree`

`check-tree <root>...` checks a diced tree's structure, which no link check sees.

| Condition | stderr | stdout | Exit |
|---|---|---|---|
| a root is not a directory | `docdicer: error: no such directory: <roots>` | | 2 |
| a markdown file under a root cannot be read | `cannot read: <path>`, before any check | | 2 |
| a root holds no `entry-point.md` | `<root>: no entry-point.md` | | 1 |
| a document's parent does not link to it | `<file>: not linked from its parent <parent>` | | 1 |
| a document has no parent inside the root | `<file>: no parent document (an index.md or entry-point.md beside it or above it)` | | 1 |
| a document is not reachable from the root's entry point | `<file>: not reachable from <entry-point>` | | 1 |

The summary is `documents checked: <N>, problems: <P>` on stdout. What it checks:
[Checks: `check-tree`](checks.md#check-tree).

## `check-plan`

`check-plan [<plan>]` checks that a development plan is in the form a program can read. `<plan>`
is a monolith or a diced plan's `entry-point.md`: `entry-point.md` names one plan with every other
`.md` file beneath its directory, entry point first, then each level in name order. Without `<plan>`
the active plan is checked, `ACTIVE_PLAN.md` or, where the monolith is absent,
`ACTIVE_PLAN/entry-point.md` under the project root, found as below.

| Condition | stderr | stdout | Exit |
|---|---|---|---|
| no breach | | `plan checked: <plan>, work packages: <N>, problems: 0` | 0 |
| without `<plan>`, no active plan under the root | | `no active plan in <root>` | 0 |
| any breach | one line per breach, below | the summary, `problems: <P>` | 1 |
| `<plan>` is named and is not a file | `docdicer: error: no such plan file: <plan> (name a plan's markdown file, or a diced plan's entry-point.md)` | | 2 |
| without `<plan>`, no project root | `no project root: neither <directory> nor any directory above it holds .git; run docdicer check-plan inside a project, or name the plan to check: docdicer check-plan <plan>` | | 2 |
| without `<plan>`, both forms of the active plan exist | `both forms of the active plan exist: <monolith> and <entry-point>: remove one`, the two paths absolute | | 2 |
| a file of the plan cannot be read, a dangling symlink included | `cannot read: <file>` | | 2 |

The exit-2 faults are found before any breach or summary is printed. Each breach line is
`<file>:<line>: <problem>: found <text>; accepted: <form>` on stderr, in the plan's file order, `<text>`
being the text found in a code span or `an empty cell`. Absence is valid: a plan with no status table
exits 0 unless it holds a breach; one with a misplaced `Release:` line exits 1 either way. Every
`<problem>` wording, and the line each is reported at:
[Checks: `check-plan`](checks.md#check-plan).

## `check-design`

`check-design [--deltas-applied] [<design>]` checks that a design is in its final form, ready to
plan from: beside the form, every pair's from passage still matches its target, so a design is
accepted only against the targets it changes. A design still being drafted fails it. `<design>` is
a monolith or a diced design's `entry-point.md`. Without `<design>` the active design is checked,
`ACTIVE_DESIGN.md` or, where the monolith is absent, `ACTIVE_DESIGN/entry-point.md` under the project
root, found as `check-plan` finds it.

| Condition | stderr | stdout | Exit |
|---|---|---|---|
| no breach, every pair's from matching | | `design checked: <design>, entries: <N>, problems: 0` | 0 |
| without `<design>`, no active design under the root | | `no active design in <root>` | 0 |
| any breach, a from no longer matching or an unreadable target included | one line per breach, below | the summary, `problems: <P>` | 1 |
| `<design>` is named and is not a file | `docdicer: error: no such design file: <design> (name a design's markdown file, or a diced design's entry-point.md)` | | 2 |
| without `<design>`, no project root | as `check-plan`'s, naming `docdicer check-design` and `docdicer check-design <design>` | | 2 |
| without `<design>`, both forms of the active design exist | `both forms of the active design exist: <monolith> and <entry-point>: remove one` | | 2 |
| a file of the design cannot be read | `cannot read: <file>` | | 2 |

Breach lines are `check-plan`'s form on stderr, in document order; every `<problem>` wording:
[Checks: `check-design`](checks.md#check-design). `## Drafts` is not a delta, so it is reported
there until the design reaches its final form. The form's Terms, how a pair is read, and the two
failures the table does not list — an `**As it stands:**` line whose next non-blank line opens no
fenced block, and a `**Becomes:**` line outside a pair — are
[Checks: `check-design`](checks.md#check-design)'s too.

With `--deltas-applied` the pairs are checked as applied: each is classified `pending`, `landed`,
`drifted`, `conflicting` or `unreadable`, and printed to stdout as `file:line: <state>: <target>`,
one per pair in document order, before the summary
`design checked: <design>, pairs: <N>, landed: <L>, pending: <G>, drifted: <D>, conflicting: <C>,
problems: <P>`. `landed` is the passing state and `pending` the expected mid-execution state; a
drifted, conflicting or unreadable pair is a breach, reported on stderr as above, and a pair counted
in no state is unreadable. Where a drifted or conflicting pair's target also holds a landed pair's
becomes passage, its breach line is followed by
`interference: <target> also holds the becomes passage of a landed pair of this design`. Exit 0
when every pair has landed and no breach stands, 1 while a pair has not landed or a breach stands.

A limit the messages do not state: a pair's block whose closing fence is immediately followed by
another opening fence reads as one passage (SPEC §9).

## `check-roadmap`

`check-roadmap [<roadmap>]` checks that `ROADMAP.md` is in the ticket layout the board reads.
`<roadmap>` is one file, whatever its name; without it `ROADMAP.md` under the project root, found as
`check-plan` finds it, is checked.

| Condition | stderr | stdout | Exit |
|---|---|---|---|
| no breach | | `roadmap checked: <roadmap>, tickets: <N>, problems: 0` | 0 |
| no `ROADMAP.md` under the root | | `no roadmap in <root>` | 0 |
| any breach | one line per breach, below | the summary, `problems: <P>` | 1 |
| `<roadmap>` is named and is not a file | `docdicer: error: no such roadmap file: <roadmap> (name a roadmap's markdown file)` | | 2 |
| no project root | as `check-plan`'s, naming `docdicer check-roadmap` and `docdicer check-roadmap <roadmap>` | | 2 |
| a file checked cannot be read | `cannot read: <roadmap>` | | 2 |

Breach lines are `check-plan`'s form on stderr, in line order; every `<problem>` wording, and a
roadmap in the layout: [Checks: `check-roadmap`](checks.md#check-roadmap).

## `kanban`

`kanban [<project-dir>]` serves a live board of a project's development-process files on
`127.0.0.1`: it prints `http://127.0.0.1:<port>/` on stdout. `<project-dir>` is any directory
inside the project; without it the project is the one the current directory is in. Columns, cards,
links, moves and refusals: [The board](kanban.md).

| Condition | stderr | stdout | Exit |
|---|---|---|---|
| more than one argument, or an unknown option | `docdicer: error: <the usage error>` | | 2 |
| `<project-dir>` is not a directory | `docdicer: error: no such directory: <project-dir>` | | 2 |
| no project root | `no project root: neither <directory> nor any directory above it holds .git; run docdicer kanban inside a project, or name a directory inside a project: docdicer kanban <project-dir>` | | 2 |
| a document the board reads cannot be read at start | `cannot read: <file>` | | 2 |
| the port cannot be bound | `cannot listen: <reason>` | | 2 |

The last two exit before the URL is printed. Once serving, the command runs until Ctrl-C or the
page's stop button, and exits 0 either way; a document that cannot be read while it runs is named on
stderr as `cannot read: <file>` and the board keeps its last good state. A project with no roadmap,
design or plan shows an empty board rather than failing.

## See also

- [Checks](checks.md) — what each check proves, and the form it reads
- [Dicing](dicing.md) — headings, head files, link rewriting, the manifest
- [The board](kanban.md) — `kanban`'s page and its moves
- [Development](development.md) — build, test, the module map in ARCHITECTURE §2, worked example
