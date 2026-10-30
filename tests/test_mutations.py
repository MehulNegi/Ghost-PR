"""Discovery and generation checks use ordinary source strings."""
import ast
from pathlib import Path
import tempfile
import unittest

from ghost_pr.models import ChangedFile
from ghost_pr.mutations import discover_mutations, generate_mutant


class MutationTests(unittest.TestCase):
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
