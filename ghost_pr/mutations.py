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


def has_sensitive_code(scope: ast.AST) -> bool:
    """Check executable names/literals, ignoring documentation and comments."""
    nodes = list(ast.walk(scope))
    docstrings = set()
    for node in nodes:
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if ast.get_docstring(node, clean=False) is not None:
                docstrings.add(node.body[0].value)
    for node in nodes:
        if isinstance(node, ast.Name):
            text = node.id
        elif isinstance(node, ast.Attribute):
            text = node.attr
        elif isinstance(node, (ast.arg, ast.keyword)):
            text = node.arg or ""
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            text = node.name
        elif isinstance(node, ast.alias):
            text = node.name + " " + (node.asname or "")
        elif isinstance(node, ast.ImportFrom):
            text = node.module or ""
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node not in docstrings:
            text = node.value
        else:
            continue
        if AUTH_WORDS.search(text):
            return True
    return False


def mutation_is_sensitive(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Keep security context local to the candidate, rather than sibling code."""
    function = None
    statement = None
    current = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if AUTH_WORDS.search(current.name):
                return True
        if function is None and isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = current
        if statement is None and isinstance(current, ast.stmt):
            statement = current
        current = parents.get(current)
    return has_sensitive_code(function or statement or node)


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
        if AUTH_WORDS.search(changed.path):
            skipped.append(SkippedFile(changed.path, "mutation_sensitive_path: unsupported authentication/sensitive path"))
            continue
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
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
            if mutation_is_sensitive(node, parents):
                skipped.append(SkippedFile(changed.path,
                    f"line {node.lineno}: mutation_sensitive_scope: unsupported authentication/sensitive code"))
                continue
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
