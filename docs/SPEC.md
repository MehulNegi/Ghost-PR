# Ghost-PR contract (v0.1)

## Product
Python-only, local, staged-change preflight and targeted mutation testing.
No GitHub writes, database, automatic fixes, or model downloads.

## Increment 1: implemented
`python -m ghost_pr check --repo PATH [--json]` inspects a Git working tree.
Exit 0 means inspection/checks completed with no findings, NOT that code is
correct. Exit 1 means completed with findings. Exit 2 means unsupported state,
operational failure or incomplete coverage. No code execution occurs.
All subprocesses use argument arrays, no shell, and a 10-second timeout.

Preconditions: Git installed, non-bare repository with HEAD, no unstaged tracked
changes anywhere, no conflicts, no submodules or symlinks among staged paths.
Untracked files are counted and excluded; ignored files are outside review.
Paths are read with NUL-delimited Git output. Added and modified regular Python
files are supported. Renames are represented as deletion plus addition.
Deleted files and non-Python files are explicitly skipped.
Changed line numbers refer to the new/index version, never the old version.
Deletion-only Python edits have no new lines and are skipped for mutation scope.
The command never prints diff contents, file contents, or raw Git error output.
No staged changes produces an empty, successful inspection.
Inspection pins HEAD and an index tree before selecting changes. Execution
uses that same tree even if files or the index change later.

## Data models
ChangedFile(path: str, lines: tuple[int, ...]); SkippedFile(path, reason).
Inspection(root: str, files: tuple[ChangedFile, ...], skipped: tuple[SkippedFile,
...], untracked_count: int, tree: str). Paths are repository-relative, root is absolute.

## Implementation status

Increments 1–4 are implemented and exercised with controlled repositories.
Increment 5 is exercised with recorded HTTP/proposal fixtures. The team also
reports a successful live qwen2.5-coder:3b distinguishing-test run in macOS
Terminal; provenance and limits are recorded in DEMO.md. This is an observed
example, not a general model reliability claim.
Execution always uses disposable copies, which are not security sandboxes.

## Architecture
CLI -> repository service -> Git subprocess adapter.
Domain models have no dependencies on CLI, Git, or AI.
Mutation, execution, AI, and reporting modules depend on domain contracts.
No command/service classes unless state or complexity justifies them.

## Execution contract

`ghost haunt [--repo PATH] --test tests/test_file.py [--test OTHER]`
explicitly executes trusted project code. Test values are relative file/directory
paths, optionally with pytest `::node` selectors; options, absolute paths and
parent traversal are rejected. Dependencies, including pytest, must be installed
in the current Python interpreter. No package installation occurs. The repository
defaults to the current directory. `ghost run` remains a compatibility alias for
the same parser and implementation, with identical options and exit codes.
`ghost check` remains read-only staged inspection; it does not execute tests or AI.

Options: `--timeout` positive finite seconds (default 10), `--max-mutants` 1–5
(default 5), `--json`, optional `--ai`, `--ai-model NAME` and `--ai-endpoint URL`
(default `http://127.0.0.1:11434`). `--ai` enables AI using qwen2.5-coder:3b
unless `--ai-model` is explicitly supplied. An explicit endpoint overrides the
default independently. `--ai-model` alone continues to enable AI; endpoint alone
does not. Option order does not affect this precedence. `--show-ai-test` requires
`--ai` or an explicit model. No AI request when neither enabling option is used.
Exit 0: completed without survivors; 1: completed with survivors;
2: inspection, snapshot, baseline, or mutant execution failure. Timeouts and
execution errors take precedence over survivors. Optional AI failure is reported
without discarding or changing the core mutation exit status.

Shared results: Inspection gains `tree` (pinned index object ID). TestRun contains
`status` (passed/failed/no_tests/timeout/execution_error), `returncode`, and
counts of passed, failed, and error reports. Mutation contains path, line,
column, AST node kind, operator and before/after expression text. MutationResult
combines mutation and outcome. RunReport combines inspection, baseline, results,
explicit skips, and AIResult. JSON adds counts and detection_ratio; it omits raw
process output and proposals unless --show-ai-test is requested. Columns are
zero-based UTF-8 AST byte offsets in JSON; terminal columns add one.

Snapshot export validates every recursive tree entry, permitting only regular
blobs (100644/100755), checks safe relative paths, and writes blob bytes without
archive extraction or checkout filters. It excludes untracked/ignored files and
preserves executable bits. A context manager cleans up on all exits. Git may
write immutable tree objects; original index and working files remain untouched.

