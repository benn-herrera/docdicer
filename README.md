# docdicer

A stdlib-only python 3.9 tool for transforming and viewing project markdown documents to facilitate AI-assisted development

- Bidirectional transformation of heavy monolithic markdown documents to and from context-friendly file hierarchy
  - Permanent project documents (SPEC, ARCHITECTURE, CONVENTIONS)
  - Working design and plan docs 
- Serves a kanban display of active designs and plans

docdicer's own documents will be diced when one passes 800 lines; below that, a single file is cheap enough to
read whole.

<img src="doctree.jpg" width="25%"/>

<img src="kanban.jpg" width="75%"/>

## Requirements

Python 3.9 or later, standard library only. The dicing commands take every input as an argument and name nothing
specific to a repository; run them from the directory the documents' relative links are written against.

## Developer

<https://keyoxide.org/wkd/benn@bennherrera.dev>

## Installation
```bash
pip install git+https://github.com/benn-herrera/docdicer
```

## Tools

One CLI, `python3 -m docdicer <command> ...` with this repository's root (the directory holding
the `docdicer` package) on `PYTHONPATH`; installed with pip, the same CLI is the `docdicer`
command. `python3 -m docdicer --version` prints the version; `-h`,
on its own or after a command, prints help. Exit status is 0 on success, 1 when a check or step
fails, 2 on bad arguments.

- `dice-doc <monolith.md> <out-dir> [map.tsv]` dices one document and runs the checks below.
  `out-dir` must be absent or empty.
- `undice <tree-dir> <monolith.md>` writes a diced tree back out as one document: section links
  return to `§N`, links to a heading's file return to `#anchor`, other relative links are rebased
  to the run directory. It then checks that dicing the result reproduces the tree, Contents blocks
  aside, reporting any `.md` the tree holds that it would not write, naming the rename, heading
  edit, Contents edit or removal that fixes it. `monolith.md` must not exist.
  The result need not equal the original source; a heading holding a markdown link loses its whole
  section, which `undice` reports as unreadable and not reproduced.
- `refactor <in.md> <out.md> [items]` turns bold run-in titles into headings (see Transforms);
  any `items` value other than empty or `0` converts bold list items too. Exit 1 on a bad hunk,
  2 on an unreadable input.
- `dice-docs <manifest.tsv> <src-dir> <work-dir>` drives several documents: refactor where
  flagged, link map, dice each, group indexes and entry point, verify. Intermediates (refactored
  copies, their `.skipped` lists, the link map `links.tsv`) go to `<work-dir>`; output
  directories not nested in another output are removed first. See Worked example for a manifest.
- `verify <map|-> <monolith> <out-dir> ...` re-runs the checks on built trees, once every tree a
  link points into exists. Exit 1 if any check fails.
- `list <doc.md>` classifies every bold-led line of a document, one TSV row each: `doc:line`,
  class, new heading level, title, enclosing heading.
- `check-links <root>...` checks markdown files that need not come from a dicing: a directory
  root is walked for every `.md`, a file root is checked alone. Each relative link or image
  outside fenced code and code spans must name an existing path, resolved from the linking file's
  directory; one with a `#fragment` must name a markdown file (the linking file itself, for a bare
  `#fragment`) with a heading whose GitHub anchor equals it. The anchor is the heading text
  lowercased, with every character but letters, digits, spaces, `-` and `_` dropped and spaces
  made `-`; a repeat in one file takes `-1`, `-2`, … in order. It is not a leaf's file-name slug.
  Headings inside fenced code have none. Links with a URL scheme and root-absolute `/` links are
  skipped. Prints `file:line: target: missing file` or `missing anchor` to stderr per broken link,
  then the count; exit 1 if any is broken, 2 on bad arguments, a missing root or an unreadable file.
- `check-tree <root>...` checks a diced tree's structure, which no link check sees: every
  document is linked from its parent, and every document is reachable by links from the root's
  `entry-point.md`. A directory's head is its `entry-point.md` where it has one (the root, a diced
  volume), else its `index.md`; a document's parent is its directory's head, and a head's parent
  is the head above it. A leaf that its index stopped listing fails even where another document,
  such as the entry point's contents, still links it. Exit 1 on any problem, 2 on bad arguments,
  a root that is not a directory, or an unreadable `.md` under one.
