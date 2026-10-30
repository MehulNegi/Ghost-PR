# Ghost-PR

Check staged Python changes. Test your tests. Keep the evidence local.

Ghost-PR exports an exact staged snapshot, runs a pytest baseline, and tests up
to five independent AST mutations on changed expressions. Optional local Ollama
can propose a test for the first surviving mutant; Ghost-PR verifies that proposal
against original and mutant copies. Mutation testing works without AI.

**Implemented and checked:** inspection, snapshot fidelity, bounded execution,
mutation discovery/generation, terminal/JSON reporting, and proposed-test
verification using recorded test fixtures. **Live example:** the team reports a
successful qwen2.5-coder:3b distinguishing-test run in macOS Terminal; see
[the observed result and its limits](docs/DEMO.md). This is not a general model
reliability claim. Recorded responses are used only in automated tests.

## Setup

Use Python 3.11+ and Git. Test execution supports macOS/Linux; Windows is
unsupported. The latest validation used macOS, Python 3.14 and pytest 9.1.1;
Linux and other Python versions have not been exercised here.

From this repository's root, manually prepare a development environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m unittest discover -s tests -v
```

The `test` extra supplies pytest. Ghost-PR itself uses the standard library and
Git; it never installs project dependencies or models. Target dependencies must
already be available to the interpreter running Ghost-PR. Avoid editable target
installations that redirect imports to the original working directory.

## Commands

```bash
ghost check --repo /absolute/path/to/repo
ghost check --repo /absolute/path/to/repo --json
ghost run --repo /absolute/path/to/trusted/repo --test tests/test_example.py
ghost run --repo /absolute/path/to/trusted/repo --test tests --timeout 10 --max-mutants 5 --json
```

`python -m ghost_pr` is equivalent to `ghost`. Repeat `--test` for multiple
relative paths; pytest `::test_name` selectors are supported. Options, absolute
paths and parent traversal are refused as test values.

`check` executes no project code. The target needs an existing HEAD, no conflicts,
and no unstaged tracked changes. Stage intended changes yourself. Untracked
files are counted and excluded; ignored files are excluded. Deleted and non-Python
files are reported as skipped. Renames become deletion plus addition.

`run` explicitly executes trusted code in disposable directories, **not security
sandboxes**. It rejects symlinks/submodules anywhere in the exported tree. Git
blobs preserve staged bytes and executable bits without copying working files.
Pinning uses a temporary index copy; original files and index bytes stay unchanged.
Immutable Git tree objects may be added. Do not edit/stage concurrently during
initial capture; later edits do not change the pinned run.

## Reading results

A baseline must pass and execute tests before any mutation runs. Failures,
collection/setup/teardown errors, timeouts, and empty or entirely skipped runs
block analysis. Each mutant starts from the original snapshot in a fresh copy.

| Outcome | Evidence |
| --- | --- |
| killed | Actual test-call failure after a passing baseline |
| survived | Tests complete successfully |
| timeout | Execution exceeds the configured limit |
| execution_error | Import, collection, fixture, internal or other execution problem |

The detection ratio is `killed / (killed + survived)`, or N/A (JSON null).
Timeouts/errors are shown separately. It is not a safety score; survivors may be
equivalent, unexercised, or expose missing assertions.

| Exit | Meaning |
| --- | --- |
| 0 | Successful inspection, or completed analysis without survivors |
| 1 | Completed analysis with survivors |
| 2 | Invalid input, repository/snapshot failure, blocked baseline, mutant timeout/error |

Exit 2 takes precedence over survivors. AI unavailability or an unverified
proposal does not change core exit status. A verified proposal also does not
change the original survivor count: the new test has not been adopted.

## Repeatable withdrawal demo

Run from the Ghost-PR root with the environment above activated. Setup refuses
an existing destination. It creates an empty initial commit **only in this new
fixture**, then stages the demonstration source and tests. Ghost-PR commands do
not create commits.

```bash
GHOST_DEMO_DIR="$(mktemp -d)/withdrawal"
python examples/create_demo.py "$GHOST_DEMO_DIR"
ghost check --repo "$GHOST_DEMO_DIR"
ghost run --repo "$GHOST_DEMO_DIR" --test test_bank.py
```

Expect baseline passed, one `<= to <` survivor, exit **1**. This is expected,
so do not place the demo commands in a shell script using `set -e`.
The test checks `withdraw(100, 40) == 60`; it never exercises equality.

Optionally try real local AI now, before adding the manual boundary test below.
Then demonstrate the missing assertion explicitly:

```bash
cat examples/exact_balance_test.txt >> "$GHOST_DEMO_DIR/test_bank.py"
git -C "$GHOST_DEMO_DIR" add -- test_bank.py
ghost run --repo "$GHOST_DEMO_DIR" --test test_bank.py --json
```

Expect baseline passed with two tests, one killed mutant, detection ratio 1.0,
and exit **0**. `withdraw(100, 100) == 0` passes on original and fails on mutant.
The text file is clearly manual example material, not a model response.

## Optional local AI

Use an already-installed Ollama and downloaded **local GGUF** model. Configure
its server for local-only operation (`OLLAMA_NO_CLOUD=1 ollama serve` in another
terminal; restart an existing server with that setting if necessary). Use
`ollama list` to find the exact installed name; replace the placeholder below.
No runner or model will be installed by Ghost-PR.

```bash
ghost run --repo "$GHOST_DEMO_DIR" --test test_bank.py \
  --ai-model 'EXACT_INSTALLED_NAME' --ai-endpoint http://127.0.0.1:11434 \
  --json --show-ai-test