Index-preservation correction: `git write-tree` can update cache extensions in
the index. Resolve the repository's real index path, copy it into a temporary
directory, and pin using `GIT_INDEX_FILE` pointing to the copy. All inspection
Git commands disable optional index locking, fsmonitor and hooks. A repository
with no index yet uses an empty temporary index. Acceptance checks compare raw
original index bytes before/after inspection and full analysis, not just staged
entries. Git objects may still be added. Concurrent writers during the index
copy are unsupported; once pinned, source/index edits cannot change the run.

Execution supports macOS/Linux only. A fresh process session permits killing the
process group on timeout and after completion. Detached processes that escape
the group are unsupported. Pytest output is discarded; a bounded structured
report distinguishes call-phase test failures from collection/setup/teardown
errors. No tests collected blocks mutation. Each mutant and AI verification uses
a fresh copy. Temporary directories are not security sandboxes.

Mutation discovery uses supported AST expressions intersecting changed lines:
single <=, >=, == comparisons and Boolean constants. Skip tests, chained
comparisons, sensitive/authentication paths or relevant code scopes, syntax errors, and
unsupported expressions explicitly. Sort by path/line/column/operator, cap at
five, replace exactly one node in an original AST, unparse and compile. Unparsing
changes formatting/comments; it does not promise source-layout preservation.

AI (adapter implemented; team-reported live example in DEMO.md): Ollama local chat API, explicit existing model;
loopback literal/localhost endpoints only, no redirects or proxies, 30-second
socket timeout, 16 KiB context and 64 KiB response limits. Send the enclosing
function, selected test excerpts and mutation, rejecting suspected credentials
and sensitive paths. Require explanation and test_code strings containing a
syntactically valid pytest test. Never run shell suggestions. A proposed test is
written only in fresh disposable copies; original pass then mutant call failure
is required for `verified distinguishing test`. This establishes a distinction,
not business correctness. Recorded responses are automated-test fixtures only.

## Acceptance and progress

Each chunk defines inputs, outputs and failure behaviour above; relevant checks
below must pass before its dependents are implemented. Initial baseline: 10
unittest tests passed before edits. No numerical coverage target.

- [x] A: inspect starter and run existing tests.
- [x] B: document command contracts and shared result shapes.
- [x] C–E: strengthen state/path/line regression checks and pin inspection (13 tests).
- [x] F: export a pinned tree without consulting working files.
- [x] G: verify fidelity, permissions, unsupported entries and cleanup (16 tests).
- [x] H: bounded pytest execution and process cleanup.
- [x] I: classify pass/fail/no-tests/collection/setup/timeout correctly (4 runner tests).
- [x] J: discover deterministic changed-line AST mutations (2 tests).
- [x] K: generate exactly one syntactically valid mutant (3 mutation tests).
- [x] L: execute one mutant independently after a passing baseline (2 workflow tests).
- [x] M: bounded deterministic independent mutation loop (2 analysis tests).
- [x] N: honest readable report and exit codes (3 analysis tests).
- [x] O: structured JSON report (29 total tests at this step).
- [x] P: repeatable staged withdrawal fixture; rehearsed baseline pass and survivor.
- [x] Q: official API checked; bounded adapter verified with recorded HTTP responses.
  The team subsequently reported a successful live example (DEMO.md).
- [x] R: validate proposed test JSON, syntax and context bounds (5 AI tests).
- [x] S: original/mutant verification in disposable copies; recorded fixtures pass.
- [x] T: README/team guide/demo script updated; controlled CLI rehearsal completed.

### Local adapter contract (Q)

Official Ollama chat/tags API checked before implementation (2026-10-31):
https://docs.ollama.com/api/chat and https://docs.ollama.com/api/tags.
Use GET `/api/tags`, require the exact installed model name, positive model size,
GGUF format and no cloud/remote metadata; then POST `/api/chat` with
`stream: false`, `format: "json"`, and system/user messages. HTTP loopback roots
only; localhost is mapped to 127.0.0.1. No proxy or redirect handling. HTTP and
JSON failures become sanitized AI errors, leaving core results usable.
Run the already-installed Ollama server with `OLLAMA_NO_CLOUD=1`; the client
cannot prove how a separately managed local server routes requests.
See https://docs.ollama.com/faq for the official cloud-disable setting.
Acceptance: controlled HTTP boundary tests for request shape, absent model,
transport failure, remote endpoint refusal, oversized and malformed responses.
Live access was unavailable in the agent environment during adapter development;
the team subsequently reported success from macOS Terminal (DEMO.md). The agent
has not downloaded a model.

