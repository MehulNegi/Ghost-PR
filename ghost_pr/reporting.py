"""Present observed results without implying code safety or business correctness."""
from dataclasses import asdict
import json
import sys

from .models import CheckReport, Inspection, RunReport


def print_command_error(message: str, *, json_output: bool, preflight: bool) -> None:
    """Render an already-sanitized message in the existing command-error format."""
    if json_output:
        error = {"error": message}
        if preflight:
            error["complete"] = False
        print(json.dumps(error))
    else:
        print(f"Ghost-PR: {message}", file=sys.stderr)


def check_data(report: CheckReport) -> dict:
    data = asdict(report)
    inspection = data.pop("inspection")
    return {**inspection, **data, "complete": all(check.complete for check in report.checks)}


def check_exit_code(report: CheckReport) -> int:
    if not all(check.complete for check in report.checks):
        return 2
    return 1 if report.findings else 0


def print_check(report: CheckReport) -> None:
    print_inspection(report.inspection)
    for kind, title in (("whitespace", "Whitespace findings"), ("suspected_secret", "Suspected-secret findings")):
        print(f"{title}:")
        findings = [finding for finding in report.findings if finding.kind == kind]
        for finding in findings:
            print(f"  {ascii(finding.path)}:{finding.line} [{finding.rule_id}] {finding.message}")
        if not findings:
            print("  None detected in checked text.")
    print("Check completion and skipped coverage:")
    for check in report.checks:
        state = "complete" if check.complete else "incomplete"
        print(f"  {check.name}: {state}; {check.checked_files} file(s). {check.message}")
        for skipped in check.skipped:
            print(f"    SKIPPED {ascii(skipped.path)}: {skipped.reason}")
    if check_exit_code(report) == 2:
        print("Result: incomplete; required coverage is missing.")
    elif report.findings:
        print(f"Result: {len(report.findings)} finding(s) detected.")
    else:
        print("Result: no findings detected by these checks; this is not a safety verdict.")


def outcome_counts(report: RunReport) -> dict[str, int]:
    counts = dict.fromkeys(("killed", "survived", "timeout", "execution_error"), 0)
    for result in report.mutants:
        counts[result.outcome] += 1
    return counts


def analysis_exit_code(report: RunReport) -> int:
    counts = outcome_counts(report)
    if report.baseline.status != "passed" or counts["timeout"] or counts["execution_error"]:
        return 2
    return 1 if counts["survived"] else 0


def analysis_data(report: RunReport, show_ai_test: bool = False) -> dict:
    counts = outcome_counts(report)
    denominator = counts["killed"] + counts["survived"]
    data = asdict(report)
    if not show_ai_test:
        data["ai"].pop("proposal")
    return {**data, "counts": counts,
            "detection_ratio": counts["killed"] / denominator if denominator else None}


def print_inspection(inspection: Inspection) -> None:
    print("Ghost-PR | staged scope inspection (not a code-safety verdict)")
    for item in inspection.files:
        print(f"  {ascii(item.path)}: changed lines {', '.join(map(str, item.lines))}")
    for item in inspection.skipped:
        print(f"  PYTHON-SCOPE SKIP {ascii(item.path)}: {item.reason}")
    print(f"Python inspection scope: {len(inspection.files)} file(s). Untracked excluded: {inspection.untracked_count}.")
    print("No project code or AI executed.")


def analysis_summary(report: RunReport) -> list[str]:
    counts = outcome_counts(report)
    lines = [f"Summary: baseline {report.baseline.status}; {counts['killed']} killed, {counts['survived']} survived."]
    if counts["timeout"] or counts["execution_error"]:
        lines.append(f"Excluded outcomes: {counts['timeout']} timeout(s), {counts['execution_error']} execution error(s).")
    if report.skipped or report.inspection.untracked_count:
        lines.append(f"Skipped coverage: {len(report.skipped)} recorded skip(s), {report.inspection.untracked_count} untracked file(s).")
    if report.baseline.status == "passed" and not report.mutants:
        lines.append("No mutants were evaluated; this provides no mutation-detection evidence.")
    if report.ai.status == "verified_distinguishing_test":
        lines.append("AI proposal verified: its test passed on the original and failed on the mutant.")
    elif report.ai.status == "not_requested":
        lines.append("AI was not requested.")
    else:
        lines.append(f"AI was requested; no verified proposal ({report.ai.status}).")
    export = report.export
    if export.status == "exported":
        lines.append(f"Verified test exported to {ascii(export.path)}.")
    elif export.status == "not_requested":
        lines.append("Test export was not requested.")
    else:
        lines.append(f"Test export {export.status}: {export.detail}")
    if report.baseline.status != "passed":
        next_action = "Resolve the baseline outcome before mutation analysis."
    elif counts["timeout"] or counts["execution_error"]:
        next_action = "Resolve incomplete execution outcomes and rerun analysis."
    elif export.status == "error":
        next_action = "Inspect the export failure and any partial file; retry with an unused writable .py path."
    elif export.status == "exported":
        next_action = "Review the saved test before adopting and staging it; then rerun analysis."
    elif report.ai.status == "verified_distinguishing_test":
        next_action = "Review the proposed test; request --export-test on a new AI run to save a verified proposal."
    elif counts["survived"]:
        next_action = "Review surviving mutations and AI outcomes, if requested; add a relevant test and rerun."
    elif not report.mutants:
        next_action = "Review staged scope and skip reasons before drawing conclusions."
    else:
        next_action = "All evaluated mutants were killed; review detailed evidence and skipped scope."
    lines.append(f"Next: {next_action}")
    return lines


def print_analysis(report: RunReport, show_ai_test: bool = False) -> None:
    counts = outcome_counts(report)
    denominator = counts["killed"] + counts["survived"]
    ratio = f"{counts['killed']}/{denominator}" if denominator else "N/A"
    print("Ghost-PR | staged mutation analysis")
    print(f"Pinned tree: {report.inspection.tree}")
    print(f"Baseline: {report.baseline.status} (passed={report.baseline.passed}, failed={report.baseline.failed}, errors={report.baseline.errors})")
    if report.baseline.status != "passed":
        print("Mutation testing blocked by baseline outcome.")
    print(f"Mutants attempted: {len(report.mutants)}")
    print("  " + ", ".join(f"{name}={value}" for name, value in counts.items()))
    print(f"Detection ratio: {ratio}; timeouts and execution errors excluded.")
    for result in report.mutants:
        mutation = result.mutation
        print(f"  {result.outcome}: {ascii(mutation.path)}:{mutation.line}:{mutation.column + 1} ({mutation.operator})")
        print(f"    {ascii(mutation.before)} -> {ascii(mutation.after)}")
    for item in report.skipped:
        print(f"  SKIPPED {ascii(item.path)}: {item.reason}")
    print(f"Untracked files excluded: {report.inspection.untracked_count}")
    print(f"AI: {report.ai.status}; model response received: {report.ai.response_received}")
    if report.ai.detail:
        print(f"  {report.ai.detail}")
    if show_ai_test and report.ai.proposal is not None:
        print(f"  Explanation: {ascii(report.ai.proposal.explanation)}")
        print("  Proposed code (escaped lines):")
        for line in report.ai.proposal.test_code.splitlines():
            print(f"    {ascii(line)}")
    print("Survivors may be equivalent, outside exercised paths, or reveal missing assertions.")
    print("\n" + "\n".join(analysis_summary(report)))
