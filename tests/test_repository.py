"""Integration tests use disposable real Git repositories, never a user's repo."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from git_fixture import GitFixture
from ghost_pr.cli import main
from ghost_pr.repository import RepositoryError, changed_lines, inspect_repository


class RepositoryTests(GitFixture):
    def test_new_file_and_unusual_filename(self):
        self.stage("a [x]\n.py", "x = 1\ny = 2\n")
        result = inspect_repository(self.root)
        self.assertEqual(result.files[0].path, "a [x]\n.py")
        self.assertEqual(result.files[0].lines, (1, 2))
        self.assertEqual((self.root / "a [x]\n.py").read_text(), "x = 1\ny = 2\n")

    def test_reject_mixed_changes(self):
        self.stage("a.py", "x = 1\n")
        (self.root / "a.py").write_text("x = 2\n")
        with self.assertRaisesRegex(RepositoryError, "unstaged"):
            inspect_repository(self.root)

    def test_skip_non_python_and_count_untracked(self):
        self.stage("README.md", "hello\n")
        (self.root / "extra.py").write_text("x = 2\n")
        result = inspect_repository(self.root)
        self.assertEqual(result.untracked_count, 1)
        self.assertEqual(result.skipped[0].reason, "not a Python file")

    def test_modified_new_side_lines(self):
        self.stage("a.py", "x = 1\ny = 2\nz = 3\n")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "file")
        self.stage("a.py", "x = 1\ny = 20\nz = 3\n")
        self.assertEqual(inspect_repository(self.root).files[0].lines, (2,))

    def test_deleted_file(self):
        self.stage("a.py", "x = 1\n")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "file")
        self.git("rm", "a.py")
        self.assertEqual(inspect_repository(self.root).skipped[0].reason, "deleted file")

    def test_symlink_rejected(self):
        (self.root / "link.py").symlink_to("elsewhere")
        self.git("add", "link.py")
        with self.assertRaisesRegex(RepositoryError, "symlinks"):
            inspect_repository(self.root)

    def test_json_contract(self):
        self.stage("a.py", "x = 1\n")
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["check", "--repo", str(self.root), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["files"][0]["lines"], [1])

    def test_not_repository(self):
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(RepositoryError):
                inspect_repository(Path(other))

    def test_empty_scope(self):
        self.assertEqual(inspect_repository(self.root).files, ())

    def test_requires_head(self):
        with tempfile.TemporaryDirectory() as empty:
            subprocess.run(["git", "init", "-q", empty], check=True)
            with self.assertRaises(RepositoryError):
                inspect_repository(Path(empty))

    def test_literal_pathspecs_and_deletion_only(self):
        names = ("-leading.py", ":(glob)*.py", "space name.py")
        for name in names:
            self.stage(name, "a = 1\nb = 2\n")
        self.assertEqual({f.path for f in inspect_repository(self.root).files}, set(names))
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "files")
        self.stage("-leading.py", "a = 1\n")
        result = inspect_repository(self.root)
        self.assertEqual(result.files, ())
        self.assertEqual(result.skipped[0].reason, "no added or modified text lines")

    def test_conflict_and_submodule_rejected(self):
        self.stage("a.py", "x = 1\n")
        blob = self.git("rev-parse", ":a.py").decode().strip()
        self.git("update-index", "--index-info", input_data=f"100644 {blob} 1\ta.py\n".encode())
        with self.assertRaisesRegex(RepositoryError, "conflicts"):
            inspect_repository(self.root)
        self.git("reset", "-q")
        head = self.git("rev-parse", "HEAD").decode().strip()
        (self.root / "sub").mkdir()
        self.git("update-index", "--add", "--cacheinfo", f"160000,{head},sub")
        with self.assertRaisesRegex(RepositoryError, "submodules"):
            inspect_repository(self.root)

    def test_hunk_ranges_and_deletion(self):
        patch = b"@@ -2 +2 @@\n@@ -5,0 +6,2 @@\n@@ -10,2 +12,0 @@\n"
        self.assertEqual(changed_lines(patch), (2, 6, 7))


if __name__ == "__main__":
    unittest.main()
