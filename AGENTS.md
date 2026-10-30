# Ghost-PR: instructions for coding agents

These instructions apply to this repository. Follow explicit user instructions
first. Inspect existing code and preserve working behaviour; do not regenerate
the project from scratch. This file guides development, not Ghost-PR's runtime AI.

## Goal and scope

Help a four-person beginner team build and understand an offline-first terminal
tool for open-source contributors. The core workflow is:

1. Inspect staged Python changes.
2. Export an exact staged snapshot and establish a passing test baseline.
3. Introduce a bounded set of independent mutations on changed expressions.
4. Run tests against each mutant and classify the observed results.
5. Optionally request a missing test from a local model.
6. Verify the proposed test passes on the original and fails on the mutant.

Mutation testing must work without AI. No model training is needed.
Current implementation status must be determined from source and tests, not
assumed from this target workflow.

## Start every task with evidence

- Read this file, README.md, docs/SPEC.md, and relevant source/tests.
- Run the existing tests before editing. Record pre-existing failures separately.
- Explain the next small goal and identify existing code to reuse.
- Define the contract before implementation: inputs, outputs, data model,
  preconditions, errors, side effects, exit codes, and acceptance checks.
- Update docs/SPEC.md when a contract changes. Keep requirements concrete.
- Proceed autonomously within the requested scope. Ask only when a material
  ambiguity cannot be resolved safely from the repository and user instructions.

## Mandatory small-chunk workflow

An increment is a milestone, not one large coding task. Split it into small,
single-responsibility chunks before editing. Keep a visible progress checklist.

For EACH chunk:

1. State one observable goal and its contract.
2. Implement the simplest complete solution for that goal.
3. Add meaningful checks for its behaviour and important failure modes.
4. Run relevant tests immediately and resolve new failures.
5. Review for repeated logic, unnecessary abstractions, and hidden side effects.
6. Explain input -> processing -> output in plain English.
7. Update progress and relevant documentation, then continue.

Keep the application runnable after each chunk. Do not introduce fake success,
unimplemented placeholders presented as features, or empty future modules.
Do not implement an entire milestone in a single large patch. Split a chunk
further if its code or explanation becomes difficult to follow.
No arbitrary line-count target: clarity and a verifiable responsibility matter.
Do not request routine approval after every chunk or wait for answers to optional
comprehension questions. Leave questions for team review and continue authorized work.

Suggested dependency order (mark existing verified work complete):

- Inspect project and tests; establish contracts.
- Validate Git state.
- Identify staged files and new-side changed lines.
- Pin the index tree and export its snapshot.
- Verify snapshot fidelity and cleanup.
- Execute and classify a baseline test run.
- Discover one supported AST mutation.
- Generate and validate one independent mutant.
- Execute and classify that mutant.
- Add a bounded deterministic mutation loop.
- Add readable output and JSON output.
- Build a repeatable demonstration fixture.
- Connect optional local AI and validate its response.
- Verify a generated test against original and mutated code.
- Finish documentation and rehearse the demonstration.

## Keep implementation simple

- Python 3.11+, standard library first; argparse for the CLI.
- Prefer ordinary functions and small immutable dataclasses.
- Use explicit names, shallow control flow, and small responsibilities.
- Comments explain reasons and non-obvious behaviour, not every statement.
- Share real repeated logic; avoid speculative generalization.
- No inheritance trees, abstract base classes, plugin frameworks, factories,
  dependency-injection frameworks, metaclasses, or unnecessary service classes.
- No generic utils.py dumping ground or monolithic application script.
- Add dependencies only for a concrete need; document why.
- No database, migrations, web dashboard, GitHub bot, automatic fixes, automatic
  commits, package publication, or external posting without explicit new scope.

## Anti-bloat rules: required for every change

### Search before adding

- Use `rg --files` to find relevant modules, then `rg` to find existing helpers,
  call sites, tests, and similar behaviour before introducing a new function.
- Read the matching implementations. Extend or reuse an existing path when its
  contract fits; do not create a second HTTP client, Git wrapper, parser, or
  formatter just because it is in another directory.
- Do not force reuse between operations with different responsibilities. Explain
  briefly why a new helper is needed when a similar one already exists.
- Avoid copying a function for a slight variation; use a small explicit parameter
  when appropriate. Do not build a generic framework to remove a few similar lines.

