"""Discovery and generation checks use ordinary source strings."""
import ast
from pathlib import Path
import tempfile
import unittest

from ghost_pr.models import ChangedFile
from ghost_pr.mutations import discover_mutations, generate_mutant


class MutationTests(unittest.TestCase):
    def test_documentation_and_unrelated_sensitive_code_do_not_block_math(self):
        source = '''"""Permission documentation, not an executable security check."""
# Permission notice retained with this module.
def bounded(value, limit):
    """Authentication terminology in documentation is not code."""
    return value <= limit

def check_permission(user):
    return user.permission == "read"
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "arithmetic.py").write_text(source)
            mutations, skipped = discover_mutations(root, (ChangedFile("arithmetic.py", (5,)),))
            self.assertEqual(len(mutations), 1)
            self.assertEqual(mutations[0].after, "value < limit")
            self.assertFalse(skipped)

    def test_sensitive_paths_and_relevant_code_still_excluded(self):
        cases = (
            ("auth.py", "allow = True\n", 1, "mutation_sensitive_path"),
            ("feature.py", "def authenticated():\n    return True\n", 2, "mutation_sensitive_scope"),
            ("feature.py", "def allowed(user):\n    return user.permission == 'read'\n", 2, "mutation_sensitive_scope"),
            ("feature.py", "def allowed(user):\n    return user['permission'] == 'read'\n", 2, "mutation_sensitive_scope"),
            ("feature.py", "class Authentication:\n    def allowed(self):\n        return True\n", 3, "mutation_sensitive_scope"),
            ("feature.py", "permission = True\n", 1, "mutation_sensitive_scope"),
            ("feature.py", "def allowed(user):\n    permission = user.can_read\n    return True\n", 3, "mutation_sensitive_scope"),
        )
        for name, source, line, rule in cases:
            with self.subTest(rule=rule, source=source), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / name).write_text(source)
                mutations, skipped = discover_mutations(root, (ChangedFile(name, (line,)),))
                self.assertFalse(mutations)
                self.assertEqual(len(skipped), 1)
                self.assertIn(rule, skipped[0].reason)
                self.assertNotIn("'read'", skipped[0].reason)
                self.assertNotIn("user", skipped[0].reason)

    def test_one_mutation_per_original_source(self):
        source = "def f(x, y):\n    return (x <= y, x >= y, x == y, True, False)\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "code.py").write_text(source)
            mutations, _ = discover_mutations(root, (ChangedFile("code.py", (2,)),))
            for index, mutation in enumerate(mutations):
                output = generate_mutant(source, mutation)
                expression = ast.parse(output).body[0].body[0].value
                original = ast.parse(source).body[0].body[0].value
                differences = [a for a, b in zip(expression.elts, original.elts)
                               if ast.dump(a) != ast.dump(b)]
                self.assertEqual(len(differences), 1)
                self.assertEqual(ast.unparse(expression.elts[index]), mutation.after)
                compile(output, "mutant", "exec")
            self.assertEqual((root / "code.py").read_text(), source)
            with self.assertRaises(ValueError):
                generate_mutant(source.replace("x <= y", "x < y"), mutations[0])

    def test_changed_lines_order_and_skips(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "code.py").write_text("a = x <= y\nb = x >= y\nc = x == y\nd = True\ne = False\nf = x < y < z\ng = 9\n")
            (root / "test_code.py").write_text("assert True\n")
            (root / "auth.py").write_text("allow = True\n")
            (root / "broken.py").write_text("def ?\n")
            files = tuple(ChangedFile(name, tuple(range(1, 8))) for name in
                          ("test_code.py", "code.py", "auth.py", "broken.py"))
            mutations, skipped = discover_mutations(root, files)
            self.assertEqual([m.line for m in mutations], [1, 2, 3, 4, 5])
            self.assertEqual([m.after for m in mutations], ["x < y", "x > y", "x != y", "False", "True"])
            self.assertTrue(any("chained" in s.reason for s in skipped))
            self.assertTrue(any("sensitive" in s.reason for s in skipped))
            selected, _ = discover_mutations(root, (ChangedFile("code.py", (2,)),))
            self.assertEqual([m.line for m in selected], [2])
            selected, skipped = discover_mutations(root, (ChangedFile("code.py", (7,)),))
            self.assertFalse(selected)
            self.assertIn("no supported", skipped[0].reason)

    def test_multiline_expression_intersects_changed_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "code.py").write_text("ok = (\n  x\n  <= y\n)\n")
            mutations, _ = discover_mutations(root, (ChangedFile("code.py", (3,)),))
            self.assertEqual(len(mutations), 1)
            self.assertEqual(mutations[0].line, 2)
