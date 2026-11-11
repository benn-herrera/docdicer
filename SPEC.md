# SPEC – docdicer

Consumer-facing behaviours and outcomes; any implementation that satisfies them is valid.

File names, the files a command writes and their content, exit statuses, the stream each message goes to, and output SPEC gives as a row format (§9.2) are contract. Message wording is not: the messages below give current wording. What is contract is which fault or result each message reports, the values it carries, shown in `<angle brackets>` (a file, a line, a heading, a count), and the remedy it names.

## §1 What docdicer is

docdicer turns large markdown documents into trees of small linked files, and checks and shows development plans as a board. It guarantees five outcomes:

- **Navigable.** Every entry point and index lists the files directly below it, so the tree's entry point leads to every file; `check-tree` verifies this (§3, §8.5).
- **Lossless.** Each line of the source appears in exactly one file, unaltered except for link rewriting (§4); this is verified after every dicing (§8.1).
- **Linked.** Cross references in the source (`§N`, `#anchor`, relative paths) resolve in the tree (§4, §8.2, §8.4).
- **Repeatable.** For every command but `kanban`, equal inputs give equal trees and messages, and nothing depends on the clock, the network, or any state outside the named inputs. `kanban`'s live server is state outside its named inputs.
- **Non-destructive.** No command modifies a source document, except that `kanban` moves entries between `ROADMAP.md` and the active design, in either direction (§11.3).

## §2 Command line

The program is the command `docdicer <command> [arguments]`.

| Command | Purpose | Section |
|---|---|---|
| `dice-doc` | dice one document, then run the reassembly and link checks | §6 |
| `undice` | write a diced tree back out as one document | §6.1 |
| `dice-docs` | dice a set of documents into one tree of volumes | §7 |
| `verify` | re-run the reassembly and link checks on built trees | §8.3 |
| `refactor` | turn bold run-in titles into headings | §9.1 |
| `list` | classify every bold-led line of a document | §9.2 |
| `check-links` | check relative links and anchors of any markdown files | §8.4 |
| `check-tree` | check the structure of diced trees | §8.5 |
| `check-plan` | check a plan's status form | §8.6 |
| `kanban` | serve a live board of the development process's files | §11 |

`docdicer --version` prints the version and exits 0. `-h`, alone or after a command, prints help and exits 0. A missing command, a wrong argument count, or an unknown option is a usage error.

**Exit status.** 0 success. 1 a step or check failed. 2 bad arguments: usage errors and the per-command argument faults named below.

**Streams.** Results and summaries go to stdout; diagnostics, warnings and failure details go to stderr, except where a command's section says otherwise.

**Run directory.** Relative links in a source document, and paths in a manifest or link map (§5, §7), are resolved against the directory the command runs in, not the document's own directory.

**Text.** Files are read and written as UTF-8 with lines split on `\n` only. A line's other bytes, including `\r` and bytes that are not valid UTF-8, are preserved from input to output. Every line written is terminated by `\n`, so a file whose last line was unterminated gains a final newline.

**Environment.** `DICER_KEEP` is a comma-separated list of titles that `refactor`, `dice-docs` and `list` never convert (§9.1). Unset it is `Open`; set empty it keeps none. No other command reads it.
## §3 The diced tree

### §3.1 Which headings split

