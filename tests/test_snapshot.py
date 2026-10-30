"""Snapshot integration checks reuse the controlled Git fixture helpers."""
from unittest.mock import patch

from ghost_pr.repository import RepositoryError, inspect_repository, staged_snapshot
from git_fixture import GitFixture


class SnapshotTests(GitFixture):
    def test_inspection_preserves_index_bytes_and_disables_fsmonitor(self):
        self.stage("a.py", "a = True\n")
        self.git("config", "core.fsmonitor", "touch fsmonitor-was-run")
        index = self.root / ".git/index"
        before = index.read_bytes()
        inspection = inspect_repository(self.root)
        with staged_snapshot(inspection):
            pass
        self.assertEqual(index.read_bytes(), before)
        self.assertFalse((self.root / "fsmonitor-was-run").exists())

    def test_pinned_bytes_permissions_and_original_preserved(self):
        (self.root / "bin").mkdir()
        self.stage("bin/run.py", "print('staged')\n")
        (self.root / "bin/run.py").chmod(0o755)
        self.git("add", "bin/run.py")
        self.stage(".gitignore", "ignored\n")
        (self.root / "data.bin").write_bytes(b"\x00\xff\r\n")
        self.git("add", "data.bin")
        (self.root / "ignored").write_text("excluded")
        (self.root / "untracked").write_text("excluded")
        inspection = inspect_repository(self.root)
        self.stage("bin/run.py", "print('later index')\n")
        (self.root / "bin/run.py").write_text("working tree differs\n")
        index_before = self.git("ls-files", "--stage", "-z")
        with staged_snapshot(inspection) as snapshot:
            self.assertEqual((snapshot / "bin/run.py").read_text(), "print('staged')\n")
            self.assertTrue((snapshot / "bin/run.py").stat().st_mode & 0o111)
            self.assertFalse((snapshot / "untracked").exists())
            self.assertFalse((snapshot / "ignored").exists())
            self.assertEqual((snapshot / "data.bin").read_bytes(), b"\x00\xff\r\n")
        self.assertFalse(snapshot.exists())
        self.assertEqual(self.git("ls-files", "--stage", "-z"), index_before)
        self.assertEqual((self.root / "bin/run.py").read_text(), "working tree differs\n")

    def test_unchanged_symlink_rejected_and_cleanup_on_error(self):
        (self.root / "link").symlink_to("missing")
        self.git("add", "link")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "link")
        inspection = inspect_repository(self.root)
        with self.assertRaisesRegex(RepositoryError, "Snapshot"):
            with staged_snapshot(inspection):
                self.fail("must reject unchanged symlink")
        self.git("rm", "link")
        inspection = inspect_repository(self.root)
        with self.assertRaisesRegex(RuntimeError, "consumer"):
            with staged_snapshot(inspection) as snapshot:
                raise RuntimeError("consumer")
        self.assertFalse(snapshot.exists())

    def test_unsafe_tree_path_rejected(self):
        inspection = inspect_repository(self.root)
        malicious = b"100644 blob " + b"a" * 40 + b"\t../escape\0"
        with patch("ghost_pr.repository.git", return_value=malicious):
            with self.assertRaisesRegex(RepositoryError, "unsafe"):
                with staged_snapshot(inspection):
                    self.fail("unsafe path exported")
