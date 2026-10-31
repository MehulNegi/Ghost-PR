"""Immutable results shared across adapters and presentation layers."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChangedFile:
    path: str
    lines: tuple[int, ...]


@dataclass(frozen=True)
class SkippedFile:
    path: str
    reason: str


@dataclass(frozen=True)
class Inspection:
    root: str
    files: tuple[ChangedFile, ...]
    skipped: tuple[SkippedFile, ...]
    untracked_count: int
    tree: str


@dataclass(frozen=True)
class Finding:
    kind: str
    rule_id: str
    path: str
    line: int
    message: str


@dataclass(frozen=True)
class CheckStatus:
    name: str
    complete: bool
    checked_files: int
    skipped: tuple[SkippedFile, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class CheckReport:
    inspection: Inspection
    findings: tuple[Finding, ...]
    checks: tuple[CheckStatus, ...]


@dataclass(frozen=True)
class TestRun:
    status: str
    returncode: int | None
    passed: int = 0
    failed: int = 0
    errors: int = 0


@dataclass(frozen=True)
class Mutation:
    path: str
    line: int
    column: int
    node_kind: str
    operator: str
    before: str
    after: str


@dataclass(frozen=True)
class MutationResult:
    mutation: Mutation
    outcome: str
    tests: TestRun


@dataclass(frozen=True)
class TestProposal:
    explanation: str
    test_code: str


@dataclass(frozen=True)
class AIResult:
    status: str = "not_requested"
    detail: str = ""
    response_received: bool = False
    mutation: Mutation | None = None
    original: TestRun | None = None
    mutant: TestRun | None = None
    proposal: TestProposal | None = None


@dataclass(frozen=True)
class ExportResult:
    status: str = "not_requested"
    path: str | None = None
    detail: str = "No test export requested."


@dataclass(frozen=True)
class RunReport:
    inspection: Inspection
    baseline: TestRun
    mutants: tuple[MutationResult, ...]
    skipped: tuple[SkippedFile, ...]
    ai: AIResult = field(default_factory=AIResult)
    export: ExportResult = field(default_factory=ExportResult)
