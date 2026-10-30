"""Shared disposable Git setup; contains no test cases."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class GitFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Ghost Test")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "--allow-empty", "-qm", "baseline")

    def git(self, *args, input_data=None):
        return subprocess.run(["git", "--literal-pathspecs", "-C", str(self.root), *args], check=True, capture_output=True, input=input_data).stdout

    def stage(self, name, content):
        (self.root / name).write_text(content)
        self.git("add", "--", name)

