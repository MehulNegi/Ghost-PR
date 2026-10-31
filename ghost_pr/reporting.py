"""Present observed results without implying code safety or business correctness."""
from dataclasses import asdict
import json
import sys

from .models import CheckReport, Inspection, RunReport


def terminal_text(value: str) -> str:
    """Keep untrusted text on one line, escaping control and non-ASCII characters."""
    return ascii(value)[1:-1]


def print_readable(text: str = "") -> None:
    """Use plain status words if stdout cannot encode our fixed symbols."""
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(encoding)
    except UnicodeEncodeError:
        for symbol, plain in (("✓", "PASS"), ("✗", "FAIL"), ("–", "-"),
                              ("•", "INFO"), ("·", "|"), ("→", "->")):
            text = text.replace(symbol, plain)
    print(text)


def print_command_error(message: str, *, json_output: bool, preflight: bool) -> None:
    """Render an already-sanitized message in the existing command-error format."""
    if json_output:
        error = {"error": message}
        if preflight:
            error["complete"] = False
        print(json.dumps(error))
    else:
        print(f"Ghost-PR: {terminal_text(message)}", file=sys.stderr)


def check_data(report: CheckReport) -> dict:
    data = asdict(report)
    inspection = data.pop("inspection")
    return {**inspection, **data, "complete": all(check.complete for check in report.checks)}


def check_exit_code(report: CheckReport) -> int:
    if not all(check.complete for check in report.checks):
        return 2
    return 1 if report.findings else 0


def print_check(report: CheckReport) -> None:
    print_readable("Ghost-PR · Scan\nScan your changes. Haunt your tests.\n")
    print_inspection(report.inspection)
    states = {check.name: check for check in report.checks}
    for kind, title in (("whitespace", "Whitespace"), ("suspected_secret", "Suspected secrets")):
        findings = [finding for finding in report.findings if finding.kind == kind]
        complete = states[kind].complete
        symbol = "✗" if findings else "✓" if complete else "!"
        print_readable(f"\n{symbol} {title} · {len(findings)} finding(s)")
        if not complete:
            print_readable("  Check incomplete; coverage is missing.")
        for finding in findings:
            print_readable(f"  {terminal_text(finding.path)}:{finding.line}")
            print_readable(f"    [{terminal_text(finding.rule_id)}] {terminal_text(finding.message)}")
        if not findings:
            print_readable("  None detected in checked text.")
    code = check_exit_code(report)
    print_readable("\n! Checks incomplete" if code == 2 else f"\n✓ {len(report.checks)} checks completed")
    for check in report.checks:
        state = "complete" if check.complete else "incomplete"
        print_readable(f"  {terminal_text(check.name)}: {state} · {check.checked_files} file(s) checked")
        if check.message:
            print_readable(f"    {terminal_text(check.message)}")
        for skipped in check.skipped:
            print_readable(f"    – Preflight skipped {terminal_text(skipped.path)}: {terminal_text(skipped.reason)}")
    if code == 2:
        print_readable(f"\nResult: incomplete · {len(report.findings)} finding(s) recorded · exit 2")
    elif report.findings:
        print_readable(f"\nResult: {len(report.findings)} finding(s) · exit 1")
    else:
        print_readable("\nResult: no findings detected · exit 0")
    print_readable("These checks are not a safety verdict.\nNo project code or AI executed.")


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
    print_readable("✓ Inspection completed")
    print_readable(f"  Python scope: {len(inspection.files)} file(s)")
    print_readable(f"  Untracked excluded: {inspection.untracked_count}")
    for item in inspection.files:
        print_readable(f"  {terminal_text(item.path)}: changed lines {', '.join(map(str, item.lines))}")
    if inspection.skipped:
        print_readable(f"  Python-scope exclusions: {len(inspection.skipped)} record(s); separate from preflight coverage")
        for item in inspection.skipped:
            print_readable(f"    – Skipped {terminal_text(item.path)}: {terminal_text(item.reason)}")


