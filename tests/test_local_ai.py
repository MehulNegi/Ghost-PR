"""Recorded protocol responses exercise the HTTP boundary; never live AI."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ghost_pr.local_ai import (AIError, MAX_RESPONSE, build_context, local_address,
                               request_json, request_proposal, validate_proposal)
from ghost_pr.models import ChangedFile
from ghost_pr.mutations import discover_mutations


LOCAL_MODEL = {"models": [{"name": "demo:latest", "size": 100,
                           "details": {"format": "gguf"}}]}


class AdapterTests(unittest.TestCase):
    def test_proposal_validation(self):
        recorded = {"explanation": "Recorded boundary example", "test_code": "from bank import withdraw\ndef test_exact(): assert withdraw(100, 100) == 0\n"}
        self.assertIn("test_exact", validate_proposal(json.dumps(recorded)).test_code)
        invalid = ["not json", "[]", "{}", "[" * 1200 + "]" * 1200,
                   json.dumps({**recorded, "shell": "echo x"}),
                   json.dumps({**recorded, "explanation": "\ud800"})]
        for code in ("def ?", "x = 1", "def test_x(arg): pass", "@mark\ndef test_x(): pass", "def test_x(): pass\ndef test_y(): pass",
                     "import subprocess\ndef test_x(): subprocess.run(['echo', 'fixture'])",
                     "def test_x(): exec('pass')"):
            invalid.append(json.dumps({**recorded, "test_code": code}))
        invalid.append(json.dumps({**recorded, "explanation": "x" * 2049}))
        for raw in invalid:
            with self.subTest(raw=raw[:40]), self.assertRaises(AIError):
                validate_proposal(raw)

    def test_context_minimal_and_screened(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "unused = 'outside context'\ndef value(a, b):\n    return a <= b\n"
            (root / "feature.py").write_text(source)
            (root / "test_feature.py").write_text("from feature import value\ndef test_value(): assert value(1, 2)\n")
            mutations, _ = discover_mutations(root, (ChangedFile("feature.py", (3,)),))
            context = build_context(root, mutations[0], ["test_feature.py"])
            self.assertNotIn("outside context", context["function"])
            self.assertEqual(context["after"], "a < b")
            (root / "test_feature.py").write_text("api_key = 'fixture-not-a-real-key'\n")
            with self.assertRaisesRegex(AIError, "credentials"):
                build_context(root, mutations[0], ["test_feature.py"])
            (root / "test_feature.py").write_text("#" * 4097)
            with self.assertRaisesRegex(AIError, "size limit"):
                build_context(root, mutations[0], ["test_feature.py"])

    def test_only_loopback_roots(self):
        self.assertEqual(local_address("http://localhost:11434"), ("127.0.0.1", 11434))
        self.assertEqual(local_address("http://[::1]:1234"), ("::1", 1234))
        for endpoint in ("https://example.com", "http://localhost.evil", "http://127.0.0.1@evil", "http://localhost/api", "http://localhost?x", "http://0.0.0.0", "file:///tmp/model", "http://localhost:0", "http://@localhost"):
            with self.subTest(endpoint=endpoint), self.assertRaises(AIError):
                local_address(endpoint)

    def test_installed_model_and_chat_shape(self):
        response = {"done": True, "message": {"content": '{"recorded": true}'}}
        context = {"path": "feature.py", "function": "def value(a, b): return a <= b",
                   "before": "a <= b", "after": "a < b", "tests": [
                       {"path": "test_feature.py", "source": "from feature import value\ndef test_value(): assert value(1, 2)\n"}]}
        with patch("ghost_pr.local_ai.request_json", side_effect=[LOCAL_MODEL, response]) as request:
            self.assertEqual(request_proposal("http://localhost:11434", "demo:latest", context), '{"recorded": true}')
        payload = request.call_args.args[2]
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["format"], "json")
        self.assertEqual(payload["model"], "demo:latest")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")
        self.assertEqual(json.loads(payload["messages"][1]["content"]), context)
        instruction = payload["messages"][0]["content"].lower()
        for requirement in (
                r"passes.*original.*fails.*mutant", r"inputs.*reach the changed expression",
                r"assert.*difference.*observable behavior", r"different case.*existing tests",
                r"comparison mutations.*boundary values.*equality.*operator change",
                r"import and call.*real implementation", r"do not.*replace.*mock.*target",
                r"explanation.*actual inputs.*assertion.*test_code",
                r"json object.*explanation.*test_code"):
            with self.subTest(requirement=requirement):
                self.assertRegex(instruction, requirement)
        self.assertNotIn("withdraw", instruction)
        with patch("ghost_pr.local_ai.request_json", return_value={"models": []}):
            with self.assertRaisesRegex(AIError, "not installed"):
                request_proposal("http://localhost", "missing", {})
        with patch("ghost_pr.local_ai.request_json", return_value={"models": [
                {**LOCAL_MODEL["models"][0], "remote_host": "cloud.example"}]}):
            with self.assertRaisesRegex(AIError, "local GGUF"):
                request_proposal("http://localhost", "demo:latest", {})

    def test_http_limits_errors_and_redirect_refusal(self):
        for status, raw in ((302, b""), (200, b"x" * (MAX_RESPONSE + 1)),
                            (200, b"invalid"), (200, b"[]")):
            with self.subTest(status=status, size=len(raw)), patch("ghost_pr.local_ai.http.client.HTTPConnection") as factory:
                connection = factory.return_value
                response = connection.getresponse.return_value
                response.status, response.read.return_value = status, raw
                with self.assertRaises(AIError):
                    request_json("http://localhost", "/api/tags")
                connection.close.assert_called_once()
        with patch("ghost_pr.local_ai.http.client.HTTPConnection") as factory:
            factory.return_value.request.side_effect = ConnectionRefusedError()
            with self.assertRaisesRegex(AIError, "unavailable"):
                request_json("http://localhost", "/api/tags")
