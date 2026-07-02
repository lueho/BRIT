from pathlib import Path
from tempfile import TemporaryDirectory

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
                    ("brit/sitemap_items.py", "sources.registry"),
                    ("inventories/models.py", "sources"),
                },
            ),
        )

        self.assertEqual(violations, [])
