# 👻 Ghost-PR

**Scan your changes. Haunt your tests.**

A local CLI for open-source contributors: catch staged whitespace mistakes and suspected secrets, then check whether your tests detect small changes to your Python code. When a mutation survives, an optional local model proposes a test—and Ghost-PR verifies it before you export it.

**Your code stays yours.** No GitHub bot, automatic fixes, model downloads, staging, or commits. Mutation testing works without AI.

[Quick start](#quick-start) · [Try the demo](#try-the-demo) · [Commands](#commands) · [Reading-results](#reading-results) · [Limits](#limits-and-execution-boundaries)

## Why test your tests?

A passing test can miss an important boundary:

```python
# Existing test: passes with both <= and <
assert withdraw(100, 40) == 60

# Boundary test: detects the difference
assert withdraw(100, 100) == 0
```

Ghost-PR deliberately changes `amount <= balance` to `amount < balance` in a temporary copy. If your existing tests still pass, the mutation **survives**. A new test is a **verified distinguishing test** only if it passes on the original and fails on the mutant.

| Command | Purpose | Executes project code? |
| --- | --- | --- |
| `ghost scan` | Inspect staged scope, whitespace, and suspected credentials | No |
| `ghost haunt --test tests` | Run a baseline and independent AST mutations | Yes |
| `ghost haunt --test tests --ai` | Also propose and verify a test for the first survivor | Yes, including proposed Python |

## Quick start

**Requirements:** Python 3.11+, Git, and macOS/Linux for test execution. Windows is unsupported. Development validation has used macOS; Linux and other Python versions are not established by that evidence.

```bash
git clone https://github.com/MehulNegi/Ghost-PR.git
cd Ghost-PR

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'

ghost --help
python -m unittest discover -s tests -v
```

The `test` extra installs pytest. Ghost-PR uses the current Python interpreter: target-project dependencies must also be installed in that environment. It never installs them for you. Avoid editable target installations that redirect imports to the original working directory.

Inside a trusted target repository:

```bash
git add -- path/to/changed_file.py
ghost scan
ghost haunt --test tests
```

The repository needs an existing commit, no conflicts, and no unstaged tracked changes. Untracked and ignored files are excluded from the snapshot. A clean clone has no staged changes to mutate.

> **Execution boundary:** Haunt runs tests and optional generated Python in disposable directories. Those directories are **not security sandboxes**. Use trusted projects; dependencies and tests can have external side effects.

## Try the demo

Run from the Ghost-PR root with its environment active. Keep the same terminal session so the demo variable remains set.

### 1. See a mutation your existing test misses

```bash
export GHOST_DEMO_DIR="$(mktemp -d)/withdrawal"
python examples/create_demo.py "$GHOST_DEMO_DIR"

ghost scan --repo "$GHOST_DEMO_DIR"
ghost haunt --repo "$GHOST_DEMO_DIR" --test test_bank.py --max-mutants 1
```

The fixture creates an empty initial commit in a new temporary repository, then stages its source and test. It refuses an existing destination.

Expected: **one passing baseline test, one surviving mutation, exit 1**. The initial test covers a partial withdrawal, not withdrawing the entire balance. Exit 1 is expected here; do not run this sequence under a shell's `set -e`.

### 2. Option A: demonstrate the missing test without AI

```bash
cat examples/exact_balance_test.txt >> "$GHOST_DEMO_DIR/test_bank.py"
git -C "$GHOST_DEMO_DIR" add -- test_bank.py

ghost haunt --repo "$GHOST_DEMO_DIR" --test test_bank.py --max-mutants 1
```

Expected: **two passing baseline tests, one killed mutant, exit 0**. This is a prepared example test, not AI generation.

### 3. Option B: generate, verify, and export with local AI

Install [Ollama](https://ollama.com/) separately. Check installed models before manually downloading the default:

```bash
ollama list
# Run only if this exact model is missing:
ollama pull gemma4:e2b-it-q4_K_M
```

For local-only operation, configure the Ollama server with `OLLAMA_NO_CLOUD=1`. If using `ollama serve`, stop any existing server first, then start this in another terminal:

```bash
OLLAMA_NO_CLOUD=1 ollama serve
```

Create a **fresh fixture** so the manual boundary test from Option A is absent:

```bash
export GHOST_DEMO_DIR="$(mktemp -d)/withdrawal"
python examples/create_demo.py "$GHOST_DEMO_DIR"

ghost haunt --repo "$GHOST_DEMO_DIR" --test test_bank.py --max-mutants 1 \
  --ai --export-test "$GHOST_DEMO_DIR/test_boundary.py"
```

A successful run reports `verified_distinguishing_test` and an exported file. **It still exits 1:** the original suite still has a survivor. Model output can vary; a proposal may remain unverified, and requested export then returns exit 2.

**Only after export succeeds**, review the actual generated code and adopt it manually:

```bash
cat "$GHOST_DEMO_DIR/test_boundary.py"
git -C "$GHOST_DEMO_DIR" add -- test_boundary.py

ghost haunt --repo "$GHOST_DEMO_DIR" --test test_bank.py \
  --test test_boundary.py --max-mutants 1
```

For the demonstrated boundary proposal: **two baseline tests pass, the mutant is killed, exit 0**. Keep `bank.py` staged; do not commit between demo runs.

## Commands

Both commands default to the current repository. `python -m ghost_pr` can replace `ghost` if the console shortcut is unavailable.

```bash
ghost scan --repo /absolute/path/to/repo --json

ghost haunt --test tests/test_example.py
ghost haunt --test tests/test_one.py --test tests/test_two.py
ghost haunt --test tests --timeout 10 --max-mutants 5 --json

ghost haunt --test tests --ai --show-ai-test
ghost haunt --test tests --ai-model EXACT_INSTALLED_NAME
```

| Option | Behaviour |
| --- | --- |
| `--repo PATH` | Target repository; defaults to the current directory |
| `--json` | Emit one JSON result instead of readable output |
| `--test PATH` | Required for Haunt; repeat for multiple relative paths; pytest `::test_name` selectors supported |
| `--timeout SECONDS` | Per-test-run limit; positive finite number, default 10 |
| `--max-mutants N` | Evaluate 1–5 mutants; default 5 |
| `--ai` | Enable Gemma 4: `gemma4:e2b-it-q4_K_M` |
| `--ai-model NAME` | Enable AI with another installed model; overrides the default |
| `--ai-endpoint URL` | Local Ollama endpoint; default `http://127.0.0.1:11434`; does not enable AI by itself |
| `--show-ai-test` | Explicitly reveal validated proposed code and explanation |
| `--export-test PATH.py` | Save a verified proposal; requires AI and a new file in an existing directory |

Only `--repo` and `--json` apply to Scan. Absolute test paths, parent traversal, and options passed as test values are refused. Explicit model/endpoint overrides work regardless of option order.

Compatibility aliases: `ghost check` → `ghost scan`; `ghost run` → `ghost haunt`.

### Export rules

Export saves exactly the verified Python, without regenerating it. It refuses existing files and symlinks, creates no directories, and never stages or commits the result. Relative output paths are relative to your invocation directory.

A failed write/close may leave a partial file; inspect it manually. Export failure or refusal returns exit 2 while retaining the analysis evidence. Proposal code and explanation stay out of reports unless `--show-ai-test` is requested.

## Reading results

| Result | What it means |
| --- | --- |
| Baseline passed | The selected tests passed before mutation and executed tests |
| Killed ✓ | A genuine test-call failure detected the mutation |
| Survived ! | Tests passed despite the mutation; investigate its meaning |
| Timeout / execution error | No reliable killed/survived conclusion for that mutant |
| Verified AI proposal ✓ | Proposed test passed on original and failed on mutant |
| Exported ✓ | Verified code was saved, but has not been adopted |
| No candidates | No supported mutation was evaluated; not evidence of strong tests |

The detection ratio is **killed / (killed + survived)**. Timeouts/errors are separate; no denominator means N/A. Survivors can be equivalent changes, unexercised paths, or missing assertions—not automatically confirmed bugs.

**AI verification does not change the existing suite's counts.** Review, adopt, stage, and rerun before claiming the suite improved.

| Exit | Scan | Haunt |
| --- | --- | --- |
| `0` | Complete, no findings | Completed without survivors |
| `1` | Complete, findings present | Completed with survivors |
| `2` | Incomplete, unsupported, or failed | Repository/snapshot failure, blocked baseline, mutant timeout/error, or requested export not performed |

Exit 2 takes precedence. AI unavailability/unverified proposals alone do not change core analysis status unless export was requested.

Readable reports use symbols plus explicit labels, with ASCII fallback for unsupported/unknown encodings. No colour or ANSI escapes are emitted. Paths/messages are escaped. See [output examples](docs/DEMO.md#readable-output-examples).

## What Scan checks

- Git whitespace diagnostics: trailing whitespace, spaces before tabs, and extra blank lines at EOF, respecting repository settings.
- Suspected credentials on **staged added lines** across supported regular UTF-8 text—not just Python.
- Selected AWS access-key ID and GitHub token formats, common private-key BEGIN markers, and nontrivial literal credential assignments.

Findings contain locations, rule IDs, and generic redacted messages. Scan does not execute project code, call AI, contact credential providers, or fix files.

Coverage limits: **200 changed paths, 1 MiB per old/new blob, 8 MiB cumulative blob bytes**. Binary, undecodable, oversized, and unsupported coverage is explicit and makes required checks incomplete. Removed and unchanged credentials are not scanned.

Credential rules are heuristics, not comprehensive detection. Placeholder filtering is value-based and can miss real values; recognised provider shapes/private-key markers are flagged independently. Dynamic/multiline assignments, encoded secrets, newer stateless GitHub App tokens, and unlisted formats can be missed. Exact patterns are in [SPEC](docs/SPEC.md).

A “not a Python file” inspection skip does **not** exclude that text file from preflight checks. “No findings detected” is not a safety verdict.

## How Haunt works

1. Capture and pin the staged Git tree.
2. Export tracked regular files with staged bytes and executable permissions.
3. Run the selected pytest baseline; block analysis if it fails, errors, times out, or executes no tests.
4. Discover supported AST expressions on changed lines.
5. Generate each independent mutant from the original snapshot and run tests in a fresh copy.
6. Report evidence; optionally request and verify a test for the first survivor.
7. Export the verified test only when explicitly requested.

Supported operators: `<= → <`, `>= → >`, `== → !=`, and Boolean flips. Tests, chained comparisons, unsupported expressions, and sensitive paths/scopes are skipped. Mutation screening ignores unrelated comments/docstrings; AI-context screening is separate.

AI uses the enclosing function, mutation evidence, and small test excerpts. The adapter requests a strict JSON schema; it does not execute shell suggestions, extract JSON fragments, or automatically retry. Only one undecorated, zero-argument proposed test plus imports is supported.

## Limits and execution boundaries

- **Trusted projects only.** Temporary directories do not isolate external side effects or protect environment credentials.
- **Original files/index are preserved during analysis.** Explicit export creates the requested file. Haunt may add immutable Git tree objects; Scan uses temporary index/object storage.
- **No concurrent staging during initial capture.** Later edits cannot change the pinned run.
- **No symlinks/submodules in Haunt's exported tree.** Scan also enforces its documented repository-state restrictions.
- **Not full-source mutation coverage.** Only supported changed expressions, at most five mutants, are evaluated.
- **AST unparsing changes formatting/comments in temporary mutants.** It does not preserve source layout.
- **Pytest isolation has limits.** Plugin autoload, ambient `PYTEST_PLUGINS`, and configured `addopts` are disabled; explicit project plugin configuration may still execute.
- **Process cleanup has limits.** Process groups are terminated on completion/timeout; detached descendants escaping the group are unsupported.
- **AI stays optional.** Missing models, invalid output, or screened context leave core results available. Offline AI requires preinstalled dependencies/model weights and a locally configured Ollama server.
- **Local endpoints only.** The adapter accepts HTTP loopback endpoints, rejects redirects/proxies, checks installed model metadata, and bounds context/response sizes and socket timeouts. It cannot prove how a separately managed server routes inference.
- **No general correctness guarantee.** Verified tests distinguish two versions; they do not establish business requirements.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `ghost: command not found` | Activate `.venv` and install with `python -m pip install -e '.[test]'`; alternatively use `python -m ghost_pr` |
| Unstaged tracked changes | Review and stage intended edits, or use a separate controlled clone; do not discard work just to run the tool |
| No mutation candidates | Confirm a supported expression is on a staged changed line; inspect reported skips |
| AI unavailable | Open the local Ollama service, run `ollama list`, and confirm the exact model/endpoint |
| Existing export destination | Choose a new `.py` filename; Ghost-PR will not overwrite |
| Tests fail before mutation | Fix the baseline or environment first; target dependencies must be available |
| Need raw test diagnostics | Run pytest directly in your trusted project; Ghost-PR omits raw pytest/Git logs |

## Development and documentation

```bash
python -m unittest discover -s tests -v
```

Automated tests use controlled Git repositories and recorded model responses. Recorded fixtures are not live-model evidence. Team-reported live Gemma results and their limits are documented separately.

| Resource | Purpose |
| --- | --- |
| [SPEC](docs/SPEC.md) | Contracts, limits, and implementation checklist |
| [TEAM_GUIDE](docs/TEAM_GUIDE.md) | Module explanations and contributor walkthrough |
| [DEMO](docs/DEMO.md) | Presentation script, examples, and observed validation |
| [AGENTS.md](AGENTS.md) | Small-chunk development and anti-bloat rules |

Module responsibilities: `cli.py` orchestrates; `repository.py` captures/exports; `mutations.py` selects/generates mutants; `runner.py` and `pytest_evidence.py` execute/record tests; `local_ai.py` handles proposals; `preflight.py` scans; `exporting.py` saves verified code; `reporting.py` presents results; `models.py` holds shared data.

Contributions should define a small contract, add meaningful verification, and explain the data flow. Keep runtime changes simple; do not introduce automatic fixes, GitHub writes, or a dashboard into this MVP.

## Credits and licence

Built with OpenAI Codex in collaboration with the team. Runtime uses Python's standard library, Git, and installed pytest for test execution. Optional inference uses the user's [Ollama](https://ollama.com/) installation and [Google DeepMind Gemma 4](https://ollama.com/library/gemma4:e2b-it-q4_K_M); model licences apply separately. No weights or external application templates are bundled.

Ghost-PR is available under the [MIT licence](LICENSE).