- `check-plan [<plan>]` checks that a development plan is in the form a program can read: a status
  table under `## Status` whose `Package` and `State` columns hold unique IDs without spaces and
  states opening with `dispatchable`, `in progress` or `landed` (an empty cell is a drafted
  package), and a `Rating` column whose cells open `mechanical` or `expert`, and a
  `Release: <version>` line, where present, first after the H1 heading. A package's title is the
  text after its ID in its heading. A package whose title opens `Post-plan review` is allowed only
  with one whose title opens `Post-plan burndown`, and the reverse. `<plan>` is a
  monolith or a diced plan's `entry-point.md`; without it the active plan is checked, `ACTIVE_PLAN.md`
  else `ACTIVE_PLAN/entry-point.md` under the nearest ancestor directory holding `.git`. Absence is
  valid: no status table, or no active plan, exits 0. Prints
  `file:line: problem: found <text>; accepted: form` to stderr per breach, in reading order, `<text>`
  being the text found in a code span (`` found `text` ``), or `an empty cell`; then
  `plan checked: <plan>, work packages: <N>, problems: <P>`; exit 1 on any breach, 2 on a `<plan>`
  that is not a file, no project root, or an unreadable plan file.
- `kanban [<project-dir>]` serves a live board of a project's development-process files on
  `127.0.0.1`: it prints `http://127.0.0.1:<port>/` on stdout; open that URL in a browser and stop
  the server with Ctrl-C (exit 0). `<project-dir>` is any directory inside the project; without it
  the project is the one the current directory is in. The columns are Roadmap (`ROADMAP.md` items
  and unlinked `ROADMAP_PLANS/` entries), Design (the active design) and, from the active plan's
  status table, Drafted, Dispatchable, In progress and Landed. The page follows edits to those files
  without a reload. Its only writes to documents are moves of an entry between `ROADMAP.md`
  and the active design, made by dropping a card on Design or on Roadmap; a move is refused if a
  file changed since the board read it. The plan columns are read-only, drawn as
  outlined boxes of flat cards against the filled, draggable Roadmap and Design: a work package's
  state changes by editing the plan, and the board shows the edit. The board keeps no state of its
  own. Exit 2 on a directory that does not exist, no project root, an unreadable file at start, or a port
  that cannot be bound.

The plan reader, `check-plan`, the board model and its server live in `kanban/`; ARCHITECTURE §2 maps
both packages module by module. The passes behind the dicing commands live in `dicerlib/`, one module each: `outline` (headings to files),
`split` (writing the tree), `linkrewrite` (section links, rebasing, the map), `reassemble` and
`linkcheck` (the checks, `check-links` included), `treecheck` (`check-tree`), `refactor` (run-ins
and the hunk check), `dicedoc` and `manifest` (the drivers), with `heads` (head-file names) and
`textfile` (file I/O and fenced code) beneath them all. `just test` runs one pytest test per golden
case under `docdicer/test/data/`, one `undice` round trip per case that dices without a map and succeeds, and the
per-module unit tests; `just build` builds a wheel into `dist/`.

## Heading convention

`#` title, then `##` sections, `###` subsections, `####` sub-subsections; deeper headings and
headings inside fenced code are text. A heading starting `N.` or `N.M` is numbered: its file is
`<number>-<slug>`, and `§N`, `§N.M` in prose link to it. Any other heading is named by its slug.
A heading with children becomes a directory with an `index.md`; otherwise one leaf file. Leaves
hold exactly the original lines, heading included. Sibling headings with the same slug would write
the same file, so they are an error and the run fails. Text before the first `##`, `###` or `####`
is `entry-point.md` with a `Contents:` list.

## Head-file names

A tree's root and each diced volume open at `entry-point.md`; every other directory opens at
`index.md`. These names are fixed, not options: a reader moving between projects finds any tree's
way in by them. `dicerlib/heads.py` holds them, and every pass reads them from there. `check-tree`
reports a tree laid out any other way.