### Proposal validation contract (R)

AI uses only the first surviving mutant. Context contains its enclosing function,
mutation evidence and at most three selected test-file excerpts. Context source
files are limited to 64 KiB each, excerpts to 4 KiB each, and encoded context to
16 KiB. Reject suspected credential assignments, known credential prefixes,
private-key headers and sensitive paths rather than sending them. This is a
conservative heuristic, not a complete secret detector. If context cannot be
provided within bounds, AI is blocked without changing mutation results.

Response must be exactly an object with nonempty `explanation` (<=2 KiB) and
`test_code` (<=8 KiB), one top-level zero-argument `test_` function and imports
only at module level. Reject decorators, pytest marks and async tests for MVP;
parse and compile the complete code. Syntax validation is not a sandbox.
Reject explicit process/package-install imports (`os`, `subprocess`, `pip`,
`ensurepip`, `venv`, `importlib`, `builtins`, `ctypes`) and dynamic execution
calls (`exec`, `eval`, `compile`, `__import__`). This rejects direct shell/install
suggestions; it does not prove arbitrary Python code harmless. Use trusted demo
code only and review a displayed proposal before adopting it manually.
Acceptance: malformed JSON/fields/syntax, credentials, oversized context and
response, plus a recorded exact-balance test. Never execute recorded responses
as if supplied by a live model.

### Distinguishing-test prompt correction

Observed live behavior (reported by the team): qwen2.5-coder:3b described an
equality boundary but repeated an existing unequal-input test. Strengthen only
the system instruction inside `request_proposal`; retain the existing context,
JSON fields, HTTP adapter, generation settings and verification path.

Input: actual function, before/after mutation expressions and existing test
excerpts. Requested output: one test importing the real implementation, with
inputs that reach the changed expression and expose different behavior, and an
assertion checking that difference. Request a different case from existing tests
that miss the mutation, and require explanation and test inputs to agree.
For comparison mutations, consider boundary values and equality when relevant
to the operator change. Do not include demo-specific values, replacement
implementations or mocked targets in the prompt's proposed approach.

Failure/exit behavior stays unchanged: a valid proposal that passes on both
versions remains unverified; model explanations cannot establish verification.
Acceptance: check semantic prompt requirements and unchanged JSON/context
construction without comparing the full prompt string; reuse the existing
both-versions-pass regression with an actual repeated partial-withdrawal test.
These automated checks do not establish improved live-generation quality.

- [x] Inspect current prompt/verification; 7 relevant tests pass before edits.
- [x] Strengthen generic instructions and check prompt construction (5 adapter tests pass).
- [x] Reuse the both-pass regression for the observed repeated-test case (2 verification tests pass).
- [x] Run relevant tests, review changes, document live-validation command in TEAM_GUIDE.

Validation commands: `/private/tmp/ghost-pr-dev/bin/python -m unittest discover
-s tests -p test_local_ai.py -v` (5 passed) and the same command with
`-p test_ai_verification.py` (2 passed). Recorded HTTP/proposal fixtures are
automated regression inputs only. The team subsequently reported a successful
post-change live run (see DEMO.md); no retries, new adapter, response schema or
CLI options were added.

### Proposed-test execution contract (S)

Write `test_ghost_proposed.py` only inside a fresh test copy, rejecting an
existing file with that name. Run only that proposed file so failures in an
unrelated existing test cannot masquerade as the proposed test distinguishing
the mutant. Its original run must pass and collect tests before its mutant run
is attempted. A mutant call failure verifies a distinction; success, no-tests,
timeout, collection/setup error or original failure remains unverified with
the observed outcomes. Both runs are bounded and cleaned up.

`--ai` or `--ai-model` opts into local request and proposed-code execution for a trusted
project. Core exit status remains based on mutation analysis. AIResult records
status, sanitized detail, whether a model response arrived, target mutation,
and verification outcomes. Source/test code and explanation are hidden by
default; `--show-ai-test` explicitly includes a validated proposal in terminal
or JSON output. It requires `--ai` or `--ai-model`. No generated file is retained or
written into the original repo. Acceptance: recorded exact-balance success,
original failure, mutant survival, unavailable model and malformed response;
original files and index remain unchanged.