A heading is a line of 1 to 6 `#` at column 0 followed by a space, outside fenced code. A fenced block opens at a line of at least three backticks or tildes (indentation by spaces allowed; a backtick fence's info string holds no backtick) and closes at a line of the same character, at least as many, followed only by spaces; an unclosed fence runs to the end of the document.

| Level | Role |
|---|---|
| 1 | The first is the document title and stays in the entry point's text. Each later level-1 heading stays as text and is reported on stderr: `extra level-1 heading at line <N> kept as text`. |
| 2, 3, 4 | Split into sections. |
| 5, 6 | Text. |

A split heading's parent is the nearest preceding split heading of a lower level, or the tree's root if none; levels may be skipped.

A section's text runs from its heading line to the line before the next split heading of any level. The entry point's text is every line before the first split heading, or the whole document if there is none.

### §3.2 File names and layout

The heading text is what follows the `#` run, with leading and trailing spaces removed. A heading is **numbered** when its text opens with digits optionally followed by `.digits` groups, an optional `.`, and a space (`1.`, `2 `, `1.1.1.`). Its **number** is that prefix without the trailing `.`; its **title** is the rest. An unnumbered heading's title is its whole text.

The **slug** of a title: ASCII uppercase lowered, backticks deleted, every maximal run of characters outside `a-z0-9` replaced by one `-`, leading and trailing `-` removed. Non-ASCII letters are separators, not transliterated.

The **name** of a section: `<number>-<slug>` when numbered with a non-empty slug; `<number>` when numbered with an empty slug; `<slug>` when unnumbered. An unnumbered heading with an empty slug is an error.

| Section | Path |
|---|---|
| Tree root (the output directory) | `entry-point.md` |
| Has child sections | `<parent dir>/<name>/index.md` |
| No child sections | `<parent dir>/<name>.md` |

**Errors, all exit 1 with nothing written to the tree** (the output directory may be left created and empty):

- `empty slug for heading at line <N>`: reported for the first such heading only.
- `path collision: <path> (lines <A> and <B>)`: two sections would write the same path. Every collision is reported, each against the previous holder of the path.

**Duplicate numbers.** Headings sharing a number are reported on stderr as `duplicate section number <number>`, once per `dice-doc` (§6), `undice` (§6.1) and `verify` pair (§8.3). Dicing continues; a reference to the number resolves to the last heading that carries it (§4.2).

### §3.3 File content

Each file holds, in order, exactly the source lines of its section, heading line included, with links rewritten (§4).

The entry point and every index end with a **Contents block** appended directly after the section's own lines (no separator line is added):

```markdown
Contents:

- [<link text>](<path>)
```

- The entry point lists every other section in document order, one line each, indented two spaces per depth below the first level, each `<path>` relative to the tree root.
- An index lists its direct children in order, unindented, each `<path>` relative to the index's directory.
- A block with nothing to list is `Contents:` and a blank line.
- `<link text>` is `§<n> <title>`, where `<n>` is the number of the section itself if numbered, else of its nearest numbered ancestor; with no numbered section at or above, it is the title alone.

## §4 Link rewriting

Rewriting applies to prose lines only: not to lines of fenced code, and not to text inside code spans. A code span opens at a run of backticks and closes at the next run of the same length; an unmatched run is literal text.

### §4.1 What is a link

A link is `[text](target)`: the first `]` after a `[`, immediately followed by `(`, with the target running to the first `)`. This includes images (`![alt](target)`). No title, angle-bracket or escape syntax is interpreted; reference-style links and autolinks are not recognised and never rewritten.

### §4.2 Section references

A reference is `§` followed by digits and `.digits` groups, taken at maximal length (`§1.1.` is the reference `§1.1`). Outside link text and code spans, each reference is handled in this order:

1. **Another document's section.** If the text just before it, on the same line, ends with `SPEC `, `ARCHITECTURE `, `THESIS ` or `CONVENTIONS ` (with or without `.md`), it is left as written and is not counted.
2. **Dangling.** If no section has that number, it is left as written and counted as dangling.
3. **Linked.** Otherwise it becomes `[§<number>](<path>)`, the path being the numbered section's file relative to the file the reference sits in. If the reference is directly followed by a space and a backticked name, and a direct child of the section has a title containing that backticked name, the link text extends over the name and the target is that child (`[§2 `beta`](...)`); with no such child only `§<number>` is linked and the name stays as text. The first matching child wins.

After the section pass, stderr carries one summary line: `refs linked: <R>; dangling: <D> distinct:` followed by ` §<number>(<count>)` for each distinct dangling number in order of first occurrence.

### §4.3 Link targets

Each link's target is classified in this order:

1. **Anchor of this document** (`#frag`, where `frag` is the GitHub-style anchor of one of the document's headings; §4.4). The target becomes the file holding that heading, relative to the linking file; plus `#<anchor within that file>` unless the heading is the first line of a non-entry file. The entry point's own headings keep their anchor.
2. **Left unchanged:** an empty target, any other `#...` target, a target opening with `/`, and a target opening with a lowercase-letter scheme and `:` (`https:`, `mailto:`).
3. **A diced document in the link map** (§5): the target's path part (before any `#`) equals a map document key. The target becomes that document's entry point and any fragment is dropped; if the text following the link opens with an optional comma, spaces and a double-quoted heading title that the map lists for that document, the target is that heading's leaf instead. The text after the link is the rest of its line; when that rest is empty or only `,` and spaces, the next line is taken as its continuation. The quoted text itself is left in place.
4. **Any other relative path** is rebased (§2) to reach the same file from the directory of the file it now sits in, fragment kept.

### §4.4 Anchors

The GitHub-style anchor of a heading (ATX, levels 1 to 6, up to three leading spaces, outside fenced code): text with closing `#` run removed, lowercased, every character that is not a letter, digit, space, `-` or `_` deleted (letters and digits include non-ASCII ones), spaces made `-`. The Nth repeat of an anchor in one file takes the suffix `-<N-1>` for N>1 (`setup`, `setup-1`, `setup-2`). In the source, repeats are counted over the whole document; in a diced file, over that file's headings alone.

## §5 The link map

A UTF-8 TSV file used by `dice-doc` and `verify` and produced by `dice-docs`. Each line has two or three tab-separated fields; other lines are ignored.

| Fields | Meaning |
|---|---|
| `<target>\t<path>` | A link whose path part is `<target>` goes to `<path>`, the diced document's entry point. |
| `<target>\t<heading>\t<path>` | A link to `<target>` whose following text quotes `"<heading>"` goes to `<path>`, that heading's leaf. `<heading>` is the title without its number. |

`dice-docs` writes the map to `<work-dir>/links.tsv`: per document, one entry-point row, then one heading row per distinct title in section order (the first section of a title wins). The `entry` document of a manifest gets an entry-point row keyed by its base name.

## §6 `dice-doc`

`docdicer dice-doc <monolith.md> <out-dir> [map.tsv]` dices one document (§3, §4), using `map.tsv` as the link map if given.

Order of effects and failures:

| Condition | stderr | Exit |
|---|---|---|
| `monolith` is not a file | `not a file: <monolith>` | 2 |
| `map` given and not a file | `not a file: <map>` | 2 |
| `out-dir` exists and is not a directory | `not a directory: <out-dir>` | 2 |
| `out-dir` exists and is not empty | `out-dir not empty: <out-dir>` | 2 |
| Planning fails (§3.2) | the §3.2 message | 1 |

Otherwise `out-dir` is created if absent, the tree is written, and stderr receives the `refs linked` line (§4.2) and any §3 warnings. The reassembly check (§8.1) then runs; on failure its message goes to stderr and the command exits 1 without running the link check. The link check (§8.2) follows; its `dead link` lines go to stderr and its summary to stdout. Exit 0 only when both checks pass. Files already written remain on failure.

### §6.1 `undice`

`docdicer undice <tree-dir> <monolith.md>` writes the document a diced tree holds as one file. It need not equal the document the tree was diced from.

**Round trip.** For a tree as `dice-doc` wrote it without a map, with well-formed Contents links (§10): move `<tree-dir>` aside and dice the unchanged `<monolith.md>` with `dice-doc`, without a map, from the same run directory, into `<tree-dir>`; the new tree equals the old byte for byte.

| Condition | stderr | Exit |
|---|---|---|
| `<tree-dir>/entry-point.md` is not a readable file | `not a tree: <tree-dir>` | 2 |
| `monolith` exists | `<monolith> exists: name another output, or move or delete it` | 2 |
| `monolith` cannot be written | `cannot write: <monolith>` | 2 |

**Content.** The entry point's lines, then each file linked from its last `Contents:` line on, in that order; a linked file that cannot be read prints `undice: cannot read <tree-dir>/<target>` to stderr, is left out, and fails the command (exit 1). From the entry point and every index, the Contents block and every line after it are dropped (§8.1's cut). Links are restored outside fenced code and code spans:

- A section link (§4.2 step 3) becomes its link text: `§<number>`, or `§<number>` and the backticked name.
- A link to a heading's place in the tree, as §4.3 step 1 writes it, becomes `#<anchor>`, the heading's anchor in `<monolith.md>` (§4.4).
- Every other relative link is rebased from its file's directory to the run directory, fragment kept. Links left unchanged by §4.3 step 2 stay unchanged.

**Self-check.** After writing, `<monolith.md>` is planned (§3, its messages to stderr as in §6); a planning failure exits 1 there. Otherwise the reassembly and link checks (§8.1, §8.2) run on it against `<tree-dir>`, with their messages and streams as in §6. Every `.md` file under `<tree-dir>` must also be one §3.2 assigns, except files under a directory below the root that holds its own `entry-point.md` (a nested volume). Each other prints to stderr, naming the remedy rather than applying one:

| The file | Message |
|---|---|
| was read as a section that §3.2 places at another path | `undice: <file> would be re-diced as <tree-dir>/<path>: rename the file or edit its heading to match` |
| was read, but opens no section | `undice: <file> opens no section: start it with a level 2 to 4 heading, or remove it and its Contents line` |
| was not read | `undice: not reproduced: <file>: link it from <tree-dir>/entry-point.md's Contents, or remove it` |

A file was read when a link from the entry point's last `Contents:` line on resolves to it. It was read as a section when its first line opens a section of `<monolith.md>` other than the entry point; a file read more than once was read as the first such section in document order. Contents blocks are not compared, so a hand-edited block is regenerated by the round trip without a report. Exit 0 if all pass, else 1; `<monolith.md>` is kept either way.

## §7 `dice-docs` and the manifest

`docdicer dice-docs <manifest.tsv> <src-dir> <work-dir>` dices several documents into one tree of **volumes** that link to each other.

### §7.1 Manifest

Tab-separated rows of `file`, `outdir`, `flags`, `label`; missing trailing fields are empty. Empty lines and lines starting with `#` are skipped.

| Field | Meaning |
|---|---|
| `file` | Source file under `<src-dir>`. Other documents link to this volume by this text (§4.3 step 3). |
| `outdir` | Output directory of the volume. |
| `flags` | Comma list, may be empty: `refactor` (apply §9.1 before dicing), `items` (with `refactor`, also convert bold list items), `entry` (see below). |
| `label` | Title of a volume group (below). |

A row flagged `entry` is not diced: its file is copied verbatim to `<outdir>/entry-point.md`, followed by a blank line, `Volumes:`, a blank line, and one line per volume whose `outdir` has `<outdir>` as its parent directory, in manifest order:

```markdown
- [<volume dir name>](<volume dir name>/entry-point.md): <purpose>
```

`<purpose>` is the first sentence of the volume document's opening paragraph (the first paragraph after its first `# ` line, joined into one line, links reduced to their text; the sentence ends at the first `. `, else the whole paragraph). A manifest has at most one effective `entry` row (the last wins).

A volume whose `outdir` is `<parent>/<group>/<name>`, where `<parent>` is another volume's `outdir`, belongs to a **group**. The group directory gets an `index.md` — `# <label>`, a blank line, `Contents:`, a blank line, then `- [<document title>](<name>/entry-point.md)` for each of its volumes in manifest order — and the parent volume's `entry-point.md` gains the line `- [<label>](<group>/index.md)` after its Contents block. `<label>` is taken from the first volume of the group; `<document title>` is the text of the volume document's first `# ` line. Parents must precede their children in the manifest. Other nesting depths are unspecified.

### §7.2 Effects

In order:

1. A manifest that is not a file exits 2 with `not a file: <manifest>`; a source directory that is not a directory exits 2 with `not a directory: <src-dir>`. `<work-dir>` is then created if absent.
2. Rows are read in order. A row whose source is absent ends the command (stderr `missing source: <src-dir>/<file>`, exit 2). A `refactor`-flagged row is refactored (§9.1) into `<work-dir>/<file>` (and `<work-dir>/<file>.skipped`) as it is read; the refactor report goes to stdout, and a refactor failure ends the command with that status. Refactored copies are the documents diced.
3. The link map is written (§5).
4. Before dicing: the `entry` row's `<outdir>/entry-point.md` is removed (its directory is created), and each volume's output directory is removed with its contents unless it lies inside another volume's output directory.
5. Each volume is diced as by `dice-doc` (§6) with the link map. Its output is preceded by `=== <file>` on stdout; its stderr is merged into stdout, and its `dead link:` lines are suppressed. A failed dicing does not stop the others; it surfaces in step 7.
6. Group indexes and the entry point are written (§7.1).
7. `verify` (§8.3) runs on every volume with the link map.
8. A final check over the files written in step 6 prints `=== files written by this script: link targets exist`, then `  checked <file>` per file, and `  DEAD <file> -> <target>` for each markdown link in those files whose target ends in `.md`, has no `#`, and names no existing file relative to the file's directory.

Exit 0 only if step 7 and step 8 pass; otherwise 1.

## §8 Checks

### §8.1 Reassembly

Passes when the files §3.2 assigns, read in section order with each entry point's and index's Contents block dropped (from its last line that is exactly `Contents:`) and §4.2 step 3 links undone, equal the source lines with their other links as rewritten by §4.3. Success prints `reassemble ok: <N> lines` to stdout; each failure prints to the command's error stream:

| Fault | Message |
|---|---|
| line differs | `reassemble: first difference at monolith line <N> (<file>)`, then `  want: <line>` and `  got:  <line>` |
| file unreadable | `reassemble: cannot read <file>` |
| no Contents block | `reassemble: no Contents block in <file>` |
| line count | `reassemble: leaves hold <K> lines, monolith <M>` |

The check compares lines, not final newlines (§2). Lines added after a Contents block (§7.1) are outside its scope.

### §8.2 Link check

Every link in the prose of every file §3.2 assigns, taken without its `#fragment`, must name a readable file relative to that file's directory. Skipped: empty targets (bare `#frag`), targets opening with `/`, and targets with a URL scheme (§4.3 step 2). Everything else is probed relative to the file and so is dead unless it exists there; a directory is dead. An assigned file that cannot be read contributes no links (§8.1 reports it). Each dead link prints `dead link: <file>:<line> -> <target>` to the error stream; the summary `links checked: <N>, dead: <D>` goes to the output stream.

### §8.3 `verify`

`docdicer verify <map|-> <monolith> <out-dir> [...]` takes a link map path or `-` for none, then one or more pairs. For each pair it prints `=== <monolith> -> <out-dir>`, then runs §8.1 and §8.2, then prints `  leaves: <K>`, K being the number of `.md` files under `<out-dir>` other than `entry-point.md` and `index.md`. All output goes to stdout: reassembly messages unindented, link-check lines indented two spaces. A pair whose `out-dir` is not a directory prints `not a directory: <out-dir>` to stderr; one whose monolith cannot be read prints `cannot read: <monolith>` to stderr. Any failing pair makes the exit status 1. An odd number of pair arguments is a usage error (2).

### §8.4 `check-links`

`docdicer check-links <root>...` checks markdown files that need not come from a dicing. A directory root contributes every `.md` file beneath it in sorted order; a file root is checked alone; a file reached twice is checked once. Every root must exist, else exit 2 (`no such root: <roots>`). Every file so contributed must be readable as a file; before any link is checked, each that is not prints `cannot read: <path>` to stderr and the command exits 2.

In prose outside fenced code and code spans, every link is checked except those with an empty target, a target opening with `/`, or a URL scheme (§4.3 step 2). The target's path part (the linking file itself, if empty) must exist, else the problem is `missing file`; given a `#fragment` it must name a markdown file with a heading whose anchor equals the fragment (§4.4, repeats counted over the file), else `missing anchor`. Each problem prints to stderr `<file>:<line>: <target>: <problem>`. The summary `links checked: <N>, broken: <B>` goes to stdout. Exit 1 if any link is broken.

### §8.5 `check-tree`

`docdicer check-tree <root>...` checks diced trees. Every root must be a directory, else exit 2 (`no such directory: <roots>`). Every `.md` file under a root must be readable as a file; before any check, each that is not prints `cannot read: <path>` to stderr and the command exits 2. A root without an `entry-point.md` is one problem (`<root>: no entry-point.md`).

A directory's **head** is its `entry-point.md` if present, else its `index.md`. A document's **parent** is the head of its directory; a head's parent is the head of the directory above. For each `.md` file under the root other than the root's `entry-point.md`:

| Problem | Message (stderr) |
|---|---|
| no parent document inside the root | `<file>: no parent document (an index.md or entry-point.md beside it or above it)` |
| parent has no link to it | `<file>: not linked from its parent <parent>` |
| not reachable by following links from the root's `entry-point.md` | `<file>: not reachable from <entry-point>` |

Links count as in §8.4. The summary `documents checked: <N>, problems: <P>` goes to stdout, summed over roots; `<N>` counts every `.md` file under a root, its `entry-point.md` included, and a root without `entry-point.md` counts none. Exit 1 if any problem.

### §8.6 `check-plan`

`docdicer check-plan [<plan>]` checks that a development plan is written in the form below, so that a program reading the plan can read all of it. The form is adjagent's plan status form. The command reports what is present and unreadable, and a post-plan review or burndown package without the other; what is otherwise absent is valid.

**Terms.**

- **plan**: a tracked markdown document that lays out work as work packages and records their progress. It is a monolith, one file, or a diced tree (§3) given by its `entry-point.md`: a file named `entry-point.md` is read as one plan together with every other `.md` file beneath its directory, the entry point first.
- **work package**: one unit of a plan's work, a row of the plan's status table, named by the ID in that row's `Package` cell. A row whose `Package` cell is empty is not a work package.
- **status table**: the first table under a `## Status` heading (a level-2 heading whose text is `Status`; the section runs to the next heading of level 1 or 2) whose header cells include `Package` and `State`, matched without regard to case. In a diced plan the heading may be in any of its files. The table is found by those two headers alone. The form also has a `Rating` header, matched without regard to case; other columns are free.
- **state**: a work package's progress as its State cell records it. A cell opening with `dispatchable` (ready to hand to an agent), `in progress` (dispatched, not yet landed) or `landed` (accepted and committed) states that word, lowercase and without markup, as a whole word; any text after it is a note. An empty cell states **drafted**.
- **rating**: a work package's kind of work as its Rating cell records it. A cell opening with `mechanical` (every edit enumerated, no design choice and no debugging) or `expert` (anything else) states that word, lowercase and without markup, as a whole word; any text after it is a note. A package whose Rating cell opens with neither word, an empty cell included, or whose table has no `Rating` column, is **unrated**.
- **release line**: a line opening with `Release:` at column 0. Its version is the text after the colon, surrounding spaces removed.
- **title**: in the first heading, in reading order, whose text opens with a work package's ID — the ID followed by neither a letter, digit or `_`, nor a `.` or `-` followed by one — the text after the ID and after any run of characters each whitespace or one of `:` `.` `,` `;` `|` `/` `)` `]` `-` `–` `—`. A package with no such heading is untitled and is neither post-plan package kind.
- **post-plan review package**, **post-plan burndown package**: A title opens with `Post-plan review` (or `Post-plan burndown`) where it begins with those characters, case-sensitive, followed by the end of the title or a character that is not a letter or digit. A package whose title opens with `Post-plan review` is a **post-plan review package**; with `Post-plan burndown`, a **post-plan burndown package**.

Headings, tables and lines inside fenced code (§3.1) are not part of the form.

**The form, as checked.** A plan with no status table, no work packages, no H1 heading, no release line or neither post-plan package is valid. A plan has a breach where:

| Breach | Reported at | `found` text |
|---|---|---|
| a work package's ID is the ID of an earlier row | the later row | the ID and the line of the row that first holds it |
| a work package's ID holds a space | the row | the ID |
| a State cell is non-empty and opens with none of the three state words | the row | the cell |
| the status table has no `Rating` column | the table's header line | the header line |
| a work package's Rating cell opens with neither rating word, an empty cell included | the row | the cell |
| a release line is not the first non-blank line after the plan's H1 heading, the first level-1 heading outside fenced code | the line | the line |
| a release line, in that place, has no version | the line | the line |
| a post-plan review package where the plan has no post-plan burndown package, or a post-plan burndown package where it has no post-plan review package | that package's row | the ID, a space, and the title, as `P4 Post-plan review` |

The form also has a work package's heading, at any level, open with its row's ID and then its title. `check-plan` reads titles (§8.6 Terms) for the post-plan pairing, but does not check the heading, and reports no missing heading: a heading that fails to open with the ID cannot be told from one that only mentions it. Tools reading the plan show such a package untitled.

**The plan checked.** With `<plan>`, that plan. Without it, the active plan of the project the command runs in. The **project root** is the nearest ancestor of the current directory, the directory itself included, that holds an entry named `.git`, found by looking at the file system; git is not run. The active plan is `ACTIVE_PLAN.md` under the root, else `ACTIVE_PLAN/entry-point.md`; where both exist, the monolith is checked. The active design is never read.

**Output.** One line to stderr per breach:

```text
<file>:<line>: <problem>: <found>; accepted: <accepted form>
```

`<file>` is the file holding the line (a diced plan's breach may be in any of its files), `<line>` its 1-based number, `<problem>` names the breach, and `<found>` renders the text the table gives: `found an empty cell` where the cell is empty; otherwise `found ` and the text in a code span that holds its own backticks (delimited by one backtick more than the text's longest run of backticks, padded with a space each side), so that the text ``a`b`` reads ``found `` a`b `` ``. `<accepted form>` states what the plan may hold there, enough to correct it without the rest of this section. The `<problem>` wording is current wording:

| Breach | `<problem>` |
|---|---|
| repeated ID | `package ID repeated in the status table` |
| ID with a space | `package ID holds a space` |
| State cell | `State cell opens with no state word` |
| no Rating column | `status table has no Rating column` |
| Rating cell | `Rating cell opens with no rating word` |
| release line placed elsewhere | `` `Release:` line is not the first non-blank line after the H1 heading `` |
| release line without a version | `` `Release:` line names no version `` |
| review without burndown | `post-plan review has no post-plan burndown package` |
| burndown without review | `post-plan burndown has no post-plan review package` |

Problems are printed in reading order: by file, in the plan's reading order (the entry point first, §8.6 Terms), then by line within a file.

The summary `plan checked: <plan>, work packages: <N>, problems: <P>` goes to stdout, `<N>` counting the rows with a non-empty `Package` cell.

**Exit status.**

| Condition | Stream | Message | Exit |
|---|---|---|---|
| no breach, status table or none | stdout | the summary | 0 |
| without `<plan>`, no active plan under the root | stdout | `no active plan in <root>` | 0 |
| any breach | stderr, stdout | the breach lines, the summary | 1 |
| `<plan>` is not a file | stderr | the usage error `no such plan file: <plan> (name a plan's markdown file, or a diced plan's entry-point.md)` | 2 |
| without `<plan>`, no project root | stderr | `no project root: neither <directory> nor any directory above it holds .git; run docdicer check-plan inside a project, or name the plan to check: docdicer check-plan <plan>` | 2 |
| a file of the plan cannot be read | stderr | `cannot read: <file>` | 2 |

A plan with an unreadable file exits 2 naming an unreadable file, before any breach or summary is printed. A diced plan's unreadable file is any `.md` file beneath the entry point's directory that cannot be read as a file, a dangling symbolic link among them.

## §9 Transforms

### §9.1 `refactor`

`docdicer refactor <in.md> <out.md> [items]` writes `<out.md>` with bold run-in titles turned into headings, and `<out.md>.skipped`. `items` other than empty or `0` also converts bold list items. An unreadable input prints `not a file: <in.md>` and exits 2.

**Classification.** Lines are examined outside fenced code and apart from heading lines. The **enclosing heading** is the last heading line (any number of `#`) above, its level the `#` count. A line is classified by the first rule that fits:

| Class | The line |
|---|---|
| none | is not led by bold: optional spaces or tabs, an optional bullet (`-`, `*`, `+`, `N.`, `N)`), optional spaces, then `**` and a non-`*` character |
| `ITEM` | at column 0 is `- **X.**` or `- **X:**` (X holds no `*`) |
| `LIST` | otherwise starts `- **X**` at column 0, or starts with a space or tab, or with `-`, `+`, `N.` or `N)` and a space |
| `MID` | follows a line that is not blank (a heading line, or the document's first line, counts as not blank) |
| `RUNIN` | is `**X**` at column 0 followed by nothing (`X` any text), or `**X.**` / `**X:**` followed by anything |
| `LABEL` | is any other bold-led paragraph start (`**Note** that ...`) |

The **title** of a `RUNIN` or `ITEM` is X without one trailing `.` or `:`. A `RUNIN` or `ITEM` is renamed `RUNIN-OUTSIDE-SECTION` or `ITEM-OUTSIDE-SECTION` when the enclosing heading has level below 2 or does not exist, and is never converted.

**Conversion.** A `RUNIN` becomes a heading of `min(level+1, 6)` `#` and the title; any text after the bold, minus leading spaces, follows after a blank line. An `ITEM`, only when `items` is given, converts the same way and then a blank line even with no text; its continuation lines (blank lines, and lines starting with two spaces, which are dedented by two) belong to the item up to the first other line. No blank line is added before whatever follows the item. Every other line is copied unchanged.

**Not converted, with the line kept verbatim:**

- *Keep list.* A `RUNIN` or `ITEM` whose title exactly, case-sensitively equals an entry of `DICER_KEEP` (§2) is class `KEEP`.
- *Long titles.* A `RUNIN` or `ITEM` of more than 8 words (split on spaces and tabs) is skipped and noted in `<out.md>.skipped` as `skipped long: line <N>: <title>`, one line per note; the file is empty if none.

**Self-check.** After writing, the changed regions of the output against the input (regions separated only by up to three unchanged blank lines are merged) must each have a conversion's shape: each bold-led title line becomes a heading line (any level) holding the same title, any text after the bold follows after a blank line (a list item's heading is followed by a blank line even with no text), and a list item's continuation lines are dedented by two; every other line is unchanged. The check does not re-derive a line's class, the heading level or the keep list. The report goes to stdout, `<count>` empty when nothing changed:

```text
<in.md>: <S> long titles skipped; merged hunks <count> bad <B>
```

Each region that is not a conversion prints `BAD merged hunk at old line <N>: <first input line of the region>` to stdout before the report. Exit 1 if B>0 (both output files are still written), else 0.

### §9.2 `list`

`docdicer list <doc.md>` prints, to stdout, one tab-separated row for each bold-led line (per §9.1 classification, with the keep list and long-title rule applied but nothing converted), in document order, then exits 0. An unreadable input prints `not a file: <doc.md>` to stderr and exits 2.

`<doc.md>:<line>` ⇥ `<class>` ⇥ `<new heading level>` ⇥ `<title>` ⇥ `<enclosing heading text>`

- `<class>` is one of the §9.1 classes, `KEEP`, or the two `-OUTSIDE-SECTION` forms; a `RUNIN` or `ITEM` over 8 words is suffixed `(long)` (`RUNIN(long)`). `ITEM` rows appear whether or not `items` would convert them. Continuation lines of an `ITEM` are not reported.
- `<new heading level>` is the enclosing level plus 1, not capped, for `RUNIN` and `ITEM` only; empty otherwise.
- `<title>` is the title for `RUNIN`, `ITEM`, `KEEP` and the `-OUTSIDE-SECTION` forms; for other classes the first 70 bytes of the line (a character may be cut).
- `<enclosing heading text>` is the text of the last heading line above, as written (trailing spaces kept); empty before the first heading.

## §10 Limits

Input outside this specification is refused with a message naming what to fix, not accommodated. Known limits:

- A source's links must be written relative to the run directory (§2); a document run from elsewhere gets mis-rebased links, which the link check (§8.2) reports only if the result no longer resolves.
- `verify` treats a map path that is not a file as no map.
- A heading's link text is used verbatim in Contents blocks; a title containing `]` or unbalanced brackets yields a malformed Contents link that no command repairs; a heading holding a link does too. `check-tree` reports it, and `undice` reports that section's file as not reproduced.
- A conversion by `refactor` can place a heading deeper than level 4, which dicing then keeps as text (§3.1).
- `undice` on a `dice-docs` volume is best effort: links made through a link map come back as paths, and its self-check (§6.1) reports what does not round-trip.
- A project root with no name of its own, the file-system root `/`, gives the kanban page an empty `<project>` (§11.2).

## §11 `kanban`

`docdicer kanban [<project-dir>]` serves a live board of a project's development-process files on the local machine, for the user to open in a browser. The board shows the roadmap, the active design and the active plan's work packages as cards in columns. Its only writes to documents are the moves of an entry between `ROADMAP.md` and the active design, made by dropping a card on Design or on Roadmap (§11.3); after a move, the entry is in exactly one of the two documents (a move that fails partway is described under **Writes**, §11.3). The plan columns are read-only: a work package's state changes only by an edit to the plan, which the board then shows (§11.4, §11.5). The board stores nothing (§11.6).

The board reads the files as they are, in the form `check-plan` checks (§8.6), and shows a plan that holds breaches of that form all the same, reading a State cell that opens with no state word as drafted. Terms of §8.6 (plan, work package, state, rating, title, status table, release line, project root, active plan) are used as defined there.

**Start.** `<project-dir>` names a directory inside the project; without it the project is the one the command runs in. The project root is found from that directory as §8.6 defines it. Once the server is listening it prints the page's URL, `http://127.0.0.1:<port>/`, on a line of its own to stdout; the user opens that URL. The server accepts connections from the local machine only (`127.0.0.1`), and refuses a request whose `Host` header is not the server's own address (`127.0.0.1` or `localhost`, with the port), so that a page served from elsewhere cannot drive the board. It then runs until interrupted; interrupting it (Ctrl-C) ends the process with exit 0. Which port it listens on is not fixed by this SPEC: the printed URL is the address. The server writes nothing per request: stdout carries the URL line only, and stderr carries only the diagnostics named in this section (§11.5).

| Condition | Stream | Message | Exit |
|---|---|---|---|
| more than one argument, or an unknown option | stderr | the usage error | 2 |
| `<project-dir>` is not a directory | stderr | the usage error `no such directory: <project-dir>` | 2 |
| no project root | stderr | `no project root: neither <directory> nor any directory above it holds .git; run docdicer kanban inside a project, or name a directory inside a project: docdicer kanban <project-dir>` | 2 |
| a document the board reads cannot be read as a file, at start | stderr | `cannot read: <file>`, before any URL is printed | 2 |
| the port cannot be bound | stderr | `cannot listen: <reason>`, before any URL is printed | 2 |

### §11.1 The project's files

Under the project root the files are at fixed paths; nothing relocates them.

| Document | Path |
|---|---|
| **roadmap** | `ROADMAP.md` |
| **active design** | `ACTIVE_DESIGN.md`, else `ACTIVE_DESIGN/entry-point.md` |
| active plan (§8.6) | `ACTIVE_PLAN.md`, else `ACTIVE_PLAN/entry-point.md` |
| **parked-plans directory** | `ROADMAP_PLANS/` |

Where both forms of the active design or the active plan exist, the monolith is read. A **parked entry** is a `.md` file in the parked-plans directory other than `README.md`, or a subdirectory there holding its own `entry-point.md`, counted as one entry. A parked design and a parked plan are not told apart. A document that is absent contributes no cards; a project with none of them shows an empty board.

### §11.2 Columns and cards

The board has six columns, left to right: Roadmap, Design, Drafted, Dispatchable, In progress, Landed. Drafted through Landed are the **plan columns**, which are read-only (§11.4).

| Column | Cards |
|---|---|
| Roadmap | each top-level list item of `ROADMAP.md`; each parked entry that no list item links and whose link section (§11.3) is not in the active design |
| Design | each level-2 section of the active design, one card each |
| Drafted | each work package whose State cell is empty or opens with a word other than the three state words |
| Dispatchable, In progress, Landed | each work package whose State cell opens with that state word |

**Roadmap cards.** A top-level list item is a line opening with `-`, `*` or `N.` (digits and a full stop) in column 0, outside fenced code; the item runs over its continuation lines to the next item or heading, or to a line in column 0 after a blank line. Its title is its bold lead where its text opens with one, else its first sentence, either without a closing `.` or `:`, and with each markdown link `[text](target)` reduced to its text; the heading that a move to Design writes (§11.3) is this title. A title taken from a first sentence is cut to at most 60 characters, ending in `…` where cut. The card shows the item's level-2 heading above it as its group, if any.

**Parked entries.** A parked entry that a list item links, by a link whose path names the entry's `.md` file (for a diced entry, its `entry-point.md`), has no card of its own: it shows inside the card of the item that links it. Links in a parked entry, or any link beyond that one, are not followed. A parked entry that no item links gets a generated card, titled by its file name without `.md` (a diced entry, by its directory's name), after all the cards of items, ordered among themselves by the entry's path within the parked-plans directory; the card exists only on the board. A parked entry whose link section (§11.3) is in the active design shows there as a Design card, and not in Roadmap.