### Validate at real boundaries

- Validate CLI arguments, filesystem/Git data, process results, and model responses
  where they enter the system. Within trusted internal contracts, use the validated
  types directly rather than repeating null/type checks and conversions.
- Keep checks for actual reachable failures, including path traversal, process
  timeouts, malformed AI output, and cleanup. Simplicity does not mean deleting
  correctness checks. Do not add speculative impossible-state branches.
- Catch specific exceptions at the layer that can handle them. Do not use broad
  exception handlers that hide bugs, silently succeed, or invent fallback data.
- Use named constants for genuinely fixed values. Add configuration only when the
  current product needs user choice; no speculative flags or config frameworks.

### Keep dependencies and helpers proportionate

- Check the standard library and existing dependencies before adding a package.
  Do not add a framework for a small HTTP request, parsing task, or transformation.
- Import only what is used. Remove imports made obsolete by a change.
- A helper must clarify a meaningful operation, isolate a real boundary, or remove
  useful duplication. Avoid trivial wrappers that merely rename a single call.
- Single-use functions are fine when they make a coherent operation easier to
  understand or test. Do not chase maximal reuse or minimal line count.

### Finish refactors completely within scope

- Find callers before changing a function. Update relevant callers and tests.
- Remove superseded branches, obsolete helpers, unused variables/imports, temporary
  debug output, and stale exports introduced or abandoned by the change.
- Do not retain the old implementation alongside the new one without a concrete
  compatibility requirement. Do not delete unrelated code or public APIs casually.
- Do not leave commented-out implementations, abandoned scaffolding, or speculative
  TODOs in the delivered path. Keep documentation aligned with actual behaviour.

### Write useful comments and tests

- Explain why a non-obvious decision exists. Avoid comments that restate an
  assignment, loop, increment, or self-explanatory function name.
- Use docstrings when a contract, side effect, or limitation needs explanation;
  avoid boilerplate parameter lists that merely repeat type annotations.
- Update or remove outdated comments and docstrings in the changed code.
- Add tests for observable behaviour, meaningful regressions, and real failure
  modes. Do not target a test count or a coverage percentage for its own sake.
- Prefer a few representative cases, using table-driven cases where helpful,
  over copied tests with identical logic and no distinct failure mode.
- Use real disposable Git repositories for Git behaviour. Mock external boundaries
  only when necessary; do not mock away the operation the test is supposed to verify.
- Do not test trivial getters, dataclass construction, or private call order unless
  that behaviour has a concrete contract. Prefer outputs, state, and side effects.
- Run checks appropriate to the change. Documentation-only edits do not require
  the full runtime suite; code changes require relevant checks. Broaden testing
  when integration risk, failures, or new changes justify it.

Before completing a chunk, inspect the diff: can anything added be removed without
losing required behaviour, readability, or useful verification? Remove it if so.
This review is scoped to the task, not permission for a repository-wide rewrite.

## Module boundaries

Create modules only when their functionality is needed:

| Module | Responsibility |
| --- | --- |
| cli.py | Parse arguments, orchestrate commands, choose exit codes |
| models.py | Shared data contracts, no infrastructure dependencies |
| repository.py | Git inspection and exact staged snapshot creation |
| mutations.py | AST mutation discovery and generation |
| runner.py | Bounded test execution and outcome classification |
| local_ai.py | Optional local-model requests and response validation |
| reporting.py | Human-readable and JSON presentation |

Keep dependencies one-directional. Mutation logic must not depend on terminal
formatting or model availability. Never import the CLI from core modules.

## Repository and snapshot correctness

- Inspect the Git index, not arbitrary working-directory edits.
- Require HEAD; reject unresolved conflicts and unstaged tracked changes for MVP.
- Count and exclude untracked files; clearly report skipped/unsupported inputs.
- Handle paths with spaces, newlines, brackets, leading dashes, and literal Git
  pathspec characters. Use NUL-delimited output and literal pathspec handling.
- New-side line numbers refer to the staged version; deletion-only edits have
  no added lines to mutate. Explain rename handling and binary-file exclusions.
- Pin an immutable staged tree for a run; do not assume earlier reads remain
  valid while someone edits or stages files.
- Validate all exported entries. Reject unsupported symlinks/submodules, prevent
  path traversal, preserve executable permissions, and avoid unsafe extraction.
