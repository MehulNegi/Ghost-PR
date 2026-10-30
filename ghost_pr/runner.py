"""Execute explicitly selected tests in a disposable, trusted project copy."""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from .models import TestRun


def validate_test_paths(paths: list[str]) -> None:
    if not paths:
        raise ValueError("Select at least one test path with --test.")
    for value in paths:
        path = value.split("::", 1)[0]
        if not path or path.startswith("-") or Path(path).is_absolute() or ".." in Path(path).parts:
            raise ValueError("Test paths must be relative paths without options or parent traversal.")


def run_tests(directory: Path, paths: list[str], timeout: float) -> TestRun:
    """Discard console output; retain only bounded pytest outcome evidence."""
    validate_test_paths(paths)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be positive and finite.")
    if sys.platform not in ("darwin", "linux"):
        return TestRun("execution_error", None)
    with tempfile.TemporaryDirectory(prefix="ghost-runner-") as control:
        control_path = Path(control)
        plugin = Path(__file__).with_name("pytest_evidence.py")
        (control_path / "ghost_evidence.py").write_bytes(plugin.read_bytes())
        evidence = control_path / "result.json"
        env = os.environ.copy()
        # Avoid importing the contributor's working tree or ambient pytest plugins.
        env["PYTHONPATH"] = control
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        env["PYTEST_ADDOPTS"] = ""
        env.pop("PYTEST_PLUGINS", None)
        env["GHOST_EVIDENCE"] = str(evidence)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        command = [sys.executable, "-m", "pytest", "-p", "ghost_evidence",
                   "-p", "no:cacheprovider", "-o", "addopts=", "-q", "--", *paths]
        try:
            process = subprocess.Popen(command, cwd=directory, env=env,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            return TestRun("execution_error", None)
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return TestRun("timeout", None)
        finally:
            # Also reap descendants left by a successful parent in this session.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        return classify_result(evidence, returncode)


def classify_result(evidence: Path, returncode: int) -> TestRun:
    if not evidence.exists() or evidence.stat().st_size > 16_384:
        return TestRun("execution_error", returncode)
    try:
        data = json.loads(evidence.read_text())
    except (OSError, ValueError, RecursionError):
        return TestRun("execution_error", returncode)
    if not isinstance(data, dict) or any(type(data.get(key)) is not int or data[key] < 0
                                         for key in ("passed", "failed", "errors", "exitstatus")):
        return TestRun("execution_error", returncode)
    passed, failed, errors = data["passed"], data["failed"], data["errors"]
    status = "execution_error"
    if data["exitstatus"] == returncode and not errors:
        if returncode == 0 and passed and not failed:
            status = "passed"
        elif returncode == 1 and failed:
            status = "failed"
        elif returncode in (0, 5) and not passed and not failed:
            status = "no_tests"
    return TestRun(status, returncode, passed, failed, errors)
