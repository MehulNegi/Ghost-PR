"""Present observed results without implying code safety or business correctness."""
from dataclasses import asdict

from .models import Inspection, RunReport


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
        print(f"  SKIPPED {ascii(item.path)}: {item.reason}")
    print(f"Reviewed scope: {len(inspection.files)} Python file(s). Untracked excluded: {inspection.untracked_count}.")
    print("Inspection only; no project code or AI executed.")


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
