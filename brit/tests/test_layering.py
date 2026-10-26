import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import SimpleTestCase

from brit.layering import LayeringContract, find_layering_violations


class LayeringContractTests(SimpleTestCase):
    def test_scanner_reports_upward_imports(self):
        with TemporaryDirectory() as directory:
            repo_root = Path(directory)
            package_dir = repo_root / "utils"
            package_dir.mkdir()
            offender = package_dir / "offender.py"
            offender.write_text(
                "from sources.registry import get_source_domain_plugins\n"
            )

            violations = find_layering_violations(
                repo_root,
                LayeringContract(layers={"utils": 0, "sources": 4}),
            )

        self.assertEqual(
            violations,
            [("utils/offender.py:1 imports sources.registry (L0 utils -> L4 sources)")],
        )

    def test_scanner_ignores_relative_imports(self):
        with TemporaryDirectory() as directory:
            repo_root = Path(directory)
            package_dir = repo_root / "utils"
            package_dir.mkdir()
            internal_import = package_dir / "internal_import.py"
            internal_import.write_text("from .sources import helper\n")

            violations = find_layering_violations(
                repo_root,
                LayeringContract(layers={"utils": 0, "sources": 4}),
            )

        self.assertEqual(violations, [])

    def test_scanner_reports_syntax_errors(self):
        with TemporaryDirectory() as directory:
            repo_root = Path(directory)
            package_dir = repo_root / "utils"
            package_dir.mkdir()
            broken_file = package_dir / "broken.py"
            broken_file.write_text("def broken(:\n")

            violations = find_layering_violations(
                repo_root,
                LayeringContract(layers={"utils": 0}),
            )

        self.assertEqual(
            violations,
            ["utils/broken.py:1 syntax error: invalid syntax"],
        )

    def test_non_test_code_only_imports_same_or_lower_layers(self):
        repo_root = Path(__file__).resolve().parents[2]

        violations = find_layering_violations(
            repo_root,
            LayeringContract(
                layers={
                    "utils": 0,
                    "users": 0,
                    "brit": 0,
                    "bibliography": 1,
                    "distributions": 1,
                    "maps": 1,
                    "materials": 2,
                    "processes": 2,
                    "inventories": 3,
                    "layer_manager": 3,
                    "sources": 4,
                    "case_studies": 5,
                    "interfaces": 5,
                },
                allowed_upward_imports={
                    ("brit/urls.py", "sources.registry"),
                    ("inventories/models.py", "sources"),
                },
            ),
        )

        self.assertEqual(violations, [])


class LayeringScannerPruningTests(SimpleTestCase):
    """The scanner must prune ignored/unrelated trees before descending."""

    contract = LayeringContract(layers={"utils": 0, "sources": 4})
    expected = [
        "utils/offender.py:1 imports sources.registry (L0 utils -> L4 sources)",
        "utils/subpkg/deep.py:1 imports sources.registry (L0 utils -> L4 sources)",
    ]

    def _build_repo(self, repo_root):
        package_dir = repo_root / "utils"
        package_dir.mkdir()
        (package_dir / "offender.py").write_text(
            "from sources.registry import get_source_domain_plugins\n"
        )
        nested_dir = package_dir / "subpkg"
        nested_dir.mkdir()
        (nested_dir / "deep.py").write_text("import sources.registry\n")
        (nested_dir / "clean.py").write_text("import utils.helpers\n")
        for ignored in ("migrations", "tests", "__pycache__"):
            ignored_dir = package_dir / ignored
            ignored_dir.mkdir()
            (ignored_dir / "ignored.py").write_text("import sources.registry\n")
        for unrelated in (".venv", "node_modules", "other_pkg"):
            unrelated_dir = repo_root / unrelated
            unrelated_dir.mkdir()
            (unrelated_dir / "bad.py").write_text("import sources.registry\n")
        deep_unrelated = repo_root / ".venv" / "lib" / "site-packages"
        deep_unrelated.mkdir(parents=True)
        (deep_unrelated / "bad.py").write_text("import sources.registry\n")
        return package_dir, nested_dir

    def test_scan_results_match_whole_repo_scan(self):
        with TemporaryDirectory() as directory:
            package_dir, _ = self._build_repo(Path(directory))
            violations = find_layering_violations(Path(directory), self.contract)
            again = find_layering_violations(Path(directory), self.contract)

        self.assertEqual(violations, self.expected)
        self.assertEqual(again, self.expected)

    def test_scandir_never_enters_ignored_or_unrelated_dirs(self):
        with TemporaryDirectory() as directory:
            repo_root = Path(directory)
            package_dir, nested_dir = self._build_repo(repo_root)
            with mock.patch("os.scandir", wraps=os.scandir) as scandir_spy:
                violations = find_layering_violations(repo_root, self.contract)

        scanned_dirs = {str(call.args[0]) for call in scandir_spy.call_args_list}
        self.assertIn(str(package_dir), scanned_dirs)
        self.assertIn(str(nested_dir), scanned_dirs)
        for scanned in scanned_dirs:
            parts = Path(scanned).parts
            for forbidden in (
                "migrations",
                "tests",
                "__pycache__",
                ".venv",
                "node_modules",
                "other_pkg",
            ):
                self.assertNotIn(forbidden, parts, scanned)
        self.assertEqual(violations, self.expected)