**Design cards.** The board reads the active design's level-2 sections, outside fenced code; in a diced design, across the entry point and its leaves, in reading order. Each section is a card, and the cards follow that order. A section that is a parked entry's link section shows as that parked entry's card; every other section shows as a card titled by its heading, with the section's text.

**Work package cards.** A card shows the package's ID, its title, its rating word (`mechanical` or `expert`) or that it is unrated, and its lifetime where the status table has a `Lifetime` column, matched without regard to case. A package's title is as §8.6 Terms defines it; an untitled package shows untitled. A plan whose table has no `Rating` column is still shown, its packages unrated. Cards in a plan column follow the status table's row order.

**Title and header.** The page is titled `<project> kanban`, `<project>` being the name of the project root's directory, in the browser's title and in the header. The header also shows the active plan's release (the version of its release line, displayed as written and never interpreted), and "hardening" where the plan's level-1 heading opens `Release hardening`.

### §11.3 Moves between Roadmap and Design

Dropping a card moves its entry between `ROADMAP.md` and the active design. After a move the entry is in exactly one of the two documents, with its text preserved. These moves are the board's only writes to documents. A section of the design is a **link section** where it is the one a move writes for a parked entry (below), unedited.

**Roadmap to Design.** Dropping a roadmap card or a generated parked-entry card on Design:

