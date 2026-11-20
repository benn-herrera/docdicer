# CONVENTIONS – docdicer

Project-specific process and house rules

Must-see:

- No user-facing behaviors and outcomes are designed here — that belongs to SPEC
- No project mechanisms or code structure are put forth — that belongs to ARCHITECTURE

## Dependencies

- Shipped code adds no dependency: the standard library only.
- Test code is idiomatic pytest. Test and development code use only the dev tools on `justfile`'s
  `_venv` install line; adding one to that line is an owner decision: propose it, don't add it.
- Shipped code uses only APIs its floor provides; the test suite runs on the oldest interpreter the
  project builds with. Types are declared in the form Python 3.9 evaluates: `Optional[X]`, `list[X]`,
  `dict[K, V]`; no `from __future__ import annotations`.

## Document size

- A plan or project document (THESIS.md, SPEC.md, ARCHITECTURE.md, CONVENTIONS.md, ACTIVE_PLAN.md)
  that grows past 800 lines is diced with docdicer, in two commits: the change that takes it past
  800 lines is committed as is; a separate commit dices it, removes the monolith, and updates every
  link to the monolith to point into the tree. From then on the tree is the source; `undice` gives a
  monolith for whole-document work, which is diced again after.

## Plan & Execute

edit gate: `just test`

checkpoint gate: `just format`, then `just test`

## Periodic review

For this project the periodic review audits the CLI and the board's page for usability, consistency
within domain, un-surprising-ness. Each review's plan closes the audit with one row per audited
surface in its status table, carrying the date the audit ran.