def analysis_summary(report: RunReport) -> list[str]:
    counts = outcome_counts(report)
    export = report.export
    lines = ["Mutation results are not an overall safety verdict."]
    if counts["survived"]:
        lines.append("Survivors are not automatically confirmed bugs; they may be equivalent or outside exercised paths.")
    if report.ai.status == "verified_distinguishing_test":
        lines.append("AI verification and export have not changed the original suite; adoption and rerunning are still required.")
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
    print_readable("Ghost-PR · Haunt\n")
    baseline = report.baseline
    symbol = "✓" if baseline.status == "passed" else "✗" if baseline.status == "failed" else "!"
    print_readable(f"{symbol} Baseline · {terminal_text(baseline.status)} · {baseline.passed} passed, {baseline.failed} failed, {baseline.errors} errors")
    print_readable(f"  Snapshot: {terminal_text(report.inspection.tree[:12])}")
    if baseline.status != "passed":
        print_readable("  Stop: mutation testing blocked by baseline outcome.")
    print_readable()
    if baseline.status != "passed":
        print_readable("• Mutation results · not run")
    elif not report.mutants:
        print_readable("• No supported mutation candidates")
        print_readable("  No mutants were evaluated; this provides no mutation-detection evidence.")
    else:
        symbol = "!" if counts["survived"] or counts["timeout"] or counts["execution_error"] else "✓"
        print_readable(f"{symbol} Mutation results · {counts['killed']} killed, {counts['survived']} survived")
    print_readable(f"  Mutants attempted: {len(report.mutants)}")
    print_readable(f"  Timeouts: {counts['timeout']} · Execution errors: {counts['execution_error']}")
    print_readable(f"  Detection ratio: {ratio}; timeouts and execution errors excluded.")
    for result in report.mutants:
        mutation = result.mutation
        symbol = "✓" if result.outcome == "killed" else "!"
        print_readable(f"  {symbol} {terminal_text(mutation.path)}:{mutation.line}:{mutation.column + 1} · {terminal_text(result.outcome.upper())}")
        print_readable(f"    {terminal_text(mutation.before)} → {terminal_text(mutation.after)} ({terminal_text(mutation.operator)})")
    print_readable(f"\n• Mutation scope · {len(report.inspection.files)} Python file(s)")
    print_readable(f"  Untracked excluded: {report.inspection.untracked_count}")
    if report.skipped:
        paths = {item.path for item in report.skipped}
        print_readable(f"  {len(report.skipped)} skip record(s) across {len(paths)} path(s)")
        print_readable("  Mutation skips do not exclude files from test execution.")
        for item in report.skipped:
            print_readable(f"  – Skipped {terminal_text(item.path)}: {terminal_text(item.reason)}")
    ai = report.ai
    print_readable()
    if ai.status == "verified_distinguishing_test":
        print_readable("✓ AI proposal verified")
        print_readable("  Passed on original · Failed on mutant")
    elif ai.status == "not_requested":
        print_readable("• AI not requested")
    elif ai.status == "not_needed":
        print_readable("• AI requested · no surviving mutation")
    else:
        print_readable(f"! AI proposal not verified · {terminal_text(ai.status)}")
    if ai.status != "not_requested":
        print_readable(f"  Model response received: {ai.response_received}")
    if ai.detail:
        print_readable(f"  {terminal_text(ai.detail)}")
    for label, tests in (("Original", ai.original), ("Mutant", ai.mutant)):
        if tests is not None:
            print_readable(f"  {label}: {terminal_text(tests.status)} · {tests.passed} passed, {tests.failed} failed, {tests.errors} errors")
    if show_ai_test and ai.proposal is not None:
        print_readable(f"  Explanation: {terminal_text(ai.proposal.explanation)}")
        print_readable("  Proposed code (escaped lines):")
        for line in ai.proposal.test_code.splitlines():
            print_readable(f"    {terminal_text(line)}")
    export = report.export
    print_readable()
    if export.status == "exported":
        print_readable("✓ Verified test exported")
    elif export.status == "not_requested":
        print_readable("• Test export not requested")
    else:
        print_readable(f"✗ Test export not performed · {terminal_text(export.status)}")
        print_readable(f"  {terminal_text(export.detail)}")
    if export.path is not None:
        print_readable(f"  {terminal_text(export.path)}")
    print_readable("\n" + "\n".join(analysis_summary(report)))
