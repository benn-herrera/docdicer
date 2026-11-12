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

Only `__init__` (`__version__`) and `__main__` sit at the package's top level, in `docdicer/`; every other module is in a subpackage: `docdicer/dicerlib/` for dicing and its checks, `docdicer/kanban/` for the plan and design reader, `check-plan`, `check-design`, the board and its server. Tests: `docdicer/test/test_dicer.py`, cases in `docdicer/test/data/<case>/`, and the per-module unit test files beside it (§8).

**`docdicer/`**

| Module | Responsibility |
|---|---|
| `__main__` | Builds the argparse parser, reconfigures stdout and stderr to UTF-8 with `surrogateescape`, reads `DICER_KEEP`, validates root arguments and refuses unreadable files (exit 2), calls one driver, and turns its result into the exit status. The only code that reads environment variables, `sys.argv` or the working directory: `check_plan`, `check_design` and `run_kanban` are given `os.getcwd()` as their `start`. |

**`docdicer/dicerlib/`**

| Module | Responsibility |
|---|---|
| `heads` | `ENTRY_POINT`, `INDEX`, `HEADS` (SPEC §3.2) and `CONTENTS`, the one spelling of the `Contents:` line. |
| `textfile` | File I/O (UTF-8, `surrogateescape`, `newline=""`); `replace_lines`, the whole-or-nothing write (§6); `\n`-only line splitting (`split_lines`, `terminated_lines`, `join_lines`); `is_blank`; `FenceTracker` / `fence_flags` (SPEC §3.1). |
| `outline` | `plan_sections` turns lines into `Section` records (SPEC §3.1, §3.2); `section_name`, the §3.2 file name of a heading, which `plan_sections` and the board's diced moves both use; `Outline` gives lookups by number, children, depth and Contents link text. |
| `refactor` | The bold-line classifier and converter (SPEC §9.1), the `list` rows (SPEC §9.2), and the `check_hunks` self-check. |
| `linkrewrite` | The single link/reference scanner `scan`, with `never_rebased` (the targets that mean the same from anywhere), the `Linker` built on it (forward rewriting and its inverse, `restore`), the `LinkMap` and `Tree` records, and the path helpers `rel` and `parent_dir` (SPEC §4, §5, §6.1). |
| `split` | The write pass: each section's lines through `Linker.forward`, plus `contents_block` (SPEC §3.3), written under the output directory; prints the `refs linked` line. |
| `reassemble` | The inverse of the write pass (SPEC §8.1). `contents_cut` finds a head's Contents block (§6); `own_end`, built on it, gives where a tree file's own lines end: a head file's (its name in `heads.HEADS`) at its Contents cut, any other file's at its end. `planform` and `dicedoc` read a file's own lines through `own_end`. |
| `linkcheck` | `check_links` (SPEC §8.2), `check_markdown_links` (SPEC §8.4), the GitHub anchor functions (SPEC §4.4), `prose_links`, `markdown_files`. |
| `treecheck` | `check_trees` (SPEC §8.5). |
| `dicedoc` | `dice_doc` (SPEC §6), `undice` (SPEC §6.1) and `verify` (SPEC §8.3); each reports duplicate section numbers once, after planning. |
| `manifest` | `dice_docs` (SPEC §7): manifest reading, refactor calls, link-map rows, group indexes, the entry point, the written-files check. |

**`docdicer/kanban/`**

