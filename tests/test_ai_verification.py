"""Recorded proposals are test fixtures, not evidence of live local inference."""
import json
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from git_fixture import GitFixture
from ghost_pr.cli import analyze_repository, main, verify_proposal
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
    def setUp(self):
        super().setUp()
        self.stage("bank.py", WITHDRAW)
        self.stage("test_bank.py", "from bank import withdraw\ndef test_partial(): assert withdraw(100, 40) == 60\n")

    def test_export_cli_preserves_analysis_index_and_files(self):
        recorded = json.dumps({"explanation": "Recorded fixture", "test_code": RECORDED_TEST})
        target = self.root / "test_boundary.py"
        index = (self.root / ".git/index").read_bytes()
        files = {name: (self.root / name).read_bytes() for name in ("bank.py", "test_bank.py")}
        results = []
        for command, ai in (("haunt", ["--ai"]), ("run", ["--ai-model", "demo:latest"])):
            output = io.StringIO()
            with tempfile.TemporaryDirectory() as workspace:
                with patch("tempfile.tempdir", workspace), patch("ghost_pr.cli.request_proposal", return_value=recorded), redirect_stdout(output):
                    code = main([command, "--repo", str(self.root), "--test", "test_bank.py",
                                 *ai, "--export-test", str(target), "--json"])
                self.assertEqual(list(Path(workspace).iterdir()), [])
            data = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertEqual(data["ai"]["status"], "verified_distinguishing_test")
            self.assertEqual(data["ai"]["original"]["status"], "passed")
            self.assertEqual(data["ai"]["mutant"]["status"], "failed")
            self.assertEqual(data["export"]["status"], "exported")
            self.assertEqual(data["detection_ratio"], 0)
            self.assertNotIn("proposal", data["ai"])
            self.assertNotIn(RECORDED_TEST, output.getvalue())
            self.assertEqual(target.read_bytes(), RECORDED_TEST.encode())
            self.assertEqual(self.git("ls-files", "--others", "--exclude-standard").strip(), b"test_boundary.py")
            self.assertEqual((self.root / ".git/index").read_bytes(), index)
            for name, contents in files.items():
                self.assertEqual((self.root / name).read_bytes(), contents)
            results.append(data)
            target.unlink()
        self.assertEqual(results[0], results[1])
        target.write_text("existing")
        with patch("ghost_pr.cli.request_proposal", return_value=recorded), redirect_stdout(io.StringIO()) as output:
            code = main(["haunt", "--repo", str(self.root), "--test", "test_bank.py", "--ai",
                         "--export-test", str(target), "--json"])
        data = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(data["export"]["status"], "error")
        self.assertEqual(data["ai"]["status"], "verified_distinguishing_test")
        self.assertEqual(target.read_text(), "existing")

    def test_requested_export_refuses_unverified_and_unavailable(self):
        partial = (self.root / "test_bank.py").read_text()
        cases = ((AIError("Unavailable"), "unavailable"), ("not JSON", "invalid_response"),
                 (json.dumps({"explanation": "Recorded repeated test", "test_code": partial}), "unverified"))
        for response, status in cases:
            target = self.root / "test_boundary.py"
            options = {"side_effect": response} if isinstance(response, AIError) else {"return_value": response}
            with patch("ghost_pr.cli.request_proposal", **options), redirect_stdout(io.StringIO()) as output:
                code = main(["haunt", "--repo", str(self.root), "--test", "test_bank.py", "--ai",
                             "--export-test", str(target), "--json"])
            data = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(data["ai"]["status"], status)
            self.assertEqual(data["export"]["status"], "not_exported")
            self.assertFalse(target.exists())

    def test_failed_baseline_retains_results_and_does_not_export(self):
        self.stage("test_bank.py", "def test_failure(): assert False\n")
        target = self.root / "test_boundary.py"
        with patch("ghost_pr.cli.request_proposal") as request, redirect_stdout(io.StringIO()) as output:
            code = main(["haunt", "--repo", str(self.root), "--test", "test_bank.py", "--ai",
                         "--export-test", str(target), "--json"])
        data = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(data["baseline"]["status"], "failed")
        self.assertEqual(data["mutants"], [])
        self.assertEqual(data["ai"]["status"], "blocked")
        self.assertEqual(data["export"]["status"], "not_exported")
        self.assertFalse(target.exists())
        request.assert_not_called()

    def test_optional_unavailable_malformed_and_recorded_response(self):
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
