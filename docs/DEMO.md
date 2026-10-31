# Three-minute Ghost-PR demonstration

Scan your changes. Haunt your tests.

## Readable output examples

These excerpts were captured from real controlled CLI runs with UTF-8 stdout;
path lists and repeated coverage details are omitted here for space. No live AI
was called. The scan fixture was the fresh withdrawal repository plus staged
sample.py with trailing whitespace and credential.txt with a synthetic,
nonfunctional all-zero GitHub-token body. The value never appeared in output.

```text
Ghost-PR · Scan
Scan your changes. Haunt your tests.

✓ Inspection completed
  Python scope: 3 file(s)
  Untracked excluded: 0

✗ Whitespace · 1 finding(s)
  sample.py:1
    [git_trailing_whitespace] Trailing whitespace.

✗ Suspected secrets · 1 finding(s)
  credential.txt:1
    [github_token] Suspected GitHub token; value redacted.

✓ 2 checks completed
  whitespace: complete · 4 file(s) checked
    Completed.
  suspected_secret: complete · 4 file(s) checked
    Completed.

Result: 2 finding(s) · exit 1
These checks are not a safety verdict.
No project code or AI executed.
```

The haunt run used a separate fresh withdrawal fixture with only the initial
partial test; exit was 1. It reported one neutral test-file mutation skip while
still executing that test. The original suite missed the boundary mutant:

```text
Ghost-PR · Haunt

✓ Baseline · passed · 1 passed, 0 failed, 0 errors
  Snapshot: 67114b27a2aa

! Mutation results · 0 killed, 1 survived
  Mutants attempted: 1
  Timeouts: 0 · Execution errors: 0
  Detection ratio: 0/1; timeouts and execution errors excluded.
  ! bank.py:5:8 · SURVIVED
    amount <= balance → amount < balance (<= to <)

• AI not requested

• Test export not requested

Mutation results are not an overall safety verdict.
Survivors are not automatically confirmed bugs; they may be equivalent or outside exercised paths.
Next: Review surviving mutations and AI outcomes, if requested; add a relevant test and rerun.
```

Both runs preserved original file/index hashes, left no temporary run copies,
and their disposable fixture parent was removed. Redirected UTF-8 output has
symbols but no ANSI styling. ASCII/unknown encodings use PASS/FAIL/INFO, plain
separators and '-' for skip markers. Untrusted names/messages are escaped even
on UTF-8 terminals; encoding support does not guarantee font glyph support.
The full snapshot ID remains available in JSON. Detailed evidence appears once
in readable sections; closing guidance does not imply automatic test adoption.

Validation for this presentation change: 8 reporting, 15 preflight, 5 analysis,
10 CLI and 5 AI workflow/verification tests passed in focused runs. The final
full suite passed **84 tests in 28.818s**. Real-Git tests compare readable output
for scan/check and haunt/run, and existing JSON/privacy/export tests remain green.
Encoding tests use redirected UTF-8 and ASCII streams; no ANSI escapes are emitted.

## Observed Gemma 4 validation: team report

The team reported live success with **gemma4:e2b-it-q4_K_M**:

| Recorded result | Reported observation |
| --- | --- |
| AI status | verified_distinguishing_test |
| Proposed test on original | 1 passed, 0 errors |
| Proposed test on mutant | 1 failed, 0 errors |

This records the team's real local run, not a new coding-agent inference or a
recorded test fixture. The generated source, runtime, runner version and exact
run timestamp were not supplied; none are invented. It demonstrates this test
on this original/mutant pair, not a general success rate or business correctness.
Each future proposal must still pass validation and two-direction verification.
The shared --ai default now selects this exact Gemma 4 tag.

Default-change validation by the coding agent: 10 CLI tests passed, including
both aliases, help, endpoint/default selection and explicit overrides. The full
suite passed 80 tests in 27.162s. A direct parser check confirms --ai selects
Gemma without --ai-model. The adapter/schema, mutation, verification, export and
summary source stayed unchanged. These automated checks are separate evidence
from the team's live result above; no new inference or model download was run.

## Earlier Qwen validation: team report

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

The walkthrough uses the current Gemma 4 default. The earlier Qwen observations
above remain separate historical evidence.

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
`run` is a compatibility alias. `--ai` selects gemma4:e2b-it-q4_K_M at the default
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

## Gemma 4 formatting history and default-selection check

The team reported gemma4:e2b-it-q4_K_M returning response_received=true,
status=invalid_response and detail="Proposed test is not valid JSON." No proposal
reached test verification. Raw response content and the installed runner version
were not provided; malformed-content cause is unconfirmed. Do not infer that
thinking caused this from status alone. The later successful live result is
recorded above; success does not retrospectively identify the earlier cause.

The existing adapter now sends a format schema requiring string explanation and
test_code fields with no extra properties, instead of JSON mode alone. It still
reads the documented message.content field and strictly validates the entire
answer. message.thinking is not a fallback. Thinking settings and generation
limits are unchanged; model-specific controls require evidence and support.
No automatic retry, fragment extraction or prepared test has been added.

To check the new default without --ai-model, activate the README environment
in macOS Terminal and run from the project root. `ghost haunt --help` also shows
the selected default tag and endpoint:

```bash
GHOST_GEMMA4_DEMO_DIR="$(mktemp -d)/withdrawal"
python examples/create_demo.py "$GHOST_GEMMA4_DEMO_DIR"
ghost haunt --repo "$GHOST_GEMMA4_DEMO_DIR" --test test_bank.py \
  --max-mutants 1 --ai --json
```

Use the already-installed model, with only the initial partial-withdrawal test.
Do not append the prepared exact-balance test. Report actual ai.status,
response_received and original/mutant outcomes, not raw output or source.
Success still requires verified_distinguishing_test with original passed and
mutant failed through a genuine test failure; baseline must pass and the initial
mutant must survive. JSON parsing alone is not verification. Exit 1 remains
expected for that original survivor. Gemma 4 is now the shared --ai default.

The team reported the successful Gemma run above. The coding environment's
previous localhost restriction is separate; no new local inference was run to
change this constant. Automated protocol fixtures do not replace real generation.
If a future response is invalid, keep it unverified. Safe follow-up
evidence includes Ollama version and non-content metadata such as done_reason,
whether content is empty and whether a separate thinking field is present;
these are not currently emitted by Ghost-PR. Do not publish raw responses.

Automated validation of this change: 8 adapter tests and 5 AI workflow/verification
tests passed; the full suite passed 79 tests in 27.475s. Tests cover the schema
request, content/thinking separation and strict refusal of malformed answers.
Synthetic protocol fixtures do not establish successful live Gemma generation.

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
