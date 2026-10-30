"""Recorded proposals are test fixtures, not evidence of live local inference."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from git_fixture import GitFixture
from ghost_pr.cli import analyze_repository, verify_proposal
from ghost_pr.local_ai import AIError
from ghost_pr.models import ChangedFile, TestProposal
from ghost_pr.mutations import discover_mutations
from ghost_pr.reporting import analysis_data, analysis_exit_code
from test_workflow import WITHDRAW


RECORDED_TEST = "from bank import withdraw\ndef test_exact(): assert withdraw(100, 100) == 0\n"


class VerificationTests(unittest.TestCase):
    def test_both_directions_and_original_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            (snapshot / "bank.py").write_text(WITHDRAW)
            partial_test = "from bank import withdraw\ndef test_partial(): assert withdraw(100, 40) == 60\n"
            (snapshot / "test_bank.py").write_text(partial_test)
            mutations, _ = discover_mutations(snapshot, (ChangedFile("bank.py", (2,)),))
            for code, expected, original, mutant in (
                    (RECORDED_TEST, "verified_distinguishing_test", "passed", "failed"),
                    ("def test_bad(): assert False\n", "unverified", "failed", None),
                    (partial_test, "unverified", "passed", "passed"),
                    ("import missing_ghost_fixture\ndef test_x(): pass\n", "unverified", "execution_error", None)):
                with self.subTest(expected=expected, original=original, mutant=mutant):
                    # An explanation claiming equality cannot verify an unequal-input test.
                    result = verify_proposal(snapshot, mutations[0], TestProposal("Equality distinguishes the versions.", code), 5)
                    self.assertEqual(result.status, expected)
                    self.assertEqual(result.original.status, original)
                    self.assertEqual(result.mutant.status if result.mutant else None, mutant)
            self.assertEqual((snapshot / "bank.py").read_text(), WITHDRAW)
            self.assertEqual((snapshot / "test_bank.py").read_text(), partial_test)
            self.assertFalse((snapshot / "test_ghost_proposed.py").exists())
            (snapshot / "test_ghost_proposed.py").write_text("existing")
            result = verify_proposal(snapshot, mutations[0], TestProposal("Recorded fixture", RECORDED_TEST), 5)
            self.assertEqual(result.status, "unverified")
            self.assertEqual((snapshot / "test_ghost_proposed.py").read_text(), "existing")


class AIWorkflowTests(GitFixture):
    def test_optional_unavailable_malformed_and_recorded_response(self):
        self.stage("bank.py", WITHDRAW)
        self.stage("test_bank.py", "from bank import withdraw\ndef test_partial(): assert withdraw(100, 40) == 60\n")
        before = self.git("ls-files", "--stage", "-z")
        with patch("ghost_pr.cli.request_proposal", side_effect=AssertionError("AI must be optional")):
            report = analyze_repository(self.root, ["test_bank.py"])
        self.assertEqual(report.ai.status, "not_requested")
        with patch("ghost_pr.cli.request_proposal", side_effect=AIError("Runner unavailable")):
            report = analyze_repository(self.root, ["test_bank.py"], ai_model="demo:latest")
        self.assertEqual(report.ai.status, "unavailable")
        self.assertEqual(analysis_exit_code(report), 1)
        with patch("ghost_pr.cli.request_proposal", return_value="not JSON"):
            report = analyze_repository(self.root, ["test_bank.py"], ai_model="demo:latest")
        self.assertEqual(report.ai.status, "invalid_response")
        recorded = json.dumps({"explanation": "Recorded exact-balance example", "test_code": RECORDED_TEST})
        with patch("ghost_pr.cli.request_proposal", return_value=recorded):
            report = analyze_repository(self.root, ["test_bank.py"], ai_model="demo:latest")
        self.assertEqual(report.ai.status, "verified_distinguishing_test")
        self.assertNotIn("proposal", analysis_data(report)["ai"])
        self.assertEqual(analysis_data(report, True)["ai"]["proposal"]["test_code"], RECORDED_TEST)
        self.assertFalse((self.root / "test_ghost_proposed.py").exists())
        self.assertEqual(before, self.git("ls-files", "--stage", "-z"))
