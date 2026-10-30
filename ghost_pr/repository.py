"""Read Git's index without modifying the developer's repository."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .models import ChangedFile, Inspection, SkippedFile


class RepositoryError(Exception):
    """An unsupported state or a failed bounded Git operation."""


def git(root: Path, *args: str, index_file: Path | None = None) -> bytes:
    env = os.environ.copy()
    if index_file is not None:
        env["GIT_INDEX_FILE"] = str(index_file)
    try:
        result = subprocess.run(
            ["git", "--no-pager", "--no-optional-locks", "--literal-pathspecs",
             "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
             "-C", str(root), *args],
            capture_output=True, timeout=10, check=False, env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepositoryError("Git unavailable, path invalid, or Git operation timed out.") from exc
    if result.returncode:
        raise RepositoryError("Git operation failed; check repository state and HEAD.")
    return result.stdout


def changed_lines(patch: bytes) -> tuple[int, ...]:
    """Read new-side hunk ranges; count omitted in a header means one."""
    lines: set[int] = set()
    for match in re.finditer(rb"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", patch, re.M):
        start = int(match[1])
        count = int(match[2]) if match[2] is not None else 1
        lines.update(range(start, start + count))
    return tuple(sorted(lines))


def pin_index(root: Path) -> str:
    """write-tree may refresh index caches, so give it a disposable index copy."""
    index = Path(git(root, "rev-parse", "--git-path", "index").decode(errors="surrogateescape").removesuffix("\n"))
    if not index.is_absolute():
        index = root / index
    with tempfile.TemporaryDirectory(prefix="ghost-index-") as directory:
        copy = Path(directory) / "index"
        if index.exists():
            shutil.copyfile(index, copy)
        return git(root, "write-tree", index_file=copy).decode().strip()


def inspect_repository(path: Path) -> Inspection:
    root = Path(git(path, "rev-parse", "--show-toplevel").decode(errors="surrogateescape").removesuffix("\n"))
    head = git(root, "rev-parse", "--verify", "HEAD").decode().strip()
    if git(root, "ls-files", "--unmerged", "-z"):
        raise RepositoryError("Resolve merge conflicts before inspection.")
    if git(root, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z"):
        raise RepositoryError("Stage or discard all unstaged tracked changes before inspection.")
    tree = pin_index(root)
    files: list[ChangedFile] = []
    skipped: list[SkippedFile] = []
    names = git(root, "diff", "--no-renames", "--name-only", "-z", head, tree).split(b"\0")
    for raw in filter(None, names):
        name = raw.decode("utf-8", errors="surrogateescape")
        entry = git(root, "ls-tree", "-z", tree, "--", name)
        if not entry:
            skipped.append(SkippedFile(name, "deleted file"))
            continue
        mode = entry.split(b" ", 1)[0]
        if mode not in (b"100644", b"100755"):
            raise RepositoryError("Staged symlinks and submodules are unsupported.")
        if not name.endswith(".py"):
            skipped.append(SkippedFile(name, "not a Python file"))
            continue
        patch = git(root, "diff", "--no-renames", "--no-ext-diff", "--no-textconv", "--unified=0", head, tree, "--", name)
        lines = changed_lines(patch)
        if lines:
            files.append(ChangedFile(name, lines))
        else:
            skipped.append(SkippedFile(name, "no added or modified text lines"))
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return Inspection(str(root), tuple(files), tuple(skipped), len(list(filter(None, untracked.split(b"\0")))), tree)


@contextmanager
def staged_snapshot(inspection: Inspection):
    """Export pinned blobs directly; always remove the disposable directory."""
    root = Path(inspection.root)
    entries = git(root, "ls-tree", "-rz", "--full-tree", inspection.tree)
    with tempfile.TemporaryDirectory(prefix="ghost-snapshot-") as directory:
        destination = Path(directory)
        for entry in filter(None, entries.split(b"\0")):
            metadata, raw_path = entry.split(b"\t", 1)
            mode, kind, object_id = metadata.split()
            if mode not in (b"100644", b"100755") or kind != b"blob":
                raise RepositoryError("Snapshot contains unsupported symlinks or submodules.")
            name = raw_path.decode("utf-8", errors="surrogateescape")
            parts = name.split("/")
            if any(part in ("", ".", "..") or part.lower() == ".git" for part in parts):
                raise RepositoryError("Snapshot contains an unsafe path.")
            target = destination.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git(root, "cat-file", "blob", object_id.decode()))
            target.chmod(0o755 if mode == b"100755" else 0o644)
        yield destination
