# Development

Build and test docdicer, and where its code lives. The contract is [THESIS](../THESIS.md),
[SPEC](../SPEC.md), [ARCHITECTURE](../ARCHITECTURE.md) and [CONVENTIONS](../CONVENTIONS.md) at the
repository root; ARCHITECTURE §2 maps the packages module by module. What the tool is, and how to
install it: [README](../README.md).

## Build and test

The recipes need `just` and Python 3.9 or later. From the repository root, run docdicer with the
root on `PYTHONPATH`:

```sh
PYTHONPATH=. python3 -m docdicer dice-doc design.md design-tree/
```

`just test` runs one pytest test per golden case under `docdicer/test/data/`, one `undice` round
trip per case that dices without a map and succeeds, and the per-module unit tests. `just build`
builds a wheel into `dist/`. `just format` runs black, isort and flake8 over `docdicer`.

## Module map

The roadmap, plan and design reader, `check-roadmap`, `check-plan`, `check-design`, the board model
and its server live in `kanban/`; ARCHITECTURE §2 maps both packages module by module. The passes
behind the dicing commands live in `dicerlib/`, one module each: `outline` (headings to files),
`anchors` (GitHub heading anchors), `split` (writing the tree), `linkrewrite` (section links,
rebasing, the map), `reassemble` and `linkcheck` (the checks, `check-links` included), `treecheck`
(`check-tree`), `dicedoc` and `manifest` (the drivers), with `heads` (head-file names), `textfile`
(file I/O and fenced code) and `linkscan` (the one line scanner, the reducer of links to their text
and the collector of link targets) beneath them all.

## Worked example

kbase's `PROJECT_DOCS/` was produced from `v0.9.0`, the last revision whose repository root held
both scoring schemes: a checkout of that tag, its documents' sections already in headings, diced in
place through kbase's own `dice-docs` justfile target with this manifest (tab separated).

| file | outdir | flags | label |
|---|---|---|---|
| THESIS.md | PROJECT_DOCS | entry | |
| SPEC.md | PROJECT_DOCS/SPEC | | |
| ARCHITECTURE.md | PROJECT_DOCS/ARCHITECTURE | | |
| CONVENTIONS.md | PROJECT_DOCS/CONVENTIONS | | |
| RIGOR_AND_BEARING_SCORING_SCHEME.md | PROJECT_DOCS/SPEC/scoring/rigor-and-bearing | | Scoring schemes |
| STRENGTH_SCORING_SCHEME.md | PROJECT_DOCS/SPEC/scoring/strength | | |

```sh
just dice-docs kbase-docs.tsv <src-dir> <work-dir>
```

From `v0.10.0` the leaves under `PROJECT_DOCS/` are the source; the root `SPEC.md`,
`ARCHITECTURE.md`, `CONVENTIONS.md` and `THESIS.md` are pointers to them.

See also: [Dicing](dicing.md) for the manifest's columns, [Commands](commands.md) for `dice-docs`.