| Module | Responsibility |
|---|---|
| `planform` | The plan- and design-form reader, the forms SPEC §8.6 and §8.7 define: `read_plan` returns a `Plan` and every `Breach` of the form it meets, sorted by the file's place in the reading order, then line. `design_files` gives a design's files in SPEC §8.7's document order, built on `reassemble.own_end` and `linkrewrite.link_targets`; it follows a Contents link only to a `.md` file beneath the entry point's directory, and files no followed link reaches come after, in `plan_files` order. `read_design` returns a `Design`: its `parts` in document order and every `Breach` of the SPEC §8.7 form; it is `design_files` followed by `design_from_files`, which reads a design from its files already read and touches no disk. The delta heading spellings live in `planform` only, as do the part kinds `SECTION`, `DELTA` and `ENTRY`, plain strings so that the board's payload carries them unchanged; `board` and `plancheck` import them. Also the project's fixed file names (`ACTIVE_DESIGN`, `ACTIVE_PLAN`, `PARKED_DESIGNS`, `ROADMAP`) and where they are found: `find_project_root` (nearest ancestor holding `.git`, by `os.path.lexists`, never by running git), `active_document`, `parked_entries`. Also `plan_files` (the files of a document, §5 `check-plan`), `file_headings`, the `HEADING` pattern (a `#` run of 1 to 6 and a space), which `board` also uses, and `h1_line`, the reading of a document's H1 (outside fenced code). |
| `plancheck` | `check_plan` (SPEC §8.6): the `check-plan` driver over `planform`. `check_design` (SPEC §8.7) is the `check-design` driver over `read_design`, sharing the breach line and the exit statuses with `check_plan`; `_found` renders a design's empty text as `found an empty line`. Both own the breach message lines (problem text and the `found` rendering), the summary, the default plan or design (project root, then monolith before tree) and the drivers' exit statuses, 2 for a missing project root or an unreadable plan or design file. |
| `board` | Over `planform` and `ROADMAP.md`. `read_board` returns the `Board`: roadmap cards from the top-level list items, the parked entries no item links, the design's cards and separators, the plan's packages. `watched_files` names every file the board reads, or would read were it there. `move_to_design` and `move_to_roadmap` are the board's only writes to documents, the moves of an entry between `ROADMAP.md` and the active design (§6); a refused move raises `MoveRefused`, a failed write `MoveWriteFailed`. `sha256` is the one digest of a file's text, used for `Board.sha256` and by `server` for its change detection; `root_relative` is the one spelling of a path relative to the root, `/`-separated. Reads the design once, through `planform`'s `design_files`, and takes its parts from that same `PlanFile` list through `design_from_files`, its digests from each file's `text` and the lines a move splices from its `lines`; the plan through `read_plan`. Every Design card, separator and section range comes from `Design.parts`, and `board` keeps no section reader of its own. Serves nothing, keeps no UI state, reads no git. |
| `server` | The board served: `KanbanServer` (a `ThreadingHTTPServer` on `127.0.0.1`, one project's board and the poll thread that keeps it current), its request handler and `run_kanban`, the `kanban` driver (§5). `CannotListen` is the constructor's report of a port that cannot be bound. Reads the page from `assets/`. Keeps no UI state and writes no file of its own; the documents it writes are `board`'s moves. |

## §3 Dependency direction

Within a subpackage, a module imports only from lower layers. `kanban` imports from `dicerlib`; `dicerlib` never imports from `kanban`. `__main__` imports from both.

`dicerlib`:

| Layer | Modules |
|---|---|
| 0 | `heads`, `textfile` |
| 1 | `outline`, `refactor` |
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

`__main__` is above both.

Exception: `linkrewrite._anchor_homes` imports `linkcheck.heading_anchor_list` inside the function, because `linkcheck` imports `linkrewrite`.

## §4 Key data structures

| Type | Module | Role |
|---|---|---|
| `Section` | `outline` | One planned file: `id`, `parent`, `kind` (`E` entry point, `I` index, `L` leaf), `path` relative to the output directory, `first`/`last` source lines (1-based, inclusive), `number`, `level`, `title`. |
| `Outline` | `outline` | Indexes over `Section`s: `children`, `depth`, `by_number` (last duplicate wins, SPEC §3.2), `duplicate_numbers`. |
| `LinkMap` | `linkrewrite` | `documents: target -> path` and `headings: (target, heading) -> path`, loaded from the TSV (SPEC §5). |
| `Tree` | `linkrewrite` | One output tree: `out` as given (prefix of reported paths), `outabs` (real path), `root` (the run directory), and the `LinkMap`. |
| `Linker` | `linkrewrite` | Holds `Outline`, `Tree`, the anchor-home table and its inverse, and the `resolved` / `dangling` counters. Methods `forward`, `rebase_only`, `revert`, `restore`. |
| `Anchor` | `linkcheck` | `base` and repeat-suffixed `name` of one heading. |
| `_Volume`, `_Entry` | `manifest` | One diced manifest row (the document actually diced, its output directory, label, `file` key); the `entry` row. |
| `Plan` | `kanban.planform` | One plan: `title` (its H1), `release` (the text after `Release:`, `None` where unnamed), `hardening` (the H1 opens `Release hardening`), `packages`, `breaches`. |
| `PlanFile` | `kanban.planform` | One file of a plan or design: `path`, `text` (as read), `lines` (split from `text`) and `fenced` (per line, inside fenced code). |
| `Heading` | `kanban.planform` | A heading outside fenced code: `path`, `line` (1-based), `level`, `text`. |
| `WorkPackage` | `kanban.planform` | One status-table row with a non-empty `Package` cell (SPEC §8.6): `id`, `title` (`""` where no heading opens with the ID; a heading that only mentions it gives none and no breach), `state` (`DRAFTED` or one of `STATE_WORDS`), `note`, `lifetime` (`None` without a `Lifetime` column), `rating` (one of `RATING_WORDS`, else `None`) and `rating_note` (the Rating cell after its word, the whole cell where it has none), and the `path` and `line` of its row. |
| `Breach` | `kanban.planform` | One fault of the form: `kind`, `path`, `line` (1-based, per file), `found` (the text as the plan or design holds it, except for a repeated ID: the ID and the line of the row that first holds it) and `accepted` (the form accepted there). |
| `BreachKind` | `kanban.planform` | One kind per breach row of SPEC §8.6 and §8.7: `ID_REPEATED`, `ID_SPACE`, `STATE_WORD`, `RELEASE_MISPLACED`, `RELEASE_EMPTY`, `RATING_MISSING`, `RATING_WORD`, `REVIEW_UNPAIRED`, `BURNDOWN_UNPAIRED`, `DELTA_MISSPELLED`, `NOT_A_DELTA`, `DELTA_REPEATED`, `DELTA_ORDER`, `NO_DELTA`, `DELTA_CONTENT`, `ENTRY_EMPTY`. |
| `Design` | `kanban.planform` | One design: `parts` (`DesignPart`s in document order) and `breaches`. |
| `DesignPart` | `kanban.planform` | One part of a design: `kind` (`SECTION`, a level-2 section that is not a delta; `DELTA`, a delta heading and the lines before its first entry; `ENTRY`), `heading` (the heading's text as written, links unreduced), `path`, and `first`/`end` (0-based line range in its file, heading line first, end exclusive; a head file's ranges end at its Contents cut). |
| `Board` | `kanban.board` | One read of a project (cards per SPEC §11.2): `release`, `hardening`, `roadmap` (`RoadmapCard`s), `parked` (`ParkedCard`s), `design` (`DesignCard`s: sections, separators and entries in document order), `packages` (the plan's `WorkPackage`s; `PLAN_COLUMNS` names the plan columns, a package sitting in the one its `state` names) and `sha256`: the digest (`sha256`) of `ROADMAP.md` and of each design file, keyed by path relative to the root, `None` for a file that is absent (`ACTIVE_DESIGN.md` is the key where there is no design). It is the state a move's hash check compares. |
| `RoadmapCard` | `kanban.board` | A top-level `ROADMAP.md` list item (SPEC §11.2): `title`, `group`, `text` (its lines as written) and `parked` (the parked entries its links name, relative to the project root). The title is cut at `TITLE_LENGTH`; each link outside code spans is first reduced to its text by `_link_texts`, a `linkrewrite.scan` with a link-text callback, so the sentence end and the cut are found on the reduced text. |
| `ParkedCard` | `kanban.board` | A parked entry no roadmap item links: `title` and `path` relative to the project root. |
| `DesignCard` | `kanban.board` | One `DesignPart` of the active design as the page draws it (SPEC §11.2): a card, or for a delta its separator, which is not a card. `title` (the heading; an entry's with links reduced by `_link_texts`), `text` (the lines below the heading, blank lines at either end dropped, newline-joined; empty for a separator), `path` (the file holding it, relative to the root), `parked` (the parked entry's path where the section is that entry's link section, else `None`) and `kind` (the part's: `SECTION`, `DELTA` for a separator, or `ENTRY`, which the page reads as `"section"`, `"delta"` and `"entry"`). |
| `MoveRefused` | `kanban.board` | Raised by `move_to_design` and `move_to_roadmap`, writing nothing; its message says why. |
| `MoveWriteFailed` | `kanban.board` | Raised where a write or deletion fails at the file system: `path` is the file, `written` the files written before it; the message is `cannot write: <path>`. |
| `CannotListen` | `kanban.server` | Raised by the `KanbanServer` constructor where the port cannot be bound; the message is the reason. |
| `_Hunk` | `refactor` | A merged changed region: start line, old lines, new lines. |

## §5 Data flow per command

### `dice-doc` (SPEC §6)

`dice_doc` creates the output directory, then runs `read_lines` → `plan_sections` → `makedirs` per section directory → `write_tree` → `check_reassembly` → `check_links`, and returns 1 at the first failure. Planning reports every collision but stops at the first empty slug; any planning failure writes nothing.

### `undice` (SPEC §6.1)

`undice` refuses an unreadable entry point before checking whether the monolith exists. `_undiced_lines` reads the entry point and each file its Contents block links, each file's own lines ending at `reassemble.own_end` (a head file's block and what follows it are dropped), reporting each linked file it cannot read and returning, with the lines, whether all were read and every read, empty ones included, in reading order: its Contents target normalized by `posixpath.normpath`, and the line of the result its own lines start at, or none when it holds no lines. A read opens the section whose `first` is that line, the entry section excepted; SPEC §6.1 states which section a file read more than once was read as. It then restores links by repeated passes of `_restored`: each plans the lines it is given and builds a `Linker` over them, and runs `Linker.restore` over the files' own lines. The first pass works from the lines as read, whose headings still hold rewritten links and so plan and anchor wrongly; each later pass works from the previous output, and a chain of headings citing headings settles one link per pass. The passes stop at a fixpoint, or after one pass per heading line read plus one, keeping the last output. A heading holding a markdown link never settles; the self-check reports it. `undice` writes the result (a write failure returns 2 at once), plans it (a failure returns 1 at once), reports duplicate numbers, then runs `check_reassembly`, `check_links` and `_all_reproduced` (the stray-file check; it relates each stray's tree-relative path to the section its reads open and prints the SPEC §6.1 message for it), all of them whatever the others return; an unread file fails the command even when they pass.

