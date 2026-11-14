# The board

`kanban` serves a live board of a project's development-process files for the user to browse. How to
run it: [Commands: `kanban`](commands.md#kanban). The documents it reads are checked by
`check-roadmap`, `check-plan` and `check-design`; their forms are in [Checks](checks.md), and a
document holding breaches is shown all the same, its breaches as [notices](#notices). The rules
behind this page are [SPEC](../SPEC.md) §11 and [ARCHITECTURE](../ARCHITECTURE.md) §5. What the tool
is, and how to install it: [README](../README.md).

## Running

`docdicer kanban` prints `http://127.0.0.1:<port>/` on stdout; open that URL in a browser and stop
the server with Ctrl-C or the page's stop button (exit 0), which asks no confirmation and ends the
page's polling. The server answers only requests naming its own host. `<project-dir>` is any
directory inside the project, the project being the nearest directory at or above it that holds a
`.git` entry; without it the project is the one the current directory is in. The
page follows edits to the files without a reload; a collapse is never written to a file. Its
connection indicator shows the server's docdicer version as hover text. Exit 2 on a directory that
does not exist, no project root, an unreadable file at start, or a port that cannot be bound.

## Columns

- **Roadmap**: `ROADMAP.md`'s tickets, and each piece of parked work in `ROADMAP_DESIGNS/` that no
  roadmap ticket links, unless its link ticket is in the active design.
- **Design**: the active design's tickets.
- **Drafted, Dispatchable, In progress, Landed**: from the active plan's status table.

### Parked work

Parked work is a `.md` file in `ROADMAP_DESIGNS/` other than `README.md`, or a subdirectory there
holding its own `entry-point.md`; its parked name is the file name without `.md`, or the directory
name. Pieces group by topic: `<topic>_DESIGN`, `<topic>_PLAN` and `<topic>_PLAN_REVIEW` make a
topic, and every parked name that is `<topic>` or opens with `<topic>_` joins it, the longest topic
where it fits more than one. Each piece shows as one parked card, titled by its parked name (a
grouped piece's is its topic), under a `ROADMAP_DESIGNS` band.

### Link tickets

A link ticket is a design ticket outside the deltas that stands for a piece of parked work: its
heading, a link to each of the piece's files, and `complete and update this design`. Where one is in
Design, the piece shows there as a card, not in Roadmap; a link ticket dropped on Roadmap is removed
and the parked card shows in Roadmap again.

## Layout

Both documents are read in the ticket layout `check-roadmap` checks — see
[Checks: `check-roadmap`](checks.md#check-roadmap). Each category is a separator band and each
ticket a movable card titled over its text; in Design, the tickets of a `SPEC delta`,
`ARCHITECTURE delta` or `Code delta` category (see [Checks: `check-design`](checks.md#check-design))
are entry cards, which cannot be dragged.

## Links

Each card's title links to the file and heading it shows, opening in a new tab; a parked card links
each of its files, and a link ticket's card its heading and each of those files. A package card
links the heading its title is read from, an untitled one its status row's file. The server serves
exactly the files the board reads, read-only; each response is `no-store` and `nosniff`, and the
pages and markdown also carry a Content-Security-Policy (ARCHITECTURE §5, **Headers.**).

## Collapsing

Double-clicking a separator band — a Roadmap category, a Design category or delta, or the
`ROADMAP_DESIGNS` band — hides the cards from it to the next band or the column's end, and doing
so again shows them; the band stays, its `▾` becoming `▸` while collapsed. Tab reaches a band,
which then shows a focus ring; Enter or Space toggles it, and focus stays on the band, so the next
Enter toggles it again. A card that arrives under a collapsed band, by an edit or a drop, stays hidden
until the band expands. A collapse lasts only while the page is open: edits and drops leave it in
place, and a reload starts with every band expanded.

## Notices

Each breach `check-roadmap` would report in `ROADMAP.md`, and each layout breach in the design,
shows as a notice at the head of its column. Lines above the first category, and a category's lines
before its first ticket, are not shown and raise no notice.

## Moves

The page's only writes are the moves made by dropping a card: a ticket's, its lines carried as
written but for relative links, which are rebased to resolve from the file the ticket joins, between
`ROADMAP.md` and the active design, a single file or a diced tree, after which it is in exactly one
of the two; a parked card's link ticket added to the design; a link ticket removed.

A `#anchor` link stays as written, so it breaks if its heading is not carried or its anchor changes
in the file joined; `check-links` reports it. The board does not reorder tickets, move one between
categories of a document, or edit any ticket's or category's text. A move creates an absent
`ACTIVE_DESIGN.md` or `ROADMAP.md`, and the page then shows a move message naming the files written;
a card that lands under a collapsed band stays hidden (see [Collapsing](#collapsing)).

- **Roadmap to Design.** A Roadmap card dropped on Design goes to the end of the design's
  `## Drafts` category (added where there is none). In a diced design, where `## Drafts` opens an
  `index.md` the ticket becomes a new leaf beside it; where there is no `## Drafts`, a new leaf in a
  `drafts/` directory beside `entry-point.md`, with its own `index.md`; where `## Drafts` is
  elsewhere in the tree, the ticket is added in the file holding it. A new leaf is listed in the
  Contents blocks that list its directory.
- **Parked to Design.** A parked card dropped on Design adds its link ticket to `## Drafts` the same
  way, a new leaf in a diced design too, touching neither the parked work nor `ROADMAP.md`.
- **Design to Roadmap.** A movable Design card dropped on Roadmap goes to the end of the category
  whose band is nearest above the drop, else the first (`## General` where `ROADMAP.md` has no
  category). A link ticket dropped there is removed and nothing is added. In a diced design, a leaf
  holding only the ticket is deleted, and its lines in the Contents blocks removed.
- A ticket moved to `## Drafts` fails `check-design` until the design reaches its final form.

## Refusals

A move is refused, and nothing written, if a file changed since the board read it, the card is no
longer on the board, a document it reads is unreadable (`cannot read: <file>`), or an entry card or
separator is dropped on Roadmap. In a diced design, it is also refused where a new leaf's title
gives no file name, a file the move would create exists, a leaf to delete is missing from its
directory's Contents block, or a ticket's text runs on into the next file; a ticket whose title
holds `]` moved into a diced design cannot move back, its leaf having no Contents line. A write that
fails is reported as `cannot write: <file>` with the files already written: the addition is written
before the removal, so the ticket ends in both documents, never neither.

## Plan columns

The plan columns are read-only, drawn as outlined boxes of flat cards against the filled, draggable
Roadmap and Design cards. A work package's state changes by editing the plan, and the board shows
the edit.
