# Three-minute Ghost-PR demonstration

Scan your changes. Haunt your tests.

## Observed live validation: team report

The team reported a successful run in macOS Terminal using the existing
Ghost-PR integration and **qwen2.5-coder:3b** after the prompt correction:

| Step | Reported observation |
| --- | --- |
| Existing tests | Missed the `<=` to `<` boundary mutant |
| Generated proposal | A new exact-balance test |
| Proposed test on original | Passed |
| Proposed test on intended mutant | Failed through a test failure |
| AI status | `verified_distinguishing_test` |

This records the team's observed run, not a new inference run by the coding
agent. The report did not include raw output, exact generated source, runtime,
or a run timestamp; none are invented here. It was real local generation, not
an automated recorded response or the prepared example test.

This single successful example does not establish a success rate, consistency
across repeated runs, performance, or business correctness. Earlier live output
repeated an ineffective existing test; the verifier correctly kept it unverified.
Future model output must still be checked by actual execution and manual review.

## Before presenting

Complete README setup and activate the Python environment containing Ghost-PR
and pytest. Run commands from the Ghost-PR root. Have local Ollama and the
already-installed model running; no installation/download is part of this demo.
Use the existing local-only server configuration. Do not use `set -e`: exit 1
for an original survivor is expected, even if AI verifies a proposed test.

## 0:00–0:30 — Show actual staged scope

“Do our tests detect a small change to code we're about to contribute?”

```bash
GHOST_DEMO_DIR="$(mktemp -d)/withdrawal"
python examples/create_demo.py "$GHOST_DEMO_DIR"
ghost scan --repo "$GHOST_DEMO_DIR"
```

Setup creates an empty HEAD only in this new fixture, then stages bank.py and
its initial partial-withdrawal test. The implementation really is in the staged
diff. No generated or prepared boundary test is present.

## 0:30–1:00 — Establish the baseline and survivor

```bash
ghost haunt --repo "$GHOST_DEMO_DIR" --test test_bank.py --max-mutants 1
```

Expect baseline passed, one survivor, ratio 0/1, exit 1. The test exercises a
partial withdrawal, which both comparisons accept. Git pins the staged tree;
each test run uses a fresh copy. The contributor's source and index stay intact.

## 1:00–2:00 — Request and verify a real local proposal

Use readable output, with no `--json`. `haunt` is the primary command;
`run` is a compatibility alias. `--ai` selects qwen2.5-coder:3b at the default
loopback endpoint; explicit model/endpoint options remain available:

```bash
ghost haunt --repo "$GHOST_DEMO_DIR" --test test_bank.py --max-mutants 1 \
  --ai --export-test "$GHOST_DEMO_DIR/test_boundary.py"
```

The model receives the actual function, before/after mutation expressions and
existing test excerpt. It must return JSON containing explanation and test_code,
importing the real target. Verification runs the proposed test alone in fresh
original and mutant copies. Only original pass plus mutant test failure earns
`verified_distinguishing_test`; collection/setup errors and timeouts do not.

Show the actual status. If generation fails or the test passes on both, show
that outcome honestly. A successful proposal leaves the original survivor count
and exit 1 unchanged: the contributor has not adopted it yet.

Export occurs only after verification and existing screening. It writes exactly
the verified Python to this new file, without adopting or staging it. A survivor
still returns exit 1 after successful export. If export is refused or fails,
exit is 2: inspect the AI/export status, and do not proceed as though a file was
saved. Existing paths (including symlinks) are never overwritten. The parent
must already exist. Do not use --show-ai-test unless code should also be printed.

## 2:00–3:00 — Manually review, adopt, stage and rerun

Review the actual generated test before editing: does it import bank.withdraw,
call the real implementation, reach the changed expression, and assert the
intended result? Check for replacement/mocked targets, unrelated actions and
whether the expected behavior makes sense. A verified distinction alone does
not establish the intended requirements.

Review the exported file, then explicitly adopt it by staging:

```bash
cat "$GHOST_DEMO_DIR/test_boundary.py"
git -C "$GHOST_DEMO_DIR" add -- test_boundary.py
git -C "$GHOST_DEMO_DIR" diff --cached -- test_boundary.py
ghost haunt --repo "$GHOST_DEMO_DIR" --test test_bank.py \
  --test test_boundary.py --max-mutants 1
```

Staging is the contributor's explicit adoption. Export alone does not adopt
the test. Do not append `examples/exact_balance_test.txt` or substitute canned test
code. Leave bank.py staged against the empty HEAD; do not commit during this
sequence, or the changed-line scope will disappear.