### `verify` (SPEC §8.3)

Per pair: plan again from the monolith (expected paths come from this plan, never from the tree on disk); run `check_reassembly` with `err=stdout`; run `check_links` into a `StringIO` whose lines are printed again, indented.

### `dice-docs` (SPEC §7)

`dice_docs` runs SPEC §7.2's steps in order: `_read_manifest`, with `refactor` where flagged, into `_Volume` / `_Entry`; `_link_map_rows` (which calls `plan_sections` per volume) into `links.tsv`; `_remove`; for each volume, `dice_doc` with both streams sent to a `StringIO`, dropping the `dead link` lines; `_write_group_indexes`, `_write_entry_point`; `verify`; `_check_written`.

The map is written before dicing because volumes link to each other. Dicing therefore reports links into trees not yet built as dead, so `dice_doc`'s status is ignored and `verify` judges every tree again. Group-index lines go after the parent's Contents block, outside reassembly's cut (§6).

### `refactor` and `list` (SPEC §9)

`_walk` is one pass over the lines, used in two modes: `converting=True` yields the output lines and the long-title notes (`convert_runins`); `converting=False` yields the TSV rows (`list_runins`). The classifier `_classify` is shared, so the `list` classes and the conversion decisions cannot drift. `refactor()` then runs `check_hunks` on the input text and the joined output.

