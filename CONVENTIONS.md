# CONVENTIONS – docdicer

## Testing

Tests protect logic. A test that fails when only wording or formatting changes is friction, not
protection.

- Every SPEC requirement is tested to hold: if it stopped holding, a test would fail. Test it at
  the lowest level that can observe it — a unit test where a function owns the logic, an
  end-to-end case where only a command's behaviour shows it. Tests are organized by the code they
  exercise, not by SPEC's structure.
- No test asserts message wording. Where a message carries a result (which file a check flagged),
  a test asserts only the values it carries (SPEC preamble). Where messages share a stream and
  their values, a test may name the fault by the one phrase SPEC gives for it.
- Tests are written for pytest: plain `assert`, `@pytest.mark.parametrize` for a rule's table of
  inputs and results, and `tmp_path` instead of a hand-managed directory. A function that takes its
  output stream gets an `io.StringIO`; `capsys` is for output printed to the process streams.
- Expected results are derived from SPEC, never copied from program output.
- A behaviour change lands with the tests that pin it, in the same commit.

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

Plans are committed files, never ignored ones.

- **`ACTIVE_PLAN.md`** in docdicer's root, beside this file, is the one plan under way: decisions
  confirmed at kickoff, work-package boundaries, sequencing and status. Dispatched agents execute
  out of it; status updates as work packages land. It records its base commit at kickoff. Each package
  updates the SPEC.md, ARCHITECTURE.md, CONVENTIONS.md and README.md text its change invalidates,
  in the commit that lands it. The file is deleted when its post-plan burndown lands.
- **`ACTIVE_PLAN_REVIEW.md`** in docdicer's root, beside `ACTIVE_PLAN.md`, holds the post-plan
  review's findings. It is a committed file, like the plan.
- **`ROADMAP_PLANS/`**, also in docdicer's root, holds partly-planned work that is not under way,
  with enough design done that someone could pick it up. A plan leaves when it becomes the active
  plan, is finished, or is abandoned. A plan there cites only tracked paths.
- **SPEC.md outranks a plan on anything the plan does not set out to change.** A package that
  changes behaviour quotes the SPEC text it replaces and the replacement. Any other disagreement
  between a plan line and SPEC is settled by SPEC, and the commit that lands the work names the
  plan line SPEC overrode.
- Working drafts and half-formed notes are scratch, not plans.

### Dispatchability

A work package is dispatchable only when:

- it names its scope in files or symbols, never a span of design sections;
- it carries the command and its answer, or the quoted line, for each fact it acts on;
- a package that changes a function signature, a class or its fields names in its scope every file
  that references it — `git grep -l '<name>' -- '*.py' '*.md'`, tests and docs included — and
  carries that command and its answer;
- it states its stop conditions: the observations, including a carried command whose answer has
  changed, on which the executor stops and reports rather than works around;
- it states its done-line in runner targets;
- it carries its rating (below);
- it has had a usability review by a prompt engineer, and an architect has revised it from those
  findings.

A plan whose packages lack these is not offered for approval, and none of its packages is
dispatched.

### Rating

Every package is rated by what it must decide, not how much it types:

- **mechanical**: the plan's text settles the work — every rule, message and `expected/` file
  content given. Runs on a stepped-down model.
- **expert**: it must choose between defensible options, diagnose behaviour, or write
  model-facing prose. Runs on the coordinator's model.

### Post-plan review

Every activated plan ends with two packages, each with its own ID and row: the post-plan review,
then the post-plan burndown. The pairing is keyed on titles opening `Post-plan review` and
`Post-plan burndown` (SPEC §8.6 Terms); `docdicer check-plan` reports one without the other.

1. An architect and a python-coder review the change since the plan's base commit, tests of all
   touched code included. Their pre-task reading is THESIS.md, SPEC.md, ARCHITECTURE.md and
   CONVENTIONS.md — not the plan: they review against standards and fitness for purpose, not the
   implementation's route.
2. The review's findings go to `ACTIVE_PLAN_REVIEW.md`.
3. The post-plan burndown package is drafted from `ACTIVE_PLAN_REVIEW.md` once the review lands, and
   meets the dispatchability rules above before any item is dispatched.
4. `ACTIVE_PLAN_REVIEW.md` and the plan are deleted together, in the commit that lands the post-plan burndown package.

### Surface audit, every third retired plan

Separate from any sprint, and executing nothing: given only what a user or agent is served — the
CLI's help, README.md and the messages the commands print — review the flows a user follows to do
their work, and report every operation that is missing or inverted, every flow that takes more
commands than its intent, and every step where the obvious command is not the right one.

Lenses, applied to every command and flow:

- **redundant**: another command, or a combination of another's arguments, already does it;
- **over-composed**: it bundles steps a user could run one at a time, with no consistency reason
  to bundle them;
- **over-fine-grained**: it leaves the user to keep files consistent, or to run a step that should
  follow automatically;
- **abstraction inversion**: a simple intent takes a chain of commands instead of one;
- **unnecessary**: no current or foreseeable need calls for it;
- **poorly named**: its name misdescribes what it does, or names a thing differently from its
  siblings.

When a plan is retired, the coordinator runs `git log --diff-filter=D --oneline -- ACTIVE_PLAN.md`;
a count divisible by three makes the audit due. An architect runs it and reports to the user;
adopted findings become a plan in `ROADMAP_PLANS/`.
