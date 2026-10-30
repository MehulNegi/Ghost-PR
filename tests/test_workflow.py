"""Controlled fixture proves baseline and mutant runs are independent."""
from pathlib import Path
import tempfile
import unittest

from ghost_pr.cli import run_mutant_tests, run_snapshot_tests
from ghost_pr.models import ChangedFile
from ghost_pr.mutations import discover_mutations


WITHDRAW = '''def withdraw(balance, amount):
    if amount <= balance:
        return balance - amount
    raise ValueError("Insufficient funds")
'''


class WorkflowTests(unittest.TestCase):
    def test_survivor_then_distinguishing_test(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            (snapshot / "bank.py").write_text(WITHDRAW)
            tests = snapshot / "test_bank.py"
            tests.write_text("from bank import withdraw\ndef test_partial(): assert withdraw(100, 40) == 60\n")
            mutations, _ = discover_mutations(snapshot, (ChangedFile("bank.py", (2,)),))
            baseline = run_snapshot_tests(snapshot, [tests.name], 5)
            self.assertEqual(baseline.status, "passed")
            result = run_mutant_tests(snapshot, mutations[0], [tests.name], 5)
            self.assertEqual(result.outcome, "survived")
            tests.write_text(tests.read_text() + "def test_exact(): assert withdraw(100, 100) == 0\n")
            result = run_mutant_tests(snapshot, mutations[0], [tests.name], 5)
            self.assertEqual(result.outcome, "killed")
            self.assertEqual((snapshot / "bank.py").read_text(), WITHDRAW)
            self.assertFalse((snapshot / "__pycache__").exists())

    def test_mutant_import_error_is_not_killed(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            (snapshot / "feature.py").write_text("if True:\n    value = 1\n")
            (snapshot / "test_code.py").write_text("from feature import value\ndef test_value(): assert value == 1\n")
            mutations, _ = discover_mutations(snapshot, (ChangedFile("feature.py", (1,)),))
            self.assertEqual(run_snapshot_tests(snapshot, ["test_code.py"], 5).status, "passed")
            self.assertEqual(run_mutant_tests(snapshot, mutations[0], ["test_code.py"], 5).outcome, "execution_error")
