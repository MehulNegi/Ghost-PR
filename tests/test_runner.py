"""Real pytest subprocesses exercise outcome and process boundaries."""
import json
from pathlib import Path
import tempfile
import time
import unittest

from ghost_pr.runner import classify_result, run_tests, validate_test_paths


class RunnerTests(unittest.TestCase):
    def test_outcomes(self):
        cases = [
            ("def test_ok(): assert True\n", "passed"),
            ("def test_bad(): assert False\n", "failed"),
            ("x = 1\n", "no_tests"),
            ("import missing_ghost_fixture_module\n", "execution_error"),
            ("import pytest\n@pytest.fixture\ndef broken(): raise ValueError()\ndef test_x(broken): pass\n", "execution_error"),
            ("import time\ndef test_slow(): time.sleep(10)\n", "timeout"),
        ]
        for source, status in cases:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "test_case.py").write_text(source)
                result = run_tests(root, ["test_case.py"], 0.7 if status == "timeout" else 5)
                self.assertEqual(result.status, status, result)

    def test_reject_options_and_traversal(self):
        for paths in ([], ["-x"], ["/tmp/test.py"], ["../test.py"], ["x/../../test.py"]):
            with self.assertRaises(ValueError):
                validate_test_paths(paths)
        validate_test_paths(["tests/test_file.py::test_one"])

    def test_missing_or_inconsistent_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            self.assertEqual(classify_result(path, 1).status, "execution_error")
            path.write_text(json.dumps(dict(passed=0, failed=1, errors=1, exitstatus=1)))
            self.assertEqual(classify_result(path, 1).status, "execution_error")
            path.write_text('[]')
            self.assertEqual(classify_result(path, 0).status, "execution_error")

    def test_process_group_cleanup_on_timeout_and_success(self):
        for timeout, pause, expected in ((0.7, "time.sleep(10)", "timeout"), (5, "pass", "passed")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                marker, ready = root / "escaped.txt", root / "child_started.txt"
                child = (f"import time; open({str(ready)!r}, 'w').write('started'); "
                         f"time.sleep(1.2); open({str(marker)!r}, 'w').write('alive')")
                source = (f"import subprocess, sys, time\nfrom pathlib import Path\ndef test_child():\n"
                          f" subprocess.Popen([sys.executable, '-c', {child!r}])\n"
                          f" while not Path({str(ready)!r}).exists(): time.sleep(0.01)\n {pause}\n")
                (root / "test_child.py").write_text(source)
                self.assertEqual(run_tests(root, ["test_child.py"], timeout).status, expected)
                self.assertTrue(ready.exists(), "child must actually start for cleanup check")
                time.sleep(1.3)
                self.assertFalse(marker.exists())
