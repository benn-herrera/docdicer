# CONVENTIONS – docdicer

Project-specific process and house rules

Must-see:

- No user-facing behaviors or outcomes are designed here — that belongs to SPEC
- No project mechanisms or code structure are put forth — that belongs to ARCHITECTURE

## Dependencies

- Shipped code (`docdicer/` outside `docdicer/test/`) uses the standard library only and runs on
  Python 3.9 and later.
- Test code is idiomatic pytest on the same minimum Python. Test and development code use only the
  dev tools on `justfile`'s `_venv` install line; adding one to that line is an owner decision:
  propose it, don't add it.

## Document size

- A plan or project document (THESIS, SPEC, ARCHITECTURE, CONVENTIONS, ACTIVE_PLAN.md) that grows
  past 800 lines is diced with docdicer, in two commits: the change that takes it past 800 lines is
  committed as is; a separate commit dices it, removes the monolith, and updates every link to the
  monolith to point into the tree. From then on the tree is the source; `undice` gives a monolith
  for whole-document work, which is diced again after.

## Plan & Execute

edit gate: `just test`

checkpoint gate: `just format`, then `just test`

## Periodic review

For this project the periodic multi-sprint review includes an audit of the MCP/CLI surfaces
for usability, consistency within domain, un-surprising-ness.
