"""Parse commands and orchestrate inspection, independent runs and optional AI."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile

from .local_ai import AIError, build_context, request_proposal, validate_proposal
from .models import AIResult, Mutation, MutationResult, RunReport, SkippedFile, TestProposal, TestRun
from .mutations import discover_mutations, generate_mutant, read_python
from .repository import RepositoryError, inspect_repository, staged_snapshot
from .reporting import analysis_data, analysis_exit_code, print_analysis, print_inspection
from .runner import run_tests, validate_test_paths


def run_snapshot_tests(snapshot: Path, paths: list[str], timeout: float,
                       mutation: Mutation | None = None,
                       proposed_test: str | None = None) -> TestRun:
    """Baseline and each mutant get fresh copies; snapshot remains pristine."""
    with tempfile.TemporaryDirectory(prefix="ghost-test-") as directory:
        copy = Path(directory) / "project"
        shutil.copytree(snapshot, copy)
        if mutation is not None:
            target = copy / mutation.path
            target.write_text(generate_mutant(read_python(target), mutation), encoding="utf-8")
        if proposed_test is not None:
            with (copy / "test_ghost_proposed.py").open("x", encoding="utf-8") as target:
                target.write(proposed_test)
        return run_tests(copy, paths, timeout)


def run_mutant_tests(snapshot: Path, mutation: Mutation, paths: list[str], timeout: float) -> MutationResult:
    try:
        tests = run_snapshot_tests(snapshot, paths, timeout, mutation)
    except (OSError, SyntaxError, ValueError, UnicodeError):
        tests = TestRun("execution_error", None)
    outcome = {"passed": "survived", "failed": "killed", "timeout": "timeout"}.get(tests.status, "execution_error")
    return MutationResult(mutation, outcome, tests)


def verify_proposal(snapshot: Path, mutation: Mutation, proposal: TestProposal, timeout: float) -> AIResult:
    paths = ["test_ghost_proposed.py"]
    try:
        original = run_snapshot_tests(snapshot, paths, timeout, proposed_test=proposal.test_code)
        if original.status != "passed":
            return AIResult("unverified", f"Proposed test on original: {original.status}.",
                            response_received=True, mutation=mutation, original=original, proposal=proposal)
        mutant = run_snapshot_tests(snapshot, paths, timeout, mutation, proposal.test_code)
    except (OSError, SyntaxError, ValueError, UnicodeError):
        return AIResult("unverified", "Proposed-test workspace could not be created or validated.",
                        response_received=True, mutation=mutation, proposal=proposal)
    status = "verified_distinguishing_test" if mutant.status == "failed" else "unverified"
    detail = ("Verified distinguishing test; this does not establish business requirements."
              if status == "verified_distinguishing_test" else f"Proposed test on mutant: {mutant.status}.")
    return AIResult(status, detail, response_received=True, mutation=mutation,
                    original=original, mutant=mutant, proposal=proposal)


def suggest_and_verify(snapshot: Path, mutation: Mutation, paths: list[str], timeout: float,
                       model: str, endpoint: str) -> AIResult:
    try:
        context = build_context(snapshot, mutation, paths)
    except AIError as exc:
        return AIResult("blocked", str(exc), mutation=mutation)
    try:
        raw = request_proposal(endpoint, model, context)
    except AIError as exc:
        return AIResult("unavailable", str(exc), mutation=mutation)
    try:
        proposal = validate_proposal(raw)
    except AIError as exc:
        return AIResult("invalid_response", str(exc), response_received=True, mutation=mutation)
    return verify_proposal(snapshot, mutation, proposal, timeout)


def analyze_repository(path: Path, paths: list[str], timeout: float = 10,
                       max_mutants: int = 5, ai_model: str | None = None,
                       ai_endpoint: str = "http://127.0.0.1:11434") -> RunReport:
    validate_test_paths(paths)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be positive and finite.")
    if not 1 <= max_mutants <= 5:
        raise ValueError("Select between one and five mutants.")
    inspection = inspect_repository(path)
    with staged_snapshot(inspection) as snapshot:
        baseline = run_snapshot_tests(snapshot, paths, timeout)
        skipped = list(inspection.skipped)
        if baseline.status != "passed":
            ai = AIResult("blocked", "Baseline did not pass.") if ai_model else AIResult()
            return RunReport(inspection, baseline, (), tuple(skipped), ai)
        mutations, discovery_skips = discover_mutations(snapshot, inspection.files)
        skipped.extend(discovery_skips)
        for mutation in mutations[max_mutants:]:
            skipped.append(SkippedFile(mutation.path, f"line {mutation.line}: mutant limit reached"))
        results = tuple(run_mutant_tests(snapshot, mutation, paths, timeout)
                        for mutation in mutations[:max_mutants])
        ai = AIResult()
        if ai_model:
            survivor = next((result.mutation for result in results if result.outcome == "survived"), None)
            ai = (suggest_and_verify(snapshot, survivor, paths, timeout, ai_model, ai_endpoint)
                  if survivor else AIResult("not_needed", "No surviving mutation."))
        return RunReport(inspection, baseline, results, tuple(skipped), ai)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ghost-PR staged Python inspection and mutation analysis")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Inspect staged scope; does not run tests or AI")
    check.add_argument("--repo", type=Path, default=Path.cwd())
    check.add_argument("--json", action="store_true")
    run = commands.add_parser("run", help="Execute tests and mutations in trusted disposable copies")
    run.add_argument("--repo", type=Path, default=Path.cwd())
    run.add_argument("--test", action="append", required=True, help="Relative test path; repeat for multiple paths")
    run.add_argument("--timeout", type=float, default=10)
    run.add_argument("--max-mutants", type=int, choices=range(1, 6), default=5)
    run.add_argument("--json", action="store_true")
    run.add_argument("--ai-model", help="Already-installed local Ollama model; opts into proposed test execution")
    run.add_argument("--ai-endpoint", default="http://127.0.0.1:11434")
    run.add_argument("--show-ai-test", action="store_true", help="Explicitly display validated proposed code and explanation")
    args = parser.parse_args(argv)
    if args.command == "run" and args.show_ai_test and not args.ai_model:
        parser.error("--show-ai-test requires --ai-model")
    try:
        if args.command == "run":
            report = analyze_repository(args.repo, args.test, args.timeout, args.max_mutants,
                                        args.ai_model, args.ai_endpoint)
            if args.json:
                print(json.dumps(analysis_data(report, args.show_ai_test), ensure_ascii=True))
            else:
                print_analysis(report, args.show_ai_test)
            return analysis_exit_code(report)
        result = inspect_repository(args.repo)
    except (RepositoryError, ValueError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(exc)}))
        else:
            print(f"Ghost-PR: {exc}", file=sys.stderr)
        return 2
    except OSError:
        if getattr(args, "json", False):
            print(json.dumps({"error": "Snapshot filesystem operation failed."}))
        else:
            print("Ghost-PR: snapshot filesystem operation failed.", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=True))
    else:
        print_inspection(result)
    return 0
