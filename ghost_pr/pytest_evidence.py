"""Tiny pytest hook module, copied outside the tested snapshot by the runner."""
import json
import os
from pathlib import Path


counts = {"passed": 0, "failed": 0, "errors": 0}


def pytest_collectreport(report):
    if report.failed:
        counts["errors"] += 1


def pytest_runtest_logreport(report):
    if report.when == "call":
        if report.passed:
            counts["passed"] += 1
        elif report.failed:
            counts["failed"] += 1
    elif report.failed:
        counts["errors"] += 1


def pytest_sessionfinish(session, exitstatus):
    evidence = {**counts, "exitstatus": int(exitstatus)}
    Path(os.environ["GHOST_EVIDENCE"]).write_text(json.dumps(evidence))
