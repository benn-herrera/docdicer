# Development

Build and test docdicer, and where its code lives. The contract is [THESIS](../THESIS.md),
[SPEC](../SPEC.md), [ARCHITECTURE](../ARCHITECTURE.md) and [CONVENTIONS](../CONVENTIONS.md) at the
repository root. This page is the one page SPEC does not contract: what follows on building,
testing and the code's layout is ARCHITECTURE §1, §2 and the `justfile`, and none of it is a
consumer-facing behavior. What the tool is, and how to install it: [README](../README.md).

## Build and test

The recipes need `just` (a `justfile` target runs each step) and Python 3.9 or later. From the
repository root:

```sh
just test
```

`just test` creates `.venv` on first use, then runs one pytest test per golden case under
`docdicer/test/data/`, one `undice` round trip per case that dices without a map and succeeds, and
the per-module unit tests. `just build` builds a wheel into `dist/`. `just format` runs black, isort
and flake8 over `docdicer`.

The `dev-*` recipes run the checkout's own code without installing it, so a change can be tried as
it stands:

```sh
just dev-dd dice-doc design.md design-tree/   # PYTHONPATH=<checkout> python3 -m docdicer <args>
just dev-check-links                          # check-links over *.md and docs
just dev-kanban                               # serve the board of this repository
```

`just dev-check-plan`, `just dev-check-design` and `just dev-check-roadmap` are the same for the
three plan, design and roadmap checks. `just dev-dd` with no arguments prints the `docdicer` help.

## Module map

[ARCHITECTURE §2](../ARCHITECTURE.md) maps both packages module by module — `dicerlib/` for the
dicing and its checks, `kanban/` for the roadmap, plan and design reader, the three `check-*`
commands, the board and its server — and states each module's responsibility. It is the one copy
of that map; this page keeps none.

## Worked example

kbase's `PROJECT_DOCS/` was produced from `v0.9.0`, the last revision whose repository root held
both scoring schemes: a checkout of that tag, its documents' sections already in headings, diced in
place through kbase's own `dice-docs` justfile target with this manifest (tab separated), its
`dice-docs` target running the command shown beneath it.

| file | outdir | flags | label |
|---|---|---|---|
| THESIS.md | PROJECT_DOCS | entry | |
| SPEC.md | PROJECT_DOCS/SPEC | | |
| ARCHITECTURE.md | PROJECT_DOCS/ARCHITECTURE | | |
| CONVENTIONS.md | PROJECT_DOCS/CONVENTIONS | | |
| RIGOR_AND_BEARING_SCORING_SCHEME.md | PROJECT_DOCS/SPEC/scoring/rigor-and-bearing | | Scoring schemes |
| STRENGTH_SCORING_SCHEME.md | PROJECT_DOCS/SPEC/scoring/strength | | |

```sh
dice-docs kbase-docs.tsv <src-dir> <work-dir>
```

From `v0.10.0` the leaves under `PROJECT_DOCS/` are the source; the root `SPEC.md`,
`ARCHITECTURE.md`, `CONVENTIONS.md` and `THESIS.md` are pointers to them.

See also: [Dicing](dicing.md) for the manifest, [Commands](commands.md) for `dice-docs`.