For the reported distinguishing test, expect baseline passed with two tests,
one killed mutant, no excluded outcomes, ratio 1/1, exit 0. Claim these outcomes
only after observing the rerun. If the reviewed test is invalid or ineffective,
inspect the actual error/result before presenting success. This adoption rerun
is a documented procedure; it was not supplied as evidence with the live report.

Close with: “Git pins scope; AST changes one expression; pytest measures each
copy; optional AI suggests a test. The contributor reviews and adopts it.”

## Preservation and cleanup evidence

The coding agent reran the full suite after the prompt correction:

```bash
/private/tmp/ghost-pr-dev/bin/python -m unittest discover -s tests -v
```

Result: **38 passed in 17.079 seconds**, macOS, Python 3.14, pytest 9.1.1.
Automated AI tests use labelled recorded responses; they are separate evidence
from the team's successful live inference. The suite covers original-source and
index preservation, snapshot-error cleanup, independent copies, and child-process
cleanup after successful and timed-out pytest runs.

A separate fresh CLI check, with only the partial test and no AI, passed its
baseline and left one survivor (exit 1). All working-file hashes and raw index
bytes matched before/after. Its dedicated temporary-workspace parent was empty
after execution, and the entire controlled fixture was then removed.

These checks establish current controlled-fixture behavior, not a retrospective
audit of the team's live machine. For a presentation audit, take source/index
checksums before Ghost-PR, compare them afterward **before manual adoption**,
and direct `TMPDIR` to a dedicated directory outside the target repo; it should
have no run copies remaining afterward. Adoption/staging intentionally changes
the source/index, so start a new checksum baseline before the adopted-test run.
Temporary copies are not security sandboxes; detached processes that escape
their process group remain unsupported. Linux and Python 3.11 were not tested
here. This evidence predates the haunt naming change; the deterministic rerun below
checks the current command routes.

## Haunt compatibility rerun

After the CLI naming change, the full suite passed **44 tests in 16.989 seconds**
using the same interpreter/command above. In a fresh deterministic fixture:

- Both haunt and its run alias, with no --repo option, inspected the current
  directory and returned identical JSON: baseline passed, one survivor, exit 1.
- After staging the existing manual boundary assertion, haunt reported a passing
  two-test baseline, one killed mutant and exit 0.
- All three runs preserved original file hashes and raw index bytes and left no
  temporary run copies. The disposable fixture was removed afterward.
- The configured ghost console entry point resolves to ghost_pr.cli:main.

This rerun used no AI. Its manual assertion is deterministic fixture material,
separate from the team's live model-generated test recorded above. CLI tests
also verify --ai defaults, explicit overrides, and preserved test selection.

## Export implementation validation (2026-10-31)

The coding agent attempted the real workflow in a fresh fixture using --ai
(qwen2.5-coder:3b) and --export-test, without recorded responses or the prepared
boundary test. Observed: baseline **1 passed**, **1 survived**, **0 killed**;
AI **unavailable**, response_received false; export **not_exported**, exit **2**.
Elapsed wall time: **0.564 seconds**, including baseline and mutant execution.
A separate loopback /api/tags probe returned PermissionError, errno 1: this
coding environment blocks localhost. This is not evidence that the team's
Ollama service or model is broken. No proposal was generated or exported here.
The source files and raw index bytes were unchanged; the dedicated temporary
workspace parent was empty after execution. The entire fixture was removed.

Run the commands above in macOS Terminal with the README environment activated
to validate real generation/export. They invoke the existing adapter and model;
there is no canned response, new adapter or automatic model download. Continue
to review/stage only after observing verified_distinguishing_test and exported.
A killed mutant after adoption must also be observed, not assumed.

Automated integration evidence for export: the final full suite command above
passed **76 tests in 27.000 seconds**. Five export tests exercise exact UTF-8
contents, relative paths, screening/refusal, existing files/symlinks, missing
parents and a late-I/O failure. Shared haunt/run integration uses explicitly
recorded responses with real Git and pytest, confirms original pass/mutant test
failure, export success with survivor exit 1, export refusal/failure exit 2,
untracked output, unchanged originals/index, and empty temporary workspaces.
Summary/privacy tests check that default terminal/JSON output hides proposal
code and describes actual recorded outcomes. These tests do not substitute for
a new real-model run. Mutation and verification semantics remain unchanged.
