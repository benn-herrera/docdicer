# ARCHITECTURE – docdicer

How this implementation meets SPEC.md. User-visible outcomes are specified there and cited here as `SPEC §N`; they are not restated.

## §1 Build, run, test

Python ≥ 3.9, standard library only; packaging is in `pyproject.toml`.

| Target | Effect |
|---|---|
| `just test` | creates `.venv` if absent, then runs pytest over `docdicer/` with the project root on `PYTHONPATH` |
| `just build` | builds the wheel into `dist/`; the wheel carries `docdicer/kanban/assets/` (the board's page) as package data, declared in `pyproject.toml` |
| `just format` | black, isort, flake8 over `docdicer` |
| `just tag` | with tracked files committed, creates and verifies a signed annotated tag `v<version>` from `docdicer --version`; needs a signing key, pushes nothing |
| `just agents` | installs the pinned devpro into `.venv` unless that version is already there, then runs `devpro install .` for the `claude` and `opencode` harnesses |

## §2 Package map

Only `__init__` (`__version__`) and `__main__` sit at the package's top level, in `docdicer/`; every other module is in a subpackage: `docdicer/dicerlib/` for dicing and its checks, `docdicer/kanban/` for the roadmap, plan and design reader, `check-roadmap`, `check-plan`, `check-design`, the board and its server. Tests: `docdicer/test/test_dicer.py`, cases in `docdicer/test/data/<case>/`, and the per-module unit test files beside it (§8).

**`docdicer/`**

| Module | Responsibility |
|---|---|
| `__main__` | Builds the argparse parser, its `--split-level` on `dice-doc`, `undice` and `verify` taking `2` to `outline.DEEPEST_SPLIT_LEVEL`, reconfigures stdout and stderr to UTF-8 with `surrogateescape`, validates root arguments and refuses unreadable files (exit 2), calls one driver, and turns its result into the exit status. The only code that reads environment variables, `sys.argv` or the working directory: `check_roadmap`, `check_plan`, `check_design` and `run_kanban` are given `os.getcwd()` as their `start`. |

**`docdicer/dicerlib/`**

| Module | Responsibility |
|---|---|
| `heads` | `ENTRY_POINT`, `INDEX`, `HEADS` (SPEC §3.2; a head, SPEC §8.5) and `CONTENTS`, the one spelling of the `Contents:` line; `contents_line` (indent, text, path), the one spelling of a Contents block's line, which `split`, `manifest` and `kanban.board` write through. |
| `textfile` | File I/O (UTF-8, `surrogateescape`, `newline=""`); `replace_lines`, the whole-or-nothing write (§6); `\n`-only line splitting (`split_lines`, `terminated_lines`, `join_lines`); `is_blank`; `FenceTracker` / `fence_flags` (SPEC §3.1). |
| `linkscan` | `scan`, the single scanner of a line: code spans pass through, each link (SPEC §4.1) goes to an `on_link` callback and, given `on_ref`, each `§N` reference to it; `plain_text` (SPEC §4.1), the one reducer of links to their text, and `link_targets`, the target of each link of a line, in order; both built on `scan`. |
| `outline` | `plan_sections` turns lines into `Section` records (SPEC §3.1, §3.2), splitting headings of level 2 to its `deepest` argument, by default `DEEPEST_SPLIT_LEVEL` (4), the one home of the default and of the largest `--split-level`, and taking each heading's plain text (`linkscan.plain_text`) once and deriving its number, title and name from that; `section_name`, the §3.2 file name of text already reduced to plain text (it reduces nothing itself), which `plan_sections` uses; `Outline` gives lookups by number, children, depth and Contents link text, the last through `contents_text(number, title)`, the one spelling of that text (`§<number> <title>`, or the title where there is no number), which `kanban.board` uses for a new leaf's Contents lines. |
| `anchors` | The GitHub anchor functions (SPEC §4.4): `github_anchor`, given a heading's text, reduces it to plain text itself, through `linkscan.plain_text`; `heading_anchor_list` gives a document's headings outside fenced code with their anchors, repeats suffixed; `heading_anchors` the set of those anchors. |
| `linkrewrite` | `never_rebased` (the targets that mean the same from anywhere), the `Linker` built on `linkscan.scan` (forward rewriting and its inverse, `restore`), the `LinkMap` and `Tree` records, and the path helpers `rel` and `parent_dir` (SPEC §4, §5, §6.1). |
| `split` | The write pass: each section's lines through `Linker.forward`, plus `contents_block` (SPEC §3.3), written under the output directory; prints the `refs linked` line. |
| `reassemble` | The inverse of the write pass (SPEC §8.1). `contents_cut` finds a head's Contents block (§6); `own_end`, built on it, gives where a tree file's own lines end: a head file's (its name in `heads.HEADS`) at its Contents cut, any other file's at its end. `planform` and `dicedoc` read a file's own lines through `own_end`. |
| `linkcheck` | `check_links` (SPEC §8.2), `check_markdown_links` (SPEC §8.4) over `anchors.heading_anchors`, `prose_links`, `markdown_files`. |
| `treecheck` | `check_trees` (SPEC §8.5). |
| `dicedoc` | `dice_doc` (SPEC §6), `undice` (SPEC §6.1) and `verify` (SPEC §8.3); each takes the deepest split level as `deepest`, `outline.DEEPEST_SPLIT_LEVEL` by default, and passes it to every `plan_sections` call it makes, `undice`'s `_restored` included; each reports duplicate section numbers once, after planning. |
| `manifest` | `dice_docs` (SPEC §7): manifest reading, link-map rows, group indexes, the entry point, the written-files check. It passes no `deepest`, so every volume is planned, diced and verified at the default (SPEC §2). |

**`docdicer/kanban/`**

| Module | Responsibility |
|---|---|
| `planform` | The layout, roadmap, plan-form and design-form reader, the forms SPEC §8.6, §8.7 and §8.8 define. `read_layout` reads files already read, touching no disk, in the SPEC §8.8 layout, each file whole unless told to cut head files at their Contents cut, as `design_from_files` does for a diced design, and returns a `Layout`: its `parts`, categories and tickets in order, and every `Breach` of the layout; it sets a ticket's `Part.runs_on` where, carrying the ticket into a later file, it reads a non-blank line there before a heading of level 3 or less (SPEC §11.3). `read_file` reads one file as a `PlanFile`; `read_roadmap` is `read_file` followed by `roadmap_from_file`, which is `read_layout` with a `NO_CATEGORY` breach added where the layout holds no `CATEGORY` part. `read_layout` is the layout's only reader: `check-roadmap`, `check-design` and the board all read through it. `read_plan` returns a `Plan` and every `Breach` of the form it meets, sorted by the file's place in the reading order, then line. `design_files` gives a design's files in SPEC §8.7's document order, built on `reassemble.own_end` and `linkscan.link_targets`; it follows a Contents link only to a `.md` file beneath the entry point's directory, and files no followed link reaches come after, in `plan_files` order. `read_design` returns a `Design`: its `parts` in document order and every `Breach` of the SPEC §8.7 form; it is `design_files` followed by `design_from_files`, which reads a design from its files already read and touches no disk: `read_layout`'s parts and breaches, a delta's category made a `DELTA` part and its tickets `ENTRY` parts, and the breaches of the delta rules, the content before a delta's first entry taken from its part's `first_text`: it reads no line itself. The delta heading spellings live in `planform` only, as do the part kinds `CATEGORY`, `DELTA`, `TICKET` and `ENTRY`, plain strings so that the board's payload carries them unchanged, and `LAYOUT_BREACHES`, the `BreachKind`s of the layout; `board` and `plancheck` import them. Also the project's fixed file names (`ACTIVE_DESIGN`, `ACTIVE_PLAN`, `PARKED_DESIGNS`, `ROADMAP`) and where they are found: `find_project_root` (nearest ancestor holding `.git`, by `os.path.lexists`, never by running git), `active_document`, `roadmap_file` (`ROADMAP.md` under a root where it is a file), `parked_work` (each piece of SPEC §11.1 parked work as a `ParkedWork`, the parked files and trees of one topic grouped in one). Also `plan_files` (the files of a document, §5 `check-plan`, read from `document_paths`, their paths in that order, unread), `file_headings` (each `Heading` with its anchor, from `anchors.heading_anchor_list`), the `HEADING` pattern (a `#` run of 1 to 6 and a space), which `board` also uses, and `h1_line`, the reading of a document's H1 (outside fenced code). |
| `plancheck` | `check_plan` (SPEC §8.6): the `check-plan` driver over `planform`. `check_design` (SPEC §8.7) is the `check-design` driver over `read_design`, and `check_roadmap` (SPEC §8.8) the `check-roadmap` driver over `read_roadmap`, each sharing the breach line and the exit statuses with `check_plan`; `_found` renders a design's or roadmap's empty text as `found an empty line`. The three own the breach message lines (problem text and the `found` rendering), the summary, the default document (project root, then monolith before tree; `roadmap_file` for a roadmap) and the drivers' exit statuses, 2 for a missing project root or an unreadable document. |
| `board` | Over `planform`. `read_board` returns the `Board`: the roadmap's separators and ticket cards, the parked work no roadmap ticket links and whose link ticket is not in the design, the design's separators and ticket cards, the plan's package cards, every card with its `href` (§4), and as notices the breaches of `ROADMAP.md` and the layout breaches of the design. `watched_files` names every file the board reads, or would read were it there. `served_files` names the files the board reads that are files, the set SPEC §11 **Start** has the server serve, built from `roadmap_file`, `document_paths` and `parked_work` and reading none of them, so that one unreadable file leaves the others served. `move_to_design` and `move_to_roadmap` are the board's only writes to documents, the moves of a ticket between `ROADMAP.md` and the active design (§6); a refused move raises `MoveRefused`, a failed write `MoveWriteFailed`. `sha256` is the one digest of a file's text, used for `Board.sha256` and by `server` for its change detection; `root_relative` is the one spelling of a path relative to the root, `/`-separated. Reads `ROADMAP.md` once through `planform`'s `read_file` and takes its parts and breaches through `roadmap_from_file`; reads the design once, through `design_files`, and takes its parts from that same `PlanFile` list through `design_from_files`; takes digests from each file's `text` and the lines a move splices from its `lines`; the plan through `read_plan`. Every card, separator and ticket range comes from `Layout.parts` or `Design.parts`, and a ticket's run-on past its file comes from its part's `runs_on`, not from a rule of `board`'s own. A Contents block's list items are read only in `_listing`, and `board` owns the editing of Contents lists for a move (SPEC §11.3), writing each line through `heads.contents_line`; `served_files` reads no file. Serves nothing, keeps no UI state, reads no git. |
| `server` | The board served: `KanbanServer` (a `ThreadingHTTPServer` on `127.0.0.1`, one project's board and the poll thread that keeps it current), its request handler and `run_kanban`, the `kanban` driver (§5). `CannotListen` is the constructor's report of a port that cannot be bound. Reads the page from `assets/`, and serves the files `board.served_files` names (§5 *Endpoints*). Puts `__version__` in the payload. Keeps no UI state and writes no file of its own; the documents it writes are `board`'s moves. |

## §3 Dependency direction

Within a subpackage, a module imports only from lower layers. `kanban` imports from `dicerlib`; `dicerlib` never imports from `kanban`. `__main__` imports from both.

`dicerlib`:

| Layer | Modules |
|---|---|
| 0 | `heads`, `textfile`, `linkscan` |
| 1 | `outline`, `anchors` |
| 2 | `linkrewrite` |
| 3 | `split`, `reassemble`, `linkcheck` |
| 4 | `treecheck`, `dicedoc` |
| 5 | `manifest` |

`kanban`:

| Layer | Modules |
|---|---|
| 0 | `planform` |
| 1 | `plancheck`, `board` |
| 2 | `server` |

`__main__` is above both. `__init__`, which holds only `__version__` and imports nothing, is below both; `kanban.server` takes `__version__` from it.

## §4 Key data structures

| Type | Module | Role |
|---|---|---|
| `Section` | `outline` | One planned file: `id`, `parent`, `kind` (`E` entry point, `I` index, `L` leaf), `path` relative to the output directory, `first`/`last` source lines (1-based, inclusive), `number`, `level`, `title`. |
| `Outline` | `outline` | Indexes over `Section`s: `children`, `depth`, `by_number` (last duplicate wins, SPEC §3.2), `duplicate_numbers`. |
| `LinkMap` | `linkrewrite` | `documents: target -> path` and `headings: (target, heading) -> path`, loaded from the TSV (SPEC §5). |
| `Tree` | `linkrewrite` | One output tree: `out` as given (prefix of reported paths), `outabs` (real path), `root` (the run directory), and the `LinkMap`. |
| `Linker` | `linkrewrite` | Holds `Outline`, `Tree`, the anchor-home table and its inverse, and the `resolved` / `dangling` counters. Methods `forward`, `rebase_only`, `revert`, `restore`. |
| `Anchor` | `anchors` | `base` and repeat-suffixed `name` of one heading. |
| `_Volume`, `_Entry` | `manifest` | One diced manifest row (the document diced, its output directory, label, `file` key); the `entry` row. |
| `Plan` | `kanban.planform` | One plan: `title` (its H1), `release` (the text after `Release:`, `None` where unnamed), `hardening` (the H1 opens `Release hardening`), `packages`, `breaches`. |
| `PlanFile` | `kanban.planform` | One file of a plan or design: `path`, `text` (as read), `lines` (split from `text`) and `fenced` (per line, inside fenced code). |
| `Heading` | `kanban.planform` | A heading outside fenced code: `path`, `line` (1-based), `level`, `text`, and `anchor` (its SPEC §4.4 anchor in its file, from `anchors.heading_anchor_list`). |
| `WorkPackage` | `kanban.planform` | One status-table row with a non-empty `Package` cell (SPEC §8.6): `id`, `title` (`""` where no heading opens with the ID; a heading that only mentions it gives none and no breach), `state` (`DRAFTED` or one of `STATE_WORDS`), `note`, `lifetime` (`None` without a `Lifetime` column), `rating` (one of `RATING_WORDS`, else `None`) and `rating_note` (the Rating cell after its word, the whole cell where it has none), the `path` and `line` of its row, and `heading` (the `Heading` its title is read from; `None` where untitled). |
| `Breach` | `kanban.planform` | One fault of the form: `kind`, `path`, `line` (1-based, per file), `found` (the text as the plan or design holds it, except for a repeated ID: the ID and the line of the row that first holds it) and `accepted` (the form accepted there). |
| `BreachKind` | `kanban.planform` | One kind per breach row of SPEC §8.6, §8.7 and §8.8: `ID_REPEATED`, `ID_SPACE`, `STATE_WORD`, `RELEASE_MISPLACED`, `RELEASE_EMPTY`, `RATING_MISSING`, `RATING_WORD`, `REVIEW_UNPAIRED`, `BURNDOWN_UNPAIRED`, `DELTA_MISSPELLED`, `NOT_A_DELTA`, `DELTA_REPEATED`, `DELTA_ORDER`, `NO_DELTA`, `DELTA_CONTENT`; the layout's, which `LAYOUT_BREACHES` names: `TICKET_OUTSIDE`, `OLD_FORM_ITEM`, `TICKET_EMPTY`; and the roadmap's `NO_CATEGORY`. |
| `Layout` | `kanban.planform` | One document read in the SPEC §8.8 layout: `parts` (`Part`s in document order) and `breaches`. |
| `Design` | `kanban.planform` | One design: `parts` (`Part`s in document order) and `breaches`, the layout's among them. |
| `Part` | `kanban.planform` | One part of a document in the layout: `kind` (`CATEGORY`, a level-2 heading and its lines before its first ticket; `TICKET`; in a design, `DELTA` for a delta's category and `ENTRY` for its tickets), `heading` (the heading's text as written, links unreduced), `title` (a ticket's SPEC §8.8 title, the plain text (SPEC §4.1) of its heading by `linkscan.plain_text`; else the heading), `anchor` (as `Heading`'s), `path`, `first` (0-based, its heading's line), `last` (0-based, its last non-blank line before the next heading of level 3 or less, or before a diced design's head file's Contents cut, so that a ticket's SPEC §11.3 lines are `first`..`last`) and `first_text` (a category's first line of text above its first ticket, in its file or a later one, as path and 1-based line: non-blank, outside fenced code and no layout breach; `None` for a ticket or a category without one) and `runs_on` (a ticket's text continues into a later file: there, a non-blank line comes before any heading of level 3 or less; `False` otherwise). |
| `ParkedWork` | `kanban.planform` | One piece of SPEC §11.1 parked work: `name` (its parked name) and `files` (its parked files and its parked trees' `entry-point.md`, sorted). |
| `Board` | `kanban.board` | One read of a project (cards per SPEC §11.2): `release`, `hardening`, `roadmap` (`RoadmapCard`s: separators and tickets in document order), `parked` (`ParkedCard`s), `design` (`DesignCard`s: separators, tickets and entries in document order), `packages` (`PackageCard`s, one per `WorkPackage` of the plan; `PLAN_COLUMNS` names the plan columns, a package sitting in the one its `state` names), `notices` (`Notice`s) and `sha256`: the digest (`sha256`) of `ROADMAP.md` and of each design file, keyed by path relative to the root, `None` for a file that is absent (`ACTIVE_DESIGN.md` is the key where there is no design). It is the state a move's hash check compares. |
| `RoadmapCard` | `kanban.board` | One `Part` of `ROADMAP.md` as the page draws it (SPEC §11.2): a ticket's card, or for a category its separator, which is not a card. `title` (the part's), `text` (the lines below the heading, blank lines at either end dropped, newline-joined; empty for a separator), `href` (`None` for a separator), `parked` (the files of the parked work its links name, relative to the project root), `kind` (`CATEGORY` or `TICKET`) and `occurrence` (the number of cards before it in `Board.roadmap` equal to it in every other field, so that no two are equal). A card's `href` is the URL path of the file holding its heading, the file's root-relative path percent-quoted (with `surrogateescape`, so that a byte of a name that is not UTF-8 is quoted as that byte), then `#` and the heading's `anchor`; `board._href` is the one builder of a served file's URL, a card's `href` and a parked file's alike. |
| `ParkedCard` | `kanban.board` | A piece of parked work no roadmap ticket links and whose link ticket is not in the design: `title` (its parked name), `paths` (its files relative to the project root, each one of the card's links) and `hrefs` (the URL path of each of `paths`, in the same order, the target of that link). |
| `DesignCard` | `kanban.board` | One `Part` of the active design as the page draws it (SPEC §11.2): a card, or for a category its separator, which is not a card. `title` (the part's), `text` (as `RoadmapCard`'s), `path` (the file holding it, relative to the root), `href` (as `RoadmapCard`'s), `parked` (the files, relative to the root, of the parked work whose link ticket the ticket is, else `None`), `parked_hrefs` (the URL path of each of `parked`, in the same order, else `None`), `kind` (the part's: `CATEGORY` or `DELTA` for a separator, `TICKET` or `ENTRY`, which the page reads as `"category"`, `"delta"`, `"ticket"` and `"entry"`) and `occurrence` (as `RoadmapCard`'s, in `Board.design`). |
| `PackageCard` | `kanban.board` | A `WorkPackage`'s fields and its `href`: to its `heading` as a ticket card's is, or, where it is untitled, the URL path of the file holding its row, with no fragment. |
| `Notice` | `kanban.board` | One breach of `ROADMAP.md`, or of the design's layout, as the page shows it: `column` (`"roadmap"` or `"design"`, the `Board` field whose cards it heads), `path` (relative to the root), `line`, `found` and `accepted`, as the `Breach` holds them. |
| `MoveRefused` | `kanban.board` | Raised by `move_to_design` and `move_to_roadmap`, writing nothing; its message says why. |
| `MoveWriteFailed` | `kanban.board` | Raised where a write fails at the file system: `path` is the file, `written` the files written before it; the message is `cannot write: <path>`. |
| `CannotListen` | `kanban.server` | Raised by the `KanbanServer` constructor where the port cannot be bound; the message is the reason. |

## §5 Data flow per command

### `dice-doc` (SPEC §6)

`dice_doc` creates the output directory, then runs `read_lines` → `plan_sections` → `makedirs` per section directory → `write_tree` → `check_reassembly` → `check_links`, and returns 1 at the first failure. Planning reports every collision but stops at the first empty slug; any planning failure writes nothing.

### `undice` (SPEC §6.1)

`undice` refuses an unreadable entry point before checking whether the monolith exists. `_undiced_lines` reads the entry point and each file its Contents block links, each file's own lines ending at `reassemble.own_end` (a head file's block and what follows it are dropped), reporting each linked file it cannot read and returning, with the lines, whether all were read and every read, empty ones included, in reading order: its Contents target normalized by `posixpath.normpath`, and the line of the result its own lines start at, or none when it holds no lines. A read opens the section whose `first` is that line, the entry section excepted; SPEC §6.1 states which section a file read more than once was read as. It then restores links in one pass of `_restored`, which plans the lines as read, builds a `Linker` over them and runs `Linker.restore` over the files' own lines. One pass suffices: a heading's number, title, name and anchor come from its plain text (SPEC §3.2, §4.4), and neither rewriting nor restoring changes the plain text of a line that reassembles (SPEC §8.1), since a section link's text is its reference and every other rewrite changes only a target; so the lines as read plan and anchor as the restored lines do. `undice` writes the result (a write failure returns 2 at once), plans it (a failure returns 1 at once), reports duplicate numbers, then runs `check_reassembly`, `check_links` and `_all_reproduced` (the stray-file check; it relates each stray's tree-relative path to the section its reads open and prints the SPEC §6.1 message for it), all of them whatever the others return; an unread file fails the command even when they pass.

### `verify` (SPEC §8.3)

Per pair: plan again from the monolith (expected paths come from this plan, never from the tree on disk); run `check_reassembly` with `err=stdout`; run `check_links` into a `StringIO` whose lines are printed again, indented.

### `dice-docs` (SPEC §7)

`dice_docs` runs SPEC §7.2's steps in order: `_read_manifest` into `_Volume` / `_Entry`, ending the command on a flag other than `entry`; `_link_map_rows` (which calls `plan_sections` per volume) into `links.tsv`; `_remove`; for each volume, `dice_doc` with both streams sent to a `StringIO`, dropping the `dead link` lines; `_write_group_indexes`, `_write_entry_point`; `verify`; `_check_written`.

The map is written before dicing because volumes link to each other. Dicing therefore reports links into trees not yet built as dead, so `dice_doc`'s status is ignored and `verify` judges every tree again. Group-index lines go after the parent's Contents block, outside reassembly's cut (§6).

### `check-links`, `check-tree` (SPEC §8.4, §8.5)

Both walk files with `markdown_files` and read links with `prose_links` (§6). `check_trees` maps each file to the real paths it links to, checks that each file's parent links to it, then walks breadth-first from the root's entry point.

### `check-plan` (SPEC §8.6)

`__main__` refuses a named plan that is not a file with `parser.error` (exit 2), then calls `check_plan(plan, start=os.getcwd(), ...)`. Without a plan, `check_plan` takes `find_project_root(start)` (a missing root returns 2 with the remedy on stderr) and `active_document(root, ACTIVE_PLAN)`, which prefers the monolith to the tree; none found prints `no active plan in <root>` to stdout and returns 0. `read_plan` reads the plan; an `OSError` from any of its files, a diced plan's leaves included, is reported as `cannot read: <file>` (the error's own file, else the plan given) and returns 2, the first failure ending the read.

`plan_files` gives the reading order: a monolith alone; for an `entry-point.md`, the entry point first, then the other `.md` files beneath its directory in `markdown_files` order: `os.walk` top-down with names sorted, so a directory's own files come before its subdirectories' and each level is in name order. `read_plan` sorts its breaches by (the file's place in that order, line), those on one line keeping the order found.

Otherwise `check_plan` prints one stderr line per `Breach` in `Plan.breaches`, built from its `path`, `line`, `found` and `accepted` with a per-`BreachKind` problem text, then the stdout summary, and returns 1 when there are breaches. `found` is rendered by `plancheck._found` per SPEC §8.6: `found an empty cell` for an empty text, else the text in a code span fenced by one backtick more than its longest run. A heading that fails to open with its row's ID is no `Breach`: `read_plan` gives the package an empty title (SPEC §8.6). `read_plan` reads the titles for the post-plan pairing: after `_packages` and before the sort, `_unpaired_post_plan` runs over the finished `WorkPackage` list and gives a `REVIEW_UNPAIRED` or `BURNDOWN_UNPAIRED` `Breach`, at the package's row, to each post-plan review package where no package's title opens with `Post-plan burndown`, and each burndown package where none opens with `Post-plan review`. `_title_opens_with(title, prefix)` applies SPEC §8.6 Terms' rule for when a title opens with a post-plan prefix. An untitled package opens with neither.

### `check-design` (SPEC §8.7)

`__main__` refuses a named design that is not a file with `parser.error` (exit 2), then calls `check_design(design, start=os.getcwd(), ...)`. Without a design, `check_design` finds the project root as `check_plan` does and takes `active_document(root, ACTIVE_DESIGN)`; none found prints `no active design in <root>` to stdout and returns 0. `read_design` reads the files `design_files` gives; an `OSError` from any of them is reported as `cannot read: <file>` and returns 2, as for a plan. Otherwise `check_design` prints one stderr line per `Breach` in `Design.breaches`, in document order, then the stdout summary, and returns 1 when there are breaches.

### `check-roadmap` (SPEC §8.8)

`__main__` refuses a `<roadmap>` that is not a file with `parser.error` (exit 2), then calls `check_roadmap(roadmap, start=os.getcwd(), ...)`. Without `<roadmap>`, `check_roadmap` finds the project root as `check_plan` does and takes `ROADMAP.md` there where it is a file; none prints `no roadmap in <root>` to stdout and returns 0. `read_roadmap` reads it; an `OSError` is reported as `cannot read: <file>` and returns 2. Otherwise `check_roadmap` prints one stderr line per `Breach` in `Layout.breaches`, in line order, then the stdout summary, and returns 1 when there are breaches.

### `kanban` (SPEC §11)

`__main__` refuses a `project-dir` that is not a directory with `parser.error` (exit 2), then calls `run_kanban(project_dir, start=os.getcwd(), ...)`; a relative `project_dir` is taken from `start`. `run_kanban` finds the project root (none: the SPEC §11 message on stderr, 2) and builds `KanbanServer`. The constructor creates its stop event and poll thread (not started), takes a snapshot of the watched files, reads the board, binds an ephemeral port on `127.0.0.1` and starts the poll thread, a daemon. An `OSError` out of the reads is printed as `cannot read: <file>` and returns 2 before any URL is printed; an `OSError` from the bind is re-raised as `CannotListen` and printed as `cannot listen: <reason>` with the same status. Otherwise `run_kanban` prints the URL and calls `serve_forever`; a `KeyboardInterrupt` or `POST /api/stop` ends it, `server_close` stops the poll thread, and the status is 0. Each request runs in its own daemon thread.

The **snapshot** maps each file of `board.watched_files` to the SHA-256 (the function `board.sha256`) of its content, `None` where it is not a file, and `"unreadable"` where it is one that cannot be read. `watched_files` names `ROADMAP.md`, `ACTIVE_DESIGN.md`, `ACTIVE_PLAN.md`, every `.md` beneath `ACTIVE_DESIGN/` and `ACTIVE_PLAN/` that exists (a diced design's leaves and a diced plan's) and the parked work, each parked file and each parked tree's `entry-point.md`; the three monoliths are listed whether or not they exist, so that their creation changes the snapshot; a file appearing beneath `ACTIVE_DESIGN/` or `ACTIVE_PLAN/` adds a key, and so does a parked file or tree appearing, since each poll's `watched_files` lists `parked_work` afresh. The poll thread, every `POLL_SECONDS` (0.25 s, which satisfies SPEC §11.5's second) and holding the server's lock, takes a new snapshot; where it differs from the held one, the thread calls `read_board` and only when that returns keeps the snapshot, increments the board's **version** (starting at 1) and wakes every waiting request. An `OSError` from `read_board` keeps the last good board and the last snapshot, so the next poll reads again and the change is adopted without a further edit; it is named once on stderr as `cannot read: <file>` (the error's own file, else the root), and the next successful refresh lets the name be reported again.

**Endpoints.** Each answers JSON but the page's files and the served documents; every `POST` takes an `application/json` object, and each move answers the board payload as it stands after it:

| Request | Body | Effect |
|---|---|---|
| `GET /`, `GET /<file>` | | `index.html`, or the named `.html`, `.js` or `.css` file of `assets/`; its 404 too carries the page's `Content-Security-Policy` |
| `GET /<path>.md` | | where `<path>.md`, percent-decoded with `surrogateescape`, is the root-relative path of a file `board.served_files` names, that file's text as `textfile.read_text` gives it, encoded back with `surrogateescape`, as `text/markdown; charset=utf-8`; else 404, as is a named file that cannot be read, alone, the others still served. The path is matched against that list and never joined onto the root |
| `GET /api/board[?since=<version>]` | | the payload; with `since` equal to the held version, the answer waits for a change, or for `LONG_POLL_SECONDS` (25) to pass, or for the server to close |
| `POST /api/to-design` | `{"card"}` | `card` as the payload served it. `move_to_design` matches it, field for field, against its own fresh read of the files (§6), else `MoveRefused`; it moves against the held `board.sha256`. Then a refresh, the payload with `written` |
| `POST /api/to-roadmap` | `{"card", "target"}` | `card` as served; a card other than a ticket's is refused before the match (§6, step 1). `target` is the Roadmap column's `"category"` separator nearest above the drop, as served: the band dropped on, else the last such band above the card or the gap the drop landed on; null where none is above it or the drop lands on the column's head band. It must be a dict or null (else 400). `move_to_roadmap` matches `card` against a design card of its fresh read, else `MoveRefused`, and reads a `target` equal to no roadmap separator of that read as null; it moves against the held `board.sha256`. Then a refresh, the payload with `written` |
| `POST /api/stop` | `{}` | answers `{}`, then calls `shutdown` from the request's thread, so that `serve_forever` returns in `run_kanban` |

The payload is `{"version", "board" (the `Board` as a dict), "plan_columns" (`PLAN_COLUMNS`, in order), "project" (the root's base name), "docdicer_version" (`__version__`)}`; the two move answers add `"written"`, the files written relative to the root in the order written, a deleted leaf among them. A move runs under the server's lock and then refreshes the board, as a failed write does too, since the files written have changed. A refresh that raises `OSError` after a move is named on stderr and does not replace the move's result: the answer keeps `written`. Status codes: 200; 400 for a body that is not a JSON object, a field of the wrong type, or a negative or non-numeric `Content-Length`; 403 for the Host check; 404 for an unknown path or file; 409 for `MoveRefused`, body `{"error": <message>}`; 415 for a non-JSON content type; 500 for `MoveWriteFailed`, body `{"error": "cannot write: <file>", "written": [...]}`, and for an `OSError` from a read the move makes, body `{"error": "cannot read: <file>"}` (relative to the root; the error's own file, else the root).

**Headers.** Every response carries `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`; the answers to `GET /`, `GET /<file>` and a served `.md` file's `GET /<path>.md` also carry `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`.

**The Host check** runs first on every request: the `Host` header must be `127.0.0.1:<port>` or `localhost:<port>`, the server's own port; a missing or other value is refused. This is the defence against a page on another origin that rebinds its DNS name to `127.0.0.1`. The second defence, against a page on another origin posting to the board, is the content type: every `POST` must be `application/json`, which a cross-origin page can send only after a CORS preflight `OPTIONS`, which the handler never answers (`BaseHTTPRequestHandler` gives 501, granting no origin); any other content type gets 415.

**The page** (`assets/index.html`, `board.css`, `board.js`) draws a column for Roadmap, one for Design, then one per entry of `plan_columns`, and keeps no state beyond the version it last drew, the payload deferred during a drag, the drag under way and whether the server is answering.

- **Drawing.** `render` draws a payload unless its version is the one drawn (a long poll that times out answers the same version), keeping each column's scroll position across a real redraw; a payload that arrives during a drag is held until the drag ends. Each payload drawn sets `document.title` and `#page-title`, the `<h1>`, to `<project> kanban` from its `project`, as text; `index.html`'s own `kanban` shows until the first payload is drawn. Each payload drawn also sets the `title` of `#connection`, its hover text, to `docdicer v` and its `docdicer_version`; `#connection` carries `role="status"` and takes its accessible name from its own text (`aria-labelledby="connection"`), the connection state. A poll that fails forgets the drawn version, since a restarted server counts from 1 again. An error inside `render` is shown in the alert as `board not drawn: <message>` and polling continues. A `"ticket"` roadmap card, and a `"ticket"` or `"entry"` design card that is not a link ticket, shows its text: the lines joined into paragraphs at blank lines, each rendered by the §7 set of inline forms (code spans, links shown as their text, `**strong**`, `*emphasis*`). It is built from text nodes and `<code>`, `<strong>` and `<em>` elements only; file text never reaches the page as markup. A `"category"` or `"delta"` part, in Roadmap or Design, is drawn not as a card but as a separator band, an `<h3 class="separator">` holding its title, below the column label's `h2`. The parked cards follow a band of their own, `ROADMAP_DESIGNS`, drawn where there is any parked card; the page's lookup of the category separator above a drop (`separatorAbove`) passes over it, as it is no category's. Each card's title but a parked card's is a link to its `href`, opening in a new tab; a parked card shows each of its `paths`, and a link ticket's card each of its `parked`, as such a link to the URL the server sent beside it (`hrefs`, `parked_hrefs`); the page builds no URL of its own. `board.notices` are drawn at the head of the column their `column` names, each as text: `<path>:<line>`, the text found (an empty one as `found an empty line`) and the form accepted.
- **Messages.** `#move-message` (`role="status"`) carries the move message, naming the files written; `#alert` (`role="alert"`) carries failures. Only a 409 opens `Not moved: `; a 500 names the files already written.
- **Drops.** Only roadmap ticket, parked and `"ticket"` design cards are draggable, and only Roadmap and Design accept a drop: `accepts` takes a roadmap or parked card on Design and any design card on Roadmap, without checking its kind: draggability alone keeps entry cards and separators off Roadmap, and the server refuses any other request (§6). On any other column `dragover` is left uncancelled, so the browser refuses the drop. With no card being dragged, `document`-level listeners cancel `dragover` and `drop` with `dropEffect = "none"`, so a file dropped anywhere does not replace the page. A work package's card is not draggable: its state changes by an edit to the plan, which the poll shows.
- **Server stopped.** After `STOPPED_AFTER` (3) consecutive failed polls the connection indicator reads `server stopped: restart docdicer kanban and open the URL it prints` and no drag starts; polling continues, and a successful poll restores `live` and drags. The `#stop` button beside `#connection` posts `/api/stop` through the page's POST helper (`act`), asking no confirmation. The button is disabled before the POST is sent and re-enabled if it fails, so a second press cannot reach a closing server; the 200 sets that stopped state at once, ends polling for good and moves keyboard focus to `#page-title` (`tabindex="-1"`).

The plan columns are drawn as outlined boxes holding flat cards, while Roadmap and Design are filled columns whose draggable cards are raised (a small shadow) and show the grab cursor. The difference is in form (outline against fill, flat against raised), so it does not depend on colour. An entry card is flat, as plan cards are; a separator is a band across the column, not a card.

Each column's label, an `h2` and nothing else, sits in a `div.column-head` band above the scrolling `.cards`. The band is outside the list, so it stays in place while the cards scroll, and it adds no control. A full-width `2px solid var(--line)` bottom rule separates it: one side only, a shape no card has, so the separation does not depend on colour either.

## §6 Mechanisms

### Link scanning is shared

`linkscan.scan` is the only scanner of a line. It skips code spans, finds `[text](target)` per SPEC §4.1, and, given an `on_ref` callback, finds `§N` references. Callers differ by callback:

| Caller | Callbacks | Used by |
|---|---|---|
| `Linker.forward` | rebaser + reference linker | write pass |
| `Linker.rebase_only` | rebaser | reassembly (expected side) |
| `Linker.revert` | un-linker | reassembly (actual side) |
| `Linker.restore` | un-linker, anchor restorer, un-rebaser | `undice` |
| `board._rebased` | rebaser | the board's moves (§6 *The board's moves*) |
| `link_targets` | collector | `prose_links`, `undice`'s read of Contents blocks, `planform.design_files`, `manifest._check_written`, `board` (`_links`, `_listed`) |
| `linkscan.plain_text` | link-text reducer | `outline.plan_sections` (a heading's number, title and name), `anchors.github_anchor`, `manifest._purpose` and `manifest._title` (SPEC §7.1), `planform` (a ticket's title and an empty ticket heading, SPEC §8.8) |

`restore` tries, in order: `revert`'s test for a section link; the inverted anchor-home table, keyed by the target resolved to a tree-root path and its fragment; `_unrebase`, the lexical inverse of `_rebase`'s `rel`. `revert` recognises a link as forward-made when its text starts with `§<digit>`, names a known number (and child name if present), and its target equals the path `forward` would compute; any other link is left as is.

### Rebasing

`_rebase` joins a target, or its link-map destination, onto `Tree.root` and takes `rel` from `outabs/<leaf dir>`. `rel` is purely lexical over `/`-split strings.

### Anchor homes

`_anchor_homes` maps each monolith heading anchor to `(file, anchor within file)`. It numbers headings per owning section (`per_file`), so repeat suffixes follow the file the heading lands in (SPEC §4.4), and marks the heading that opens a non-entry file as needing no fragment. The owner of a source line is found by a line-to-section table built from `Section.first` / `last`.

### Contents blocks and the cut

`contents_block` is appended last, so `check_reassembly` cuts at the last line equal to `heads.CONTENTS` (`reassemble.contents_cut`). This drops lines appended after it (group lines) and ignores any earlier `Contents:` line from the source. A head file's own lines are found by `reassemble.own_end`, built on `contents_cut`, which `undice`'s reads, `planform`'s `design_files` and, for a diced design, `read_layout` use.

### Planning

`plan_sections` makes two passes. The first collects splittable headings outside fences. The second assigns parents using a stack of open headings, names and paths each section, and finds collisions with a path-to-line dict.

### The board's moves

`move_to_design(root, card, read=...)` and `move_to_roadmap(root, card, target=..., read=...)` are the same procedure in two directions. `read` is the `Board.sha256` the server holds. Each returns the files written, relative to the root, in the order written.

1. **One private read.** `_read(root)` reads the roadmap and the design files afresh into lines (not the server's board) and finds the card in them: a roadmap ticket, a parked card, or a design ticket, by equality with the card given (`asdict` of the fresh card against the dict served; no other check of the card exists; `occurrence` tells apart cards alike in every other field, and a roadmap separator's, categories titled alike). One refusal precedes the match, raising `MoveRefused`: `move_to_roadmap` refuses a `card` whose `kind` is not `TICKET`. Absent, the move raises `MoveRefused` (`the card is no longer on the board`). The read never touches the active plan. An `OSError` from it propagates, and the server answers it as `cannot read:`.
2. **Ticket ranges.** A ticket's lines are its `Part`'s `first`..`last` (§4 `Part`); its category is the `CATEGORY` or `DELTA` part before it. A design `TICKET` part (never an `ENTRY`) is a link ticket where its lines `first`..`last` equal `_link_ticket`'s for parked work no roadmap ticket links, its links made from that file's directory: `_link_ticket` writes the form and is the only recogniser of it (below).
3. **In-memory splices.** The move builds each changed file's new lines by splicing the lines it read; nothing is written yet. A file is `(path, lines)`, `lines` being `None` for a leaf the move deletes. The list is in write order, the addition first.
4. **Hash re-check.** `_write` reads each file of the list again and compares its digest, or its absence, with `read`, where a file the board did not read, or found absent, counts as `None`: a file the move creates must still be absent. A difference raises `MoveRefused` (`<file> changed since the board read it`) and nothing is written. The check completes for every file before the first write, and the check and the writes are not atomic.
5. **Whole-file writes** in list order, by `textfile.replace_lines`, a new file's missing directory made just before it by `os.makedirs`, and a leaf's deletion in its place, by `os.remove`. `replace_lines` resolves a symbolic link and writes through it; writes a temporary file beside the target, named `<target>.<pid>.tmp` so that no reader of a directory's `.md` files sees it; copies an existing file's permission bits onto it; and renames it over the target, so a failed write leaves the old file whole and the temporary file removed. A failure, a deletion's or a directory's included (a directory's reported as the file it was made for), raises `MoveWriteFailed` with the files already written; the addition having come first, a failure partway leaves the ticket in both documents and never in neither.

**Splices.** `_added(lines, category, ticket)` puts a ticket's lines after the last non-blank line of the category's last ticket (`TICKET` or `ENTRY` part), or of the category's own part where it has none, a blank line before them and a blank line after them where a heading follows directly; `_removed(lines, part)` drops a ticket's `first`..`last` and the blank lines directly above it. `_rebased(lines, source, destination)` gives a ticket's lines moved from a file in directory `source` to one in `destination`, both relative to the root (SPEC §11.3 **Links**); between equal directories it returns them unchanged. `_listed(lines, leaf, text)` adds a leaf's line to a diced design's full listing (SPEC §11.3), at the listing's end where no line of it links the leaf's head, and returns `None` where `entry-point.md` has none.

A diced design refuses, each with its own message, where `section_name` returns `""` for a leaf the move adds, where a file the move creates exists (`os.path.lexists`), and where a ticket moved to Roadmap runs on past its file, as its part's `runs_on` (§4 `Part`) records.

**Roadmap to design.** The ticket goes to the end of `## Drafts`, the first `CATEGORY` part whose heading text is `Drafts` (the constant `DRAFTS`). A roadmap ticket's lines are carried through `_rebased`, from the root to the directory of the file that will hold them; a parked card's ticket, `_link_ticket`'s, is `### <name>`, `<name>` the parked work's parked name, a blank line, then the link body: a line `[<path>](<link>)` per file of the parked work, in order, a blank line, and `INSTRUCTION` (`complete and update this design`), each link being the file's path from the root, relative to the directory of the file holding the ticket (`linkrewrite.rel`).

| Design | Writes, in order |
|---|---|
| none | `ACTIVE_DESIGN.md` created as `CREATED_DESIGN_HEADING` (`# ACTIVE DESIGN`), a blank line, `## Drafts`, a blank line, the ticket |
| monolith | the file through `_added` to `## Drafts`; with none, the file with `## Drafts` and the ticket appended, a blank line before each unless the line above is blank or there is none |
| diced, `## Drafts` opening an `index.md` | the ticket as a new leaf `<name>.md` beside that `index.md`, `<name>` being `outline.section_name(title)`; then that `index.md` with `- [<text>](<name>.md)` after the last item of the list under its last `Contents:` line; then `entry-point.md` through `_listed`, where it has a full listing |
| diced, no `## Drafts` | the leaf `drafts/<name>.md`, its directory made where absent; then `drafts/index.md` created as `## Drafts`, a blank line, `Contents:`, a blank line, `- [<text>](<name>.md)`; then `entry-point.md` with `- [Drafts](drafts/index.md)` and `  - [<text>](drafts/<name>.md)` after the last item of the list under its last `Contents:` line, or a `Contents:` block holding them at its end where it has none |
| diced, `## Drafts` elsewhere | the file holding it through `_added`, the category ending, in a head file, at its Contents cut |
| (a roadmap ticket) | then `ROADMAP.md` through `_removed`; a parked card leaves it unwritten |

In the diced rows, `<text>` is `outline.contents_text` of the title's `outline.split_number`, the link text dicing gives the leaf's section (SPEC §11.3), and each line is written through `heads.contents_line`.

**Design to roadmap.** A link ticket adds nothing to `ROADMAP.md`. Any other ticket's lines, through `_rebased` from the directory of its file to the root, go into `ROADMAP.md`, the first write: through `_added` to the category of `target` where it equals a roadmap separator card of the fresh read, else to the first `CATEGORY` part; where `ROADMAP.md` has no `CATEGORY` part, `GENERAL_HEADING` (`## General`) and the lines are appended, a blank line before each unless the line above is blank or there is none; where it is absent, it is created as `CREATED_ROADMAP_HEADING` (`# ROADMAP`), a blank line, `## General`, a blank line, the lines. The ticket is then removed from the design:

- *a leaf holding exactly the ticket* (SPEC §11.3): a file not in `heads.HEADS` whose directory has a head, blank above the heading, the ticket running to its last non-blank line and only blank lines after. The head's Contents line linking it (the first line of the list `_listing` finds under the head's last `Contents:` with a link target that normalizes to the leaf's name) is removed from the head; where the head is not `entry-point.md`, the full listing's line whose link target normalizes to the leaf's path from the entry point's directory is removed from `entry-point.md`, where it holds one; then the leaf is deleted, so that a failure between leaves a leaf nothing links, not a link to nothing. Where the head holds no such line, the move is refused before anything is written.
- *otherwise*: the file holding the ticket through `_removed`.

**Links.** `_rebased` is the one rebaser of a moved ticket's lines. It uses `linkscan.scan` and `linkrewrite.never_rebased` (the targets that mean the same from anywhere: empty, `#...`, `/...`, URLs), skipping fenced code and code spans and keeping any fragment. Each relative target is resolved from the source file's directory and rewritten with `rel` from the destination's. The result of `rel` is a normal form, so a rebase out and back is the identity on a target already in it. A link ticket is written by `_link_ticket` for the file that holds it and is never rebased.

## §7 Invariants

- A document is a list of lines; structure is line ranges over it (sections, tickets, tables), and every transform is a splice of lines. No markdown parser or syntax tree: a feature that needs one is past this tool's scope. The board page (`board.js`) holds to the same line: it renders a small fixed set of inline forms (code spans, links shown as their text, `**strong**` and `*emphasis*`) and joins a ticket's lines into paragraphs at blank lines; any other markdown shows as written, and rendering more is past the tool's scope.
- Head-file names are spelled only in `heads.py`; every other module imports them.
- Fenced code is defined only by `FenceTracker`; `outline`, `anchors`, `split`, `reassemble`, `linkcheck`, `dicedoc`, `manifest`, and `kanban.planform` and `kanban.board` (through `fence_flags`) use it.
- Only `textfile` opens files for text; passes use its readers and writers. One exception: `kanban.server` reads the page's files from the package's `assets/` through `importlib.resources`, `Traversable.read_text`, because a packaged resource, which may sit in a zip, has no path to give `textfile`.
- Passes are functions of their arguments and write only to the `out` / `err` streams they are given (drivers take `stdout` / `stderr`). Nothing below `__main__` touches `sys.stdout`, which is what lets `manifest` capture a volume's output in a `StringIO`. Drivers own filesystem layout and exit statuses.
- `Section` lists are in document order with `id == index`; `sections[0]` is always the entry point.
- Sections' `first`..`last` ranges partition `1..len(lines)`.
- The file-name slug (`slug`, in `outline`; `section_name` builds the §3.2 name from it) and the heading anchor (`anchors.github_anchor`) are separate functions and never substituted for each other.
- `linkscan.plain_text` is the only reducer of links to their text; no module reduces links by a pattern of its own. The page's script (`kanban/assets/board.js`) is not a module of the package and is outside this rule.
- The code spells the `Contents:` line as `heads.CONTENTS` and locates a head's Contents block with `reassemble.contents_cut`; no test enforces this.
- The board changes a document only by writing it with `textfile.replace_lines`, whole or not at all, or by deleting a diced design's leaf that a move removes; no test enforces this.

## §8 Test harness

`docdicer/test/test_dicer.py` holds the end-to-end harness as pytest functions; the per-module unit test files are named below.

`test_cases` is parametrized over the directories under `data/`, one test per case, its id the directory name; `test_cases_exist` requires at least one case. A case holds:

| Path | Content |
|---|---|
| `input/` | the working tree the command runs in (symlinks copied as symlinks) |
| `args` | the command-line arguments, one per line |
| `expected/names` | the values the output carries, one entry per output line: `<stream>[\t<name>...]`, `<stream>` being `stdout` or `stderr`; any other line, or an empty name, is malformed, and an empty file is valid. A stream's lines are its bytes split at `\n` after removing one final `\n`; a non-empty stream must end in `\n`, and an empty one has no lines. A stream has exactly as many lines as entries, and passes when each entry is given a distinct line it matches (bipartite matching by augmenting paths); a stream with no entries is empty. An entry of `<stream>` alone matches any line; otherwise its names are found left to right, each search starting where the previous match ended, each name a whole token: no ASCII letter or digit beside it, nor a `.` or `-` joined to one. Matching is on bytes, each name encoded UTF-8 with `surrogateescape`. The harness sets `COLUMNS=1000`, so an argparse usage line never wraps |
| `expected/exit` | the status and a newline |
| `expected/tree/` | every file of the working tree after the run, inputs included |

The harness copies `input/` into the test's pytest `tmp_path`, which `just test` places under `docdicer/test/temp/` (git-ignored) through `--basetemp`, and which pytest deletes and recreates on each run; it runs `sys.executable -m docdicer <args>` there as a subprocess, and compares the exit status, a `{relative path: bytes}` map of all files and the `expected/names` assertions. Only files are compared, so empty directories are not asserted.

`test_undice_then_dice_reproduces_the_tree` is parametrized over every case whose args are `dice-doc` with no map, with or without `--split-level <level>`, and whose expected exit is 0; each copies its `expected/tree/` into its `tmp_path`, runs `undice <out> mono.md`, renames `<out>` aside, runs `dice-doc mono.md <out>`, both runs given the case's `--split-level <level>` where its args hold one, and requires both runs to exit 0 and the two trees' file maps equal (SPEC §6.1). `test_round_trip_cases_exist` requires at least one case to qualify. Both runs go through the same subprocess call as the golden cases.

The per-module unit tests call the owning functions directly: `test_textfile.py`, `test_linkscan.py`, `test_outline.py`, `test_anchors.py`, `test_split.py`, `test_reassemble.py`, `test_linkrewrite.py`, `test_undice.py`, `test_manifest.py`, `test_treecheck.py`, `test_planform.py`, `test_plancheck.py`, `test_board.py`, `test_server.py`. `test_server.py` starts `KanbanServer` on an ephemeral port in a thread against a `tmp_path` project holding `.git` and drives it over HTTP; it also calls `run_kanban` directly. Its two subprocess tests run `python -m docdicer kanban`, read the URL line and fetch the page through `_serve_the_command`; `test_the_command_prints_the_url_and_serves_until_interrupted` then sends SIGINT, and `test_the_command_serves_until_stopped_from_the_page` POSTs `/api/stop`; each requires exit 0 and nothing further on either stream. `test_plancheck.py` covers the default plan, design and roadmap and the project-root exits, which no golden case can (a golden case's `tmp_path` sits inside this repository's `.git`); the `check-plan-*` golden cases name `<plan>`, the `check-design-*` cases `<design>` and the `check-roadmap-*` cases `<roadmap>`. The driver tests pass the directory as `start` rather than changing directory; the two no-project-root tests also patch `os.path.lexists`, since the test directory sits inside this repository's `.git`.

## §9 Extension points

- *A new command*: add a parser in `__main__._parser`, a driver in the layer that owns its inputs, and a golden case; exit statuses follow SPEC §2.
- *A new link form*: change `scan` and `Linker` only (§6).
- *A deeper split level*: `outline.DEEPEST_SPLIT_LEVEL`, the default and the largest `--split-level` accepted; the heading-width test in `plan_sections` bounds what is a heading at all.
- *A new plan-, design-, layout- or roadmap-form breach*: a `BreachKind` and its detection in `kanban.planform.read_plan`, `read_layout`, `roadmap_from_file` or `design_from_files`, and its problem text in `kanban.plancheck._PROBLEMS`; a layout breach is also named in `LAYOUT_BREACHES`. The reader's callers receive it through `Plan.breaches`, `Layout.breaches` or `Design.breaches`.
- *Head-file names*: fixed, not an extension point.