Boundary review acceptance: reject malformed/deep JSON and invalid Unicode
proposals with sanitized AI errors, enforce valid endpoint ports, and ensure
mutant execution errors take precedence over survivors in exit codes. Third-party
pytest plugins do not autoload; projects depending on them must configure explicit
plugins themselves and verify a passing baseline. No dependency is installed by
Ghost-PR. The optional `test` extra is only a manual development setup aid.

## Final validation record

- Before implementation: `python3 -m unittest discover -s tests -v` — 10 passed.
- Final: `/private/tmp/ghost-pr-dev/bin/python -m unittest discover -s tests -v`
  — 38 passed on macOS, Python 3.14, pytest 9.1.1. The isolated interpreter reused
  already-cached pytest/dependency files; no dependency/model downloads occurred.
- Actual `check --json` reported staged bank.py and test_bank.py with new-side
  lines and the pinned tree ID.
- Actual fixture run with partial-withdrawal test: baseline passed, one survivor,
  exit 1. After staging the exact-balance test: baseline passed (two tests), one
  killed mutant, exit 0.
- Actual missing-runner request: AI unavailable, response_received false, core
  survivor unchanged, exit 1.
- HTTP/model response tests use recorded fixtures. At that development checkpoint,
  live inference was unverified; the later team report is recorded in DEMO.md.
  Linux and Python 3.11 execution remain unverified. Windows is unsupported.
- No package publishing, remote writes or original-repository commits occurred.
  Demo setup alone creates an initial empty commit in a newly created fixture.

Supported imports are ordinary snapshot-relative modules/packages and project
pytest configuration. Editable installs pointing to original source, custom
import redirection, external services and detached processes are outside the
controlled-demo guarantee; they can undermine isolation or staged-source fidelity.

## Demo handoff acceptance (documentation only)

Inputs: the team's reported live result and a fresh full-suite/preservation check.
Outputs: attributed evidence in DEMO.md, readable existing CLI commands, manual
review/adoption/staging instructions, and four teammate explanations with judge
questions. No runtime contracts, model settings, code or tests change.

- [x] Full suite: 38 passed in 17.079 seconds with
  `/private/tmp/ghost-pr-dev/bin/python -m unittest discover -s tests -v`.
- [x] Fresh controlled CLI check: baseline passed (one test), boundary mutant
  survived, exit 1; working-file hashes and raw index bytes unchanged. Zero run
  workspaces remained, and the disposable fixture was removed afterward.
- [x] Record the team-reported live run separately from automated fixtures.
- [x] Document terminal presentation and manual test adoption followed by staging.
- [x] Add each teammate's module explanation and three judge questions/answers.

Manual adoption is intentional editing by the contributor after review. To
demonstrate the same mutation again, leave bank.py staged against the fixture's
empty HEAD; stage the reviewed generated test and rerun both selected test files.
Only claim the adopted run killed the mutant after observing its output.

## Haunt command change: acceptance checklist

Inputs: existing CLI options, with haunt as primary name and run as an alias.
Output: the existing RunReport and terminal/JSON output. Repository default,
required explicit test paths, repeated --test values, node selectors, failures
and exit 0/1/2 remain unchanged. The configured console entry point remains
`ghost = "ghost_pr.cli:main"`. Mutation and AI verification code are out of scope.

- [x] Inspect starter and run existing suite: 38 tests pass before edits.
- [x] Define command/AI precedence before implementation.
- [x] Route haunt/run through one parser and one execution branch; 4 CLI and 5 analysis tests pass.
- [x] Add --ai defaults without overriding explicit choices; 6 CLI tests pass.
- [x] Update README/help/demo examples and rerun the deterministic demo.
- [x] Run complete suite and review only the intended changes: 44 tests passed
  in 16.989 seconds using `/private/tmp/ghost-pr-dev/bin/python -m unittest
  discover -s tests -v`.

Deterministic acceptance: haunt and run, invoked from the target directory
without --repo, produced identical JSON and exit 1 for the partial-test survivor.
After explicitly staging the manual boundary assertion, haunt reported two
passing baseline tests, one killed mutant and exit 0. Each run preserved source
and index bytes and removed run copies. No AI was requested. The existing console
entry-point configuration was loaded and confirmed to resolve to cli.main.

## Scoped mutation screening correction

