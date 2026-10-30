"""Read Git's index without modifying the developer's repository."""
from contextlib import contextmanager
from functools import partial
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .models import ChangedFile, Inspection, SkippedFile


class RepositoryError(Exception):
    """An unsupported state or a failed bounded Git operation."""


def git_result(root: Path, *args: str, index_file: Path | None = None,
               git_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """One bounded executor; callers classify expected nonzero statuses safely."""
    env = os.environ.copy()
    if git_env is not None:
        env.update(git_env)
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
    return result


def git(root: Path, *args: str, index_file: Path | None = None,
        git_env: dict[str, str] | None = None) -> bytes:
    result = git_result(root, *args, index_file=index_file, git_env=git_env)
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


def git_path(root: Path, name: str, git_env: dict[str, str] | None = None) -> Path:
    path = Path(git(root, "rev-parse", "--git-path", name, git_env=git_env)
                .decode(errors="surrogateescape").removesuffix("\n"))
    return path if path.is_absolute() else root / path


def pin_index(root: Path, git_env: dict[str, str] | None = None) -> str:
    """write-tree may refresh index caches, so give it a disposable index copy."""
    index = git_path(root, "index", git_env)
    with tempfile.TemporaryDirectory(prefix="ghost-index-") as directory:
        copy = Path(directory) / "index"
        if index.exists():
            shutil.copyfile(index, copy)
        return git(root, "write-tree", index_file=copy, git_env=git_env).decode().strip()


def inspect_repository(path: Path, *, git_env: dict[str, str] | None = None) -> Inspection:
    read_git = partial(git, git_env=git_env)
    root = Path(read_git(path, "rev-parse", "--show-toplevel").decode(errors="surrogateescape").removesuffix("\n"))
    head = read_git(root, "rev-parse", "--verify", "HEAD").decode().strip()
    if read_git(root, "ls-files", "--unmerged", "-z"):
        raise RepositoryError("Resolve merge conflicts before inspection.")
    if read_git(root, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z"):
        raise RepositoryError("Stage or discard all unstaged tracked changes before inspection.")
    tree = pin_index(root, git_env)
    files: list[ChangedFile] = []
    skipped: list[SkippedFile] = []
    names = read_git(root, "diff", "--no-renames", "--no-ext-diff", "--no-textconv", "--name-only", "-z", head, tree).split(b"\0")
    for raw in filter(None, names):
        name = raw.decode("utf-8", errors="surrogateescape")
        entry = read_git(root, "ls-tree", "-z", tree, "--", name)
        if not entry:
            skipped.append(SkippedFile(name, "deleted file"))
            continue
        mode = entry.split(b" ", 1)[0]
        if mode not in (b"100644", b"100755"):
            raise RepositoryError("Staged symlinks and submodules are unsupported.")
        if not name.endswith(".py"):
            skipped.append(SkippedFile(name, "not a Python file"))
            continue
        patch = read_git(root, "diff", "--no-renames", "--no-ext-diff", "--no-textconv", "--unified=0", head, tree, "--", name)
        lines = changed_lines(patch)
        if lines:
            files.append(ChangedFile(name, lines))
        else:
            skipped.append(SkippedFile(name, "no added or modified text lines"))
    untracked = read_git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return Inspection(str(root), tuple(files), tuple(skipped), len(list(filter(None, untracked.split(b"\0")))), tree)


@contextmanager
def inspection_snapshot(path: Path):
    """Capture checks without writing even tree objects into the real repository."""
    root = Path(git(path, "rev-parse", "--show-toplevel").decode(errors="surrogateescape").removesuffix("\n"))
    index = git_path(root, "index")
    objects = git_path(root, "objects")
    with tempfile.TemporaryDirectory(prefix="ghost-check-") as directory:
        temporary = Path(directory)
        copy = temporary / "index"
        if index.exists():
            shutil.copyfile(index, copy)
        (temporary / "objects").mkdir()
        # Git accepts C-quoted alternate paths, including colons and newlines.
        alternates = json.dumps(str(objects), ensure_ascii=False)
        existing = os.environ.get("GIT_ALTERNATE_OBJECT_DIRECTORIES")
        if existing:
            alternates += os.pathsep + existing
        git_env = {"LC_ALL": "C", "GIT_INDEX_FILE": str(copy),
                   "GIT_OBJECT_DIRECTORY": str(temporary / "objects"),
                   "GIT_ALTERNATE_OBJECT_DIRECTORIES": alternates}
        head = git(root, "rev-parse", "--verify", "HEAD", git_env=git_env).decode().strip()
        inspection = inspect_repository(root, git_env=git_env)
        if git(root, "rev-parse", "--verify", "HEAD", git_env=git_env).decode().strip() != head:
            raise RepositoryError("HEAD changed during check capture; retry without concurrent edits.")
        yield inspection, head, git_env


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
