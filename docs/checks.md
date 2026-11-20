# Checks

What each check proves, and the form it reads. Two checks follow every dicing — reassembly and
links — run by `dice-doc`, `dice-docs` and `verify`. The `check-*` commands prove a document's
form or a tree's structure without dicing anything. Each command's arguments, exit statuses and
streams: [Commands](commands.md). What the tool is, and how to install it: [README](../README.md).

## Reassembly

The files a dicing writes, in section order, with section links reverted and the entry point's and
each `index.md`'s `Contents:` block dropped, reproduce the monolith's lines with every other link
in its rewritten form. Proves nothing was lost, moved or edited, within the check's own scope:
SPEC §8.1 compares lines and not final newlines, and does not check lines added after a Contents
block.

## Links

Every link in the output except those with an empty target, a target opening with `/` or a URL
scheme must name an existing file from the linking file's directory. Proves the tree and the
cross-document map are consistent; it does not check `#anchor` fragments, which `check-links`
does. The two link checkers print differently: a dicing's link check reports each dead link as
`dead link: <file>:<line> -> <target>` on stderr and summarises `links checked: <N>, dead: <D>` on
stdout, where `check-links` reports `<file>:<line>: <target>: missing file` and
`links checked: <N>, broken: <B>` (see [`check-links`](#check-links)).

## `check-links`

Checks markdown files that need not come from a dicing: each relative link or image outside fenced
code and code spans must name an existing path, resolved from the linking file's directory; one
with a `#fragment` must name a markdown file (the linking file itself, for a bare `#fragment`) with
a heading whose GitHub anchor equals it. Links with a URL scheme and root-absolute `/` links are
skipped. Each broken link prints to stderr `<file>:<line>: <target>: missing file` or
`missing anchor`; the summary `links checked: <N>, broken: <B>` goes to stdout.

The anchor is the heading text lowercased, with every character but letters, digits, spaces, `-`
and `_` dropped and spaces made `-`, all on the heading's plain text (see
[Heading convention](dicing.md#heading-convention)); a repeat in one file takes `-1`, `-2`, … in
order. It is not a leaf's file-name slug. Headings inside fenced code have none.

## `check-tree`

Checks a diced tree's structure, which no link check sees: every document is linked from its
parent, and every document is reachable by links from the root's `entry-point.md`. A directory's
head is its `entry-point.md` where it has one (the root, a diced volume), else its `index.md`; a
document's parent is its directory's head, and a head's parent is the head above it. A leaf that its
index stopped listing fails even where another document, such as the entry point's contents, still
links it. A root without an `entry-point.md` is one problem.

## `check-plan`

Checks that a development plan is in the form a program can read: a status table under `## Status`
whose header cells include `Package` and `State`, matched without regard to case, and a `Rating`
column, also matched without regard to case, and, where the plan has an H1 heading, a
`Release: <version>` line first after it. One stderr line per breach:
`<file>:<line>: <problem>: found <text>; accepted: <form>`, `<text>` the text found in a code span
or `an empty cell`, in the plan's file order — by file, then by line.

| `<problem>` | Reported at |
|---|---|
| `package ID repeated in the status table` | the later row |
| `package ID holds a space` | the row |
| `State cell opens with no state word` | the row |
| `status table has no Rating column` | the header line of the table |
| `Rating cell opens with no rating word` | the row |
| `` `Release:` line is not the first non-blank line after the H1 heading `` | that line |
| `` `Release:` line names no version `` | that line |
| `post-plan review has no post-plan burndown package` | that package's row |
| `post-plan burndown has no post-plan review package` | that package's row |

A State cell opening with none of `drafted`, `dispatchable`, `in progress` or `landed`, lowercase and
as a whole word, is a breach, an empty cell included; so is a Rating cell opening with neither
`mechanical` nor `expert`. A table with no `Rating` column is the one breach reported at the table's
header line rather than at a row: deleting the column to avoid filling it in still breaches. A
package's title is the text after its ID in the heading whose text opens with the ID. A package's
title opening `Post-plan review` is allowed only with one opening `Post-plan burndown`, and the
reverse. The summary `plan checked: <plan>, work packages: <N>, problems: <P>` goes to stdout.

## `check-design`

A design is in its final form, ready to plan from, when its form and its delta pairs both hold.
The form is the ticket layout `check-roadmap` checks (see below) with deltas added: a level-2 heading
whose text is exactly `SPEC delta`, `ARCHITECTURE delta` or `Code delta` — that is their order —
opens a delta that runs to the next heading of level 1 or 2, and an entry is a ticket inside a
delta. A delta with no entries is valid. A design whose form is intact but whose from has moved
since fails the check.

| `<problem>` | Reported at |
|---|---|
| `delta heading misspelled` | the heading, where it equals a delta heading but for case or whitespace |
| `section is not a delta` | any other level-2 heading, `## Drafts` among them |
| `delta heading repeated` | the later heading |
| `delta heading out of order` | the heading, where a delta before it is one the order places after it |
| `design has no delta` | the H1, else line 1 of the design's first file |
| `delta holds content outside an entry` | the first non-blank line inside a delta before its first entry, once per delta |
| `entry heading carries more than one link` | the heading, where its title is not empty once its links are reduced to their text |
| `pair is incomplete` | a pair label that opens no pair |
| `target cannot be read` | the pair's `**As it stands:**` line |
| `from not found` | the pair's `**As it stands:**` line |
| `pair has drifted` | the pair's `**As it stands:**` line, with `--deltas-applied` |
| `pair is conflicting` | the pair's `**As it stands:**` line, with `--deltas-applied` |

Each line is `check-plan`'s form on stderr, in document order, and every layout breach is a breach
of the design form, reported as `check-roadmap` reports it. The first six are separate breaches at
separate lines — a misspelled heading, a stray level-2 heading, a repeated delta heading and one out
of order each print their own line where they stand, such a heading is not a missing delta, and a
delta count is not checked — so one design can print several lines at several places. Whether an
entry's link resolves is `check-links`'s to say.

An entry's pairs are checked where its heading names a file. A heading whose link is a URL, is
empty, is a bare `#fragment`, or carries more than one link gives no target, and an entry without a
target has no pairs and no pair breaches. A pair is an `**As it stands:**` line — outside fenced
code, alone on its line — with the fenced block whose opening line is the next non-blank line after
it, then a `**Becomes:**` line so placed with the fenced block whose opening line is the next
non-blank line after it. A label outside a fenced block whose next non-blank line does not open one
opens no pair, and is a breach; so is a `**Becomes:**` line outside a pair.

With `--deltas-applied` the check is the pairs' instead: each pair is classified by whether its
two passages match in its target — `pending`, `landed`, `drifted`, `conflicting`, or `unreadable`
where the target cannot be read. An addition — a pair whose `from` passage is not empty and whose
`becomes` passage contains it — is never conflicting, and is landed once its `becomes` is present.
A removal — a pair whose `from` passage contains its `becomes` — is conflicting while its `from`
is present, landed only once its `from` is gone. `landed` is the passing state, `pending` the
expected mid-execution state; `drifted`, `conflicting` and `unreadable` are breaches. One stdout
line per pair, in document order, carries its state, and the summary counts them: a pair counted
in no state is unreadable.

A diced design is read in document order, following the links of each head file's last
`Contents:` list.

## `check-roadmap`

Checks that `ROADMAP.md` is in the ticket layout the board reads: a category is a level-2 heading
and its lines; a ticket is a level-3 heading inside a category and its lines, up to the next
heading of level 1 to 3, deeper headings being part of its text; every other line is free. One
stderr line per breach, `check-plan`'s form, in line order:

| `<problem>` | Reported at |
|---|---|
| `ticket outside a category` | a level-3 heading outside any category |
| `list item in the old ticket form` | a line outside any ticket opening in column 0 with a list marker (`-`, `*`, `+`, `1.` or `1)`), a space and `**` |
| `ticket heading names nothing` | a ticket heading whose text, links reduced to their text, is empty |
| `roadmap has no category` | the first level-1 heading, else line 1 |

Fenced code is not read. The summary `roadmap checked: <roadmap>, tickets: <N>, problems: <P>` goes
to stdout. A `ROADMAP.md` in the layout, the second ticket linking a parked file:

```markdown
# ROADMAP

## General

### Cache the link map

Rebuilding it on every run is slow on large trees.

## Later

### Export to HTML

[export-html](ROADMAP_DESIGNS/export-html.md)
```

See also: [The board](kanban.md), which reads the same layout and shows the breaches as notices.
