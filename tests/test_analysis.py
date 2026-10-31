"""End-to-end orchestration runs only controlled, staged fixture code."""
from unittest.mock import patch
from contextlib import redirect_stdout
import io
import json

from git_fixture import GitFixture
from ghost_pr.cli import analyze_repository, main
from ghost_pr.models import MutationResult, TestRun
from ghost_pr.reporting import analysis_exit_code


class AnalysisTests(GitFixture):
    def test_mutant_execution_error_takes_precedence_over_survivor(self):
        self.stage("feature.py", "def value(): return True, False\n")
        self.stage("test_feature.py", "from feature import value\ndef test_value(): assert len(value()) == 2\n")
        def recorded_outcome(snapshot, mutation, paths, timeout):
            if mutation.before == "True":
                return MutationResult(mutation, "survived", TestRun("passed", 0, passed=1))
            return MutationResult(mutation, "execution_error", TestRun("execution_error", 2, errors=1))
        with patch("ghost_pr.cli.run_mutant_tests", side_effect=recorded_outcome):
            report = analyze_repository(self.root, ["test_feature.py"])
        self.assertEqual(analysis_exit_code(report), 2)

    def test_json_report_survivor_and_blocked_baseline(self):
        self.stage("feature.py", "def value(): return True\n")
        self.stage("test_feature.py", "from feature import value\ndef test_value(): assert isinstance(value(), bool)\n")
        args = ["run", "--repo", str(self.root), "--test", "test_feature.py", "--json"]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 1)
        data = json.loads(output.getvalue())
        self.assertEqual(data["counts"]["survived"], 1)
        self.assertEqual(data["detection_ratio"], 0)
        self.assertEqual(data["mutants"][0]["mutation"]["before"], "True")
        self.stage("test_feature.py", "x = 1\n")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 2)
        data = json.loads(output.getvalue())
        self.assertEqual(data["baseline"]["status"], "no_tests")
        self.assertIsNone(data["detection_ratio"])

    def test_terminal_report_and_exit_codes(self):
        self.stage("feature.py", "def value(): return True\n")
        for test, expected in (("assert isinstance(value(), bool)", 1),
                               ("assert value() is True", 0), ("assert False", 2)):
            self.stage("test_feature.py", f"from feature import value\ndef test_value(): {test}\n")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["run", "--repo", str(self.root), "--test", "test_feature.py"])
            self.assertEqual(code, expected, output.getvalue())
            self.assertIn("Baseline", output.getvalue())
            self.assertIn("Detection ratio:", output.getvalue())
            self.assertIn("AI not requested", output.getvalue())
            alias_output = io.StringIO()
            with redirect_stdout(alias_output):
                alias_code = main(["haunt", "--repo", str(self.root), "--test", "test_feature.py"])
            self.assertEqual(alias_code, expected)
            self.assertEqual(alias_output.getvalue(), output.getvalue())

    def test_cap_independence_and_original_preservation(self):
        source = "def flags():\n    return [True, True, True, True, True, True]\n"
        self.stage("feature.py", source)
        # A cumulative second mutation would make this assertion fail.
        self.stage("test_feature.py", "from feature import flags\ndef test_flags(): assert sum(flags()) >= 5\n")
        before = self.git("ls-files", "--stage", "-z")
        index_bytes = (self.root / ".git/index").read_bytes()
        report = analyze_repository(self.root, ["test_feature.py"])
        self.assertEqual(report.baseline.status, "passed")
        self.assertEqual(len(report.mutants), 5)
        self.assertEqual([m.outcome for m in report.mutants], ["survived"] * 5)
        self.assertTrue(any("limit" in s.reason for s in report.skipped))
        self.assertEqual((self.root / "feature.py").read_text(), source)
        self.assertEqual(before, self.git("ls-files", "--stage", "-z"))
        self.assertEqual(index_bytes, (self.root / ".git/index").read_bytes())

    def test_failed_baseline_stops_discovery(self):
        self.stage("test_bad.py", "def test_bad(): assert False\n")
        with patch("ghost_pr.cli.discover_mutations", side_effect=AssertionError("must not discover")):
            report = analyze_repository(self.root, ["test_bad.py"])
        self.assertEqual(report.baseline.status, "failed")
        self.assertEqual(report.mutants, ())
