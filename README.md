# docdicer

A stdlib-only python 3.9 tool for transforming and viewing project markdown documents to facilitate
AI-assisted development.

Agents reading entire large documents for the fraction they need waste context and attention.
docdicer provides small linked files instead:

- Bidirectional transformation of heavy monolithic markdown documents to and from context-friendly
  file hierarchy
  - Permanent project documents (SPEC, ARCHITECTURE, CONVENTIONS)
  - Working design and plan docs

![An active design as a diced tree](docs/images/doctree.webp)

*The sections of one design as files; the root opens at `entry-point.md`, every directory below it at
its `index.md`*

Agents like document-centric workflows, but humans prefer more visual representations.
docdicer provides a kanban view of roadmap, design, and plan docs to allow each to work in their
preferred manner.

- Checks a roadmap, a plan and a design against the forms the tools read (`check-roadmap`,
  `check-plan`, `check-design`), and the links and structure of a diced tree
- Serves a kanban display of the roadmap, parked designs, active designs and plans

![The kanban board](docs/images/kanban.webp)

*A plan's work packages on the board `docdicer kanban` serves*

docdicer's capabilities are used in its own development.

## Requirements and Supported Platforms

- Python 3.9 or later

Building from a clone additionally needs [`just`](https://github.com/casey/just); the recipes to
build, test and format are [Development](docs/development.md)'s.

## Quick Start

docdicer is primarily used via integration into [devpro](https://github.com/benn-herrera/devpro) and this
is the recommended way to use it.

If you want to try it on its own, it runs from a checkout with a Python plus nothing else, or
installs as the `docdicer` command. The examples below are written for the installed command; from
a checkout they run as `PYTHONPATH=<checkout> python3 -m docdicer <command> ...`, with `<checkout>`
the directory holding the `docdicer` package.

### Install

```bash
pip install --upgrade git+https://github.com/benn-herrera/docdicer
```

`--upgrade` on the first install and on every later one: pip caches a copied repository by its URL,
so a repeat `pip install git+...` without it can reinstall the revision it first took.

pipx runs it in an environment of its own instead:

```bash
pipx install git+https://github.com/benn-herrera/docdicer
pipx upgrade docdicer
```

### Dicing

```bash
docdicer dice-doc design.md design-tree/
docdicer undice design-tree/ rebuilt.md
```

Run them from the directory the document's relative links are written against: a relative link in the
source is resolved against the run directory, and one pointing outside the document is rewritten to
reach the same file from wherever the line lands in the tree. Inside the tree, every link resolves
from the file holding it.

`design-tree/` must be absent or empty, and its way in is `design-tree/entry-point.md`. Document
headings drive the split — `##` and deeper become sections, down to `####` by default — and the
lines above the first one become the entry point's text, whose Contents block lists every section
below it. `undice` writes the tree back out as one document and checks that dicing the result
reproduces the tree.

### Kanban

Run it from within a project directory to see the board:

```bash
docdicer kanban
```

The server prints `http://127.0.0.1:<port>/`. Open that URL; stop the server with Ctrl-C or the
page's stop button.

The board is built from files at fixed paths under the project root:

| File | What the board shows from it |
|---|---|
| [`ROADMAP.md`](docs/kanban.md#columns) | the roadmap's tickets |
| `ROADMAP_DESIGNS/` | parked designs no roadmap ticket links |
| `ACTIVE_DESIGN.md`, else `ACTIVE_DESIGN/entry-point.md` | the active design |
| `ACTIVE_PLAN.md`, else `ACTIVE_PLAN/entry-point.md` | the active plan's work packages |

A project holding none of them shows an empty board. What each file must contain, and what the
board can write, is [The board](docs/kanban.md); again, recommended usage is via devpro, with which
it is closely integrated.

## Commands

`docdicer <command> ...`. `--version` prints the version; `-h`, alone or after a command, prints
help.

| Command | What it does |
|---|---|
| `dice-doc` | Dice one document into a tree of linked files, then run the reassembly and link checks. |
| `undice` | Write a diced tree back out as one document, and check that dicing it reproduces the tree. |
| `dice-docs` | Dice a set of documents into one tree of volumes that link to each other. |
| `verify` | Re-run the reassembly and link checks on built trees. |
| `check-links` | Check relative links and anchors of any markdown files. |
| `check-tree` | Check a diced tree's structure. |
| `check-plan` | Check a plan's status form. |
| `check-design` | Check a design's final form and its delta pairs against their targets. |
| `check-roadmap` | Check `ROADMAP.md`'s ticket layout. |
| `kanban` | Serve a live board of the project's roadmap, design and plan. |

Arguments, options, exit statuses and messages, command by command — exit 2 covers bad arguments,
including a non-empty output directory, an output file that already exists and an unusable
`<map|->`: [docs/commands.md](docs/commands.md).

## Learn more

- [Commands](docs/commands.md) — every command's arguments, options, exit statuses and messages.
- [Dicing](docs/dicing.md) — heading convention, link rewriting and the link map, the manifest.
- [Checks](docs/checks.md) — what reassembly, links, `check-tree` and the plan, design and roadmap
  checks prove.
- [The board](docs/kanban.md) — columns, layout, links, notices, moves, refusals and collapsing.
- [Development](docs/development.md) — build, test, the module map in ARCHITECTURE §2, worked
  example.

## Developer

<https://keyoxide.org/wkd/benn@bennherrera.dev>

## Third Party Acknowledgements

- **pytest** (the pytest developers, MIT): Python test runner
- **black** (Łukasz Langa and contributors, MIT): Python formatter
- **isort** (Timothy Crosley and contributors, MIT): Python import sorter
- **flake8** (Tarek Ziadé, Python Code Quality Authority, MIT): Python linter

The kanban-from-markdown idea is Jason Coleman's (<https://github.com/sangrail>); it is an idea
credit, not a package this project depends on.