Investigation before edits: in the local boltons-ghost-trial checkout, the staged
mathutils.py comparison is in ceil, line 92. The previous source-wide AUTH_WORDS
search matched `permission` in a module-level license comment at line 17,
column 22, outside ceil (lines 72–94). The path did not match. A generic license
comment plus a simple changed comparison reproduces the same false exclusion.
This was the mutation-discovery gate, not the separate AI-context credential
screen. Its early skip also prevented any later surviving-mutant AI request.

New contract: retain the conservative sensitive-path exclusion. For each
supported changed expression, inspect actual AST names and non-docstring string
literals in its nearest enclosing function (or nearest statement outside a
function), and names of enclosing functions/classes. Ignore comments, docstrings
and unrelated sibling code elsewhere in the file. A security cue inside the
relevant function still blocks its mutations conservatively, even if its precise
data flow is unknown. This heuristic is not semantic authentication analysis.

Input/output models, changed-line restrictions, mutation operators, test execution
and exit codes stay unchanged. Skip reasons identify `mutation_sensitive_path`
or `mutation_sensitive_scope`, with a candidate line where relevant, without
echoing identifiers, literals or suspected values. A supported expression blocked
by this rule should not also be described as having no supported expressions.

AI-context path checks, suspected-credential screening and size limits remain
independent and unchanged; allowing a mutation does not authorize sending source
to AI. No Boltons-specific exception, new CLI option or global bypass is added.

- [x] Inspect actual staged source and reproduce false exclusion before changes.
- [x] Baseline relevant tests: 3 mutation and 5 AI adapter tests pass.
- [x] Implement scoped AST screening and focused false-positive/intended-exclusion tests (5 mutation tests pass).
- [x] Verify AI credential screening remains independent (6 AI adapter tests pass).
- [x] Attempt the selected real-repository CLI trial and record the execution blocker.

Post-fix discovery in the actual staged mathutils.py yields one == to !=
candidate at line 92, with no screening skip. The CLI rerun stopped during
`git write-tree`: this environment could not create Git objects in that checkout
(`Operation not permitted`, exit 2). It did not reach the baseline or execute a
mutant. The earlier 16-test baseline is the team's report, not a new measured
baseline. Tracked file hashes/index bytes stayed unchanged and no run copies
remained. This is not yet a successful real-repository mutation run.

Final regression command:
`/private/tmp/ghost-pr-dev/bin/python -m unittest discover -s tests -v`
— 47 tests passed in 17.193 seconds. The AI adapter/context-screening file is
byte-for-byte unchanged; the new separation regression verifies that suspected
credentials still block context construction after arithmetic discovery succeeds.

## Read-only preflight contract

`ghost check [--repo PATH] [--json]` retains inspection fields (`root`, `files`,
`skipped`, `untracked_count`, `tree`) and adds `findings`, `checks`, and overall
`complete`. Finding(kind, rule_id, path, line, message) contains only safe metadata:
kind is whitespace or suspected_secret; line is one-based new-side location;
messages never contain source or matched values. CheckStatus(name, complete,
checked_files, skipped, message) records coverage and sanitized failures.
Inspection's existing files/skipped fields still describe Python mutation scope;
each check's coverage covers all eligible staged text paths, regardless of suffix.

Exit 0: all checks complete, no findings. Exit 1: all complete with findings.
Exit 2 takes precedence for incomplete checks or unsupported/operational states.
Haunt/run behavior and exit codes are unchanged. No project code, AI, provider
validation, dependency installation, network requests or automatic fixes occur.

Capture uses a copied index and disposable Git object directory with the real
object store as an alternate. Pinning and all cached diffs use that copy; no
working files, real index, Git objects or configuration are modified. Existing
HEAD/conflict/mixed-edit/symlink/submodule rules remain. Concurrent initial
capture is unsupported; detect a HEAD change during capture and fail. Later
source/index edits cannot change the captured checks.

Whitespace uses bounded `git diff --cached --check --no-ext-diff --no-textconv`
with a pinned HEAD, no renames and no color, one literal path at a time. Respect
repository whitespace settings; set only the child process locale to C. Actual
Git probes returned 0 clean, 2 with findings, and 128 for an invalid revision.
Supported diagnostic rules: git_trailing_whitespace, git_space_before_tab,
git_blank_eof. Match the known raw path prefix and discard each accompanying
source record; do not parse combined filenames with a line-splitting heuristic.
Unexpected exit codes, stderr or unrecognized diagnostics mean incomplete,
never clean. Raw stdout/stderr are never exposed.