### `check-links`, `check-tree` (SPEC §8.4, §8.5)

Both walk files with `markdown_files` and read links with `prose_links` (§6). `check_trees` maps each file to the real paths it links to, checks that each file's parent links to it, then walks breadth-first from the root's entry point.

### `check-plan` (SPEC §8.6)

`__main__` refuses a named plan that is not a file with `parser.error` (exit 2), then calls `check_plan(plan, start=os.getcwd(), ...)`. Without a plan, `check_plan` takes `find_project_root(start)` (a missing root returns 2 with the remedy on stderr) and `active_document(root, ACTIVE_PLAN)`, which prefers the monolith to the tree; none found prints `no active plan in <root>` to stdout and returns 0. `read_plan` reads the plan; an `OSError` from any of its files, a diced plan's leaves included, is reported as `cannot read: <file>` (the error's own file, else the plan given) and returns 2, the first failure ending the read.

`plan_files` gives the reading order: a monolith alone; for an `entry-point.md`, the entry point first, then the other `.md` files beneath its directory in `markdown_files` order: `os.walk` top-down with names sorted, so a directory's own files come before its subdirectories' and each level is in name order. `read_plan` sorts its breaches by (the file's place in that order, line), those on one line keeping the order found.

Otherwise `check_plan` prints one stderr line per `Breach` in `Plan.breaches`, built from its `path`, `line`, `found` and `accepted` with a per-`BreachKind` problem text, then the stdout summary, and returns 1 when there are breaches. `found` is rendered by `plancheck._found` per SPEC §8.6: `found an empty cell` for an empty text, else the text in a code span fenced by one backtick more than its longest run. A heading that fails to open with its row's ID is no `Breach`: `read_plan` gives the package an empty title (SPEC §8.6). `read_plan` reads the titles for the post-plan pairing: after `_packages` and before the sort, `_unpaired_post_plan` runs over the finished `WorkPackage` list and gives a `REVIEW_UNPAIRED` or `BURNDOWN_UNPAIRED` `Breach`, at the package's row, to each post-plan review package where no package's title opens with `Post-plan burndown`, and each burndown package where none opens with `Post-plan review`. `_title_opens_with(title, prefix)` applies SPEC §8.6 Terms' rule for when a title opens with a post-plan prefix. An untitled package opens with neither.

### `check-design` (SPEC §8.7)

`__main__` refuses a named design that is not a file with `parser.error` (exit 2), then calls
`check_design(design, start=os.getcwd(), ...)`. Without a design, `check_design` finds the
project root as `check_plan` does and takes `active_document(root, ACTIVE_DESIGN)`; none found
prints `no active design in <root>` to stdout and returns 0. `read_design` reads the files
`design_files` gives; an `OSError` from any of them is reported as `cannot read: <file>` and
returns 2, as for a plan. Otherwise `check_design` prints one stderr line per `Breach` in
`Design.breaches`, in document order, then the stdout summary, and returns 1 when there are
breaches.

### `kanban` (SPEC §11)

`__main__` refuses a `project-dir` that is not a directory with `parser.error` (exit 2), then calls `run_kanban(project_dir, start=os.getcwd(), ...)`; a relative `project_dir` is taken from `start`. `run_kanban` finds the project root (none: the SPEC §11 message on stderr, 2) and builds `KanbanServer`. The constructor creates its stop event and poll thread (not started), takes a snapshot of the watched files, reads the board, binds an ephemeral port on `127.0.0.1` and starts the poll thread, a daemon. An `OSError` out of the reads is printed as `cannot read: <file>` and returns 2 before any URL is printed; an `OSError` from the bind is re-raised as `CannotListen` and printed as `cannot listen: <reason>` with the same status. Otherwise `run_kanban` prints the URL and calls `serve_forever`; a `KeyboardInterrupt` ends it, `server_close` stops the poll thread, and the status is 0. Each request runs in its own daemon thread.

The **snapshot** maps each file of `board.watched_files` to the SHA-256 (the function `board.sha256`) of its content, `None` where it is not a file, and `"unreadable"` where it is one that cannot be read. `watched_files` names `ROADMAP.md`, `ACTIVE_DESIGN.md`, `ACTIVE_DESIGN/entry-point.md`, `ACTIVE_PLAN.md`, every `.md` beneath `ACTIVE_DESIGN/` and `ACTIVE_PLAN/` that exists (a diced design's leaves and a diced plan's) and the parked entries; the files the board would read were they there are listed so that their creation changes the snapshot. The poll thread, every `POLL_SECONDS` (0.25 s, which satisfies SPEC §11.5's second) and holding the server's lock, takes a new snapshot; where it differs from the held one, the thread calls `read_board` and only when that returns keeps the snapshot, increments the board's **version** (starting at 1) and wakes every waiting request. An `OSError` from `read_board` keeps the last good board and the last snapshot, so the next poll reads again and the change is adopted without a further edit; it is named once on stderr as `cannot read: <file>` (the error's own file, else the root), and the next successful refresh lets the name be reported again.

**Endpoints.** Each answers JSON but the page's files; every `POST` takes an `application/json` object and answers the board payload as it stands after it:

| Request | Body | Effect |
|---|---|---|
| `GET /`, `GET /<file>` | | `index.html`, or the named `.html`, `.js` or `.css` file of `assets/`; its 404 too carries the page's `Content-Security-Policy` |
| `GET /api/board[?since=<version>]` | | the payload; with `since` equal to the held version, the answer waits for a change, or for `LONG_POLL_SECONDS` (25) to pass, or for the server to close |
| `POST /api/to-design` | `{"card"}` | `card` as the payload served it. `move_to_design` matches it, field for field, against its own fresh read of the files (§6), else `MoveRefused`; it moves against the held `board.sha256`. Then a refresh, the payload with `written` |
| `POST /api/to-roadmap` | `{"card", "target"}` | `card` as served; a card other than a section's is refused before the match (§6, step 1). `target` is the roadmap or parked card the drop landed on, as served, or null; it must be a dict or null (else 400). `move_to_roadmap` matches `card` against a design card of its fresh read, else `MoveRefused`, and reads a `target` equal to no roadmap card of that read as null; it moves against the held `board.sha256`. Then a refresh, the payload with `written` |

The payload is `{"version", "board" (the `Board` as a dict), "plan_columns" (`PLAN_COLUMNS`, in order), "project" (the root's base name)}`; the two move answers add `"written"`, the files written relative to the root in the order written. A move runs under the server's lock and then refreshes the board, as a failed write does too, since the files written have changed. A refresh that raises `OSError` after a move is named on stderr and does not replace the move's result: the answer keeps `written`. Status codes: 200; 400 for a body that is not a JSON object, a field of the wrong type, or a negative or non-numeric `Content-Length`; 403 for the Host check; 404 for an unknown path or file; 409 for `MoveRefused`, body `{"error": <message>}`; 415 for a non-JSON content type; 500 for `MoveWriteFailed`, body `{"error": "cannot write: <file>", "written": [...]}`, and for an `OSError` from a read the move makes, body `{"error": "cannot read: <file>"}` (relative to the root; the error's own file, else the root).

**Headers.** Every response carries `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`; the answers to `GET /` and `GET /<file>` also carry `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`.

**The Host check** runs first on every request: the `Host` header must be `127.0.0.1:<port>` or `localhost:<port>`, the server's own port; a missing or other value is refused. This is the defence against a page on another origin that rebinds its DNS name to `127.0.0.1`.

**The page** (`assets/index.html`, `board.css`, `board.js`) draws a column for Roadmap, one for Design, then one per entry of `plan_columns`, and keeps no state beyond the version it last drew, the payload deferred during a drag, the drag under way and whether the server is answering.

- **Drawing.** `render` draws a payload unless its version is the one drawn (a long poll that times out answers the same version), keeping each column's scroll position across a real redraw; a payload that arrives during a drag is held until the drag ends. Each payload drawn sets `document.title` and `#page-title`, the `<h1>`, to `<project> kanban` from its `project`, as text; `index.html`'s own `kanban` shows until the first payload is drawn. A poll that fails forgets the drawn version, since a restarted server counts from 1 again. An error inside `render` is shown in the alert as `board not drawn: <message>` and polling continues. A `"section"` or `"entry"` design card that is not a link section shows its text: the lines joined into paragraphs at blank lines, each rendered by the §7 set of inline forms (code spans, links shown as their text, `**strong**`, `*emphasis*`). It is built from text nodes and `<code>`, `<strong>` and `<em>` elements only; file text never reaches the page as markup. A `"delta"` part is drawn not as a card but as a separator band, an `<h3 class="separator">` holding its title, below the column label's `h2`.
- **Messages.** `#notice` (`role="status"`) carries a move's success, naming the files written; `#alert` (`role="alert"`) carries failures. Only a 409 opens `Not moved: `; a 500 names the files already written.
- **Drops.** Only roadmap, parked and `"section"` design cards are draggable, and only Roadmap and Design accept a drop: `accepts` takes a roadmap or parked card on Design and any design card on Roadmap, without checking its kind: draggability alone keeps entry cards and separators off Roadmap, and the server refuses any other request (§6). On any other column `dragover` is left uncancelled, so the browser refuses the drop. With no card being dragged, `document`-level listeners cancel `dragover` and `drop` with `dropEffect = "none"`, so a file dropped anywhere does not replace the page. A work package's card is not draggable: its state changes by an edit to the plan, which the poll shows.
- **Server stopped.** After `STOPPED_AFTER` (3) consecutive failed polls the connection indicator reads `server stopped: restart docdicer kanban and open the URL it prints` and no drag starts; polling continues, and a successful poll restores `live` and drags.

The plan columns are drawn as outlined boxes holding flat cards, while Roadmap and Design are filled columns whose draggable cards are raised (a small shadow) and show the grab cursor. The difference is in form (outline against fill, flat against raised), so it does not depend on colour. An entry card is flat, as plan cards are; a separator is a band across the column, not a card.

Each column's label, an `h2` and nothing else, sits in a `div.column-head` band above the scrolling `.cards`. The band is outside the list, so it stays in place while the cards scroll, and it adds no control. A full-width `2px solid var(--line)` bottom rule separates it: one side only, a shape no card has, so the separation does not depend on colour either.

## §6 Mechanisms

### Link scanning is shared

`linkrewrite.scan` is the only scanner of a line. It skips code spans, finds `[text](target)` per SPEC §4.1, and, given an `on_ref` callback, finds `§N` references. Callers differ by callback:

| Caller | Callbacks | Used by |
|---|---|---|
| `Linker.forward` | rebaser + reference linker | write pass |
| `Linker.rebase_only` | rebaser | reassembly (expected side) |
| `Linker.revert` | un-linker | reassembly (actual side) |
| `Linker.restore` | un-linker, anchor restorer, un-rebaser | `undice` |
| `link_targets` | collector | `prose_links`, `undice`'s read of Contents blocks, `planform.design_files`, the board's Contents-line removal |
| `board._link_texts` | link-text reducer | roadmap and entry card titles |
| `board._rebased` | rebaser | the board's moves (§6) |

`restore` tries, in order: `revert`'s test for a section link; the inverted anchor-home table, keyed by the target resolved to a tree-root path and its fragment; `_unrebase`, the lexical inverse of `_rebase`'s `rel`. `revert` recognises a link as forward-made when its text starts with `§<digit>`, names a known number (and child name if present), and its target equals the path `forward` would compute; any other link is left as is.

### Rebasing

`_rebase` joins a target, or its link-map destination, onto `Tree.root` and takes `rel` from `outabs/<leaf dir>`. `rel` is purely lexical over `/`-split strings.

### Anchor homes

`_anchor_homes` maps each monolith heading anchor to `(file, anchor within file)`. It numbers headings per owning section (`per_file`), so repeat suffixes follow the file the heading lands in (SPEC §4.4), and marks the heading that opens a non-entry file as needing no fragment. The owner of a source line is found by a line-to-section table built from `Section.first` / `last`.

### Contents blocks and the cut

`contents_block` is appended last, so `check_reassembly` cuts at the last line equal to `heads.CONTENTS` (`reassemble.contents_cut`). This drops lines appended after it (group lines) and ignores any earlier `Contents:` line from the source. A head file's own lines are found by `reassemble.own_end`, built on `contents_cut`, which `undice`'s reads and `planform`'s `design_files` and `design_from_files` use; the board's Contents-line splices use `contents_cut` directly.

### Planning

`plan_sections` makes two passes. The first collects splittable headings outside fences. The second assigns parents using a stack of open headings, names and paths each section, and finds collisions with a path-to-line dict.

### Refactor self-check

`check_hunks` diffs `terminated_lines` of input and output with `difflib.SequenceMatcher(autojunk=False)`, merges changed regions separated by up to three blank unchanged lines, and compares each merged hunk's new side with `_expected(old)`, which derives the conversion separately from `_walk` / `_classify`, sharing only the `_BOLD_ITEM` / `_BOLD_RUNIN` patterns. A divergence between the two derivations is reported as `BAD`.

### The board's moves

`move_to_design(root, card, read=...)` and `move_to_roadmap(root, card, target=..., read=...)` are the same procedure in two directions. `read` is the `Board.sha256` the server holds. Each returns the files written, relative to the root, in the order written.

1. **One private read.** `_read(root)` reads the roadmap and the design files afresh into lines (not the server's board) and finds the card in them: a roadmap item, a parked card, or a design section, by equality with the card given (`asdict` of the fresh card against the dict served; no other check of the card exists). Two refusals precede the match, each raising `MoveRefused`: `move_to_roadmap` refuses a `card` whose `kind` is not `SECTION`, and `move_to_design` a `card` whose title is a delta heading's text. Absent, the move raises `MoveRefused` (`the card is no longer on the board`). The read never touches the active plan. An `OSError` from it propagates, and the server answers it as `cannot read:`.
2. **Section ranges.** A design's sections are its `Design.parts` of kind `SECTION`, each part's `first`..`end` its range (§4 `DesignPart`). A diced design's files are in `design_files` order (SPEC §8.7's document order; §2 `planform`). A section is a link section where its heading is the unlinked parked entry's name, written `## <name>`, and its body equals the link body for that file's directory (below). A roadmap item's range is `_items`' first to last non-blank line.
3. **In-memory splices.** The move builds each changed file's new lines by splicing the lines it read; nothing is written yet. A file is `(path, lines)` or `(path, None)` for a deletion. The list is in write order, the addition first.
4. **Hash re-check.** `_write` reads each file of the list again and compares its digest, or its absence, with `read`, where a file the board did not read, or found absent, counts as `None`: the new leaf and an absent `ROADMAP.md` must still be absent. A difference raises `MoveRefused` (`<file> changed since the board read it`) and nothing is written. The check completes for every file before the first write, and the check and the writes are not atomic.
5. **Whole-file writes** in list order, `textfile.replace_lines` for a file, `os.remove` for a deletion. `replace_lines` resolves a symbolic link and writes through it; writes a temporary file beside the target, named `<target>.<pid>.tmp` so that no reader of a directory's `.md` files sees it; copies an existing file's permission bits onto it; and renames it over the target, so a failed write leaves the old file whole and the temporary file removed. A failure raises `MoveWriteFailed` with the files already written; the addition having come first, a failure partway leaves the entry in both documents and never in neither.

**Roadmap to design.** The section is `## <title>`, a blank line, then the body. A roadmap item's body is its lines with the list marker removed from the first, links rebased; a parked card's is the link body: `[<path>](<link>)`, a blank line, and `INSTRUCTION` (`complete and update this design`), the link being the entry's path relative to the file's directory (`linkrewrite.rel`).

| Design | Writes, in order |
|---|---|
| none | `ACTIVE_DESIGN.md` created as `CREATED_DESIGN_HEADING` (`# ACTIVE DESIGN`, never the card's title), a blank line, the section |
| monolith | the file with the section appended, a blank line between unless its last line is blank |
| diced | the section as a new leaf `<name>.md` beside `entry-point.md`, `name` being `outline.section_name(title)`; then `entry-point.md` with `- [<title>](<name>.md)` after the last item of the list under its last `Contents:` line, or a `Contents:` block at its end where it has none |
| (a roadmap item) | then `ROADMAP.md` without the item's lines; a parked card leaves it unwritten |

A diced design refuses, each with its own message, where `section_name` returns `""` and where the leaf exists (`os.path.lexists`).

**Design to roadmap.** A link section adds nothing to `ROADMAP.md`. Any other section returns as an item, the first write, in `ROADMAP.md` (created where absent) at the end of its `##` group's items (`_roadmap_with`), the group being that of `target` where it is a roadmap card, else the file's last, with the marker of that group's items (a numbered group's next number, `- ` where it has none). The body is the section's lines below its heading, trimmed, links rebased. `_returned_item` returns it as the item it was where both hold: `_roadmap_title` of the marker and first body line (links reduced to their text, as for a card's title) gives the heading, and `_items` over the marker and body reads back one item whose last line is the body's last line (SPEC §11.3); otherwise the heading is the item's bold lead, the first body line follows it and later lines are indented under the marker. At the file's end the item goes after the last item of the final group when only blank lines follow it, else after a separator at the end. The section is then removed, in one of two ways:

- *a leaf beside `entry-point.md` holding exactly the section*: a non-head file in the entry point's directory, blank above the heading, the section running to its last line. The Contents line linking it (the first line below the last `Contents:` with a link target that normalizes to the leaf's name) is removed from `entry-point.md`, then the leaf is deleted, so a failure between leaves a leaf nothing links, not a link to nothing. Where no such line is found (`_without_contents_line` returns `None`: no Contents block, or no line of it links the leaf), the move is refused before anything is written.
- *otherwise*: the section's lines are removed from the file holding it, and a blank line left last when the section ended the file is dropped. A section in `entry-point.md`, or a leaf with more than the section, is removed this way, with no leaf deleted and no Contents line removed.