```

Use a fresh fixture if the manual boundary test has already killed the mutant.
`--ai-model` opts into requesting and executing proposed Python in disposable
copies of a trusted project. The default omits code and explanation from output;
`--show-ai-test` explicitly reveals a validated proposal for review. Nothing is
written into the contributor's repository, and generated files are removed.

Only a proposal that passes on original and produces a genuine test failure on
mutant is labelled `verified_distinguishing_test`. Other outcomes are unverified
with observed results. Verification demonstrates a distinction, not intended
business requirements. Missing models, malformed responses and screened context
leave core mutation results available.

The adapter follows official [chat](https://docs.ollama.com/api/chat),
[model-list](https://docs.ollama.com/api/tags) and
[local-only server settings](https://docs.ollama.com/faq). It accepts only HTTP
loopback endpoints, no redirects/proxies, checks installed model metadata, and
uses bounded context/response sizes and 30-second socket timeouts. Authentication
and secret screening are conservative heuristics, not complete detectors. A
separately managed localhost server must actually be configured to run locally.

## Limits and debugging

- Operators: `<=` to `<`, `>=` to `>`, `==` to `!=`, Boolean flips. Tests, chained
  comparisons, unsupported expressions and sensitive/authentication cues are skipped.
- AST unparsing changes formatting/comments; each mutant is syntax checked.
- Pytest plugin autoload, ambient `PYTEST_PLUGINS`, and configured `addopts` are
  disabled. Explicit project plugin configuration may still run. Integration-heavy
  projects may need additional support; check the baseline first.
- Process groups are killed on completion/timeout. Detached processes that escape
  their group are unsupported. Dependencies can have external side effects;
  disposable directories do not isolate them or protect environment credentials.
- Proposed tests support one undecorated, zero-argument test plus imports. AI uses
  only the first survivor, its enclosing function and small test excerpts.
- Output contains counts and mutation evidence, not raw pytest/Git logs. To debug
  a controlled fixture, run `python -m pytest test_bank.py -v` in that fixture and
  compare the reported before/after expression. Temporary run copies are not kept.
- Large repositories are not optimized: export reads one Git blob per subprocess.
  There are no whitespace checks, comprehensive secret scans or PR drafting.

## Understand and contribute

`cli.py` orchestrates; `repository.py` inspects/pins/exports; `mutations.py`
discovers and generates; `runner.py` manages processes; `pytest_evidence.py`
records pytest phases; `local_ai.py` screens and requests proposals;
`reporting.py` presents results; `models.py` holds immutable data.

Read [the contract and checklist](docs/SPEC.md),
[the team walkthrough](docs/TEAM_GUIDE.md) and [the demo script](docs/DEMO.md).
Define each small contract, test meaningful failure modes, and explain the data
flow before extending it. No database, dashboard, GitHub writes, automatic fixes,
or automatic commits belong in the tool.

## Credits and licence

Developed with OpenAI Codex in collaboration with the team. Runtime uses Python's
standard library, Git and installed pytest for target execution. Optional local
inference uses the user's Ollama installation and chosen model; model licences
remain their own. No model weights or external application templates are bundled.
The team must review and understand generated code. MIT; see [LICENSE](LICENSE).
