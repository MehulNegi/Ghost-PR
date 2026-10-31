"""Parse commands and orchestrate inspection, independent runs and optional AI."""
import argparse
from dataclasses import replace
import json
import math
from pathlib import Path
import shutil
import tempfile

from .exporting import export_verified_test
from .local_ai import AIError, build_context, request_proposal, validate_proposal
from .models import AIResult, Mutation, MutationResult, RunReport, SkippedFile, TestProposal, TestRun
from .mutations import discover_mutations, generate_mutant, read_python
from .preflight import check_repository
from .repository import RepositoryError, inspect_repository, staged_snapshot
from .reporting import (
    analysis_data, analysis_exit_code, check_data, check_exit_code,
    print_analysis, print_check, print_command_error,
)
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


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate command options without inspecting a repository."""
    parser = argparse.ArgumentParser(description="Scan your changes. Haunt your tests.")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("scan", aliases=["check"],
                                help="Inspect staged scope, whitespace and suspected credentials; no tests or AI (check is a compatibility alias)")
    # Preserve the existing preflight dispatch and error handling for both names.
    check.set_defaults(command="check")
    check.add_argument("--repo", type=Path, default=Path.cwd())
    check.add_argument("--json", action="store_true")
    haunt = commands.add_parser("haunt", aliases=["run"],
                                help="Execute tests and mutations in trusted copies (run is a compatibility alias)")
    haunt.set_defaults(command="haunt")
    haunt.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository path (default: current directory)")
    haunt.add_argument("--test", action="append", required=True, help="Relative test path; repeat for multiple paths")
    haunt.add_argument("--timeout", type=float, default=10)
    haunt.add_argument("--max-mutants", type=int, choices=range(1, 6), default=5)
    haunt.add_argument("--json", action="store_true")
    haunt.add_argument("--ai", action="store_true",
                       help="Enable local AI with qwen2.5-coder:3b at http://127.0.0.1:11434")
    haunt.add_argument("--ai-model", help="Enable AI with an installed Ollama model (overrides --ai model)")
    haunt.add_argument("--ai-endpoint", default="http://127.0.0.1:11434",
                       help="Local Ollama URL (default: http://127.0.0.1:11434; overrides --ai endpoint)")
    haunt.add_argument("--show-ai-test", action="store_true", help="Explicitly display validated proposed code and explanation")
    haunt.add_argument("--export-test", type=Path,
                       help="Exclusively write a verified AI test to a new .py file; requires AI")
    args = parser.parse_args(argv)
    if args.command == "haunt":
        if args.ai and args.ai_model is None:
            args.ai_model = "qwen2.5-coder:3b"
        if args.export_test is not None and not args.ai_model:
            parser.error("--export-test requires --ai or --ai-model")
        if args.show_ai_test and not args.ai_model:
            parser.error("--show-ai-test requires --ai or --ai-model")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    try:
        if args.command == "haunt":
            report = analyze_repository(args.repo, args.test, args.timeout, args.max_mutants,
                                        args.ai_model, args.ai_endpoint)
            if args.export_test is not None:
                report = replace(report, export=export_verified_test(report.ai, args.export_test))
            if args.json:
                print(json.dumps(analysis_data(report, args.show_ai_test), ensure_ascii=True))
            else:
                print_analysis(report, args.show_ai_test)
            if args.export_test is not None and report.export.status != "exported":
                return 2
            return analysis_exit_code(report)
        result = check_repository(args.repo)
    except (RepositoryError, ValueError) as exc:
        print_command_error(str(exc), json_output=args.json, preflight=args.command == "check")
        return 2
    except OSError:
        message = "Check filesystem operation failed." if args.command == "check" else "Snapshot filesystem operation failed."
        print_command_error(message, json_output=args.json, preflight=args.command == "check")
        return 2
    if args.json:
        print(json.dumps(check_data(result), ensure_ascii=True))
    else:
        print_check(result)
    return check_exit_code(result)
