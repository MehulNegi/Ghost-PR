"""Small, deterministic AST mutations restricted to staged changed expressions."""
import ast
from pathlib import Path
import re
import tokenize

from .models import ChangedFile, Mutation, SkippedFile


COMPARISONS = {ast.LtE: (ast.Lt, "<= to <"), ast.GtE: (ast.Gt, ">= to >"),
               ast.Eq: (ast.NotEq, "== to !=")}
AUTH_WORDS = re.compile(r"auth|login|password|permission|credential|secret|token|session|access_control", re.I)


def read_python(path: Path) -> str:
    """Honor Python encoding declarations, including non-UTF-8 source."""
    with tokenize.open(path) as source:
        return source.read()


def discover_mutations(root: Path, files: tuple[ChangedFile, ...]) -> tuple[list[Mutation], list[SkippedFile]]:
    mutations = []
    skipped = []
    for changed in sorted(files, key=lambda item: item.path):
        path = Path(changed.path)
        if "tests" in path.parts or path.name.startswith("test_") or path.name.endswith("_test.py") or path.name == "conftest.py":
            skipped.append(SkippedFile(changed.path, "test file"))
            continue
        try:
            source = read_python(root / path)
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeError):
            skipped.append(SkippedFile(changed.path, "source cannot be parsed"))
            continue
        # Conservative text heuristic; this is not semantic security analysis.
        if AUTH_WORDS.search(changed.path) or AUTH_WORDS.search(source):
            skipped.append(SkippedFile(changed.path, "authentication/sensitive cues; excluded conservatively"))
            continue
        found = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Compare, ast.Constant)):
                continue
            if not any(node.lineno <= line <= node.end_lineno for line in changed.lines):
                continue
            if isinstance(node, ast.Compare):
                if len(node.ops) != 1:
                    skipped.append(SkippedFile(changed.path, f"line {node.lineno}: chained comparison"))
                    continue
                replacement = COMPARISONS.get(type(node.ops[0]))
                if replacement is None:
                    continue
                before = ast.unparse(node)
                original = node.ops[0]
                node.ops[0] = replacement[0]()
                after = ast.unparse(node)
                node.ops[0] = original
                operator = replacement[1]
            elif type(node.value) is bool:
                before, after = str(node.value), str(not node.value)
                operator = f"{before} to {after}"
            else:
                continue
            found = True
            mutations.append(Mutation(changed.path, node.lineno, node.col_offset,
                                      type(node).__name__, operator, before, after))
        if not found:
            skipped.append(SkippedFile(changed.path, "no supported expression on changed lines"))
    mutations.sort(key=lambda item: (item.path, item.line, item.column, item.operator))
    return mutations, skipped


def generate_mutant(source: str, mutation: Mutation) -> str:
    """Change exactly one recorded node in a fresh original AST, then compile."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (type(node).__name__, getattr(node, "lineno", None), getattr(node, "col_offset", None)) != (
                mutation.node_kind, mutation.line, mutation.column):
            continue
        if ast.unparse(node) != mutation.before:
            raise ValueError("Mutation evidence does not match original source.")
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in COMPARISONS:
            node.ops[0] = COMPARISONS[type(node.ops[0])][0]()
        elif isinstance(node, ast.Constant) and type(node.value) is bool:
            node.value = not node.value
        else:
            raise ValueError("Unsupported mutation node.")
        if ast.unparse(node) != mutation.after:
            raise ValueError("Mutation replacement does not match evidence.")
        result = ast.unparse(tree) + "\n"
        compile(result, mutation.path, "exec")
        return result
    raise ValueError("Mutation location not found in original source.")
