import ast
from pathlib import Path

from django.test import SimpleTestCase


class FileExportLayeringTests(SimpleTestCase):
    def test_file_export_does_not_import_sources(self):
        file_export_dir = Path("utils/file_export")

        for file_path in file_export_dir.rglob("*.py"):
            with self.subTest(path=file_path):
                tree = ast.parse(file_path.read_text())
                imported_modules = set()

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imported_modules.add(alias.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported_modules.add(node.module.split(".")[0])

                self.assertNotIn("sources", imported_modules)
