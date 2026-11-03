# CONVENTIONS – docdicer

## Testing

Tests protect logic. A test that fails when only wording or formatting changes is friction, not
protection.

- Each rule SPEC states about a function's result gets a unit test against the function that owns
  it, so a failure names the rule and where it lives. Rules about a command's exit status and the
  files it writes are covered by end-to-end cases.
- No test asserts message wording. Where a message carries a result (which file a check flagged),
  a test asserts only the values it carries (SPEC preamble).
- Tests are written for pytest: plain `assert`, `@pytest.mark.parametrize` for a rule's table of
  inputs and results, and fixtures (`tmp_path`, `capsys`) instead of hand-managed directories and
  streams.
- Expected results are derived from SPEC, never copied from program output.
- A behaviour change lands with the tests that pin it, in the same commit.

## Plan & Execute

Plans are committed files, never ignored ones.

- **`ACTIVE_PLAN.md`** in docdicer's root, beside this file, is the one plan under way: decisions
  confirmed at kickoff, work-package boundaries, sequencing and status. Dispatched agents execute
  out of it; status updates as work packages land. It records its base commit at kickoff. Each package
  updates the SPEC.md, ARCHITECTURE.md, CONVENTIONS.md and README.md text its change invalidates,
  in the commit that lands it. The file is deleted when its post-sprint burndown lands.
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

### Post-sprint review

Every activated plan ends with this review:

1. An architect and a python-coder review the change since the plan's base commit, tests of all
   touched code included. Their pre-task reading is THESIS.md, SPEC.md, ARCHITECTURE.md and
   CONVENTIONS.md — not the plan: they review against standards and fitness for purpose, not the
   implementation's route.
2. Findings go to `ACTIVE_PLAN_REVIEW_BURNDOWN.md`, which meets the dispatchability rules above
   before any item is dispatched.
3. The burndown file is deleted with the plan.

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
