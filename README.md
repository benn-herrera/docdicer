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

## Requirements

- Python 3.9+

## Quick Start

docdicer is primarily used via integration into [devpro](https://github.com/benn-herrera/devpro) and this
is the recommended way to use it.

If you want to try it on its own, it can be installed via pip or pipx.

### Dicing

```bash
pip install git+https://github.com/benn-herrera/docdicer
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

It has expected file and directory names, making it potentially cranky if your projects don't use
the names it likes. Again, recommended usage is via devpro, with which it is closely integrated.

## Commands

`docdicer <command> ...`. `--version` prints the version; `-h`, alone or after a command, prints
help; exit status is 0 on success, 1 when a check or step fails, 2 on bad arguments.

| Command | What it does |
|---|---|
| `dice-doc` | Dice one document into a tree of linked files, then run the reassembly and link checks. |
| `undice` | Write a diced tree back out as one document, and check that dicing it reproduces the tree. |
| `dice-docs` | Dice a set of documents into one tree of volumes that link to each other. |
| `verify` | Re-run the reassembly and link checks on built trees. |
| `check-links` | Check relative links and anchors of any markdown files. |
| `check-tree` | Check a diced tree's structure. |
| `check-plan` | Check a plan's status form. |
| `check-design` | Check a design's final form. |
| `check-roadmap` | Check `ROADMAP.md`'s ticket layout. |
| `kanban` | Serve a live board of the project's roadmap, design and plan. |

Arguments, options and exit statuses: [docs/commands.md](docs/commands.md).

## Learn more

- [Dicing](docs/dicing.md) — heading convention, head-file names, link rewriting and the link map,
  the manifest.
- [Checks](docs/checks.md) — what reassembly, links, `check-tree` and the plan, design and roadmap
  checks prove.
- [The board](docs/kanban.md) — columns, layout, links, notices, moves, refusals and collapsing.
- [Development](docs/development.md) — build, test, module map, worked example.

## Developer

<https://keyoxide.org/wkd/benn@bennherrera.dev>

## Third Party Acknowledgements

Credit to Jason Coleman (https://github.com/sangrail) for the kanban-from-markdown idea

- **pytest** (the pytest developers, MIT): Python test runner
- **black** (Łukasz Langa and contributors, MIT): Python formatter
- **isort** (Timothy Crosley and contributors, MIT): Python import sorter
- **flake8** (Tarek Ziadé and contributors, Python Code Quality Authority, MIT): Python linter