**Links.** Rebasing uses `linkrewrite.scan` and `never_rebased` (the targets that mean the same from anywhere: empty, `#...`, `/...`, URLs), skipping fenced code and code spans and keeping any fragment. Each relative target is resolved from the source file's directory and rewritten with `rel` from the destination's; the roadmap sits at the root and a monolith design beside it needs none. The result of `rel` is a normal form, so a rebase out and back is the identity on a target already in it.

**A round trip** is byte-identical on the conditions of SPEC §11.3; where the mechanism decides them: `replace_lines` ends each line with a newline, so a file with none gains it; the item returns after the last item of the group dropped on (`_roadmap_with`), so a blank line between them, or a different group, returns it elsewhere; and a design file's trailing blank line is not restored. In a diced design the line added at the list's end is the one removed, but a Contents block the move had to add stays, and an empty list keeps a blank line. The reverse trip (design, roadmap, design) puts a leaf's Contents line at the end of the list, not where it was. A parked entry's round trip writes only the design: the link section is added, then removed.

## §7 Invariants

- A document is a list of lines; structure is line ranges over it (sections, items, tables), and every transform is a splice of lines. No markdown parser or syntax tree: a feature that needs one is past this tool's scope. The board page (`board.js`) holds to the same line: it renders a small fixed set of inline forms (code spans, links shown as their text, `**strong**` and `*emphasis*`) and joins a section's lines into paragraphs at blank lines; any other markdown shows as written, and rendering more is past the tool's scope.
- Head-file names are spelled only in `heads.py`; every other module imports them.
- Fenced code is defined only by `FenceTracker`; `outline`, `split`, `reassemble`, `linkcheck`, `refactor`, `dicedoc`, `kanban.planform` and `kanban.board` (through `fence_flags`) use it.
- Only `textfile` opens files for text; passes use its readers and writers. One exception: `kanban.server` reads the page's files from the package's `assets/` through `importlib.resources`, `Traversable.read_text`, because a packaged resource, which may sit in a zip, has no path to give `textfile`.
- Passes are functions of their arguments and write only to the `out` / `err` streams they are given (drivers take `stdout` / `stderr`). Nothing below `__main__` touches `sys.stdout`, which is what lets `manifest` capture a volume's output in a `StringIO`. Drivers own filesystem layout and exit statuses.
- `Section` lists are in document order with `id == index`; `sections[0]` is always the entry point.
- Sections' `first`..`last` ranges partition `1..len(lines)`.
- The file-name slug (`slug`, in `outline`; `section_name` builds the §3.2 name from it) and the heading anchor (`linkcheck.github_anchor`) are separate functions and never substituted for each other.
- The code spells the `Contents:` line as `heads.CONTENTS` and locates a head's Contents block with `reassemble.contents_cut`; no test enforces this.
- The board writes a document with `textfile.replace_lines`, whole or not at all, and otherwise changes one only by `os.remove` of a leaf; no test enforces this.