- *roadmap card*: the item is removed from `ROADMAP.md` and a level-2 section is added to the design, its heading the card's title and its body the item's text as written, its marker removed and its relative links rebased as below;
- *parked-entry card*: a level-2 section is added whose heading is the card's title and whose body is a link to the parked entry, resolving from the file holding the section, and the line `complete and update this design`; the entry file and `ROADMAP.md` are not touched.

| The active design | The addition |
|---|---|
| absent | `ACTIVE_DESIGN.md` is created, opening with the level-1 heading `# ACTIVE DESIGN` (never the moved card's title), then the section |
| a monolith | the section is appended to it, a blank line parting it from the text above |
| a diced tree | the section is a new leaf in the directory of `entry-point.md`, named as dicing names a level-2 section (`<name>.md`, the §3.2 name of the title: `<number>-<slug>` where numbered), and the line `- [<title>](<name>.md)` is added at the end of the list under the last `Contents:` line of `entry-point.md` (a Contents block is added at its end where there is none) |

**Design to Roadmap.** Dropping a design card on Roadmap removes its section from the design and, unless the card is a link section, adds an item to `ROADMAP.md`. In a diced design a section held by a leaf is that leaf: the leaf and its line in the Contents list are removed. A link section is removed and nothing is added; its parked entry has no card of its own again and shows in Roadmap (§11.2).

The item is a top-level list item (§11.2) placed at the end of the level-2 group of the Roadmap card the drop landed on, or at the end of the file where the drop landed on a parked-entry card, on no card, on a card with no group, or on a card that is no longer on the board. It takes the list marker of the items of the group it is placed in (a numbered group's next number), or, placed at the end of the file, of the group open at the end of `ROADMAP.md`; `-` where that group has no items or the file has none. `ROADMAP.md` is created, holding the item alone, where it is absent.

- A section that is **unchanged** since its addition returns as the item it was, so that moving a card to Design and back leaves `ROADMAP.md` and the design byte-identical to before, on the conditions under **Links** below. A section is unchanged only where both hold: its heading is the title that its body, read as an item, would give (§11.2); and its lines, after the list marker, read back as exactly one top-level list item.
- Any other section returns in the bold-lead form: an item whose bold lead is its heading and whose text is its body.

**A section in `entry-point.md`.** A level-2 section that sits in a diced design's `entry-point.md`, not in a leaf, moves as a monolith section does: its lines are removed from the file holding them, with no leaf and no Contents line removed. The Roadmap to Design addition in a diced design is a leaf (above); it is never written into `entry-point.md`.

**Links.** A move rebases each relative link target in the entry's text from the directory of the source file to that of the destination file, by the rule for a link target in §4.3 step 4; targets that §4.3 step 2 leaves unchanged stay unchanged. This holds in both directions. The rebase is its own inverse for links in normal form.

A round trip (Roadmap to Design and back) leaves `ROADMAP.md` and the design byte-identical only where nothing was edited in between and all of these hold:

- the entry's links are in normal form;
- the item was the last of its level-2 group, with no blank line before it, and is dropped back on a card of that group;
- the design did not end in a blank line before the addition;
- for a diced design, `entry-point.md` already held a `Contents:` block over a non-empty list;
- each file written ends in a newline (a file that does not gains one).

Where a condition fails the entry still returns with its text preserved, but the surrounding blank lines, the item's place or a `Contents:` block may differ.

**Refusals.** A move is refused, and nothing is written, where:

- a file the move writes (`ROADMAP.md`, the design file, or in a diced design `entry-point.md` and the leaf) has a content, existence or absence different from when the board last read it, checked for every such file immediately before the first write; a change after that check is not detected;
- the active design is a diced tree and the title's §3.2 name is empty (an unnumbered title with an empty slug), refused with a message naming that cause;
- the active design is a diced tree and the leaf to add already exists, refused with a message naming that cause;
- the move must remove a line from the Contents list of a diced design's `entry-point.md` and cannot find it;
- a document the move reads cannot be read, refused with `cannot read: <file>`, `<file>` as a path from the project root (a move never reads the active plan); or
- the dropped card is no longer on the board, its item, parked entry or section having changed or been removed since the page showed it.

The refusal is shown to the user and names the cause.

**Writes.** Each file is written whole. The addition is written before the removal, so that a failure partway leaves the entry in both documents and never in neither. A write that fails at the file system is reported as `cannot write: <file>`, `<file>` the file that could not be written, and names the files already written. After a move the page shows a notice naming the files written, as paths from the project root with `/` separators.

### §11.4 The plan columns are read-only

The cards in the plan columns cannot be dragged, and nothing can be dropped on a plan column. The page shows this on sight: the plan columns and their cards are visibly set apart from Roadmap and Design, whose cards can be dragged. A work package's state changes only by an edit to the plan file, which the board shows (§11.5).

**Drops not accepted.** The only drops accepted are a roadmap or parked-entry card on Design and a design card on Roadmap (both §11.3). Any other drop is not accepted and the card returns to its column. A departure from the common path, such as a plan with no design or a skipped step, is never refused and never asks for confirmation.

### §11.5 Live following

A change to a watched file, to its content, creation or deletion, appears on the open page without a reload, within about a second. The watched files are the roadmap, the parked entries, the active design and the active plan with its leaves.

When three consecutive attempts of the page to reach the server fail, the page says the server has stopped and to restart `docdicer kanban` and open the URL it prints, and no drag starts. The page keeps trying; a successful attempt restores the board's live state and drags.

A document that cannot be read as a file while the server runs is named on stderr as `cannot read: <file>`, and the board keeps its last good state until the file reads again.

### §11.6 The board stores nothing

The board keeps no UI state and writes no file, in the project or elsewhere, for itself. Its only writes are the moves of §11.3. A restarted server shows the files as they then are, and nothing else.

### §11.7 What `kanban` does not do

It makes no inference call, runs no subprocess, reads no git history and fetches nothing from the network; every write is a fixed transformation of file content (§11.3). It has no filters, pull-downs, search, sorting or custom drop affordances. The project root is found by looking at the file system (§8.6).
