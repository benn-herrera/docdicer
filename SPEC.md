# SPEC – docdicer

Consumer-facing behaviours and outcomes; any implementation that satisfies them is valid.

File names, the files a command writes and their content, exit statuses, the stream each message goes to, and output SPEC gives as a row format (§9.2) are contract. Message wording is not: the messages below give current wording. What is contract is which fault or result each message reports, the values it carries, shown in `<angle brackets>` (a file, a line, a heading, a count), and the remedy it names.

## §1 What docdicer is

docdicer turns large markdown documents into trees of small linked files. It guarantees five outcomes:

- **Navigable.** Every entry point and index lists the files directly below it, so the tree's entry point leads to every file; `check-tree` verifies this (§3, §8.5).
- **Lossless.** Each line of the source appears in exactly one file, unaltered except for link rewriting (§4); this is verified after every dicing (§8.1).
- **Linked.** Cross references in the source (`§N`, `#anchor`, relative paths) resolve in the tree (§4, §8.2, §8.4).
- **Repeatable.** Equal inputs give equal trees and messages. Nothing depends on the clock, the network, or any state outside the named inputs.
- **Non-destructive.** No command modifies a source document.

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