## §8 Test harness

`docdicer/test/test_dicer.py` holds the end-to-end harness as pytest functions; the per-module unit test files are named below.

`test_cases` is parametrized over the directories under `data/`, one test per case, its id the directory name; `test_cases_exist` requires at least one case. A case holds:

| Path | Content |
|---|---|
| `input/` | the working tree the command runs in (symlinks copied as symlinks) |
| `args` | the command-line arguments, one per line |
| `env` | optional `KEY=VALUE` lines; `DICER_KEEP` is removed from the inherited environment otherwise |
| `expected/names` | the values the output carries, one entry per output line: `<stream>[\t<name>...]`, `<stream>` being `stdout` or `stderr`; any other line, or an empty name, is malformed, and an empty file is valid. A stream's lines are its bytes split at `\n` after removing one final `\n`; a non-empty stream must end in `\n`, and an empty one has no lines. A stream has exactly as many lines as entries, and passes when each entry is given a distinct line it matches (bipartite matching by augmenting paths); a stream with no entries is empty. An entry of `<stream>` alone matches any line; otherwise its names are found left to right, each search starting where the previous match ended, each name a whole token: no ASCII letter or digit beside it, nor a `.` or `-` joined to one. Matching is on bytes, each name encoded UTF-8 with `surrogateescape`. A `list` case's entries name `stderr` only. The harness sets `COLUMNS=1000`, so an argparse usage line never wraps |
| `expected/stdout` | `list` cases only: exact bytes (SPEC §9.2 rows are contract) |
| `expected/exit` | the status and a newline |
| `expected/tree/` | every file of the working tree after the run, inputs included |