Secrets scan only new-side lines from zero-context staged diffs, using the
existing changed_lines parser and captured blob text. Removed/unchanged values
are excluded. Supported regular text is strict UTF-8 (including ASCII), without
NUL bytes. Limits: 1 MiB per old/new blob, 8 MiB cumulative old/new blob bytes,
and 200 changed paths. Binary diffs, oversized/undecodable/unsupported files and
limits are reported as skipped coverage and make required checks incomplete.
Deleted files and mode-only changes have no added text and do not create findings.

Precise, case-sensitive provider formats: aws_access_key_id is AKIA or ASIA plus
16 uppercase alphanumeric characters; github_token is ghp_/gho_/ghu_/ghs_/ghr_
plus 36 alphanumeric characters, or github_pat_ plus 22 alphanumerics, underscore,
59 alphanumerics. Require token boundaries. private_key_begin recognizes standard
PRIVATE KEY, ENCRYPTED/RSA/DSA/EC/OPENSSH PRIVATE KEY BEGIN markers.

credential_assignment recognizes api_key, access_token, client_secret, password
and passwd (case-insensitive; optional underscore/hyphen in compound names),
quoted literal assignments/JSON/YAML keys and simple unquoted environment-file
assignments. Require at least 12 characters. Ignore empty values, explicit
YOUR_*/example/sample/dummy/fake/test/fixture/replace prefixes, changeme,
${...}, $NAME and <...> placeholders/references. This is value-based, never a
whole-file exclusion. Provider-shaped tokens/private-key markers are independently
flagged even in examples/tests. Dynamic expressions and complex/multiline
assignments are outside these narrow rules. Placeholder handling is not proof of
harmlessness; no entropy-only detector or validity claim is made.

AI context screening intentionally stays separate: it withholds whole context
conservatively and accepts broader patterns; its partial matches are unsuitable
for precise user-facing findings. Mutation scope exclusions also stay separate.
No existing AI/mutation screening behavior changes. Both terminal and JSON show
only location, stable rule ID and generic redacted message. Sort/deduplicate by
path/line/kind/rule_id. Escape filenames in terminal and ensure_ascii JSON.

Acceptance/progress:

- [x] Inspect existing code; 47 tests pass before edits; probe real Git diagnostics.
- [x] 1: add result/completion contracts without changing execution behavior (13 repository tests pass).
- [x] 2: shared bounded Git result access, isolated index, per-path whitespace checks (3 preflight and 4 snapshot tests pass).
- [x] 3: precise added-line credential rules and bounded regular-text coverage (8 preflight tests pass).
- [x] 4: integrate check CLI and existing reporting (13 repository, 6 CLI, 8 preflight tests pass).
- [x] 5: integration/privacy/failure/preservation regressions with real disposable repos (15 preflight tests pass).
- [x] 6: README/team walkthrough/controlled demo, full integrated suite, final review.

Format references checked during implementation: [AWS identifier prefixes](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html),
[GitHub token prefixes](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github#githubs-token-formats),
and [Git object-directory environment](https://git-scm.com/docs/git#Documentation/git.txt-codeGITALTERNATEOBJECTDIRECTORIEScode).
The selected GitHub patterns cover legacy 40-character tokens and the selected
fine-grained shape used here; newer stateless GitHub App installation tokens and
other lengths are not covered. Unquoted uppercase identifier references are
also excluded from assignment findings. `complete` means these configured checks
completed within supported coverage, not that all possible credentials were found.
The returned tree is the captured hash; check's temporary tree objects are not
retained in the real object store.

Integrated validation: `/private/tmp/ghost-pr-dev/bin/python -m unittest discover
-s tests -v` — 62 tests passed in 20.759 seconds (47 passed before this task).
The 15 preflight tests cover real Git whitespace statuses, unusual paths,
added/removed lines, placeholders, privacy in both outputs, mixed edits, binary/
size/encoding/path/byte-budget gaps, failure precedence and repository preservation.
Existing mutation/AI screening and analysis/verification functions are unchanged.

Actual controlled demo: staged whitespace plus a synthetic all-zero GitHub token
body produced two generic findings, complete=true, exit 1, with no value in
terminal or JSON. After explicit manual editing/staging to remove whitespace and
use an environment reference, complete=true, zero findings, exit 0. Entire fixture
file hashes (including index, objects and config) stayed identical across each
check. All run copies and the demonstration fixture were cleaned up. No tools
were installed, no provider contacted, and no commit/push/publish of this project
was performed. The existing fixture setup alone creates an empty initial commit
inside its new disposable repository.
