"""CLI boundary checks leave Git/pytest execution to the integration tests."""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ghost_pr.cli import main
from ghost_pr.models import CheckReport, CheckStatus, Inspection, Mutation, MutationResult, RunReport, TestRun


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.inspection = Inspection("/fixture", (), (), 0, "a" * 40)
        self.report = RunReport(self.inspection, TestRun("passed", 0, passed=1), (), ())

    def test_aliases_share_routing_and_exit_codes(self):
        mutation = Mutation("feature.py", 1, 0, "Constant", "True to False", "True", "False")
        survivor = MutationResult(mutation, "survived", TestRun("passed", 0, passed=1))
        cases = ((self.report, 0), (replace(self.report, mutants=(survivor,)), 1),
                 (replace(self.report, baseline=TestRun("failed", 1, failed=1)), 2))
        paths = ["tests/test_feature.py::test_one", "tests/test_other.py"]
        for command in ("haunt", "run"):
            for report, expected in cases:
                with self.subTest(command=command, expected=expected):
                    output = io.StringIO()
                    with patch("ghost_pr.cli.analyze_repository", return_value=report) as analyze, redirect_stdout(output):
                        code = main([command, "--test", paths[0], "--test", paths[1],
                                     "--timeout", "3.5", "--max-mutants", "2", "--json"])
                    self.assertEqual(code, expected)
                    analyze.assert_called_once_with(Path.cwd(), paths, 3.5, 2, None,
                                                    "http://127.0.0.1:11434")
                    self.assertEqual(json.loads(output.getvalue())["baseline"]["status"], report.baseline.status)

    def test_preflight_aliases_stay_on_preflight_path(self):
        report = CheckReport(self.inspection, (), (CheckStatus("whitespace", True, 0),
                                                 CheckStatus("suspected_secret", True, 0)))
        for command in ("scan", "check"):
            with self.subTest(command=command):
                with patch("ghost_pr.cli.check_repository", return_value=report) as check:
                    with patch("ghost_pr.cli.analyze_repository") as analyze, redirect_stdout(io.StringIO()):
                        self.assertEqual(main([command, "--json"]), 0)
                check.assert_called_once_with(Path.cwd())
                analyze.assert_not_called()

    def test_preflight_help_is_shared(self):
        outputs = []
        for command in ("scan", "check"):
            output = io.StringIO()
            with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
                main([command, "--help"])
            self.assertEqual(raised.exception.code, 0)
            self.assertIn("--repo", output.getvalue())
            self.assertIn("--json", output.getvalue())
            self.assertNotIn("--test", output.getvalue())
            self.assertNotIn("--ai", output.getvalue())
            outputs.append(output.getvalue())
        self.assertEqual(outputs[0], outputs[1])

    def test_ai_shorthand_respects_explicit_overrides(self):
        default_model = "qwen2.5-coder:3b"
        default_endpoint = "http://127.0.0.1:11434"
        custom_endpoint = "http://localhost:12000"
        cases = (
            (["--ai"], default_model, default_endpoint),
            (["--ai", "--show-ai-test"], default_model, default_endpoint),
            (["--ai-model", "other:tag", "--show-ai-test"], "other:tag", default_endpoint),
            (["--ai", "--ai-model", "other:tag"], "other:tag", default_endpoint),
            (["--ai-model", "other:tag", "--ai"], "other:tag", default_endpoint),
            (["--ai", "--ai-endpoint", custom_endpoint], default_model, custom_endpoint),
            (["--ai-endpoint", custom_endpoint], None, custom_endpoint),
            (["--ai", "--ai-model", "other:tag", "--ai-endpoint", custom_endpoint], "other:tag", custom_endpoint),
        )
        for command in ("haunt", "run"):
            for options, model, endpoint in cases:
                with self.subTest(command=command, options=options):
                    with patch("ghost_pr.cli.analyze_repository", return_value=self.report) as analyze:
                        with redirect_stdout(io.StringIO()):
                            self.assertEqual(main([command, "--repo", "/fixture", "--test", "tests", *options]), 0)
                    analyze.assert_called_once_with(Path("/fixture"), ["tests"], 10, 5, model, endpoint)

    def test_show_ai_test_requires_enabling_ai(self):
        for command in ("haunt", "run"):
            with self.subTest(command=command), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main([command, "--test", "tests", "--show-ai-test"])
                self.assertEqual(raised.exception.code, 2)

    def test_test_selection_is_still_required(self):
        for command in ("haunt", "run"):
            with self.subTest(command=command), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main([command])
                self.assertEqual(raised.exception.code, 2)

    def test_help_lists_primary_command_and_alias(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("haunt (run)", output.getvalue())
        self.assertIn("scan (check)", output.getvalue())
        self.assertIn("Scan your changes. Haunt your tests.", output.getvalue())
        self.assertIn("compatibility alias", output.getvalue())