The harness copies `input/` into the test's pytest `tmp_path`, which `just test` places under `docdicer/test/temp/` (git-ignored) through `--basetemp`, and which pytest deletes and recreates on each run; it runs `sys.executable -m docdicer <args>` there as a subprocess, and compares the exit status, a `{relative path: bytes}` map of all files, the `expected/names` assertions, and for `list` cases stdout. Only files are compared, so empty directories are not asserted.

`test_undice_then_dice_reproduces_the_tree` is parametrized over every case whose args are `dice-doc` with no map and whose expected exit is 0; each copies its `expected/tree/` into its `tmp_path`, runs `undice <out> mono.md`, renames `<out>` aside, runs `dice-doc mono.md <out>`, and requires both runs to exit 0 and the two trees' file maps equal (SPEC §6.1). `test_round_trip_cases_exist` requires at least one case to qualify. Both runs go through the same subprocess call as the golden cases.

The per-module unit tests call the owning functions directly: `test_textfile.py`, `test_outline.py`, `test_split.py`, `test_linkcheck.py`, `test_reassemble.py`, `test_linkrewrite.py`, `test_undice.py`, `test_refactor.py`, `test_treecheck.py`, `test_planform.py`, `test_plancheck.py`, `test_board.py`, `test_server.py`. `test_server.py` starts `KanbanServer` on an ephemeral port in a thread against a `tmp_path` project holding `.git` and drives it over HTTP; it also calls `run_kanban` directly. Its one subprocess test, `test_the_command_prints_the_url_and_serves_until_interrupted`, runs `python -m docdicer kanban`, reads the URL line, fetches the page, sends SIGINT, and requires exit 0 and nothing further on either stream. `test_plancheck.py` covers the default plan and design and the project-root exits, which no golden case can (a golden case's `tmp_path` sits inside this repository's `.git`); the `check-plan-*` golden cases name `<plan>` and the `check-design-*` cases `<design>`. The driver tests pass the directory as `start` rather than changing directory; the two no-project-root tests also patch `os.path.lexists`, since the test directory sits inside this repository's `.git`.

## §9 Extension points

- *A new command*: add a parser in `__main__._parser`, a driver in the layer that owns its inputs, and a golden case; exit statuses follow SPEC §2.
- *A new link form*: change `scan` and `Linker` only (§6).
- *A new split level*: `outline._DEEPEST_SPLIT_LEVEL`; the heading-width test in `plan_sections` bounds what is a heading at all.
- *A new plan- or design-form breach*: a `BreachKind` and its detection in `kanban.planform.read_plan` or `design_from_files`, and its problem text in `kanban.plancheck._PROBLEMS`; the reader's callers receive it through `Plan.breaches` or `Design.breaches`.
- *Head-file names*: fixed, not an extension point.