## Transforms (`refactor`)

A paragraph opening with `**Title.**`, `**Title:**` or a whole-line `**Title**` becomes a heading one
level below its enclosing heading (at most `######`), then a blank line and the rest. With `items`, a
column-0 list item `- **Title.** rest` does the same and its continuation lines are dedented by 2.
Titles over 8 words are skipped and listed in `<out.md>.skipped`. Left as they are, unlisted: bold
followed by more sentence (`**Note** that ...`); indented items; bold at the start of a wrapped line;
bold outside any section. Every changed hunk is checked to be one of these conversions.

Titles in the keep-list are never converted: the paragraph or item stays verbatim inside its section's
leaf and produces no hunk. The list is the comma-separated environment variable `DICER_KEEP` (read by
`refactor`, `dice-docs` and `list`), default `Open`; set it empty to keep none. Matching is exact and
case-sensitive on the title without its trailing `.` or `:`. `list` shows kept lines as `KEEP`.

## Link rewriting and the map

`§N` links to its file; followed by a backticked name, it goes to the child whose heading holds that
name. A `§N` right after `SPEC `, `ARCHITECTURE `, `THESIS ` or `CONVENTIONS ` is left as
text (another document's section). A link to a heading of the document itself, `#anchor`, goes to
the file now holding that heading: to the file alone where the heading opens it, else with the
heading's anchor within that file. An anchor that names no heading is left as written, for
`check-links` to report. Relative links to files outside the document are rewritten to resolve from
each leaf. The map is TSV: `<target>\t<new path from the run directory>` points a link
to a diced document at its entry point; `<target>\t<heading>\t<path>` points a link whose
following text quotes that heading, as `, "The walk"`, at the heading's leaf.

## Manifest (`dice-docs`)

Tab separated: `file`, `outdir`, `flags`, `label`; blank lines and lines starting `#` are skipped.
Flags (comma list, may be empty): `refactor`, `items`, `entry` (the file is copied verbatim to
`<outdir>/entry-point.md` with a `Volumes:` list of the volumes directly under `<outdir>`, each with
the first sentence of its opening paragraph; it is not diced). A volume nested as
`<parent>/<group>/<name>` takes the group's title in `label`; the group gets an `index.md` and the
parent's entry point gains a line for it. Parents precede children. Documents link to each other by
`file` as written in the manifest; the `entry` document by its base name.

## Checks

- Reassembly: concatenating the leaves in order, with the added `Contents:` blocks removed and
  section links reverted, reproduces the monolith's lines exactly (outside links are compared in
  their rewritten form). Proves nothing was lost, moved or edited.
- Links: every link in the output, root-absolute `/` links and links with a URL scheme skipped, resolves
  to an existing file from the linking file's directory. Proves the tree and the cross-document map
  are consistent; it does not check `#anchor` fragments, which `check-links` does.

## Worked example

kbase's `PROJECT_DOCS/` was first produced from its root documents with this manifest (tab
separated; kbase's `tools/dicer/kbase-docs.tsv`, in the commit that introduced it), the sources
copied from `HEAD` into a scratch directory, run by kbase's own `dice-docs` justfile target:

| file | outdir | flags | label |
|---|---|---|---|
| THESIS.md | PROJECT_DOCS | entry | |
| SPEC.md | PROJECT_DOCS/SPEC | refactor | |
| ARCHITECTURE.md | PROJECT_DOCS/ARCHITECTURE | refactor | |
| CONVENTIONS.md | PROJECT_DOCS/CONVENTIONS | refactor,items | |
| RIGOR_AND_BEARING_SCORING_SCHEME.md | PROJECT_DOCS/SPEC/scoring/rigor-and-bearing | | Scoring schemes |
| STRENGTH_SCORING_SCHEME.md | PROJECT_DOCS/SPEC/scoring/strength | | |

    just dice-docs kbase-docs.tsv <src-dir> <work-dir>

The leaves under `PROJECT_DOCS/` are now the source; the root `SPEC.md`, `ARCHITECTURE.md`,
`CONVENTIONS.md` and `THESIS.md` are pointers to them.
