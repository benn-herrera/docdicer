# Checks

What each check proves, and the form it reads. Two checks follow every dicing — reassembly and
links — run by `dice-doc`, `dice-docs` and `verify`. The `check-*` commands prove a document's
form or a tree's structure without dicing anything. Each command's arguments, messages and exit
statuses: [Commands](commands.md). What the tool is, and how to install it: [README](../README.md).

## Reassembly

The files a dicing writes, in section order, with section links reverted and the entry point's and
each `index.md`'s `Contents:` block dropped, reproduce the monolith's lines exactly (outside links
are compared in their rewritten form). Proves nothing was lost, moved or edited.

## Links

Every link in the output, root-absolute `/` links and links with a URL scheme skipped, resolves to
an existing file from the linking file's directory. Proves the tree and the cross-document map are
consistent; it does not check `#anchor` fragments, which `check-links` does.

## `check-links`

Checks markdown files that need not come from a dicing: each relative link or image outside fenced
code and code spans must name an existing path, resolved from the linking file's directory; one
with a `#fragment` must name a markdown file (the linking file itself, for a bare `#fragment`) with
a heading whose GitHub anchor equals it. Links with a URL scheme and root-absolute `/` links are
skipped.

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
links it.

## `check-plan`

Checks that a development plan is in the form a program can read: a status table under `## Status`
whose `Package` and `State` columns hold unique IDs without spaces and states opening with
`dispatchable`, `in progress` or `landed` (an empty cell is a drafted package), and a `Rating`
column whose cells open `mechanical` or `expert`, and a `Release: <version>` line, where present,
first after the H1 heading. A package's title is the text after its ID in its heading. A package
whose title opens `Post-plan review` is allowed only with one whose title opens
`Post-plan burndown`, and the reverse.

## `check-design`

A design is in its final form, ready to plan from, when it holds one to three level-2 delta
sections headed exactly `SPEC delta`, `ARCHITECTURE delta` and `Code delta`, each at most once and
in that order, and no other level-2 heading. The design is read in the ticket layout
`check-roadmap` checks, each of its breaches a breach of the design: a delta is a category, and
its entries are its tickets; a delta with no entries is valid, but a line before its first entry
is not. Lines outside a delta are free except a level-2 heading and what the layout does not
admit. Whether an entry's link resolves is `check-links`'s to say.

A diced design is read in document order, following the links of each head file's last
`Contents:` list.

## `check-roadmap`

Checks that `ROADMAP.md` is in the ticket layout the board reads: a category is a level-2 heading
and its lines; a ticket is a level-3 heading inside a category and its lines, up to the next
heading of level 1 to 3, deeper headings being part of its text; every other line is free. A
level-3 heading outside any category, a ticket heading whose text, links reduced to their text, is
empty, a roadmap with no category, and a line outside any ticket opening in column 0 with a list
marker (`-`, `*`, `+`, `1.` or `1)`), a space and `**` (the old ticket form) are breaches. Fenced
code is not read.

A `ROADMAP.md` in the layout, the second ticket linking a parked file:

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
