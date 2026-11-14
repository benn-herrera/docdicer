# Dicing

How a monolith becomes a tree of linked files, and how its links survive the trip. The commands
that do it: [Commands](commands.md). What the checks prove: [Checks](checks.md). The rules behind
this page are [SPEC](../SPEC.md) §3 and §4. What the tool is, and how to install it:
[README](../README.md).

## Heading convention

`#` title, then `##` sections, `###` subsections, `####` sub-subsections; deeper headings and
headings inside fenced code are text. `####` is the deepest split at the default; `--split-level 3`
makes it `###` and `--split-level 2` makes it `##`, deeper headings staying text in their section's
file. A heading's number, title, file name and anchor come from its text with each link reduced to
its text: `### [Plan Status Form](x)` is titled `Plan Status Form`, named and anchored
`plan-status-form`. A heading is numbered when its text opens with digits, then optionally `.digits`
groups, an optional `.`, and a space (`1.`, `2 `, `1.1.1.`). Its number is that prefix without the
trailing `.`; its file is `<number>-<slug>`, or `<number>` where the title leaves no slug; and `§N`,
`§N.M` in prose link to it. Any other heading is named by its slug. A heading with
children becomes a directory with an `index.md`; otherwise one leaf file. Leaves hold exactly the
original lines, heading included. Sibling headings with the same slug would write the same file, so
they are an error and the run fails. Text before the first heading that splits is `entry-point.md`
with a `Contents:` list.

## Head-file names

A tree's root and each diced volume open at `entry-point.md`; every other directory opens at
`index.md`. These names are fixed, not options: a reader moving between projects finds any tree's
way in by them. `dicerlib/heads.py` holds them, and every pass reads them from there. `check-tree`
reports a tree laid out any other way.

## Link rewriting and the map

`§N` links to its file; followed by a backticked name, it goes to the direct child whose title
contains that name. A `§N` right after `SPEC `, `ARCHITECTURE `, `THESIS ` or `CONVENTIONS ` is left
as text (another document's section). A link to a heading of the document itself, `#anchor`, goes to
the file now holding that heading: to the file alone where the heading is the first line of a
non-entry file, else with the heading's anchor within that file, the entry point's own headings
keeping theirs. An anchor that names no heading is left as written, for
`check-links` to report. Relative links to files outside the document are rewritten to resolve from
each leaf. The map is TSV: `<target>\t<new path from the run directory>` points a link to a diced
document at its entry point; `<target>\t<heading>\t<path>` points a link whose following text
quotes that heading, as `, "The walk"`, at the heading's leaf.

## Manifest (`dice-docs`)

Tab separated: `file`, `outdir`, `flags`, `label`; blank lines and lines starting `#` are skipped.
Flags (comma list, may be empty): `entry`, the only flag (the file is copied verbatim to
`<outdir>/entry-point.md` with a `Volumes:` list of the volumes directly under `<outdir>`, each
with the first sentence of its opening paragraph, as plain text; it is not diced). A volume nested
as `<parent>/<group>/<name>` takes the group's title in `label`; the group gets an `index.md`, each
of its volumes listed by the plain text of its document's title, and the parent's entry point gains
a line for it (SPEC §7.1). Parents precede children. Documents link to each other by `file` as
written in the manifest; the `entry` document by its base name.

A manifest in use: [Worked example](development.md#worked-example).