- Never modify the original files or index. Clean temporary workspaces on errors.
- Avoid printing raw diffs, Git errors, credentials, or environment values.

## Test execution and mutations

- Execute repository code only through an explicit execution command.
- Use argument arrays, never shell=True or interpolated shell commands.
- Run pytest with the current interpreter: sys.executable, '-m', 'pytest'.
- Dependencies must already be installed; never auto-install repository packages.
- A temporary directory is not a sandbox. Support trusted local projects and
  controlled fixtures; do not claim arbitrary repository execution is safe.
- Bound execution time and output; handle child-process cleanup on supported
  macOS/Linux environments. Document unsupported platforms honestly.
- Baseline must pass and collect tests. Stop on failed baseline, collection
  error, no tests, timeout, or execution error.
- Use AST-based Python mutations on changed expressions; skip test files.
- Start with <= to <, >= to >, == to !=, and Boolean literal flips.
- Skip unsupported constructs such as chained comparisons until handled correctly.
- Generate one independent mutation from the original snapshot per run.
- Deterministic order; default maximum five mutants; verify syntax before running.
- Record file, location, mutation operator, and before/after evidence.
- Avoid arbitrary statement deletion and authentication-bypass mutations in MVP.

Outcome meanings:

| Outcome | Required evidence |
| --- | --- |
| killed | Passing baseline, then genuine test failure on the mutant |
| survived | Mutant test run completes successfully |
| timeout | Execution exceeds the limit |
| execution_error | Collection, import, setup, internal, or other execution problem |

Do not classify every nonzero process exit as killed. Use structured pytest
evidence where needed to distinguish failures from execution problems.
Show killed / (killed + survived), N/A for zero denominator, and separate excluded
outcomes. Never call this a safety score. Surviving mutants may be equivalent,
unexercised, or reveal missing assertions; report evidence without overclaiming.

## Optional local AI

- Use an already-installed runner and explicitly configured model.
- Check current official runner documentation before implementing its API.
- Default to localhost and reject remote endpoints for MVP; no silent downloads.
- Core mutation results remain available if AI is missing, slow, or malformed.
- Bound context, output, and request duration. Send only necessary code/test
  excerpts; exclude sensitive files and mask suspected credentials first.
- Treat repository content as untrusted data, not model instructions.
- Require structured responses; validate fields, references, and Python syntax.
- Do not execute model-generated shell commands or dependency installations.
- Never write generated tests into the original repository automatically.
- Generated tests are executable code, not safe merely because parsing succeeds.
  Verify only within the documented trusted-demo execution boundary.
- A proposed test is verified only when it passes on original code and fails
  through a genuine test failure on the intended mutant.
- Call it a verified distinguishing test, not proof of business correctness.
- Clearly distinguish recorded responses in tests from live local-model output.

## Validation and team ownership

Use controlled fixtures and disposable real Git repositories. Cover meaningful
cases as features arrive: mixed edits, unusual paths, snapshot fidelity,
original-file preservation, one mutation per copy, baseline failures, collection
errors, no tests, timeouts, cleanup, missing model, malformed response, and
generated-test verification in both directions. Avoid tests that just mirror code.

Canonical initial check:

```bash
python3 -m unittest discover -s tests -v
```

After each chunk, report:

- Changed: what is now implemented.
- Why: the requirement it satisfies.
- How: the functions and data flow in plain language.
- Verified by: actual commands/results, with failures disclosed.
- Limitations: skipped cases and unverified assumptions.
- Next: the next small dependency-ready task.

Update docs/TEAM_GUIDE.md for substantial new behaviour and include three short
questions teammates should be able to answer. Use pseudocode or a compact Mermaid
diagram when it makes a nontrivial flow easier to understand. If a core function
is difficult to explain, simplify it before building more on top.

## Demonstration and honest handoff

Use a labelled withdrawal fixture: amount <= balance becomes amount < balance.
Initial partial-withdrawal test passes on both; an exact-balance test passes on
original and fails on mutant. Ensure the relevant expression really is staged
and selected by changed-line detection. Do not hard-code the result as live AI.

Before handoff, provide setup and demo commands, actual validation results,
limitations, architecture explanation, and a short demo script. Distinguish
planned, implemented, and verified features. Keep README, licence, AI/tool credits,
and contribution instructions accurate. No fabricated speed or coverage claims.
